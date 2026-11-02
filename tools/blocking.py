"""Validate, inspect and render bounded blocking-0.1 motion studies."""

import argparse
import json
import signal
import time
from pathlib import Path

from reelforge.blocking.contract import load_blocking
from reelforge.blocking.sampling import blocking_frame, blocking_layers, inspect_frame
from reelforge.core.errors import InputError, OperationError


def capabilities():
    return {
        "version": "blocking-0.1",
        "experimental": True,
        "production_render_ready": False,
        "character": "rowan_01",
        "base_versions": ["scene-0.1", "environment-0.1", "composition-0.1"],
        "frames": 90,
        "fps": 30,
        "modes": ["idle", "walk", "run", "stop", "turn"],
        "max_segments": 12,
        "minimum_segment_frames": 6,
        "minimum_turn_frames": 12,
        "route": (
            "horizontal world-coordinate Hermite segments; no slopes, obstacles or depth navigation"
        ),
        "support": "level_field on orchard_ground_01 or trusted generated_ground only",
        "cameras": ["base", "locked", "exit_right"],
        "walk_end_speed": [10, 45],
        "run_end_speed": [40, 90],
        "max_acceleration": 240,
        "stride_factor": [0.7, 1.3],
        "max_cycles_per_bout": 16,
        "turn": "bounded stationary two-facing cross-dissolve, not 3D yaw",
        "contact_tolerance_world": 1e-7,
        "pose_continuity_tolerance_radians": 0.001,
        "pose_continuity_root_units": 0.005,
        "budget_mib": 256,
        "reserve_mib": 64,
    }


def inspect_plan(plan):
    return {
        "contract": "blocking-0.1",
        "frames": 90,
        "corridor_world": plan.corridor,
        "support_world": plan.support,
        "actor_scale": plan.scale,
        "base_graph_is_stationary_reference": True,
        "segments": [
            {
                "id": s.id,
                "range": [s.start, s.end],
                "mode": s.mode,
                "position": [s.x0, s.x1, s.y],
                "velocity": [s.v0, s.v1],
                "facing": s.facing,
                "acting": s.acting,
                "expression": s.expression,
            }
            for s in plan.segments
        ],
        "clocks": [
            {
                "start": c.start,
                "end": c.end,
                "distance_rig": c.total_distance,
                "cycles": c.total_cycles,
                "phase_factor": c.factor,
                "contact_step_count": len(c.steps),
            }
            for c in plan.clocks
        ],
        "paths_allowance": plan.compiled.path_allowance,
        "operations_allowance": plan.compiled.operation_allowance,
    }


def render(path, output, *, stills_only=False):
    plan = load_blocking(path)
    from scene import render_scene

    from reelforge.resources.deployment import memory_observability
    from reelforge.resources.monitor import JobMonitor

    parent = output.resolve().parent
    while not parent.exists():
        parent = parent.parent
    started = time.perf_counter()
    with JobMonitor(workspace=parent) as monitor:
        result = render_scene(
            plan.compiled,
            output,
            stills_only=stills_only,
            frame_evaluator=lambda c, f: blocking_frame(plan, f),
            layer_evaluator=lambda c, f: blocking_layers(plan, f),
        )
    observation = memory_observability(monitor.initial, monitor.final)
    if (
        monitor.cancelled.is_set()
        or not monitor.oom_telemetry_continuous
        or observation["oom_events_changed"]
    ):
        raise OperationError("BLOCKING_RESOURCE", "Whole-job observation failed")
    (output / "blocking_job.json").write_text(
        json.dumps(
            {
                "scope": (
                    "Compiled motion plan; native rendering, encoder children "
                    "and full decode under strict monitoring"
                ),
                "wall_seconds": time.perf_counter() - started,
                "memory": monitor.report(),
                "observability": observation,
                "blocking": inspect_plan(plan),
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
        raise KeyboardInterrupt("Blocking render interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.command == "capabilities":
            result = capabilities()
        elif args.command == "schema":
            from reelforge.blocking.schema import blocking_schema

            result = blocking_schema()
        elif args.command == "render":
            r = render(args.path, args.output_dir, stills_only=args.stills_only)
            result = {"success": r["success"], "report": str(args.output_dir)}
        else:
            plan = load_blocking(args.path)
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
                    "error": {"code": getattr(e, "code", "BLOCKING_RUNTIME"), "message": str(e)},
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
