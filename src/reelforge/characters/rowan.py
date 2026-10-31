"""Rowan Vale: original code-authored orchard keeper. Fixed, bounded vector artwork."""

from dataclasses import dataclass, replace

from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import (
    DrawPath,
    LinearGradient,
    PathOp,
    RenderError,
    Stroke,
    Transform,
    finite,
)

from .presets import EXPRESSIONS, SKELETON
from .rig import Pose, Skeleton

INK = color("302d29")
RUST, RUST_LIGHT, RUST_DARK = color("a6583c"), color("c77b51"), color("663c32")
DENIM, DENIM_LIGHT = color("354d54"), color("607477")
LEATHER, LEATHER_LIGHT = color("59402e"), color("97704a")
OCHRE, CREAM = color("c69b4c"), color("efd9b2")


def path(*ops) -> tuple[PathOp, ...]:
    return tuple(PathOp(op[0], tuple(op[1:])) for op in ops)


def shape(outline, fill, *, width=1.0):
    return DrawPath(outline, fill, Stroke(INK, width))


def line(outline, paint=INK, width=0.7):
    return DrawPath(outline, stroke=Stroke(paint, width))


def grad(a, b, start=(-20, -50), end=(20, 0)):
    return LinearGradient(start, end, ((0, a), (1, b)))


@dataclass(frozen=True)
class Part:
    joint: str
    order: int
    commands: tuple[DrawPath, ...]


