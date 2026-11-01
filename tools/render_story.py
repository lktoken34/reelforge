"""Stream a validated experimental story through one accepted Cairo/FFmpeg job."""

import argparse
import json
import resource
import signal
import time
from pathlib import Path

from reelforge.contracts.project import project_digest
from reelforge.core.errors import InputError, OperationError
from reelforge.stories.contract import Story, load_story
from reelforge.stories.sampling import sample_story, story_frame


def render(story: Story, output_dir: Path) -> dict:
    if story.audio is not None:
        from render_audio_story import render_with_audio

        return render_with_audio(story, output_dir, render_silent=render)
    # Validation in main happens before optional/native imports or output-directory creation.
    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.media.process import run_bounded
    from reelforge.media.verify import verify_video
    from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
    from reelforge.rendering.diagnostic import color
    from reelforge.resources.deployment import check_workspace, memory_observability
    from reelforge.resources.monitor import JobMonitor, preflight_memory

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    check_workspace(output_dir)
    preflight_memory()
    output = output_dir / "story.mp4"
    renderer = CairoRenderer()
    own = time.process_time()
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    timings = {
        s.id: {
            "frames": 0,
            "geometry_seconds": 0.0,
            "draw_seconds": 0.0,
            "stream_write_seconds": 0.0,
        }
        for s in story.shots
    }
    hashes, duplicates, peak_commands, peak_ops = [], [], 0, 0
    with JobMonitor(workspace=output_dir) as monitor:
        started = time.perf_counter()
        with FFmpegEncoder(
            output,
            width=story.output.width,
            height=story.output.height,
            frames=story.output.frames,
            timeout=max(120, story.output.frames / 2),
            cancelled=monitor.cancelled,
        ) as encoder:
            monitor.encoder_pid = encoder.proc.pid
            with renderer.surface(story.output.width, story.output.height) as surface:
                renderer.draw(surface, (), background=color("243e49"), logical_size=(360, 640))
                blank_hash = surface.pixel_sha256()
                for frame in range(story.output.frames):
                    sample = sample_story(story, frame)
                    record = timings[sample.shot.id]
                    tick = time.perf_counter()
                    commands = story_frame(story, frame)
                    record["geometry_seconds"] += time.perf_counter() - tick
                    peak_commands = max(peak_commands, len(commands))
                    peak_ops = max(peak_ops, sum(len(c.path) + len(c.clip or ()) for c in commands))
                    tick = time.perf_counter()
                    renderer.draw(
                        surface, commands, background=color("243e49"), logical_size=(360, 640)
                    )
                    record["draw_seconds"] += time.perf_counter() - tick
                    digest = surface.pixel_sha256()
                    if digest == blank_hash:
                        raise OperationError("STORY_BLANK", f"Blank source at frame {frame}")
                    if hashes and hashes[-1] == digest:
                        duplicates.append(frame)
                    hashes.append(digest)  # <=900 bounded text hashes; no retained video frames.
                    tick = time.perf_counter()
                    encoder.write_surface(surface)
                    record["stream_write_seconds"] += time.perf_counter() - tick
                    record["frames"] += 1
        seconds = time.perf_counter() - started
        verification = verify_video(
            output,
            width=story.output.width,
            height=story.output.height,
            frames=story.output.frames,
            cancelled=monitor.cancelled,
        )
        rc, raw, errors = run_bounded(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "json",
                str(output),
            ],
            timeout=30,
            cancelled=monitor.cancelled,
        )
        if rc or errors.strip():
            raise OperationError("STORY_STREAMS", "Could not verify video-only stream layout")
        stream_types = [stream.get("codec_type") for stream in json.loads(raw)["streams"]]
        if stream_types != ["video"]:
            raise OperationError(
                "STORY_STREAMS", "Expected one video stream and no audio/subtitle tracks"
            )
        encoder.confirm_cleanup()
    if renderer.active_surfaces or renderer.allocated_bytes:
        raise OperationError("SURFACE_LEAK", "Story rendering retained surfaces")
    observability = memory_observability(monitor.initial, monitor.final)
    if not monitor.oom_telemetry_continuous or observability["oom_events_changed"]:
        raise OperationError("OOM_TELEMETRY", "Story OOM telemetry was lost or counters changed")
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        "scope": "Phase 4A experimental multi-shot story on development host; not target VM",
        "story": story.to_data(),
        "story_digest": project_digest(story.to_data()),
        "versions": backend_versions(),
        "technical_rendering_success": True,
        "artistic_approval": False,
        "deployment_gate_approved": False,
        "frames_written": encoder.frames_written,
        "encoder_invocations": 1,
        "render_encode_seconds": seconds,
        "encoded_fps": story.output.frames / seconds,
        "per_shot_timings": timings,
        "render_timings": {
            key: sum(r[key] for r in timings.values())
            for key in ("geometry_seconds", "draw_seconds", "stream_write_seconds")
        },
        "whole_job_memory": monitor.report(),
        "memory_observability": observability,
        "cpu_seconds": {
            "renderer": time.process_time() - own,
            "children_user": after.ru_utime - child.ru_utime,
            "children_system": after.ru_stime - child.ru_stime,
        },
        "peak_commands": peak_commands,
        "peak_path_and_clip_operations": peak_ops,
        "source_surface_sha256": hashes,
        "source_hash_format": "Cairo native ARGB32 surface including pixel layout header",
        "blank_source_frames": [],
        "adjacent_duplicate_source_frames": duplicates,
        "cut_boundaries": [
            {
                "frame": s.start_frame,
                "from": story.shots[i - 1].id,
                "to": s.id,
                "before_sha256": hashes[s.start_frame - 1],
                "after_sha256": hashes[s.start_frame],
            }
            for i, s in enumerate(story.shots)
            if i
        ],
        "verification": verification,
        "stream_types": stream_types,
        "encoder_exit_status": encoder.returncode,
        "live_surfaces_after": renderer.active_surfaces,
        "allocated_surface_bytes_after": renderer.allocated_bytes,
        "transaction_clean": not Path(encoder.command[-1]).parent.exists(),
        "file_size_bytes": output.stat().st_size,
    }
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    def interrupt(signum, frame):
        raise KeyboardInterrupt("Story render interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    try:
        story = load_story(args.story)
        report = render(story, args.output_dir)
    except InputError as exc:
        print(json.dumps({"ok": False, "render_ready": False, "issue": exc.issue.as_dict()}))
        return 2
    except (OperationError, OSError, ImportError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "render_ready": False,
                    "error": {"code": getattr(exc, "code", "STORY_RUNTIME"), "message": str(exc)},
                }
            )
        )
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "render_ready": False, "cancelled": True}))
        return 130
    print(
        json.dumps(
            {
                "ok": True,
                "render_ready": False,
                "scope": "experimental story",
                "frames": report["frames_written"],
                "encoded_fps": report["encoded_fps"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
