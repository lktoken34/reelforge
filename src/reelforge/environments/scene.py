"""Pure depth composition and bounded shot sampling; preserves DrawPath/Cairo API."""

from dataclasses import dataclass, replace

from reelforge.characters.presets import CharacterPreset, sample_pose, smooth
from reelforge.characters.rowan import draw_character
from reelforge.characters.secondary import preset_secondary
from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import DrawPath, RenderError, Transform, finite

from . import artwork as art
from .presets import EnvironmentPreset

FRAMES = 180
DEFAULT_PRESET = EnvironmentPreset()


@dataclass(frozen=True)
class Layer:
    id: str
    depth: float
    commands: tuple[DrawPath, ...]


@dataclass(frozen=True)
class Camera:
    x: float
    y: float
    zoom: float

    def transform(self, depth: float) -> Transform:
        finite(depth)
        if not 0 <= depth <= 1.5:
            raise RenderError("Depth must be in [0, 1.5]")
        z = 1 + (self.zoom - 1) * depth
        return Transform(180 * (1 - z) - self.x * depth, 400 * (1 - z) - self.y * depth, sx=z, sy=z)


def camera_at(preset: EnvironmentPreset, frame: int) -> Camera:
    if type(frame) is not int or not 0 <= frame < FRAMES:
        raise RenderError("Environment proof requires frame 0..179 at 30 FPS")
    u = smooth(frame / (FRAMES - 1))
    if preset.shot == "locked":
        return Camera(preset.framing * 8, 0, 1)
    if preset.shot == "orchard_pan":
        return Camera(-10 + 20 * u + preset.framing * 8, 0, 1.025)
    return Camera(-4 + 10 * u + preset.framing * 8, -2 * u, 1 + 0.085 * u)


def transform_command(command: DrawPath, parent: Transform) -> DrawPath:
    """Uniform parent scale composes with local rotated/nonuniform character parts."""
    if parent.rotation or parent.sx != parent.sy or parent.sx <= 0:
        raise RenderError("Scene parent must have positive uniform scale and no rotation")
    t = command.transform
    return replace(
        command,
        transform=Transform(
            parent.tx + t.tx * parent.sx,
            parent.ty + t.ty * parent.sy,
            t.rotation,
            parent.sx * t.sx,
            parent.sy * t.sy,
        ),
    )


def layers_at(preset: EnvironmentPreset, frame: int) -> tuple[Layer, ...]:
    camera_at(preset, frame)  # validate before generating geometry
    t = frame / 30
    orchard = []
    for x, y, s in (
        (-15, 405, 0.72),
        (43, 414, 0.8),
        (98, 410, 0.64),
        (360, 422, 0.96),
        (407, 405, 0.72),
    ):
        orchard.extend(art.placed(art.tree(int(x)), x, y, s))
    # Small midground props make scale and use legible: water trough, barrel, split rails.
    props = list(art.placed(art.fence(), -37, 432, 0.66))
    props.extend(art.placed(art.fence(), 288, 444, 0.8))
    props.extend(
        [
            art.polygon(((276, 435), (307, 433), (305, 449), (278, 451)), color("525c4b")),
            art.line(((276, 435), (307, 433)), color("b1aa80"), 2),
            DrawPath(ellipse(290, 435, 13, 2), color("293e3d")),
            art.polygon(((283, 450), (281, 457), (284, 457), (286, 450)), color("263c34")),
        ]
    )
    character = CharacterPreset(action="look_around", expression="concerned")
    pose = sample_pose(character, t)
    rowan = [
        DrawPath(ellipse(165, 499, 19, 3), color("122c2d", 0.13)),
        DrawPath(ellipse(165, 499, 12, 1.6), color("10272a", 0.22)),
    ]
    rowan.extend(
        draw_character(
            pose,
            position=(165, 498),
            scale=0.69,
            expression=character.expression,
            secondary=preset_secondary(character, t),
        )
    )
    light = [
        art.polygon(
            ((206, 406), (223, 408), (171, 493), (123, 473)),
            color("efc584", 0.035 + preset.warmth * 0.035),
        )
    ]
    return (
        Layer("sky", 0, art.sky(preset.warmth)),
        Layer("hills", 0.18, art.hills(preset.atmosphere)),
        Layer("ground", 1, art.ground()),
        Layer("orchard", 0.72, tuple(orchard)),
        Layer("barn", 0.85, art.placed(art.barn(), 257, 405, 0.91)),
        Layer("fence_props", 1, tuple(props)),
        Layer("door_light", 1, tuple(light)),
        Layer("rowan", 1, tuple(rowan)),
        Layer("foreground", 1.4, art.foreground(preset.breeze, t)),
        Layer(
            "edge_grade",
            0,
            (
                DrawPath(
                    art.path(("M", 0, 0), ("L", 360, 0), ("L", 360, 640), ("L", 0, 640), ("Z",)),
                    art.gradient(color("071c27", 0.25), color("071c27", 0), 0, 230),
                ),
                DrawPath(
                    art.path(("M", 0, 0), ("L", 360, 0), ("L", 360, 640), ("L", 0, 640), ("Z",)),
                    art.gradient(color("0d292b", 0), color("0d292b", 0.45), 480, 640),
                ),
            ),
        ),
    )


def environment_frame(
    frame: int, preset: EnvironmentPreset = DEFAULT_PRESET, *, only_layer: str | None = None
) -> tuple[DrawPath, ...]:
    camera = camera_at(preset, frame)
    layers = layers_at(preset, frame)
    if only_layer is not None and only_layer not in {layer.id for layer in layers}:
        raise RenderError("Unknown layer; choose " + ", ".join(layer.id for layer in layers))
    return tuple(
        transform_command(c, camera.transform(layer.depth))
        for layer in layers
        if only_layer is None or layer.id == only_layer
        for c in layer.commands
    )