# Local geometry pivots align with skeleton attachments. Sleeves/cuffs overlap by 2..5 units.
TORSO = (
    shape(
        path(
            ("M", -15, -53),
            ("C", -23, -49, -22, -30, -20, -15),
            ("L", -17, 4),
            ("C", -9, 9, 7, 10, 16, 4),
            ("L", 18, -29),
            ("C", 19, -45, 11, -55, 3, -56),
            ("Z",),
        ),
        grad(RUST_LIGHT, RUST_DARK),
    ),
    DrawPath(
        path(
            ("M", 1, -53),
            ("L", 4, 5),
            ("C", 9, 7, 13, 6, 16, 4),
            ("L", 18, -28),
            ("C", 17, -43, 10, -51, 1, -53),
            ("Z",),
        ),
        RUST,
    ),
    shape(
        path(("M", -12, -53), ("L", -3, -58), ("L", 4, -46), ("L", -3, -36), ("Z",)),
        color("e1bb7a"),
        width=0.75,
    ),
    shape(
        path(("M", 3, -56), ("L", 11, -52), ("L", 13, -40), ("L", 4, -46), ("Z",)),
        RUST_DARK,
        width=0.75,
    ),
    line(path(("M", 2, -42), ("L", 4, 3)), color("492f29"), 1),
    line(path(("M", -16, 1), ("C", -5, 5, 6, 6, 14, 1)), color("d39367"), 0.65),
    shape(
        path(
            ("M", -15, -24),
            ("L", -6, -23),
            ("L", -6, -12),
            ("C", -9, -9, -12, -10, -15, -12),
            ("Z",),
        ),
        RUST_DARK,
        width=0.6,
    ),
    line(path(("M", -14, -21), ("L", -7, -20)), color("d6a17b"), 0.5),
    shape(
        path(("M", -10, -53), ("L", -6, -55), ("L", 17, -4), ("L", 13, -2), ("Z",)),
        LEATHER,
        width=0.65,
    ),
    shape(
        path(("M", 2, -30), ("L", 7, -32), ("L", 10, -25), ("L", 5, -23), ("Z",)), OCHRE, width=0.65
    ),
    DrawPath(ellipse(7, -15, 1, 1), OCHRE),
    DrawPath(ellipse(7, -5, 1, 1), OCHRE),
)
BAG = (
    shape(
        path(
            ("M", -17, -37),
            ("C", -28, -39, -31, -34, -30, -22),
            ("L", -29, 1),
            ("C", -23, 6, -15, 6, -11, 1),
            ("L", -12, -24),
            ("Z",),
        ),
        grad(LEATHER_LIGHT, LEATHER),
    ),
    shape(
        path(
            ("M", -30, -31),
            ("C", -25, -34, -17, -33, -12, -28),
            ("L", -13, -18),
            ("C", -19, -14, -25, -15, -30, -18),
            ("Z",),
        ),
        color("86603e"),
        width=0.7,
    ),
    shape(
        path(("M", -23, -21), ("L", -19, -21), ("L", -19, -14), ("L", -23, -14), ("Z",)),
        OCHRE,
        width=0.6,
    ),
    line(path(("M", -27, -9), ("L", -27, 0), ("L", -17, 2)), color("b78c60"), 0.65),
)
NECK = (
    shape(path(("M", -7, -16), ("L", 8, -16), ("L", 8, 8), ("L", -6, 7), ("Z",)), color("c89973")),
    shape(
        path(
            ("M", -11, 3),
            ("C", -6, -1, 4, -1, 10, 1),
            ("L", 13, 8),
            ("C", 3, 13, -8, 10, -12, 7),
            ("Z",),
        ),
        OCHRE,
        width=0.8,
    ),
    line(path(("M", -7, 5), ("C", -2, 8, 4, 8, 9, 5)), color("f4d392"), 0.65),
)
SCARF = (
    shape(
        path(
            ("M", 0, 0),
            ("C", -9, 1, -16, 8, -28, 7),
            ("L", -24, 15),
            ("C", -14, 16, -3, 10, 5, 5),
            ("Z",),
        ),
        OCHRE,
        width=0.8,
    ),
    line(path(("M", -22, 11), ("C", -14, 12, -7, 5, -2, 4)), color("f0c873"), 0.65),
)
HEAD = (
    shape(
        path(
            ("M", -27, -39),
            ("C", -29, -57, -18, -68, -3, -68),
            ("C", 15, -68, 28, -57, 30, -40),
            ("C", 34, -23, 27, -8, 13, -3),
            ("C", -1, 3, -21, -2, -26, -18),
            ("Z",),
        ),
        grad(color("f4dfb9"), color("c89975"), (-18, -55), (33, -12)),
        width=1.1,
    ),
    DrawPath(
        path(
            ("M", -26, -41),
            ("C", -24, -18, -15, -5, 1, -2),
            ("C", -14, 1, -24, -7, -26, -18),
            ("Z",),
        ),
        color("b68160", 0.24),
    ),
    shape(
        path(
            ("M", -27, -38),
            ("C", -37, -42, -37, -27, -28, -25),
            ("C", -24, -26, -24, -34, -27, -38),
            ("Z",),
        ),
        color("d8ad84"),
        width=0.75,
    ),
    line(path(("M", -31, -34), ("C", -27, -34, -31, -29, -28, -29)), color("956b54"), 0.65),
    DrawPath(
        path(
            ("M", -26, -40),
            ("L", -23, -52),
            ("C", -13, -51, -12, -58, -6, -59),
            ("C", 1, -54, 7, -57, 11, -62),
            ("C", -4, -75, -27, -63, -27, -45),
            ("Z",),
        ),
        color("453a31"),
    ),
    line(path(("M", 19, -32), ("C", 19, -28, 23, -27, 20, -25)), color("976d56"), 0.75),
    DrawPath(ellipse(21, -22, 4, 2), color("b5735e", 0.18)),
    DrawPath(ellipse(13, -23, 0.65, 0.65), color("aa7a5d")),
    DrawPath(ellipse(16, -24, 0.6, 0.6), color("aa7a5d")),
    DrawPath(ellipse(10, -24, 0.6, 0.6), color("aa7a5d")),
)
HAT = (
    shape(
        path(
            ("M", -29, -59),
            ("L", -25, -78),
            ("C", -22, -86, -15, -86, -8, -82),
            ("C", 0, -85, 12, -86, 18, -79),
            ("L", 25, -60),
            ("Z",),
        ),
        grad(color("b69861"), color("756143"), (-22, -82), (25, -58)),
        width=1.1,
    ),
    DrawPath(
        path(
            ("M", -24, -76),
            ("C", -9, -81, 0, -75, 15, -80),
            ("L", 18, -74),
            ("C", 3, -70, -12, -76, -24, -70),
            ("Z",),
        ),
        color("d4b87e", 0.35),
    ),
    shape(
        path(
            ("M", -28, -65),
            ("C", -13, -61, 8, -62, 23, -66),
            ("L", 25, -59),
            ("C", 6, -54, -13, -56, -29, -59),
            ("Z",),
        ),
        LEATHER,
        width=0.75,
    ),
    shape(
        path(
            ("M", -40, -62),
            ("C", -30, -57, -21, -60, -8, -58),
            ("C", 10, -59, 27, -65, 39, -59),
            ("C", 48, -55, 40, -49, 27, -51),
            ("C", 6, -52, -22, -49, -39, -55),
            ("C", -46, -58, -46, -64, -40, -62),
            ("Z",),
        ),
        grad(color("bfa36c"), color("846943"), (-31, -64), (24, -49)),
        width=1.05,
    ),
    line(path(("M", -38, -57), ("C", -15, -51, 14, -59, 36, -55)), color("e0c992"), 0.65),
    shape(
        path(("M", 15, -64), ("L", 21, -64), ("L", 21, -58), ("L", 15, -58), ("Z",)),
        color("568078"),
        width=0.65,
    ),
    DrawPath(ellipse(18, -61, 0.8, 0.8), CREAM),
)


