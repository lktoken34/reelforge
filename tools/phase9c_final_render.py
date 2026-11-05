"""Phase 9C final render: the 15-second silent Frost Peak reel.

Assembles the five corrected Phase 9C storyboards (tools/phase9c_snowy_storyboard.py) into one
silent ``episode-0.2`` and renders all 450 frames through the existing audited episode workflow
(``reelforge.episodes.workflow.render_episode`` -> the shared bounded ``render_av`` transaction):
memory admission, owned private workspace, one continuous FFmpegEncoder streaming
``direction_frame`` per frame, full decode + exact-PTS verification, no-clobber publish and
cleanup. No frames are written to disk as PNGs and no new video engine is introduced.

Usage (WSL Ubuntu, Python 3.12 with pycairo + ffmpeg):
    python3 tools/phase9c_final_render.py --out-dir outputs/frost_peak_final
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from threading import Event

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import phase9c_snowy_storyboard as story  # noqa: E402

from reelforge.episodes.contract import compile_episode  # noqa: E402
from reelforge.episodes.workflow import render_episode  # noqa: E402

TITLE = "Yellow Mellow - The Last Light of Frost Peak"
REGISTRY_ROOT = REPO / "assets" / "audio"
FINAL_NAME = "YellowMellow_FrostPeak_15s_Final.mp4"


def build_episode() -> dict:
    """The silent five-segment episode built from the corrected storyboard shot builders."""
    segments = [
        {"id": f"shot_{num}", "storyboard": builder()}
        for (num, _title, _size, builder, _frame, _story, _reads) in story.SHOTS
    ]
    return {
        "schema_version": "episode-0.2",
        "title": TITLE,
        "segments": segments,
        "audio": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="outputs/frost_peak_final")
    parser.add_argument("--final", default=None, help="final MP4 path (default alongside out-dir)")
    args = parser.parse_args()

    out_dir = (REPO / args.out_dir).resolve()
    if out_dir.exists():
        raise SystemExit(f"{out_dir} already exists; choose a fresh output directory")
    final = Path(args.final).resolve() if args.final else out_dir.parent / FINAL_NAME

    plan = compile_episode(build_episode())
    print(f"episode: {len(plan.segments)} segments, {plan.frames} frames, silent={plan.silent}")

    report = render_episode(plan, out_dir, registry_root=REGISTRY_ROOT, cancelled=Event())

    keys = (
        "success",
        "published",
        "media_verified",
        "transaction_clean",
        "error",
        "cleanup_error",
        "resource_error",
    )
    print(json.dumps({k: report.get(k) for k in keys}, indent=2))
    if not report.get("success"):
        raise SystemExit("render did not report success; see report.json")

    reel = out_dir / "reel.mp4"
    if not reel.is_file():
        raise SystemExit("published reel.mp4 missing")
    shutil.copy2(reel, final)
    print(
        f"frames={report['frames']} seconds={report['frames'] / 30:.3f} "
        f"size={report['file_size_bytes']} bytes"
    )
    print(f"editorial_cuts={report['video_report']['editorial_cuts']}")
    print(f"final video: {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
