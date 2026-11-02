"""Validate, inspect and render bounded storyboard-0.1 narrative studies."""

import argparse
import json
import signal
import time
from pathlib import Path

from reelforge.core.errors import InputError, OperationError
from reelforge.direction.sampling import direction_frame, direction_layers
from reelforge.storyboards.compiler import (
    inspect_beats,
    inspect_frame,
    inspect_plans,
    load_storyboard,
)


def capabilities() -> dict:
    from reelforge.storyboards.patterns import BEAT_ACTIONS, pattern_capabilities

    return {
        "version": "storyboard-0.1",
        "experimental": True,
        "production_render_ready": False,
        "frames": 90,
        "fps": 30,
        "output": [720, 1280],
        "max_beats": 10,
        "max_views": 6,
        "max_subjects": 16,
        "patterns": pattern_capabilities(),
        "beat_actions": BEAT_ACTIONS,
        "world_versions": ["scene-0.1", "environment-0.1", "composition-0.1"],
        "camera_views": "Adjacent beats with the same view share one shot; no implicit cut",
        "reaction_and_escape_minimum_frames": 12,
        "minimum_other_beat_frames": 6,
        "requires_admitted_travel_bout": True,
        "audio_present": False,
        "editorial_max_cut_pan_logical": 60,
        "safe_margin_logical": 8,
        "budget_mib": 256,
        "reserve_mib": 64,
        "commands": ["capabilities", "schema", "validate", "beats", "compile", "frame", "render"],
    }


def render(path, output, *, stills_only=False):
    from scene import render_scene

    from reelforge.resources.deployment import memory_observability
    from reelforge.resources.monitor import JobMonitor

    parent = output.resolve().parent
    while not parent.exists():
        parent = parent.parent
    started = time.perf_counter()
    with JobMonitor(workspace=parent) as monitor:
        plan = load_storyboard(path)
        result = render_scene(
            plan.direction.compiled,
            output,
            stills_only=stills_only,
            frame_evaluator=lambda c, f: direction_frame(plan.direction, f),
            layer_evaluator=lambda c, f: direction_layers(plan.direction, f),
        )
    observation = memory_observability(monitor.initial, monitor.final)
    if (
        monitor.cancelled.is_set()
        or not monitor.oom_telemetry_continuous
        or observation["oom_events_changed"]
    ):
        raise OperationError("STORYBOARD_RESOURCE", "Whole-job observation failed")
    (output / "storyboard_job.json").write_text(
        json.dumps(
            {
                "scope": (
                    "Compilation, safety admission; native rendering, encoder children "
                    "and full decode under strict monitoring"
                ),
                "wall_seconds": time.perf_counter() - started,
                "memory": monitor.report(),
                "observability": observation,
                "storyboard": inspect_beats(plan),
            },
            indent=2,
        )
        + "\n"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("capabilities")
    subs.add_parser("schema")
    for name in ("validate", "beats", "compile", "frame", "render"):
        p = subs.add_parser(name)
        p.add_argument("path", type=Path)
        if name == "frame":
            p.add_argument("--frame", type=int, required=True)
        if name == "render":
            p.add_argument("--output-dir", type=Path, required=True)
            p.add_argument("--stills-only", action="store_true")
    args = parser.parse_args()

    def interrupted(signum, frame):
        raise KeyboardInterrupt("Storyboard render interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.command == "capabilities":
            result = capabilities()
        elif args.command == "schema":
            from reelforge.storyboards.schema import storyboard_schema

            result = storyboard_schema()
        elif args.command == "render":
            r = render(args.path, args.output_dir, stills_only=args.stills_only)
            result = {"success": r["success"], "report": str(args.output_dir)}
        else:
            plan = load_storyboard(args.path)
            result = (
                inspect_frame(plan, args.frame)
                if args.command == "frame"
                else inspect_plans(plan)
                if args.command == "compile"
                else inspect_beats(plan)
            )
            if args.command == "validate":
                result = {"valid": True, "frames": 90}
    except InputError as e:
        print(json.dumps({"ok": False, "issue": e.issue.as_dict()}))
        return 2
    except (OperationError, ValueError, OSError, ImportError) as e:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"code": getattr(e, "code", "STORYBOARD_RUNTIME"), "message": str(e)},
                }
            )
        )
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "cancelled": True}))
        return 130
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
