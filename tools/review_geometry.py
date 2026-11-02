"""Fixed Phase 5C evidence generation through public JSON and accepted rendering tooling."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from reelforge.geometry.compiler import inspect_geometry
from reelforge.geometry.composition import (
    compile_composition,
    inspect_composition,
    load_composition,
)
from reelforge.geometry.contract import load_geometry
from reelforge.media.process import run_bounded
from reelforge.resources.monitor import JobMonitor
from reelforge.scenes.assets import cost
from reelforge.scenes.graph import scene_frame

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase5c"
SCENES = (
    "woodland_relay",
    "settlement_checkpoint",
    "shelter_supply",
    "orchard_checkpoint",
    "heldout_station",
)


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def sheet(cells: list[tuple[str, Path]], destination: Path) -> None:
    import cairo

    height = ((len(cells) + 2) // 3) * 690
    target = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1080, height)
    ctx = cairo.Context(target)
    ctx.set_source_rgb(0.06, 0.14, 0.18)
    ctx.paint()
    ctx.select_font_face("sans-serif")
    ctx.set_font_size(14)
    for i, (label, path) in enumerate(cells):
        x = i % 3 * 360
        y = i // 3 * 690
        ctx.set_source_rgb(0.91, 0.85, 0.7)
        ctx.move_to(x + 8, y + 25)
        ctx.show_text(label)
        source = cairo.ImageSurface.create_from_png(str(path))
        ctx.save()
        ctx.translate(x, y + 40)
        ctx.scale(0.5, 0.5)
        ctx.set_source_surface(source)
        ctx.paint()
        ctx.restore()
        source.finish()
    target.write_to_png(str(destination))
    ctx = None
    target.finish()


def main() -> None:
    proofs = OUT / "proofs"
    proofs.mkdir(exist_ok=False)
    started = time.perf_counter()
    cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    records = []

    def run(arguments):
        command = [sys.executable, str(ROOT / "tools/geometry.py"), *arguments]
        rc, stdout, stderr = run_bounded(
            command, timeout=180, max_bytes=65536, cancelled=monitor.cancelled
        )
        record = {
            "command": command,
            "returncode": rc,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
        records.append(record)
        # No retry and no masking: valid media and error reports survive for independent review.
        save(
            OUT / "proof_execution.json",
            {
                "scope": "Public JSON CLI calls, single attempts, all exit statuses retained",
                "jobs": records,
            },
        )

    with JobMonitor(workspace=OUT) as monitor:
        for filename in ("survival_objects", "heldout_wash_station"):
            path = ROOT / f"examples/geometry/{filename}.json"
            doc = load_geometry(path)
            save(OUT / f"{filename}_inspection.json", inspect_geometry(doc))
            for a in doc.assets:
                run(
                    [
                        "preview",
                        str(path),
                        "--asset",
                        a.id,
                        "--output-dir",
                        str(proofs / ("asset_" + a.id)),
                    ]
                )
        for name in SCENES:
            path = ROOT / f"examples/compositions/{name}.json"
            save(OUT / f"{name}_inspection.json", inspect_composition(load_composition(path)))
            run(
                [
                    "render",
                    str(path),
                    "--stills-only",
                    "--output-dir",
                    str(proofs / (name + "_stills")),
                ]
            )
        for name in SCENES[:2]:
            run(
                [
                    "render",
                    str(ROOT / f"examples/compositions/{name}.json"),
                    "--output-dir",
                    str(proofs / (name + "_video")),
                ]
            )
        run(
            [
                "render",
                str(ROOT / "examples/compositions/settlement_checkpoint.json"),
                "--output-dir",
                str(proofs / "settlement_repeat"),
            ]
        )
    end = resource.getrusage(resource.RUSAGE_CHILDREN)
    save(
        OUT / "review_job_resources.json",
        {
            "scope": (
                "Sequential proof orchestration including child renderers, FFmpeg and decode; "
                "contacts generated separately"
            ),
            "wall_seconds": time.perf_counter() - started,
            "children_cpu_seconds": end.ru_utime + end.ru_stime - cpu.ru_utime - cpu.ru_stime,
            "memory": monitor.report(),
        },
    )
    doc = load_geometry(ROOT / "examples/geometry/survival_objects.json")
    sheet(
        [(a.id, proofs / ("asset_" + a.id) / "frame_045.png") for a in doc.assets]
        + [("held-out wash station", proofs / "asset_wash_station/frame_045.png")],
        OUT / "asset_showcases.png",
    )
    sheet(
        [(n.replace("_", " "), proofs / (n + "_stills") / "frame_045.png") for n in SCENES],
        OUT / "scene_compositions.png",
    )
    sheet(
        [
            (n.replace("_", " ") + f" / {f}", proofs / (n + "_stills") / f"frame_{f:03}.png")
            for n in SCENES[:3]
            for f in (0, 45, 89)
        ],
        OUT / "camera_contact_sheet.png",
    )
    sheet(
        [
            ("woodland: mast .70 / cart .70", proofs / "woodland_relay_stills/frame_045.png"),
            (
                "settlement: cart .65 / radio .40",
                proofs / "settlement_checkpoint_stills/frame_045.png",
            ),
            ("shelter: mast .65 / cart .65", proofs / "shelter_supply_stills/frame_045.png"),
        ],
        OUT / "reuse_comparison.png",
    )
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    renderer = CairoRenderer()
    evidence = {}
    with JobMonitor(workspace=OUT) as monitor:
        for name in SCENES:
            c = load_composition(ROOT / f"examples/compositions/{name}.json")
            compiled = compile_composition(c)
            geometry = {}
            pixels = {}
            counts = {}
            for frame in (89, 0, 45, 0, 89, 45):
                commands = scene_frame(compiled, frame)
                g = hashlib.sha256(repr(commands).encode()).hexdigest()
                assert frame not in geometry or geometry[frame] == g
                geometry[frame] = g
                counts[frame] = cost(commands)
                with renderer.surface(720, 1280) as surface:
                    renderer.draw(
                        surface, commands, background=color("243e49"), logical_size=(360, 640)
                    )
                    p = surface.pixel_sha256()
                    assert frame not in pixels or pixels[frame] == p
                    pixels[frame] = p
                original = json.loads(
                    (proofs / (name + "_stills") / "stills_report.json").read_text()
                )
                assert original["source_pixel_sha256"][str(frame)] == p
            evidence[name] = {
                "geometry_sha256": geometry,
                "source_pixel_sha256": pixels,
                "actual_counts": counts,
                "path_allowance": compiled.path_allowance,
                "operation_allowance": compiled.operation_allowance,
                "nodes": len(compiled.scene.nodes),
                "instances": len(compiled.painter_ids),
                "out_of_order_deterministic": True,
            }
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    save(OUT / "determinism.json", {"scenes": evidence, "memory": monitor.report()})
    a = json.loads((proofs / "settlement_checkpoint_video/render_report.json").read_text())
    b = json.loads((proofs / "settlement_repeat/render_report.json").read_text())
    assert (
        a["source_pixel_sha256"] == b["source_pixel_sha256"]
        and a["verification"]["decoded_rgb_sha256"] == b["verification"]["decoded_rgb_sha256"]
    )
    save(
        OUT / "video_repeat.json",
        {
            "all_90_source_frames_equal": True,
            "all_90_decoded_frames_equal": True,
            "first_render_success": a["success"],
            "repeat_render_success": b["success"],
            "scope": "Same native build; byte-identical cross-build AAC/MP4 is not claimed",
        },
    )
    hashes = json.loads((OUT / "compiler_before_heldout.json").read_text())["sha256"]
    assert all(
        hashlib.file_digest((ROOT / p).open("rb"), "sha256").hexdigest() == digest
        for p, digest in hashes.items()
    )
    save(
        OUT / "heldout_evidence.json",
        {
            "description": "examples/geometry/heldout_description.txt",
            "public_request": "examples/geometry/heldout_wash_station.json",
            "compiler_and_tool_hashes_unchanged_after_authoring": True,
            "compiler_sha256": hashes,
            "claim": (
                "Authoring exercise, not a blinded benchmark or automatic language understanding"
            ),
        },
    )


if __name__ == "__main__":
    main()
