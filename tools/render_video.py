"""One bounded engineering render/verify job; not an installed weak-agent command."""

import argparse
import json
import platform
import time
from pathlib import Path

from reelforge.media.encoder import FFmpegEncoder
from reelforge.media.process import run_bounded
from reelforge.media.verify import verify_video
from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
from reelforge.rendering.diagnostic import BACKGROUND, LOGICAL_SIZE
from reelforge.rendering.video_diagnostic import diagnostic_frame
from reelforge.resources.monitor import JobMonitor, preflight_memory


def render_job(output: Path, *, width: int, height: int, frames: int = 150) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    renderer = CairoRenderer()
    source_samples = {}
    with JobMonitor() as monitor:
        preflight_memory(snapshot=monitor.initial)
        started = time.perf_counter()
        with FFmpegEncoder(
            output, width=width, height=height, frames=frames, cancelled=monitor.cancelled
        ) as encoder:
            monitor.encoder_pid = encoder.proc.pid
            with renderer.surface(width, height) as surface:
                for frame in range(frames):
                    renderer.draw(
                        surface,
                        diagnostic_frame(frame, frames),
                        background=BACKGROUND,
                        logical_size=LOGICAL_SIZE,
                    )
                    if frame in {0, frames // 2, frames - 1}:
                        source_samples[str(frame)] = surface.pixel_sha256()
                    encoder.write_surface(surface)
        render_seconds = time.perf_counter() - started
        if len(set(source_samples.values())) != 3:
            raise RuntimeError("Source geometry did not change at the three checkpoints")
        verification = verify_video(
            output, width=width, height=height, frames=frames, cancelled=monitor.cancelled
        )
        if renderer.active_surfaces != 0 or renderer.allocated_bytes != 0:
            raise RuntimeError("Surface ownership was not released")
    rc, version, _ = run_bounded(["ffmpeg", "-version"], max_bytes=65536)
    return {
        "output": str(output),
        "width": width,
        "height": height,
        "fps": 30,
        "frames": frames,
        "render_encode_seconds": render_seconds,
        "effective_encoded_fps": frames / render_seconds,
        "file_size_bytes": output.stat().st_size,
        "encoder_exit_status": encoder.returncode,
        "encoder_command": encoder.command,
        "source_checkpoint_sha256": source_samples,
        "verification": verification,
        "whole_job_memory": monitor.report(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "distribution": platform.freedesktop_os_release()["PRETTY_NAME"],
            "ffmpeg_version": version.decode().splitlines()[0],
            **backend_versions(),
        },
        "resource_scope": "Renderer worker and child tools from preflight through full decode. "
        "CPU-only; host swap counters are recorded; not a target-VM certification.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, choices=[360, 720], default=360)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = render_job(args.output.resolve(), width=args.width, height=args.width * 16 // 9)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "peak_tree_mib": report["whole_job_memory"][
                    "estimated_simultaneous_tree_peak_rss_bytes"
                ]
                / 1048576,
                "seconds": report["render_encode_seconds"],
                "verified": True,
            }
        )
    )


if __name__ == "__main__":
    main()
