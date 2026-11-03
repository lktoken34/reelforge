"""One owned transaction for accepted storyboard rendering and registered audio processing."""

import json
import os
import resource
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from threading import Event

from reelforge.audio.processing import command, mix_pcm, mux_audio, verify_audio
from reelforge.audio.registry import AudioRegistry, digest
from reelforge.core.errors import OperationError
from reelforge.core.transaction import OwnedDirectory
from reelforge.media.verify import verify_video
from reelforge.resources.deployment import check_workspace, memory_observability
from reelforge.resources.monitor import JobMonitor, memory_snapshot, preflight_memory

from .contract import AudioRequest, Reel, cue_schedule, metadata_plan

VIDEO_ALLOWANCE = 32 * 1024**2


def cancelled_check(cancelled: Event) -> None:
    if cancelled.is_set():
        raise OperationError("REEL_CANCELLED", "Reel job cancelled")


def temporary_size(root: Path) -> int:
    # Logical stage sizes, including hard links; this deliberately overcounts shared inodes.
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def stream_check(path: Path, cancelled: Event, frames: int = 90, *, silent: bool = False) -> dict:
    metadata = json.loads(
        command(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            cancelled=cancelled,
        )
    )
    streams = metadata.get("streams", [])
    if silent:
        if len(streams) != 1 or streams[0].get("codec_type") != "video":
            raise OperationError("REEL_STREAMS", "Expected exactly one silent video stream")
        video = streams[0]
        audio = None
    else:
        if len(streams) != 2 or [s.get("codec_type") for s in streams] != ["video", "audio"]:
            raise OperationError("REEL_STREAMS", "Expected exactly video then audio")
        video, audio = streams
    video_ok = (
        video.get("codec_name") == "h264"
        and video.get("width") == 720
        and video.get("height") == 1280
        and video.get("pix_fmt") == "yuv420p"
        and video.get("avg_frame_rate") == "30/1"
        and video.get("nb_frames") == str(frames)
        and Fraction(video.get("duration", "0")) == Fraction(frames, 30)
        and Fraction(video.get("start_time", "99")) == 0
    )
    audio_ok = silent or (
        audio.get("profile") == "LC"
        and audio.get("codec_name") == "aac"
        and audio.get("sample_rate") == "48000"
        and audio.get("channels") == 2
    )
    if not (video_ok and audio_ok):
        raise OperationError("REEL_STREAMS", "Reel stream format or presentation interval differs")
    clock = json.loads(
        command(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_frames",
                "-show_entries",
                "frame=best_effort_timestamp",
                "-of",
                "json",
                str(path),
            ],
            cancelled=cancelled,
        )
    )["frames"]
    pts = [int(f["best_effort_timestamp"]) for f in clock]
    base = Fraction(video["time_base"])
    if len(pts) != frames or any(value * base != Fraction(i, 30) for i, value in enumerate(pts)):
        raise OperationError("REEL_PTS", "Expected exact rational video PTS F/30")
    return {
        "metadata": metadata,
        "video_pts_ticks": pts,
        "exact_video_pts": True,
        "audio_streams": 0 if silent else 1,
        "aac_target_bitrate": None if silent else 128000,
        "observed_aac_bitrate": None if silent else audio.get("bit_rate"),
    }


def error_data(error: BaseException) -> dict:
    return {
        "code": getattr(
            error,
            "code",
            "REEL_CANCELLED" if isinstance(error, KeyboardInterrupt) else "REEL_RUNTIME",
        ),
        "message": str(error),
    }


def render_reel(
    plan: Reel,
    output_dir: Path,
    *,
    registry_root: Path,
    render_silent: Callable,
    cancelled: Event | None = None,
) -> dict:
    return render_av(
        plan,
        output_dir,
        frames=90,
        visual_plan=plan.storyboard,
        render_silent=render_silent,
        registry_root=registry_root,
        cancelled=cancelled,
    )


