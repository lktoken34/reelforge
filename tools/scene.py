"""Experimental scene tools; the production episode CLI stays unchanged."""

import argparse
import json
import resource
import signal
import time
from dataclasses import asdict
from pathlib import Path

from reelforge.core.errors import InputError, OperationError
from reelforge.scenes.assets import ASSETS, cost
from reelforge.scenes.contract import (
    CAMERAS,
    KINDS,
    MAX_DEPTH,
    MAX_INSTANCES,
    MAX_LAYERS,
    MAX_NODES,
    MAX_OPS,
    MAX_PATHS,
    load_scene,
)
from reelforge.scenes.graph import compile_scene, evaluate_layers, inspect_scene, scene_frame


def capabilities() -> dict:
    return {
        "experimental": True,
        "production_render_ready": False,
        "versions": ["scene-0.1"],
        "node_kinds": KINDS,
        "assets": [asdict(a) for a in ASSETS],
        "cameras": CAMERAS,
        "limits": {
            "nodes": MAX_NODES,
            "instances": MAX_INSTANCES,
            "depth": MAX_DEPTH,
            "layers": MAX_LAYERS,
            "draw_paths": MAX_PATHS,
            "path_operations": MAX_OPS,
        },
        "transforms": "positive uniform scale + clockwise rotation + translation; no shear",
        "workflow": "validate SCENE; inspect SCENE --frame 0; render SCENE --output-dir DIR",
    }


