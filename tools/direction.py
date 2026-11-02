"""Validate, inspect and render bounded direction-0.1 cinematic studies."""

import argparse
import json
import signal
import time
from pathlib import Path

from reelforge.core.errors import InputError, OperationError
from reelforge.direction.contract import load_direction
from reelforge.direction.sampling import direction_frame, direction_layers, inspect_frame


def capabilities():
    from reelforge.direction.contract import BEHAVIORS, FRAMINGS

    return {
        "version": "direction-0.1",
        "experimental": True,
        "production_render_ready": False,
        "frames": 90,
        "fps": 30,
        "output": [720, 1280],
        "max_shots": 6,
        "minimum_shot_frames": 8,
        "behaviors": BEHAVIORS,
        "framing": FRAMINGS,
        "base_versions": ["scene-0.1", "environment-0.1", "composition-0.1", "blocking-0.1"],
        "targets": ["actor", "node", "point"],
        "zoom": [0.9, 1.7],
        "pan_bounds_logical": [-240, 240],
        "max_pan_speed_logical_per_second": 240,
        "max_zoom_speed_per_second": 1.5,
        "max_look_ahead_seconds": 0.35,
        "transitions": ["hard_cut"],
        "tracking_tolerance_logical": 1e-7,
        "budget_mib": 256,
        "reserve_mib": 64,
        "commands": ["capabilities", "schema", "validate", "inspect", "frame", "render"],
    }


def inspect_plan(plan):
    from dataclasses import asdict

    return {
        "contract": "direction-0.1",
        "frames": 90,
        "fps": 30,
        "continuous_source_time": True,
        "shots": [asdict(s) for s in plan.shots],
        "path_allowance": plan.compiled.path_allowance,
        "operation_allowance": plan.compiled.operation_allowance,
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
        plan = load_direction(path)
        result = render_scene(
            plan.compiled,
            output,
            stills_only=stills_only,
            frame_evaluator=lambda c, f: direction_frame(plan, f),
            layer_evaluator=lambda c, f: direction_layers(plan, f),
        )
    observation = memory_observability(monitor.initial, monitor.final)
    if (
        monitor.cancelled.is_set()
        or not monitor.oom_telemetry_continuous
        or observation["oom_events_changed"]
    ):
        raise OperationError("DIRECTION_RESOURCE", "Whole-job observation failed")
    (output / "direction_job.json").write_text(
        json.dumps(
            {
                "scope": (
                    "Compilation, safety admission; native rendering, encoder children "
                    "and full decode under strict monitoring"
                ),
                "wall_seconds": time.perf_counter() - started,
                "memory": monitor.report(),
                "observability": observation,
                "direction": inspect_plan(plan),
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
    for name in ("validate", "inspect", "frame", "render"):
        p = subs.add_parser(name)
        p.add_argument("path", type=Path)
        if name == "frame":
            p.add_argument("--frame", type=int, required=True)
        if name == "render":
            p.add_argument("--output-dir", type=Path, required=True)
            p.add_argument("--stills-only", action="store_true")
    args = parser.parse_args()

    def interrupted(signum, frame):
        raise KeyboardInterrupt("Direction render interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.command == "capabilities":
            result = capabilities()
        elif args.command == "schema":
            from reelforge.direction.schema import direction_schema

            result = direction_schema()
        elif args.command == "render":
            r = render(args.path, args.output_dir, stills_only=args.stills_only)
            result = {"success": r["success"], "report": str(args.output_dir)}
        else:
            plan = load_direction(args.path)
            result = (
                inspect_frame(plan, args.frame) if args.command == "frame" else inspect_plan(plan)
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
                    "error": {"code": getattr(e, "code", "DIRECTION_RUNTIME"), "message": str(e)},
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
