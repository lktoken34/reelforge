"""Experimental unified 90-frame storyboard/audio workflow; production CLI unchanged."""

import argparse
import json
import signal
from dataclasses import asdict
from pathlib import Path
from threading import Event

from reelforge.audio.registry import AudioRegistry
from reelforge.core.errors import InputError, OperationError
from reelforge.reels.contract import inspect_reel, load_reel, metadata_plan
from reelforge.reels.schema import reel_schema

AUDIO_ROOT = Path(__file__).resolve().parents[1] / "assets/audio"


def capabilities():
    return {
        "contract": "reel-0.1",
        "experimental": True,
        "production_render_ready": False,
        "commands": ["capabilities", "schema", "assets", "validate", "inspect", "frame", "render"],
        "frames": 90,
        "fps": 30,
        "output": [720, 1280],
        "sample_rate": 48000,
        "samples_per_frame": 1600,
        "effective_samples_per_channel": 144000,
        "audio": "Accepted AudioPlan; registered IDs only; <=1 narration + 4 SFX",
        "budget_mib": 256,
        "reserve_mib": 64,
        "planning_validation": "metadata-only; full media validation always required at render",
    }


def render_storyboard(plan, output, **kwargs):
    from scene import render_scene

    from reelforge.direction.sampling import direction_frame, direction_layers

    return render_scene(
        plan.direction.compiled,
        output,
        frame_evaluator=lambda c, f: direction_frame(plan.direction, f),
        layer_evaluator=lambda c, f: direction_layers(plan.direction, f),
        **kwargs,
    )


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
            result = reel_schema()
        elif args.command == "assets":
            result = {
                "validation": "metadata-only",
                "assets": [asdict(a) for a in AudioRegistry(args.registry_root).assets.values()],
            }
        elif args.command == "render":
            from reelforge.reels.workflow import render_reel
            from reelforge.resources.monitor import JobMonitor

            parent = args.output_dir.resolve().parent
            result = None
            try:
                with JobMonitor(workspace=parent, cancelled=cancelled) as monitor:
                    plan = load_reel(args.manifest)
                    result = render_reel(
                        plan,
                        args.output_dir,
                        registry_root=args.registry_root,
                        render_silent=render_storyboard,
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
            plan = load_reel(args.manifest)
            resolved = metadata_plan(plan, AudioRegistry(args.registry_root))
            result = (
                {
                    "valid": True,
                    "registry_validation": "metadata-only",
                    "media_bytes_validated": False,
                }
                if args.command == "validate"
                else inspect_reel(plan, resolved, args.frame if args.command == "frame" else None)
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