def arm(far=False):
    main = color("724733") if far else RUST
    return (
        shape(
            path(
                ("M", -6, -3),
                ("C", -9, 0, -8, 11, -6, 20),
                ("L", -5, 33),
                ("C", -1, 36, 4, 35, 6, 31),
                ("L", 6, 10),
                ("C", 7, 0, 4, -5, -1, -5),
                ("Z",),
            ),
            main,
        ),
        line(
            path(("M", -5, 2), ("C", -4, 12, -4, 19, -3, 28)),
            color("c1835c") if not far else color("946443"),
            0.75,
        ),
        shape(
            path(("M", -6, 24), ("L", 1, 22), ("L", 5, 29), ("L", -2, 32), ("Z",)),
            color("8a8060") if not far else color("5f624f"),
            width=0.55,
        ),
        line(path(("M", -3, 25), ("L", 0, 28)), color("d0b487"), 0.5),
    )


def forearm(far=False):
    return (
        shape(
            path(
                ("M", -5, -3),
                ("C", -7, 2, -5, 16, -4, 26),
                ("L", -4, 30),
                ("L", 5, 30),
                ("C", 6, 18, 7, 5, 5, -2),
                ("C", 3, -5, -2, -5, -5, -3),
                ("Z",),
            ),
            color("754731") if far else RUST,
        ),
        line(path(("M", -3, 2), ("L", -2, 24)), color("a46644") if far else color("ca8b5e"), 0.65),
        shape(
            path(("M", -5, 25), ("L", 6, 25), ("L", 6, 31), ("L", -4, 31), ("Z",)),
            LEATHER_LIGHT,
            width=0.75,
        ),
    )


def hand(far=False):
    return (
        shape(
            path(
                ("M", -4, -1),
                ("C", -6, 4, -4, 11, 0, 12),
                ("C", 5, 14, 8, 9, 6, 5),
                ("C", 12, 8, 12, 1, 7, 0),
                ("L", 4, -2),
                ("Z",),
            ),
            color("8d6e43") if far else color("bc945c"),
            width=0.8,
        ),
        line(path(("M", 0, 4), ("L", 3, 10)), color("705635"), 0.55),
    )


def thigh(far=False):
    return (
        shape(
            path(
                ("M", -7, -4),
                ("C", -9, 8, -6, 28, -5, 43),
                ("C", -2, 47, 3, 47, 6, 43),
                ("L", 7, 11),
                ("L", 8, -3),
                ("Z",),
            ),
            color("293c42") if far else grad(DENIM_LIGHT, DENIM, (-6, 0), (6, 42)),
            width=0.95,
        ),
        line(path(("M", -5, 4), ("L", -3, 38)), color("5d7172") if far else color("8b9990"), 0.6),
    )


def shin(far=False):
    commands = [
        shape(
            path(
                ("M", -5, -3),
                ("C", -7, 3, -4, 25, -4, 44),
                ("L", 5, 45),
                ("C", 7, 29, 6, 9, 5, -2),
                ("C", 3, -5, -2, -5, -5, -3),
                ("Z",),
            ),
            color("2e4146") if far else grad(DENIM_LIGHT, DENIM, (-5, 2), (6, 43)),
            width=0.9,
        ),
        line(path(("M", -3, 7), ("L", -2, 39)), color("647d7d"), 0.6),
    ]
    if not far:
        commands += [
            shape(
                path(("M", -4, 3), ("L", 4, 4), ("L", 4, 14), ("L", -3, 15), ("Z",)),
                color("7c897c"),
                width=0.6,
            ),
            line(path(("M", -2, 5), ("L", 2, 6), ("L", 2, 12)), color("d0bc8a"), 0.5),
        ]
    return tuple(commands)


