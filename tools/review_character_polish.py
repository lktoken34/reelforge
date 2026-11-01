"""Phase 3A.1 engineering proof sheets and bounded, full-resolution A/B video comparison."""

import argparse
import hashlib
import json
import os
import signal
import tempfile
from pathlib import Path

from reelforge.characters.review import expression_sheet, review_sheet, transition_sheet
from reelforge.characters.study import BACKGROUND, character_frame
from reelforge.media.process import run_bounded
from reelforge.media.verify import verify_video
from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.diagnostic import color
from reelforge.resources.deployment import check_workspace, memory_observability
from reelforge.resources.monitor import JobMonitor, preflight_memory

BASELINE = Path(__file__).resolve().parents[1] / "artifacts/phase3a/rowan_idle_walk_run.mp4"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(65536):
            h.update(block)
    return h.hexdigest()


def sheets(directory):
    check_workspace(directory)
    preflight_memory()
    renderer = CairoRenderer()
    with JobMonitor(workspace=directory):
        for name, commands, size, bg in (
            ("transition_sheet.png", transition_sheet(), (1080, 1280), BACKGROUND),
            ("expression_sheet.png", expression_sheet(), (1200, 960), color("efe9da")),
            ("review_sheet.png", review_sheet(), (1440, 1280), color("efe9da")),
        ):
            with renderer.surface(*size) as surface:
                renderer.draw(surface, commands, background=bg, logical_size=size)
                surface.write_png(directory / name)
        for frame in (24, 30, 35, 84, 90, 95):
            with renderer.surface(720, 1280) as surface:
                renderer.draw(
                    surface, character_frame(frame), background=BACKGROUND, logical_size=(360, 640)
                )
                surface.write_png(directory / f"transition_{frame:03}.png")


def comparison(after, directory):
    check_workspace(directory)
    preflight_memory()
    baseline_report = json.loads(BASELINE.with_name("report.json").read_text())
    assert digest(BASELINE) == baseline_report["artifact_sha256"][BASELINE.name]
    output = directory / "before_after.mp4"
    temporary = None
    with JobMonitor(workspace=directory) as monitor:
        before_meta = verify_video(BASELINE, width=720, height=1280, cancelled=monitor.cancelled)
        after_meta = verify_video(after, width=720, height=1280, cancelled=monitor.cancelled)
        temporary = tempfile.TemporaryDirectory(prefix=".reelforge-comparison-", dir=directory)
        pending = Path(temporary.name) / "pending.mp4"
        try:
            command = [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-threads",
                "1",
                "-i",
                str(BASELINE),
                "-threads",
                "1",
                "-i",
                str(after),
                "-filter_complex_threads",
                "1",
                "-filter_complex",
                "[0:v]setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]hstack=inputs=2[v]",
                "-map",
                "[v]",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-threads:v",
                "1",
                "-x264-params",
                "rc-lookahead=0:sync-lookahead=0:bframes=0",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-frames:v",
                "150",
                "-r",
                "30",
                "-f",
                "mp4",
                str(pending),
            ]
            rc, out, err = run_bounded(
                command, timeout=120, max_bytes=65536, cancelled=monitor.cancelled
            )
            if rc:
                raise RuntimeError(err.decode(errors="replace")[-2048:])
            verification = verify_video(
                pending, width=1440, height=1280, cancelled=monitor.cancelled
            )
            with pending.open("rb") as handle:
                os.fsync(handle.fileno())
            os.link(pending, output)  # same-directory atomic no-clobber publication
        finally:
            pending.unlink(missing_ok=True)
            temporary.cleanup()
    metrics = monitor.report()
    metrics["encoder_peak_rss_bytes"] = None
    metrics["root_role"] = (
        "comparison utility; sequential media children, encoder PID not separately registered"
    )
    observability = memory_observability(monitor.initial, monitor.final)
    if not monitor.oom_telemetry_continuous:
        observability["sufficient_for_technical_validation"] = False
        observability["limitations"].append("OOM telemetry was not continuous")
    if observability["oom_events_changed"]:
        raise RuntimeError("Cgroup OOM counters changed during comparison; inspect diagnostics")
    result = {
        "scope": "Development A/B: left Phase 3A baseline / right Phase 3A.1 candidate",
        "baseline_commit": "05be54725926c14f30c897b7d70590c07de840be",
        "baseline_sha256": digest(BASELINE),
        "after_sha256": digest(after),
        "same_resolution_per_panel": [720, 1280],
        "same_fps": 30,
        "same_frames": 150,
        "before_verification": before_meta,
        "after_verification": after_meta,
        "comparison_verification": verification,
        "command": command,
        "whole_job_memory": metrics,
        "memory_observability": observability,
        "artistic_approval": False,
        "deployment_gate_approved": False,
    }
    (directory / "comparison_report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()

    def interrupt(signum, frame):
        raise KeyboardInterrupt("Comparison interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sheets(args.output_dir.resolve())
    r = comparison(args.after.resolve(), args.output_dir.resolve())
    print(
        json.dumps(
            {
                "comparison_peak_mib": r["whole_job_memory"][
                    "estimated_simultaneous_tree_peak_rss_bytes"
                ]
                / 1048576
            }
        )
    )


if __name__ == "__main__":
    main()
