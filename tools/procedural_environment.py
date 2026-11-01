"""Discover, validate, inspect and render bounded environment-0.1 requests."""

import argparse
import json
import signal
from pathlib import Path

from reelforge.core.errors import InputError, OperationError
from reelforge.procedural.compiler import compile_environment, inspect_environment
from reelforge.procedural.contract import FAMILIES, load_environment
from reelforge.procedural.planning import BOUNDS


def capabilities():
    return {
        "contract": "environment-0.1",
        "experimental": True,
        "production_render_ready": False,
        "families": FAMILIES,
        "seed": [0, 2**32 - 1],
        "composition": {
            "density": [1, 3],
            "path_alignment": [-1, 1],
            "structure": [0, 1],
            "framing": [0, 1],
            "detail": ["standard", "rich"],
        },
        "art_direction": {"lighting": ["dusk", "overcast"], "atmosphere": [0, 1]},
        "rowan": {
            "enabled": "boolean",
            "action": ["idle", "look_around", "react"],
            "side": ["left", "right"],
        },
        "output": {
            "width": 720,
            "height": 1280,
            "fps": 30,
            "frames": 90,
            "codec": "h264",
            "pixel_format": "yuv420p",
        },
        "recipe_envelopes": BOUNDS,
        "agent_geometry_code": False,
        "legacy_scene_contract_changed": False,
    }


def render_request(request, output, *, stills_only=False):
    import resource
    import time

    from scene import render_scene

    from reelforge.procedural.compiler import compile_plan
    from reelforge.procedural.planning import plan_environment
    from reelforge.resources.deployment import memory_observability
    from reelforge.resources.monitor import JobMonitor

    parent = output.resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    cpu = time.process_time()
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    with JobMonitor(workspace=parent) as monitor:
        tick = time.perf_counter()
        plan = plan_environment(request)
        planning_seconds = time.perf_counter() - tick
        tick = time.perf_counter()
        compiled = compile_plan(plan)
        geometry_seconds = time.perf_counter() - tick
        monitor.sample()
        if monitor.cancelled.is_set():
            raise OperationError(
                "ENVIRONMENT_RESOURCE", "Cancelled before rendering generated geometry"
            )
        result = render_scene(compiled, output, stills_only=stills_only)
    observability = memory_observability(monitor.initial, monitor.final)
    if (
        monitor.cancelled.is_set()
        or not monitor.oom_telemetry_continuous
        or observability["oom_events_changed"]
    ):
        raise OperationError("ENVIRONMENT_RESOURCE", "Whole-job resource or OOM observation failed")
    end = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        "scope": (
            "Validation complete before job; strict monitor covers planning, "
            "geometry, native rendering and decode"
        ),
        "planning_seconds": planning_seconds,
        "geometry_generation_seconds": geometry_seconds,
        "wall_seconds": time.perf_counter() - started,
        "parent_cpu_seconds": time.process_time() - cpu,
        "child_cpu_seconds": end.ru_utime + end.ru_stime - children.ru_utime - children.ru_stime,
        "whole_job_memory": monitor.report(),
        "observability": observability,
        "render_report": "stills_report.json" if stills_only else "render_report.json",
    }
    (output / "environment_job.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "generation.json").write_text(
        json.dumps(inspect_environment(plan, compiled), indent=2) + "\n"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("capabilities")
    subs.add_parser("schema")
    for name in ("validate", "inspect", "render"):
        sub = subs.add_parser(name)
        sub.add_argument("request", type=Path)
        if name == "render":
            sub.add_argument("--output-dir", required=True, type=Path)
            sub.add_argument("--stills-only", action="store_true")
    args = parser.parse_args()

    def interrupted(signum, frame):
        raise KeyboardInterrupt("Environment rendering interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.command == "capabilities":
            result = capabilities()
        elif args.command == "schema":
            from reelforge.procedural.schema import environment_schema

            result = environment_schema()
        else:
            request = load_environment(args.request)
            if args.command != "render":
                plan, compiled = compile_environment(request)
            if args.command == "validate":
                result = {
                    "valid": True,
                    "family": request.family,
                    "seed": request.seed,
                    "path_allowance": plan.path_allowance,
                    "operation_allowance": plan.operation_allowance,
                }
            elif args.command == "inspect":
                result = inspect_environment(plan, compiled)
            else:
                result = render_request(request, args.output_dir, stills_only=args.stills_only)
                result = {
                    "success": result["success"],
                    "frames": 90,
                    "report": str(args.output_dir),
                }
    except InputError as e:
        print(json.dumps({"ok": False, "issue": e.issue.as_dict()}))
        return 2
    except (OperationError, ValueError, OSError, ImportError) as e:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"code": getattr(e, "code", "ENVIRONMENT_RUNTIME"), "message": str(e)},
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