def render_scene(compiled, output: Path, *, stills_only: bool = False) -> dict:
    # Native imports occur only after native-free validation and graph compilation.
    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.media.verify import verify_video
    from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
    from reelforge.rendering.diagnostic import color
    from reelforge.resources.deployment import check_workspace, memory_observability
    from reelforge.resources.monitor import JobMonitor

    output = output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise OperationError("OUTPUT_EXISTS", "Choose a new output directory") from error
    video = output / "scene.mp4"
    report_file = output / ("stills_report.json" if stills_only else "render_report.json")
    if video.exists() or video.is_symlink() or report_file.exists():
        raise OperationError(
            "OUTPUT_EXISTS", "Choose a fresh output directory; no output is overwritten"
        )
    check_workspace(output)
    renderer = CairoRenderer()
    timing = dict(geometry_seconds=0.0, raster_seconds=0.0, stream_seconds=0.0)
    frames = compiled.scene.frames
    own = time.process_time()
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    hashes = {}
    maximum_paths = maximum_ops = 0
    cleanup_error = None
    verification = None
    with JobMonitor(workspace=output) as monitor:
        if stills_only:
            for frame in (0, frames // 2, frames - 1):
                commands = scene_frame(compiled, frame)
                with renderer.surface(720, 1280) as surface:
                    renderer.draw(
                        surface, commands, background=color("243e49"), logical_size=(360, 640)
                    )
                    hashes[str(frame)] = surface.pixel_sha256()
                    surface.write_png(output / f"frame_{frame:03}.png")
            for layer in evaluate_layers(compiled, frames // 2):
                with renderer.surface(720, 1280) as surface:
                    renderer.draw(
                        surface,
                        layer.commands,
                        background=color("243e49", 0),
                        logical_size=(360, 640),
                    )
                    surface.write_png(output / f"layer_{layer.id}.png")
        else:
            with FFmpegEncoder(
                video,
                width=720,
                height=1280,
                frames=frames,
                timeout=120,
                cancelled=monitor.cancelled,
            ) as encoder:
                monitor.encoder_pid = encoder.proc.pid
                with renderer.surface(720, 1280) as surface:
                    for frame in range(frames):
                        tick = time.perf_counter()
                        commands = scene_frame(compiled, frame)
                        timing["geometry_seconds"] += time.perf_counter() - tick
                        paths, ops = cost(commands)
                        maximum_paths = max(maximum_paths, paths)
                        maximum_ops = max(maximum_ops, ops)
                        tick = time.perf_counter()
                        renderer.draw(
                            surface, commands, background=color("243e49"), logical_size=(360, 640)
                        )
                        timing["raster_seconds"] += time.perf_counter() - tick
                        hashes[str(frame)] = surface.pixel_sha256()
                        tick = time.perf_counter()
                        encoder.write_surface(surface)
                        timing["stream_seconds"] += time.perf_counter() - tick
            encode_seconds = time.perf_counter() - started
            verification = verify_video(
                video, width=720, height=1280, frames=frames, cancelled=monitor.cancelled
            )
            try:
                encoder.confirm_cleanup()
            except OperationError as error:
                # Preserve the failure and valid media for independent review. Never report
                # overall success or sweep a restored directory on this execution host.
                cleanup_error = {"code": error.code, "message": str(error)}
        monitor.sample()
    observability = memory_observability(monitor.initial, monitor.final)
    if (
        monitor.cancelled.is_set()
        or not monitor.oom_telemetry_continuous
        or observability["oom_events_changed"]
    ):
        raise OperationError("SCENE_RESOURCE", "Resource guard or OOM telemetry failed")
    if renderer.active_surfaces or renderer.allocated_bytes:
        raise OperationError("SURFACE_LEAK", "Scene render retained surfaces")
    end_child = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {
        "scope": "Experimental scene-0.1 development proof; no deployment approval",
        "success": cleanup_error is None,
        "stills_only": stills_only,
        "cleanup_error": cleanup_error,
        "versions": backend_versions(),
        "scene": inspect_scene(compiled),
        "frames": frames,
        "source_pixel_sha256": hashes,
        "maximum_paths": maximum_paths,
        "maximum_ops": maximum_ops,
        "timings": timing,
        "wall_seconds": time.perf_counter() - started,
        "encoded_fps": None if stills_only else frames / encode_seconds,
        "cpu_seconds": {
            "parent": time.process_time() - own,
            "children_user": end_child.ru_utime - child.ru_utime,
            "children_system": end_child.ru_stime - child.ru_stime,
        },
        "memory": monitor.report(),
        "observability": observability,
        "verification": verification,
        "live_surfaces_after": renderer.active_surfaces,
        "surface_bytes_after": renderer.allocated_bytes,
    }
    report_file.write_text(json.dumps(result, indent=2) + "\n")
    if cleanup_error:
        raise OperationError(cleanup_error["code"], cleanup_error["message"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("schema")
    for name in ("validate", "inspect", "render"):
        command = sub.add_parser(name)
        command.add_argument("scene", type=Path)
        if name == "inspect":
            command.add_argument("--frame", type=int, default=0)
        if name == "render":
            command.add_argument("--output-dir", required=True, type=Path)
            command.add_argument("--stills-only", action="store_true")
    args = parser.parse_args()

    def interrupt(signum, frame):
        raise KeyboardInterrupt("Scene render interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    try:
        if args.command == "capabilities":
            result = capabilities()
        elif args.command == "schema":
            from reelforge.scenes.schema import scene_schema

            result = scene_schema()
        else:
            compiled = compile_scene(load_scene(args.scene))
            if args.command == "validate":
                result = {"valid": True, "experimental": True, "production_render_ready": False}
            elif args.command == "inspect":
                result = inspect_scene(compiled, args.frame)
            else:
                report = render_scene(compiled, args.output_dir, stills_only=args.stills_only)
                result = {
                    "ok": report["success"],
                    "experimental": True,
                    "production_render_ready": False,
                    "frames": report["frames"],
                    "encoded_fps": report["encoded_fps"],
                    "report": str(
                        args.output_dir
                        / ("stills_report.json" if args.stills_only else "render_report.json")
                    ),
                }
    except InputError as error:
        print(json.dumps({"ok": False, "issue": error.issue.as_dict()}))
        return 2
    except (OperationError, OSError, ImportError, ValueError) as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": getattr(error, "code", "SCENE_RUNTIME"),
                        "message": str(error),
                    },
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