def foot(far=False):
    return (
        shape(
            path(
                ("M", -6, -9),
                ("L", 5, -9),
                ("L", 7, -1),
                ("C", 13, 0, 20, 2, 20, 6),
                ("L", 19, 9),
                ("L", -8, 9),
                ("L", -9, 5),
                ("L", -7, 0),
                ("Z",),
            ),
            color("48382b") if far else grad(LEATHER_LIGHT, LEATHER, (-4, -9), (15, 8)),
            width=1,
        ),
        shape(
            path(("M", -8, 5), ("C", 2, 7, 10, 5, 20, 6), ("L", 19, 10), ("L", -8, 10), ("Z",)),
            color("302e29"),
            width=0.6,
        ),
        line(path(("M", -3, -5), ("L", 3, -4), ("M", -3, -2), ("L", 4, -1)), color("cfb184"), 0.65),
        line(path(("M", 8, 2), ("C", 12, 2, 16, 4, 17, 5)), color("bd9565"), 0.6),
    )


PARTS = tuple(
    [
        Part("far_thigh", 10, thigh(True)),
        Part("far_shin", 11, shin(True)),
        Part("far_foot", 12, foot(True)),
        Part("near_thigh", 20, thigh()),
        Part("near_shin", 21, shin()),
        Part("near_foot", 22, foot()),
        Part("far_arm", 30, arm(True)),
        Part("far_forearm", 31, forearm(True)),
        Part("far_hand", 32, hand(True)),
        Part("torso", 35, BAG),
        Part("neck", 40, NECK),
        Part("scarf", 41, SCARF),
        Part("torso", 50, TORSO),
        Part("near_arm", 60, arm()),
        Part("near_forearm", 61, forearm()),
        Part("near_hand", 62, hand()),
        Part("head", 70, HEAD),
        Part("head", 80, HAT),
    ]
)


def face(expression: str, blink: bool):
    if expression not in EXPRESSIONS or type(blink) is not bool:
        raise RenderError("Unknown expression or nonboolean blink")
    eyes = (
        [
            line(path(("M", -2, -34), ("L", 2, -34)), width=1.2),
            line(path(("M", 11, -34), ("L", 16, -34)), width=1.2),
        ]
        if blink
        else [DrawPath(ellipse(0, -34, 1.65, 2.15), INK), DrawPath(ellipse(14, -34, 1.9, 2.4), INK)]
    )
    lift = 2 if expression == "concerned" else -1 if expression == "focused" else 0
    return tuple(eyes) + (
        line(path(("M", -4, -41 + lift), ("L", 3, -41 - lift * 0.4)), width=1),
        line(path(("M", 10, -41 - lift * 0.4), ("L", 17, -41 + lift)), width=1),
        line(
            path(
                ("M", 3, -16), ("C", 6, -18 if expression == "concerned" else -14, 9, -17, 11, -16)
            ),
            color("785445"),
            0.85,
        ),
    )


def draw_character(
    pose: Pose,
    *,
    position=(180, 540),
    scale=1.0,
    direction="right",
    expression="concerned",
    blink=False,
    skeleton: Skeleton = SKELETON,
    artwork: tuple[Part, ...] = PARTS,
) -> tuple[DrawPath, ...]:
    finite(*position, scale)
    if not 0.1 <= scale <= 4 or direction not in ("left", "right"):
        raise RenderError("Character scale .1..4; direction left/right")
    worlds = skeleton.evaluate(pose)
    sign = 1 if direction == "right" else -1
    parts = (*artwork, Part("head", 75, face(expression, blink)))
    commands = []
    for part in sorted(parts, key=lambda p: p.order):
        if part.joint not in worlds:
            raise RenderError("Artwork refers to an unknown joint")
        w = worlds[part.joint]
        for command in part.commands:
            if command.transform != Transform():
                raise RenderError("Artwork is local geometry; joint transform owns placement")
            commands.append(
                replace(
                    command,
                    transform=Transform(
                        position[0] + sign * scale * w.x,
                        position[1] + scale * w.y,
                        sign * w.angle,
                        sign * scale,
                        scale,
                    ),
                )
            )
    return tuple(commands)


def preset_commands(data: dict, frame_index: int) -> tuple[DrawPath, ...]:
    """Experimental data-to-trusted-geometry entry point; root travel is in world space.

    A future trusted compositor handles camera/framing. No supplied geometry/code is accepted.
    """
    from .presets import CharacterPreset, sample_pose

    if type(frame_index) is not int or not 0 <= frame_index < 18000:
        raise RenderError("Preset frame must be an integer in 0..17999 at fixed 30 FPS")
    preset = CharacterPreset.from_data(data)
    return draw_character(
        sample_pose(preset, frame_index / 30),
        direction=preset.direction,
        expression=preset.expression,
    )
