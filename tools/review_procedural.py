"""Fixed six-example quality evidence; no user code, raster packs or whole-orchard backgrounds."""

import hashlib
import json
import sys
import time
from pathlib import Path

from reelforge.core.errors import OperationError
from reelforge.procedural.compiler import compile_environment, inspect_environment
from reelforge.procedural.contract import load_environment
from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
from reelforge.rendering.diagnostic import color
from reelforge.resources.monitor import JobMonitor
from reelforge.scenes.assets import cost
from reelforge.scenes.graph import scene_frame

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase5b"
NAMES = (
    "woodland_trail_417",
    "woodland_trail_9",
    "settlement_street_417",
    "settlement_street_33",
    "rocky_shelter_417",
    "rocky_shelter_3",
)


def contact_sheet(names, path, *, temporal=False):
    import cairo

    width = 1080
    height = 1400 if not temporal else 2070
    sheet = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(sheet)
    ctx.set_source_rgb(0.06, 0.14, 0.18)
    ctx.paint()
    ctx.select_font_face("sans-serif")
    ctx.set_font_size(16)
    if temporal:
        cells = [
            (name, f, row * 3 + col)
            for row, name in enumerate(names)
            for col, f in enumerate((0, 45, 89))
        ]
    else:
        cells = [(name, 45, (i % 2) * 3 + i // 2) for i, name in enumerate(names)]
    for name, frame, index in cells:
        x = (index % 3) * 360
        y = (index // 3) * 690
        ctx.set_source_rgb(0.91, 0.85, 0.7)
        ctx.move_to(x + 10, y + 25)
        ctx.show_text(name.replace("_", " ") + (f" / {frame}" if temporal else ""))
        image = cairo.ImageSurface.create_from_png(str(OUT / name / f"frame_{frame:03}.png"))
        ctx.save()
        ctx.translate(x, y + 40)
        ctx.scale(0.5, 0.5)
        ctx.set_source_surface(image, 0, 0)
        ctx.paint()
        ctx.restore()
        image.finish()
    sheet.write_to_png(str(path))
    ctx = None
    sheet.finish()


def main():
    renderer = CairoRenderer()
    evidence = {}
    started = time.perf_counter()
    with JobMonitor(workspace=OUT) as monitor:
        for name in NAMES:
            request = load_environment(ROOT / f"examples/procedural/{name}.json")
            tick = time.perf_counter()
            plan, c = compile_environment(request)
            compile_seconds = time.perf_counter() - tick
            geom = {}
            pixels = {}
            counts = {}
            for frame in (89, 0, 45, 0, 89, 45):
                commands = scene_frame(c, frame)
                key = str(frame)
                sha = hashlib.sha256(repr(commands).encode()).hexdigest()
                if key in geom:
                    assert geom[key] == sha
                geom[key] = sha
                counts[key] = cost(commands)
                with renderer.surface(720, 1280) as surface:
                    renderer.draw(
                        surface, commands, background=color("243e49"), logical_size=(360, 640)
                    )
                    digest = surface.pixel_sha256()
                    if key in pixels:
                        assert pixels[key] == digest
                    pixels[key] = digest
                original = json.loads((OUT / name / "stills_report.json").read_text())
                assert original["source_pixel_sha256"][key] == digest
            (OUT / name / "generation.json").write_text(
                json.dumps(inspect_environment(plan, c), indent=2) + "\n"
            )
            evidence[name] = {
                "compile_seconds": compile_seconds,
                "geometry_sha256": geom,
                "source_pixels": pixels,
                "actual_paths_ops": counts,
                "path_bound": plan.path_allowance,
                "operation_bound": plan.operation_allowance,
                "nodes": len(c.scene.nodes),
                "instances": plan.instance_allowance,
                "deterministic_out_of_order": True,
                "static_generated_assets": len(c.generated),
                "actor_ground": [plan.actor_x, plan.actor_y],
            }
        contact_sheet(NAMES, OUT / "seed_contact_sheet.png")
        contact_sheet(NAMES[::2], OUT / "camera_contact_sheet.png", temporal=True)
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    result = {
        "scope": "Six fixed JSON requests, seed-only pairs, pinned native build",
        "versions": backend_versions(),
        "examples": evidence,
        "wall_seconds": time.perf_counter() - started,
        "memory": monitor.report(),
    }
    for a, b in zip(NAMES[::2], NAMES[1::2], strict=True):
        assert evidence[a]["geometry_sha256"] != evidence[b]["geometry_sha256"]
        assert evidence[a]["source_pixels"] != evidence[b]["source_pixels"]
    (OUT / "determinism_report.json").write_text(json.dumps(result, indent=2) + "\n")


def rocky_repeat():
    from procedural_environment import render_request

    request = load_environment(ROOT / "examples/procedural/rocky_shelter_417.json")
    output = ROOT / "outputs/phase5b-rocky-repeat"
    error = None
    started = time.perf_counter()
    monitor = JobMonitor(workspace=OUT)
    try:
        with monitor:
            render_request(request, output)
    except OperationError as e:
        error = {"code": e.code, "message": str(e)}
    report = {
        "scope": (
            "One controlled repeat for consistency and full workflow measurement; "
            "cleanup failures retained"
        ),
        "wall_seconds": time.perf_counter() - started,
        "whole_job_memory": monitor.report(),
        "error": error,
    }
    (OUT / "rocky_repeat_job.json").write_text(json.dumps(report, indent=2) + "\n")
    if (output / "render_report.json").is_file():
        repeat = json.loads((output / "render_report.json").read_text())
        first = json.loads((OUT / "rocky_video/render_report.json").read_text())
        equal = (
            first["source_pixel_sha256"] == repeat["source_pixel_sha256"]
            and first["verification"]["decoded_rgb_sha256"]
            == repeat["verification"]["decoded_rgb_sha256"]
        )
        assert equal
        (OUT / "rocky_repeat_report.json").write_text(json.dumps(repeat, indent=2) + "\n")
        (OUT / "video_repeat_consistency.json").write_text(
            json.dumps(
                {
                    "all_90_source_and_decoded_frames_equal": equal,
                    "first_job_success": first["success"],
                    "repeat_job_success": repeat["success"],
                    "scope": "Media determinism is separate from cleanup acceptance",
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    if "--repeat-rocky" in sys.argv:
        rocky_repeat()
    else:
        main()