def render_av(
    plan: AudioRequest,
    output_dir: Path,
    *,
    frames: int,
    visual_plan: object,
    registry_root: Path,
    render_silent: Callable,
    cancelled: Event | None = None,
    contract_version: str = "reel-0.1",
    silent: bool = False,
) -> dict:
    """Trusted bounded orchestration shared by reel-0.1 and episode-0.1/0.2; no new media engine.

    When ``silent`` is true the audio stages (registry snapshot, PCM mix, AAC mux and audio
    verification) are skipped and the silent ``scene.mp4`` is verified and published directly,
    producing one H.264 video stream and zero audio streams. All other guarantees — owned private
    transaction, no-clobber publish-by-link, resource monitoring, full video decode verification
    and cleanup — are identical to the audio path.
    """
    if type(frames) is not int or frames not in range(90, 901, 90):
        raise OperationError("AV_FRAMES", "Use 1..10 segments of 90 frames")
    started = time.perf_counter()
    own = time.process_time()
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    cancellation = cancelled if cancelled is not None else Event()
    registry = AudioRegistry(registry_root)
    planned = () if silent else metadata_plan(plan, registry, frames)
    cancelled_check(cancellation)
    output_dir = output_dir.resolve()
    if output_dir.exists() or output_dir.is_symlink():
        raise OperationError("OUTPUT_EXISTS", "Choose a new output directory")
    preflight_memory()
    check_workspace(output_dir.parent)
    output_dir.mkdir(exist_ok=False)
    output = output_dir / "reel.mp4"
    owner = None
    monitor = None
    result = {
        "contract": contract_version,
        "title": plan.title,
        "success": False,
        "published": False,
        "media_verified": False,
        "transaction_clean": False,
        "error": None,
        "cleanup_error": None,
        "resource_error": None,
        "frames": frames,
        "fps": 30,
        "audio_cues": cue_schedule(planned),
        "artistic_approval": False,
        "deployment_gate_approved": False,
    }
    stages = {}
    storage = {}
    current_stage = "admission"
    try:
        with JobMonitor(workspace=output_dir, cancelled=cancellation) as monitor:
            try:
                owner = OwnedDirectory(output_dir, ".reelforge-audio-")
                private = owner.path
                result["transaction_path"] = str(private)
                for name in ("validation", "assets", "encode"):
                    (private / name).mkdir()
                assets = {r.asset.id: r.asset for r in planned}
                estimate = (
                    2 * sum(a.size_bytes for a in assets.values())
                    + 2 * frames * 1600 * 8
                    + 3 * VIDEO_ALLOWANCE
                    + 1024**2
                )
                result["temporary_storage"] = {
                    "preflight_estimate_bytes": estimate,
                    "disk_reserve_bytes": 64 * 1024**2,
                    "stage_samples_bytes": storage,
                }
                check_workspace(
                    output_dir, minimum_free_bytes=max(256 * 1024**2, estimate + 64 * 1024**2)
                )

                def sample(stage):
                    cancelled_check(cancellation)
                    storage[stage] = temporary_size(private)
                    if storage[stage] > estimate:
                        raise OperationError(
                            "REEL_STORAGE", "Stage exceeded preflight storage allowance"
                        )
                    monitor.sample()
                    cancelled_check(cancellation)

                resolved = ()
                snapshots = {}
                if not silent:
                    current_stage = "registry_validation"
                    tick = time.perf_counter()
                    resolved = registry.resolve(
                        plan.audio,
                        frames,
                        cancelled=cancellation,
                        validation_root=private / "validation",
                    )
                    for r in resolved:
                        cancelled_check(cancellation)
                        if r.asset.id in snapshots:
                            continue
                        target = private / "assets" / r.asset.file
                        with r.path.open("rb") as source, target.open("xb") as destination:
                            while block := source.read(65536):
                                cancelled_check(cancellation)
                                destination.write(block)
                        if digest(target) != r.asset.sha256:
                            raise OperationError(
                                "AUDIO_CHANGED", "Audio changed during private snapshot"
                            )
                        snapshots[r.asset.id] = target
                    stages[current_stage] = time.perf_counter() - tick
                    sample(current_stage)
                current_stage = "silent_render"
                tick = time.perf_counter()
                video_report = render_silent(
                    visual_plan,
                    private / "video",
                    encoder_staging=private / "encode",
                    cancelled=cancellation,
                )
                result["video_report"] = video_report
                if not video_report["success"]:
                    raise OperationError("REEL_VIDEO", "Silent renderer failed")
                video = private / "video" / "scene.mp4"
                if video.stat().st_size > VIDEO_ALLOWANCE:
                    raise OperationError("REEL_STORAGE", "Silent MP4 exceeds 32 MiB allowance")
                stages[current_stage] = time.perf_counter() - tick
                sample(current_stage)
                reference, decoded = private / "reference.f32", private / "decoded.f32"
                pending = private / "pending.mp4"
                if silent:
                    # Publish the verified silent video directly: no mix, mux or audio stages.
                    current_stage = "verify"
                    tick = time.perf_counter()
                    verified = verify_video(
                        video, width=720, height=1280, frames=frames, cancelled=cancellation
                    )
                    if (
                        verified["decoded_rgb_sha256"]
                        != video_report["verification"]["decoded_rgb_sha256"]
                    ):
                        raise OperationError("REEL_VIDEO_CHANGED", "Decoded silent video changed")
                    result["verification"] = verified
                    result["streams"] = stream_check(video, cancellation, frames, silent=True)
                    pending = video
                    stages[current_stage] = time.perf_counter() - tick
                    sample(current_stage)
                else:
                    current_stage = "mix"
                    tick = time.perf_counter()
                    result["mix"] = mix_pcm(
                        resolved, frames, snapshots, reference, cancelled=cancellation
                    )
                    stages[current_stage] = time.perf_counter() - tick
                    sample(current_stage)
                    current_stage = "mux"
                    tick = time.perf_counter()
                    result["mux_command"] = mux_audio(
                        video, reference, pending, frames, cancelled=cancellation
                    )
                    if pending.stat().st_size > VIDEO_ALLOWANCE:
                        raise OperationError("REEL_STORAGE", "Muxed MP4 exceeds 32 MiB allowance")
                    stages[current_stage] = time.perf_counter() - tick
                    sample(current_stage)
                    current_stage = "verify"
                    tick = time.perf_counter()
                    result["audio_verification"] = verify_audio(
                        video, pending, reference, decoded, resolved, frames, cancelled=cancellation
                    )
                    verified = verify_video(
                        pending, width=720, height=1280, frames=frames, cancelled=cancellation
                    )
                    if (
                        verified["decoded_rgb_sha256"]
                        != video_report["verification"]["decoded_rgb_sha256"]
                    ):
                        raise OperationError(
                            "REEL_VIDEO_CHANGED", "Decoded video changed through mux"
                        )
                    result["verification"] = verified
                    result["streams"] = stream_check(pending, cancellation, frames)
                    stages[current_stage] = time.perf_counter() - tick
                    sample(current_stage)
                result["media_verified"] = True
                current_stage = "publish"
                with pending.open("rb") as handle:
                    os.fsync(handle.fileno())
                observation = memory_observability(monitor.initial, memory_snapshot())
                if not monitor.oom_telemetry_continuous or observation["oom_events_changed"]:
                    raise OperationError("REEL_RESOURCE", "Lost telemetry or changed OOM counters")
                cancelled_check(cancellation)
                os.link(pending, output)
                result["published"] = True
                result["file_size_bytes"] = output.stat().st_size
                result["output_sha256"] = digest(output)
                result["temporary_storage"] = {
                    "stage_samples_bytes": storage,
                    "sampled_logical_peak_bytes": max(storage.values()),
                    "preflight_estimate_bytes": estimate,
                    "disk_reserve_bytes": 64 * 1024**2,
                    "scope": (
                        "Logical stage boundaries; hard links double-counted; "
                        "transient peaks may be missed"
                    ),
                }
            except (Exception, KeyboardInterrupt) as error:
                result["error"] = {**error_data(error), "stage": current_stage}
            finally:
                if owner is not None:
                    try:
                        owner.cleanup()
                        owner.assert_absent()
                        result["transaction_clean"] = True
                    except OperationError as error:
                        result["cleanup_error"] = error_data(error)
    except (Exception, KeyboardInterrupt) as error:
        result["resource_error"] = error_data(error)
    if owner is not None and result["transaction_clean"]:
        try:
            owner.assert_absent()
        except OperationError as error:
            result["transaction_clean"] = False
            result["cleanup_error"] = error_data(error)
    if monitor is not None and hasattr(monitor, "final"):
        result["whole_job_memory"] = monitor.report()
        result["memory_observability"] = memory_observability(monitor.initial, monitor.final)
        if (
            not monitor.oom_telemetry_continuous
            or result["memory_observability"]["oom_events_changed"]
            or cancellation.is_set()
        ):
            result["resource_error"] = result["resource_error"] or {
                "code": "REEL_RESOURCE",
                "message": "Whole-job monitoring refused success",
            }
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    result["cpu_seconds"] = {
        "parent": time.process_time() - own,
        "children_user": after.ru_utime - child.ru_utime,
        "children_system": after.ru_stime - child.ru_stime,
    }
    result["total_wall_seconds"] = time.perf_counter() - started
    result["workflow_fps"] = frames / result["total_wall_seconds"]
    result["stage_seconds"] = stages
    result["success"] = (
        result["published"]
        and result["media_verified"]
        and result["transaction_clean"]
        and all(result[k] is None for k in ("error", "cleanup_error", "resource_error"))
    )
    (output_dir / "report.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result
