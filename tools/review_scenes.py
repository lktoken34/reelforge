"""Bounded deterministic, layer/composition and hierarchy evidence for the three JSON scenes."""

import hashlib
import json
import time
from html import escape
from pathlib import Path

from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
from reelforge.rendering.diagnostic import color
from reelforge.resources.monitor import JobMonitor
from reelforge.scenes.assets import cost
from reelforge.scenes.contract import load_scene
from reelforge.scenes.graph import compile_scene, inspect_scene, scene_frame

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("rural_outpost", "tree_path", "barn_approach")


def diagram(compiled):
    children = {r.id: [] for r in compiled.hierarchy}
    for r in compiled.hierarchy:
        if r.parent is not None:
            children[r.parent].append(r.id)
    xy = {}
    cursor = 0

    def place(name, level):
        nonlocal cursor
        if children[name]:
            ys = [place(child, level + 1) for child in children[name]]
            y = sum(ys) / len(ys)
        else:
            y = 55 + cursor * 65
            cursor += 1
        xy[name] = (20 + level * 195, y)
        return y

    place(next(r.id for r in compiled.hierarchy if r.parent is None), 0)
    width = max(x for x, y in xy.values()) + 190
    height = cursor * 65 + 40
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect width="{width}" height="{height}" fill="#142c34"/>',
    ]
    for r in compiled.hierarchy:
        x, y = xy[r.id]
        if r.parent:
            px, py = xy[r.parent]
            out.append(
                f'<path d="M{px + 165},{py} C{px + 180},{py} {x - 15},{y} {x},{y}" '
                'fill="none" stroke="#718d83"/>'
            )
        fill = (
            "#9a8056"
            if r.kind in ("asset", "character", "background", "environment")
            else "#365c60"
        )
        out.append(f'<rect x="{x}" y="{y - 21}" width="165" height="42" rx="5" fill="{fill}"/>')
        out.append(
            f'<text x="{x + 7}" y="{y - 4}" fill="#f4e5c7" '
            f'font-family="sans-serif" font-size="12">{escape(r.id)}</text>'
        )
        detail = r.kind + (f" / depth {r.depth:g}" if r.kind == "layer" else "")
        out.append(
            f'<text x="{x + 7}" y="{y + 12}" fill="#d3ded3" '
            f'font-family="sans-serif" font-size="11">{detail}</text>'
        )
    return "\n".join(out + ["</svg>"]) + "\n"


def main():
    import cairo

    output = ROOT / "artifacts/phase5a"
    renderer = CairoRenderer()
    report = {}
    started = time.perf_counter()
    with JobMonitor(workspace=output) as monitor:
        for name in NAMES:
            compiled = compile_scene(load_scene(ROOT / f"examples/scenes/{name}.json"))
            hashes = {}
            geometry = {}
            timing = dict(geometry_seconds=0.0, raster_seconds=0.0)
            for frame in (89, 0, 45, 0, 89, 45):
                tick = time.perf_counter()
                commands = scene_frame(compiled, frame)
                timing["geometry_seconds"] += time.perf_counter() - tick
                digest = hashlib.sha256(repr(commands).encode()).hexdigest()
                if str(frame) in geometry:
                    assert geometry[str(frame)] == digest
                geometry[str(frame)] = digest
                with renderer.surface(720, 1280) as surface:
                    tick = time.perf_counter()
                    renderer.draw(
                        surface, commands, background=color("243e49"), logical_size=(360, 640)
                    )
                    timing["raster_seconds"] += time.perf_counter() - tick
                    pixel = surface.pixel_sha256()
                    if str(frame) in hashes:
                        assert hashes[str(frame)] == pixel
                    hashes[str(frame)] = pixel
                # Match independently rendered stills, not only samples within this loop.
                still = json.loads((output / name / "stills_report.json").read_text())
                assert still["source_pixel_sha256"][str(frame)] == pixel
            plan = inspect_scene(compiled, 45)
            (output / name / "compiled.json").write_text(json.dumps(plan, indent=2) + "\n")
            (output / name / "structure.svg").write_text(diagram(compiled))
            paths, ops = cost(scene_frame(compiled, 45))
            report[name] = {
                "source_pixels": hashes,
                "geometry": geometry,
                "out_of_order_repeat_equal": True,
                "independent_stills_equal": True,
                "actual_paths": paths,
                "actual_ops": ops,
                "path_allowance": compiled.path_allowance,
                "operation_allowance": compiled.operation_allowance,
                "node_count": len(compiled.hierarchy),
                "timings": timing,
            }
        # A labeled contact sheet: native bitmap composition only, no new artwork.
        sheet = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1080, 700)
        ctx = cairo.Context(sheet)
        ctx.set_source_rgb(0.07, 0.16, 0.19)
        ctx.paint()
        ctx.select_font_face("sans-serif")
        for i, name in enumerate(NAMES):
            ctx.set_source_rgb(0.92, 0.84, 0.69)
            ctx.set_font_size(17)
            ctx.move_to(i * 360 + 15, 30)
            ctx.show_text(name.replace("_", " ").title())
            image = cairo.ImageSurface.create_from_png(str(output / name / "frame_045.png"))
            ctx.save()
            ctx.translate(i * 360, 45)
            ctx.scale(0.5, 0.5)
            ctx.set_source_surface(image, 0, 0)
            ctx.paint()
            ctx.restore()
            image.finish()
        sheet.write_to_png(str(output / "composition_contact_sheet.png"))
        ctx = None
        sheet.finish()
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    (output / "determinism_report.json").write_text(
        json.dumps(
            {
                "scope": (
                    "Pinned native build; absolute-time evaluation, "
                    "three independently authored scene layouts"
                ),
                "versions": backend_versions(),
                "scenes": report,
                "wall_seconds": time.perf_counter() - started,
                "memory": monitor.report(),
                "live_surfaces_after": renderer.active_surfaces,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
