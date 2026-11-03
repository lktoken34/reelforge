"""Create a 3–30-second vertical episode from accepted segments and global registered audio."""

import argparse
import json
import signal
from dataclasses import asdict
from pathlib import Path
from threading import Event

from reelforge.audio.registry import AudioRegistry
from reelforge.core.errors import InputError, OperationError
from reelforge.episodes.contract import inspect_episode, load_episode
from reelforge.episodes.schema import episode_schema
from reelforge.reels.contract import metadata_plan

AUDIO_ROOT = Path(__file__).resolve().parents[1] / "assets/audio"


def capabilities():
    return {
        "contract": ["episode-0.1", "episode-0.2"],
        "experimental": True,
        "render_available": True,
        "production_render_ready": False,
        "commands": ["capabilities", "schema", "assets", "validate", "inspect", "frame", "render"],
        "frames_per_segment": 90,
        "segments": [1, 10],
        "seconds": [3, 30],
        "editorial_cuts_between_segments": True,
        "fps": 30,
        "output": [720, 1280],
        "sample_rate": 48000,
        "samples_per_frame": 1600,
        "effective_samples_per_channel": "segments*90*1600",
        "audio": "episode-0.1: accepted AudioPlan, registered IDs only, <=1 narration + 4 SFX",
        "silent": "episode-0.2: audio=null renders one H.264 video stream and zero audio streams",
        "characters": ["rowan_01", "yellow_mellow_v2"],
        "character_selector": "storyboard rowan.character (optional; default rowan_01)",
        "budget_mib": 256,
        "reserve_mib": 64,
        "planning_validation": "metadata-only; full media validation always required at render",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry-root",
        type=Path,
        default=AUDIO_ROOT,
        help="Trusted operator registry; never selected by manifest",
    )
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("capabilities", "schema", "assets"):
        subs.add_parser(name)
    for name in ("validate", "inspect", "frame", "render"):
        p = subs.add_parser(name)
        p.add_argument("manifest", type=Path)
        if name == "frame":
            p.add_argument("--frame", type=int, required=True)
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
            result = episode_schema()
        elif args.command == "assets":
            result = {
                "validation": "metadata-only",
                "assets": [asdict(a) for a in AudioRegistry(args.registry_root).assets.values()],
            }
        elif args.command == "render":
            from reelforge.episodes.workflow import render_episode
            from reelforge.resources.monitor import JobMonitor

            parent = args.output_dir.resolve().parent
            result = None
            try:
                with JobMonitor(workspace=parent, cancelled=cancelled) as monitor:
                    plan = load_episode(args.manifest)
                    result = render_episode(
                        plan,
                        args.output_dir,
                        registry_root=args.registry_root,
                        cancelled=cancelled,
                    )
            except OperationError as error:
                if result is None:
                    raise
                result["success"] = False
                result["resource_error"] = {"code": error.code, "message": str(error)}
            result["end_to_end_memory"] = monitor.report()
            if cancelled.is_set():
                result["success"] = False
                result["resource_error"] = result["resource_error"] or {
                    "code": "REEL_RESOURCE",
                    "message": "Outer monitor cancelled",
                }
            (args.output_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
        else:
            plan = load_episode(args.manifest)
            if not plan.silent:
                metadata_plan(plan, AudioRegistry(args.registry_root), plan.frames)
            result = (
                {
                    "valid": True,
                    "silent": plan.silent,
                    "audio_streams": 0 if plan.silent else 1,
                    "registry_validation": "not-applicable" if plan.silent else "metadata-only",
                    "media_bytes_validated": False,
                }
                if args.command == "validate"
                else inspect_episode(
                    plan,
                    AudioRegistry(args.registry_root),
                    args.frame if args.command == "frame" else None,
                )
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
