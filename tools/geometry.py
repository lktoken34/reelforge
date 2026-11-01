"""Discover, validate, inspect, preview and compose bounded data-authored geometry."""

import argparse
import json
import signal
import time
from pathlib import Path

from reelforge.core.errors import InputError, OperationError
from reelforge.geometry.compiler import inspect_geometry, preview_scene
from reelforge.geometry.composition import (
    compile_composition,
    inspect_composition,
    load_composition,
)
from reelforge.geometry.contract import load_geometry
from reelforge.geometry.schema import composition_schema, geometry_schema


def capabilities() -> dict:
    return {
        "versions": ["geometry-0.1", "composition-0.1"],
        "experimental": True,
        "production_render_ready": False,
        "primitives": ["rect", "ellipse", "polygon", "path", "group"],
        "path_commands": {"M": 2, "L": 2, "C": 6, "Z": 0},
        "document_limits": {
            "bytes": 1048576,
            "json_containers": 32,
            "assets": 8,
            "palette_colors": 32,
            "anchors_per_asset": 8,
            "entries_per_asset": 128,
            "group_depth": 4,
            "paths_per_asset": 128,
            "ops_per_asset": 4096,
            "total_paths": 512,
            "total_ops": 16000,
            "instances": 16,
        },
        "numbers": {
            "reference_size": [1, 512],
            "coordinates": [-512, 512],
            "local_scale": [0.25, 2],
            "composed_local_scale": [0.1, 4],
            "local_rotation_degrees": [-45, 45],
            "composed_rotation_degrees": [-90, 90],
            "stroke_width": [0.25, 12],
            "gradient_stops": [2, 8],
        },
        "materials": (
            "named #RRGGBB[AA] colors and linear palette gradients; one local closed clip per leaf"
        ),
        "reference_bounds": (
            "transformed geometry/control points and anchors inside size; "
            "strokes may extend by half width"
        ),
        "group_semantics": (
            "ordered children, inherited similarity transform; no material/clip inheritance"
        ),
        "unsupported": [
            "code",
            "URLs",
            "includes",
            "SVG",
            "raster",
            "asset recursion",
            "shear",
            "nonuniform scale",
            "reflections",
            "authored character support",
            "new audio",
        ],
        "scene_caps": {
            "nodes": 64,
            "instances": 32,
            "layers": 8,
            "paths": 4096,
            "operations": 80000,
        },
    }


def render_file(path: Path, output: Path, *, asset=None, stills_only=False) -> dict:
    # All hostile input validation completes before native import or output creation.
    doc = load_geometry(path) if asset else load_composition(path)
    from scene import render_scene

    from reelforge.resources.deployment import memory_observability
    from reelforge.resources.monitor import JobMonitor

    started = time.perf_counter()
    parent = output.resolve().parent
    while not parent.exists():
        parent = parent.parent
    with JobMonitor(workspace=parent) as monitor:
        tick = time.perf_counter()
        compiled = preview_scene(doc, asset) if asset else compile_composition(doc)
        compile_seconds = time.perf_counter() - tick
        monitor.sample()
        if monitor.cancelled.is_set():
            raise OperationError("GEOMETRY_RESOURCE", "Cancelled before native rendering")
        result = render_scene(compiled, output, stills_only=stills_only)
    observation = memory_observability(monitor.initial, monitor.final)
    if (
        monitor.cancelled.is_set()
        or not monitor.oom_telemetry_continuous
        or observation["oom_events_changed"]
    ):
        raise OperationError("GEOMETRY_RESOURCE", "Whole-job resource observation failed")
    report = {
        "scope": (
            "Geometry compilation, native render, encode and decode "
            "under unchanged strict whole-job monitor"
        ),
        "compile_seconds": compile_seconds,
        "wall_seconds": time.perf_counter() - started,
        "memory": monitor.report(),
        "observability": observation,
    }
    (output / "geometry_job.json").write_text(json.dumps(report, indent=2) + "\n")
    if not result["success"]:
        raise OperationError("TRANSACTION_CLEANUP", result["cleanup_error"]["message"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("capabilities")
    p = subs.add_parser("schema")
    p.add_argument("--composition", action="store_true")
    for name in (
        "validate",
        "inspect",
        "validate-composition",
        "inspect-composition",
        "preview",
        "render",
    ):
        p = subs.add_parser(name)
        p.add_argument("path", type=Path)
        if name in ("preview", "render"):
            p.add_argument("--output-dir", required=True, type=Path)
            if name == "preview":
                p.add_argument("--asset", required=True)
            else:
                p.add_argument("--stills-only", action="store_true")
    args = parser.parse_args()

    def interrupted(signum, frame):
        raise KeyboardInterrupt("Geometry job interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.command == "capabilities":
            result = capabilities()
        elif args.command == "schema":
            result = composition_schema() if args.composition else geometry_schema()
        elif args.command in ("preview", "render"):
            report = render_file(
                args.path,
                args.output_dir,
                asset=getattr(args, "asset", None),
                stills_only=args.command == "preview" or args.stills_only,
            )
            result = {"success": report["success"], "report": str(args.output_dir)}
        elif "composition" in args.command:
            c = load_composition(args.path)
            result = inspect_composition(c)
            if args.command == "validate-composition":
                result = {
                    "valid": True,
                    "paths": result["graph"]["path_allowance"],
                    "operations": result["graph"]["operation_allowance"],
                }
        else:
            doc = load_geometry(args.path)
            result = inspect_geometry(doc)
            if args.command == "validate":
                result = {"valid": True, "assets": len(doc.assets)}
    except InputError as e:
        print(json.dumps({"ok": False, "issue": e.issue.as_dict()}))
        return 2
    except (OperationError, ValueError, OSError, ImportError) as e:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"code": getattr(e, "code", "GEOMETRY_RUNTIME"), "message": str(e)},
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
