"""Create a silent 6-60 second vertical reel from an ordered production-0.1 plan.

A production is rendered as sequential silent episode-0.2 chunks (<=10 ninety-frame segments
each) through the existing audited episode workflow, then joined with an FFmpeg stream-copy
concat and verified end to end. No engine source changes are needed to author another story.

Commands:
  python tools/production.py capabilities
  python tools/production.py schema
  python tools/production.py validate  MANIFEST
  python tools/production.py inspect   MANIFEST
  python tools/production.py render    MANIFEST --output-dir DIR
"""

import argparse
import json
import signal
from pathlib import Path
from threading import Event

from reelforge.core.errors import InputError, OperationError
from reelforge.productions.contract import (
    MAX_SEGMENTS,
    MAX_SEGMENTS_PER_CHUNK,
    MIN_SEGMENTS,
    load_production,
)
from reelforge.productions.schema import production_schema

AUDIO_ROOT = Path(__file__).resolve().parents[1] / "assets/audio"


def capabilities() -> dict:
    return {
        "contract": "production-0.1",
        "experimental": True,
        "render_available": True,
        "commands": ["capabilities", "schema", "validate", "inspect", "render"],
        "frames_per_segment": 90,
        "segments": [MIN_SEGMENTS, MAX_SEGMENTS],
        "seconds": [MIN_SEGMENTS * 3, MAX_SEGMENTS * 3],
        "max_segments_per_chunk": MAX_SEGMENTS_PER_CHUNK,
        "assembly": "sequential silent episode-0.2 chunks joined by FFmpeg stream-copy concat",
        "fps": 30,
        "output": [720, 1280],
        "audio": "silent only (audio: null); zero audio streams",
        "characters": ["rowan_01", "yellow_mellow_v2"],
        "budget_mib": 256,
        "reserve_mib": 64,
        "preserves": "episode-0.1/0.2 bounds and all historical contracts are unchanged",
    }


def inspect(plan) -> dict:
    return {
        "contract": "production-0.1",
        "title": plan.title,
        "segments": len(plan.segments),
        "frames": plan.frames,
        "seconds": plan.seconds,
        "fps": 30,
        "output": [720, 1280],
        "audio_streams": 0,
        "chunks": [
            {
                "index": c.index,
                "start_frame": c.start_frame,
                "frames": c.frames,
                "segments": [s.id for s in c.episode.segments],
            }
            for c in plan.chunks
        ],
        "chunk_boundaries": plan.chunk_boundaries,
        "editorial_cuts": plan.editorial_cuts,
        "segment_ids": [s.id for s in plan.segments],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", type=Path, default=AUDIO_ROOT)
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("capabilities", "schema"):
        subs.add_parser(name)
    for name in ("validate", "inspect", "render"):
        p = subs.add_parser(name)
        p.add_argument("manifest", type=Path)
        if name == "render":
            p.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    cancelled = Event()
    signal.signal(signal.SIGTERM, lambda *_: cancelled.set())
    signal.signal(signal.SIGINT, lambda *_: cancelled.set())

    try:
        if args.command == "capabilities":
            result = capabilities()
        elif args.command == "schema":
            result = production_schema()
        elif args.command == "render":
            from reelforge.productions.workflow import render_production
            from reelforge.resources.monitor import JobMonitor

            plan = load_production(args.manifest)
            parent = args.output_dir.resolve().parent
            with JobMonitor(workspace=parent, cancelled=cancelled) as monitor:
                result = render_production(
                    plan, args.output_dir, registry_root=args.registry_root, cancelled=cancelled
                )
            result["end_to_end_memory"] = monitor.report()
            if cancelled.is_set():
                result["success"] = False
        else:
            plan = load_production(args.manifest)
            result = (
                {
                    "valid": True,
                    "segments": len(plan.segments),
                    "frames": plan.frames,
                    "seconds": plan.seconds,
                    "audio_streams": 0,
                }
                if args.command == "validate"
                else inspect(plan)
            )
    except InputError as error:
        print(json.dumps({"ok": False, "issue": error.issue.as_dict()}))
        return 2
    except (OperationError, OSError, ValueError, ImportError) as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": getattr(error, "code", "REEL_RUNTIME"),
                        "message": str(error),
                    },
                }
            )
        )
        return 1
    print(json.dumps(result))
    return 0 if result.get("success", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
