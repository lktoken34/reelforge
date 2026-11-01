"""Reproducible layer/contact sheets and sequential repeat proof on development hardware."""

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path

from render_environment import render

from reelforge.characters.study import character_frame, label
from reelforge.environments.presets import EnvironmentPreset
from reelforge.environments.scene import environment_frame, layers_at, transform_command
from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.diagnostic import color
from reelforge.rendering.model import DrawPath, PathOp, Transform, rectangle
from reelforge.resources.monitor import preflight_memory


def clipped(command: DrawPath) -> DrawPath:
    # Art extends beyond the shot for camera overscan; sheets need per-cell clipping.
    if command.clip is not None:
        return command
    t = command.transform
    points = []
    for x, y in ((0, 0), (360, 0), (360, 640), (0, 640)):
        dx, dy = x - t.tx, y - t.ty
        points.append(
            (
                (dx * math.cos(t.rotation) + dy * math.sin(t.rotation)) / t.sx,
                (-dx * math.sin(t.rotation) + dy * math.cos(t.rotation)) / t.sy,
            )
        )
    clip = tuple(PathOp("M" if i == 0 else "L", p) for i, p in enumerate(points))
    return replace(command, clip=clip + (PathOp("Z"),))


def sheets(directory: Path) -> None:
    preflight_memory()
    renderer = CairoRenderer()
    commands = []
    names = (
        "SKY",
        "HILLS",
        "GROUND",
        "ORCHARD",
        "BARN",
        "FENCE PROPS",
        "DOOR LIGHT",
        "ROWAN",
        "FOREGROUND",
        "EDGE GRADE",
    )
    for i, layer in enumerate(layers_at(EnvironmentPreset(), 90)):
        x, y = (i % 5) * 360, (i // 5) * 700
        commands.append(DrawPath(rectangle(x, y, 360, 640), color("b5b8a6")))
        commands.extend(
            transform_command(clipped(c), Transform(x, y))
            for c in environment_frame(90, only_layer=layer.id)
        )
        commands.extend(label(names[i], x + 15, y + 660, 2, color("e8d2a9")))
    with renderer.surface(1800, 1400) as surface:
        renderer.draw(
            surface, tuple(commands), background=color("233c40"), logical_size=(1800, 1400)
        )
        surface.write_png(directory / "depth_breakdown.png")
    comparison = [clipped(c) for c in character_frame(90)]
    comparison.extend(
        transform_command(clipped(c), Transform(360, 0)) for c in environment_frame(90)
    )
    with renderer.surface(1440, 1280) as surface:
        renderer.draw(
            surface, tuple(comparison), background=color("173235"), logical_size=(720, 640)
        )
        surface.write_png(directory / "flat_vs_environment.png")
    # Sequential decoded checkpoint contact sheet; no stored native frames.
    commands = []
    for i, frame in enumerate((0, 90, 179)):
        commands.extend(
            transform_command(clipped(c), Transform(i * 360, 0)) for c in environment_frame(frame)
        )
    with renderer.surface(1080, 640) as surface:
        renderer.draw(
            surface, tuple(commands), background=color("243e49"), logical_size=(1080, 640)
        )
        surface.write_png(directory / "camera_contact_sheet.png")
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeat-dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sheets(args.output_dir)
    if args.repeat_dir:
        first = json.loads((args.output_dir / "report.json").read_text())
        second = render(args.repeat_dir)
        decoded = (
            first["verification"]["decoded_rgb_sha256"]
            == second["verification"]["decoded_rgb_sha256"]
        )
        source = first["source_checkpoint_sha256"] == second["source_checkpoint_sha256"]
        report = {
            "decoded_all_180_frames_equal": decoded,
            "source_checkpoints_equal": source,
            "repeat_render_encode_seconds": second["render_encode_seconds"],
            "repeat_whole_job_memory": second["whole_job_memory"],
            "scope": "Exact same-host source and decoded pixels, not cross-platform identity",
        }
        (args.output_dir / "repeat_consistency.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        if not decoded or not source:
            raise RuntimeError("Repeat output differs; review source/codec determinism")
    print(json.dumps({"sheets": True, "repeat": bool(args.repeat_dir)}))


if __name__ == "__main__":
    main()
