"""Trusted Phase 3B proof renderer; strict resource policy; no episode integration."""

import argparse
import json
import resource
import signal
import time
from pathlib import Path

from render_video import confirm_transaction_cleanup

from reelforge.core.errors import OperationError
from reelforge.environments.presets import EnvironmentPreset, load_preset
from reelforge.environments.scene import environment_frame, layers_at
from reelforge.media.encoder import FFmpegEncoder
from reelforge.media.verify import verify_video
from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
from reelforge.rendering.diagnostic import color
from reelforge.resources.deployment import check_workspace, memory_observability, pressure_snapshot
from reelforge.resources.monitor import JobMonitor, preflight_memory

BACKGROUND = color("243e49")


def render(output_dir: Path, *, stills_only=False, preset_path=None):
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    check_workspace(output_dir)
    preflight_memory()  # default strict; no deployment policy flags introduced here
    renderer = CairoRenderer()
    preset = load_preset(preset_path) if preset_path else EnvironmentPreset()
    if stills_only:
        for index in (0, 90, 179):
            with renderer.surface(720, 1280) as surface:
                renderer.draw(
                    surface,
                    environment_frame(index, preset),
                    background=BACKGROUND,
                    logical_size=(360, 640),
                )
                surface.write_png(output_dir / f"frame_{index:03}.png")
        for layer in layers_at(preset, 90):
            with renderer.surface(720, 1280) as surface:
                renderer.draw(
                    surface,
                    environment_frame(90, preset, only_layer=layer.id),
                    background=color("243e49", 0),
                    logical_size=(360, 640),
                )
                surface.write_png(output_dir / f"layer_{layer.id}.png")
        return {"stills": True}
    output = output_dir / "orchard_cinematic.mp4"
    own = time.process_time()
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    pressure = pressure_snapshot()
    with JobMonitor(workspace=output_dir) as monitor:
        preflight_memory(snapshot=monitor.initial)
        started = time.perf_counter()
        hashes = {}
        timings = {"geometry_seconds": 0.0, "draw_seconds": 0.0, "stream_write_seconds": 0.0}
        with FFmpegEncoder(
            output, width=720, height=1280, frames=180, timeout=120, cancelled=monitor.cancelled
        ) as encoder:
            monitor.encoder_pid = encoder.proc.pid
            with renderer.surface(720, 1280) as surface:
                for frame in range(180):
                    tick = time.perf_counter()
                    commands = environment_frame(frame, preset)
                    timings["geometry_seconds"] += time.perf_counter() - tick
                    tick = time.perf_counter()
                    renderer.draw(
                        surface,
                        commands,
                        background=BACKGROUND,
                        logical_size=(360, 640),
                    )
                    timings["draw_seconds"] += time.perf_counter() - tick
                    if frame in (0, 60, 120, 179):
                        hashes[str(frame)] = surface.pixel_sha256()
                    tick = time.perf_counter()
                    encoder.write_surface(surface)
                    timings["stream_write_seconds"] += time.perf_counter() - tick
        seconds = time.perf_counter() - started
        verification = verify_video(
            output, width=720, height=1280, frames=180, cancelled=monitor.cancelled
        )
        confirm_transaction_cleanup(Path(encoder.command[-1]), output)
    if renderer.active_surfaces or renderer.allocated_bytes:
        raise OperationError("SURFACE_LEAK", "Environment proof retained surfaces")
    observability = memory_observability(monitor.initial, monitor.final)
    if not monitor.oom_telemetry_continuous:
        observability["sufficient_for_technical_validation"] = False
        observability["limitations"].append("OOM telemetry was not continuous")
    if observability["oom_events_changed"]:
        raise OperationError("OOM_EVENTS", "OOM counters changed during character proof")
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        "scope": "Phase 3B development-host cinematic environment; not target VM",
        "versions": backend_versions(),
        "technical_rendering_success": True,
        "artistic_approval": False,
        "peak_commands": max(len(environment_frame(i, preset)) for i in (0, 90, 179)),
        "deployment_gate_approved": False,
        "render_encode_seconds": seconds,
        "render_timings": timings,
        "encoded_fps": 180 / seconds,
        "whole_job_memory": monitor.report(),
        "cpu_seconds": {
            "renderer": time.process_time() - own,
            "children_user": after.ru_utime - child.ru_utime,
            "children_system": after.ru_stime - child.ru_stime,
        },
        "file_size_bytes": output.stat().st_size,
        "encoder_exit_status": encoder.returncode,
        "source_checkpoint_sha256": hashes,
        "verification": verification,
        "memory_observability": observability,
        "pressure_before": pressure,
        "pressure_after": pressure_snapshot(),
        "live_surfaces_after": renderer.active_surfaces,
        "allocated_surface_bytes_after": renderer.allocated_bytes,
    }
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stills-only", action="store_true")
    parser.add_argument("--preset", type=Path)
    args = parser.parse_args()

    def interrupt(signum, frame):
        raise KeyboardInterrupt("Environment proof interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    result = render(args.output_dir, stills_only=args.stills_only, preset_path=args.preset)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k in ("stills", "encoded_fps", "render_encode_seconds")
            }
        )
    )


if __name__ == "__main__":
    main()
