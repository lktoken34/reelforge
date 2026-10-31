"""Four fresh render+encode+full-decode workers; compare repeats by decoded visual content."""

import argparse
import json
import sys
from pathlib import Path

from reelforge.media.process import run_bounded
from reelforge.resources.memory import add_memory_policy_argument


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_memory_policy_argument(parser)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/phase2b"))
    parser.add_argument("--scratch-dir", type=Path, default=Path("outputs/phase2b-repeats"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for width in (360, 720):
        hashes = None
        for repeat in range(2):
            root = args.output_dir if repeat == 0 else args.scratch_dir
            output = root / f"diagnostic_{width}x{width * 16 // 9}.mp4"
            report_path = args.scratch_dir / f"report_{width}_{repeat}.json"
            rc, out, err = run_bounded(
                [
                    sys.executable,
                    str(Path(__file__).with_name("render_video.py").resolve()),
                    "--memory-policy",
                    args.memory_policy,
                    "--width",
                    str(width),
                    "--output",
                    str(output),
                    "--report",
                    str(report_path),
                ],
                timeout=120,
                max_bytes=65536,
            )
            if rc:
                raise RuntimeError(err.decode(errors="replace")[-4096:])
            print(out.decode().strip(), flush=True)
            report = json.loads(report_path.read_text())
            # Reaped worker: reconcile only its known private transaction path. This also
            # keeps checkpointed/shared workspace views clean after child-process exit.
            pending = Path(report["encoder_command"][-1])
            if (
                pending.parent.parent.resolve() != output.parent.resolve()
                or not pending.parent.name.startswith(".reelforge-encode-")
            ):
                raise RuntimeError("Worker reported an unexpected transaction directory")
            pending.unlink(missing_ok=True)
            if pending.parent.exists():
                pending.parent.rmdir()

            if report["whole_job_memory"]["encoder_peak_rss_bytes"] <= 0:
                raise RuntimeError("Encoder RSS was not measured")
            if hashes is not None and report["verification"]["decoded_rgb_sha256"] != hashes:
                raise RuntimeError("Repeated decoded visual content differs")
            hashes = report["verification"]["decoded_rgb_sha256"]
            report["repeat"] = repeat + 1
            runs.append(report)
    result = {
        "milestone": "2B",
        "runs": runs,
        "decoded_repeat_match": True,
        "note": "Each worker is a complete renderer+child-tools job. Batch launcher is "
        "outside worker memory measurements. No dedicated target VM/cgroup cap.",
    }
    (args.output_dir / "benchmark_results.json").write_text(json.dumps(result, indent=2) + "\n")
    # Static proof frames are extracted after encoding, never between Cairo and FFmpeg.
    for width in (360, 720):
        output = args.output_dir / f"diagnostic_{width}x{width * 16 // 9}.mp4"
        contact = args.output_dir / f"checkpoints_{width}.png"
        rc, _, err = run_bounded(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-threads",
                "1",
                "-i",
                str(output),
                "-filter_threads",
                "1",
                "-vf",
                "select=eq(n\\,0)+eq(n\\,75)+eq(n\\,149),scale=240:426,tile=3x1",
                "-frames:v",
                "1",
                "-threads:v",
                "1",
                str(contact),
            ],
            timeout=30,
            max_bytes=65536,
        )
        if rc:
            raise RuntimeError(err.decode(errors="replace"))


if __name__ == "__main__":
    main()
