"""Sequential supervised audio workflow around the unchanged silent story renderer."""

import json
import os
import resource
import shutil
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from reelforge.audio.processing import command, mix_pcm, mux_audio, verify_audio
from reelforge.audio.registry import AudioRegistry, digest, inspect_wav
from reelforge.audio.transaction import private_directory
from reelforge.core.errors import OperationError
from reelforge.media.verify import verify_video
from reelforge.resources.deployment import check_workspace, memory_observability
from reelforge.resources.monitor import JobMonitor
from reelforge.stories.contract import Story, validate_story

AUDIO_ROOT = Path(__file__).resolve().parents[1] / "assets/audio"
VIDEO_ALLOWANCE = 32 * 1024**2


def temporary_size(root: Path) -> int:
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


def portable_report(value, private: Path):
    """Reports retain command templates without references to deleted private files."""
    if isinstance(value, dict):
        return {key: portable_report(item, private) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable_report(item, private) for item in value]
    if isinstance(value, str):
        return value.replace(str(private), "<audio_transaction>")
    return value


def render_with_audio(
    story: Story, output_dir: Path, *, render_silent: Callable, registry_root: Path = AUDIO_ROOT
) -> dict:
    validate_story(story.to_data())
    started = time.perf_counter()
    own = time.process_time()
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "story.mp4"
    if output.exists() or output.is_symlink():
        raise OperationError(
            "OUTPUT_EXISTS", "Successful output exists; select a fresh output directory"
        )
    check_workspace(output_dir)
    registry = AudioRegistry(registry_root)
    disk_samples = {}
    with private_directory(output_dir) as private:
        with JobMonitor(workspace=output_dir) as monitor:
            validation_start = time.perf_counter()
            tool_version = (
                command(["ffmpeg", "-version"], cancelled=monitor.cancelled)
                .decode()
                .splitlines()[0]
            )
            resolved = registry.resolve(
                story.audio, story.output.frames, cancelled=monitor.cancelled, workspace=private
            )
            snapshot_bytes = sum(
                a.size_bytes for a in {r.asset.id: r.asset for r in resolved}.values()
            )
            estimate = (
                snapshot_bytes
                + max(r.asset.size_bytes for r in resolved)
                + 2 * story.output.frames * 1600 * 8
                + 2 * VIDEO_ALLOWANCE
                + 1024**2
            )
            check_workspace(
                output_dir, minimum_free_bytes=max(256 * 1024**2, estimate + 64 * 1024**2)
            )
            snapshot_root = private / "assets"
            snapshot_root.mkdir()
            snapshots = {}
            for r in resolved:
                if r.asset.id in snapshots:
                    continue
                path = snapshot_root / r.asset.file
                shutil.copyfile(r.path, path)
                if digest(path) != r.asset.sha256:
                    raise OperationError("AUDIO_CHANGED", f"{r.asset.id}: changed during snapshot")
                actual = inspect_wav(
                    path, r.asset.role, cancelled=monitor.cancelled, workspace=private
                )
                if any(actual[k] != getattr(r.asset, k) for k in actual):
                    raise OperationError("AUDIO_CHANGED", "Snapshot metadata mismatch")
                snapshots[r.asset.id] = path
            validation_seconds = time.perf_counter() - validation_start
            disk_samples["snapshots"] = temporary_size(private)
            tick = time.perf_counter()
            silent = replace(story, schema_version="story-0.1", audio=None)
            video_report = render_silent(silent, private / "video")
            video = private / "video/story.mp4"
            if video.stat().st_size > VIDEO_ALLOWANCE:
                raise OperationError(
                    "AUDIO_STORAGE", "Silent video exceeds the 32 MiB stage allowance"
                )
            video_seconds = time.perf_counter() - tick
            disk_samples["video"] = temporary_size(private)
            tick = time.perf_counter()
            reference = private / "reference.f32"
            decoded = private / "decoded.f32"
            pending = private / "pending.mp4"
            mix = mix_pcm(
                resolved, story.output.frames, snapshots, reference, cancelled=monitor.cancelled
            )
            disk_samples["mixed_pcm"] = temporary_size(private)
            mix_seconds = time.perf_counter() - tick
            tick = time.perf_counter()
            mux_command = mux_audio(
                video, reference, pending, story.output.frames, cancelled=monitor.cancelled
            )
            mux_seconds = time.perf_counter() - tick
            disk_samples["muxed"] = temporary_size(private)
            tick = time.perf_counter()
            audio_verification = verify_audio(
                video,
                pending,
                reference,
                decoded,
                resolved,
                story.output.frames,
                cancelled=monitor.cancelled,
            )
            verification = verify_video(
                pending,
                width=720,
                height=1280,
                frames=story.output.frames,
                cancelled=monitor.cancelled,
            )
            if (
                verification["decoded_rgb_sha256"]
                != video_report["verification"]["decoded_rgb_sha256"]
            ):
                raise OperationError("AUDIO_VIDEO_CHANGED", "Decoded video differs after muxing")
            verification_seconds = time.perf_counter() - tick
            disk_samples["verification"] = temporary_size(private)
            if max(disk_samples.values()) > estimate:
                raise OperationError(
                    "AUDIO_STORAGE", "Temporary storage exceeded its preflight allowance"
                )
            # No candidate is published before full video/audio verification and fsync.
            # The no-clobber hard link also protects an output created during this workflow.
            with pending.open("rb") as f:
                os.fsync(f.fileno())
            monitor.sample()
            if monitor.cancelled.is_set():
                raise OperationError(
                    "AUDIO_CANCELLED", "Resource monitor cancelled before publication"
                )
        observability = memory_observability(monitor.initial, monitor.final)
        if not monitor.oom_telemetry_continuous or observability["oom_events_changed"]:
            raise OperationError(
                "AUDIO_OOM", "Workflow OOM telemetry unavailable or counters changed"
            )
        if monitor.cancelled.is_set():
            raise OperationError("AUDIO_CANCELLED", "Resource monitor cancelled before publication")
        os.link(pending, output)
        pending.unlink()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    total = time.perf_counter() - started
    report = {
        "scope": "Phase 4B complete sequential video + audio workflow, development host only",
        "story": story.to_data(),
        "audio_native_version": tool_version,
        "technical_rendering_success": True,
        "artistic_approval": False,
        "deployment_gate_approved": False,
        "frames_written": video_report["frames_written"],
        "encoded_fps": video_report["encoded_fps"],
        "workflow_fps": story.output.frames / total,
        "total_wall_seconds": total,
        "asset_validation_seconds": validation_seconds,
        "video_stage_wall_seconds": video_seconds,
        "audio_mix_seconds": mix_seconds,
        "audio_mux_seconds": mux_seconds,
        "verification_seconds": verification_seconds,
        "audio_processing_seconds": mix_seconds + mux_seconds + verification_seconds,
        "render_encode_seconds": video_report["render_encode_seconds"],
        "cpu_seconds": {
            "renderer": time.process_time() - own,
            "children_user": after.ru_utime - children.ru_utime,
            "children_system": after.ru_stime - children.ru_stime,
        },
        "whole_job_memory": monitor.report(),
        "memory_observability": observability,
        "temporary_storage": {
            "stage_samples_bytes": disk_samples,
            "sampled_peak_bytes": max(disk_samples.values()),
            "preflight_estimate_bytes": estimate,
            "disk_reserve_bytes": 64 * 1024**2,
        },
        "assets": [
            {
                "id": r.asset.id,
                "sha256": r.asset.sha256,
                "role": r.asset.role,
                "source_rate": r.asset.sample_rate,
                "source_channels": r.asset.channels,
            }
            for r in resolved
        ],
        "mix": mix,
        "mux_command": mux_command,
        "audio_verification": audio_verification,
        "verification": verification,
        "video_report": video_report,
        "source_surface_sha256": video_report["source_surface_sha256"],
        "stream_types": ["video", "audio"],
        "file_size_bytes": output.stat().st_size,
        "live_surfaces_after": video_report["live_surfaces_after"],
        "allocated_surface_bytes_after": video_report["allocated_surface_bytes_after"],
        "transaction_clean": not private.exists(),
    }
    report = portable_report(report, private)
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report
