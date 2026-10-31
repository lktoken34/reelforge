"""A fixed geometry fixture, authored in trusted Python; not a character or environment."""

import math

from .model import Color, DrawPath, LinearGradient, PathOp, Stroke, Transform, rectangle

LOGICAL_SIZE = (360.0, 640.0)
BACKGROUND = Color(0.035, 0.055, 0.10)


def color(hex_rgb: str, alpha: float = 1) -> Color:
    return Color(*(int(hex_rgb[i : i + 2], 16) / 255 for i in (0, 2, 4)), alpha)


def rounded(x: float, y: float, width: float, height: float, radius: float):
    k = radius * 0.5522847498307936
    r = radius
    return (
        PathOp("M", (x + r, y)),
        PathOp("L", (x + width - r, y)),
        PathOp("C", (x + width - r + k, y, x + width, y + r - k, x + width, y + r)),
        PathOp("L", (x + width, y + height - r)),
        PathOp(
            "C",
            (
                x + width,
                y + height - r + k,
                x + width - r + k,
                y + height,
                x + width - r,
                y + height,
            ),
        ),
        PathOp("L", (x + r, y + height)),
        PathOp("C", (x + r - k, y + height, x, y + height - r + k, x, y + height - r)),
        PathOp("L", (x, y + r)),
        PathOp("C", (x, y + r - k, x + r - k, y, x + r, y)),
        PathOp("Z"),
    )


def ellipse(cx: float, cy: float, rx: float, ry: float):
    k = 0.5522847498307936
    return (
        PathOp("M", (cx + rx, cy)),
        PathOp("C", (cx + rx, cy + ry * k, cx + rx * k, cy + ry, cx, cy + ry)),
        PathOp("C", (cx - rx * k, cy + ry, cx - rx, cy + ry * k, cx - rx, cy)),
        PathOp("C", (cx - rx, cy - ry * k, cx - rx * k, cy - ry, cx, cy - ry)),
        PathOp("C", (cx + rx * k, cy - ry, cx + rx, cy - ry * k, cx + rx, cy)),
        PathOp("Z"),
    )


def diagnostic_commands() -> tuple[DrawPath, ...]:
    """Painter's order is explicit; no seed, assets, fonts, caches or time dependence."""
    cyan, orange, white = color("64e5e5"), color("ffb267"), color("e5f4f4")
    commands = []
    for y, height in ((24, 194), (238, 170), (428, 188)):
        commands.append(
            DrawPath(
                rounded(18, y, 324, height, 16),
                LinearGradient(
                    (18, y), (342, y + height), ((0, color("162b43")), (1, color("0d182b")))
                ),
                Stroke(color("304b65"), 1),
            )
        )
    # Panel 1: native-resolution crisp grid, smooth cubic ribbon, translucent overlaps.
    clip = rounded(28, 34, 304, 174, 10)
    for x in range(36, 340, 16):
        commands.append(
            DrawPath(
                (PathOp("M", (x, 30)), PathOp("L", (x, 218))),
                stroke=Stroke(color("567c91", 0.15), 0.5),
                clip=clip,
            )
        )
    for y in range(46, 216, 16):
        commands.append(
            DrawPath(
                (PathOp("M", (24, y)), PathOp("L", (336, y))),
                stroke=Stroke(color("567c91", 0.15), 0.5),
                clip=clip,
            )
        )
    commands.append(DrawPath(ellipse(259, 91, 38, 38), orange))
    commands.append(
        DrawPath(
            ellipse(232, 116, 46, 46), color("64e5e5", 0.48), Stroke(color("a5f8ed", 0.85), 1.5)
        )
    )
    ribbon = (
        PathOp("M", (38, 165)),
        PathOp("C", (92, 35, 168, 227, 222, 151)),
        PathOp("C", (244, 121, 268, 129, 319, 147)),
    )
    commands.append(DrawPath(ribbon, stroke=Stroke(color("071323"), 19)))
    commands.append(DrawPath(ribbon, stroke=Stroke(cyan, 10)))
    commands.append(DrawPath(ribbon, stroke=Stroke(color("c8ffff", 0.8), 1.5)))
    commands.append(
        DrawPath(
            (PathOp("M", (42, 74)), PathOp("L", (65, 52)), PathOp("L", (88, 74))),
            stroke=Stroke(white, 2, "miter", "butt"),
        )
    )
    # Panel 2: sharp clipped stripes and overlapping transformed cards.
    window = rounded(32, 252, 296, 142, 10)
    commands.append(DrawPath(window, color("e8ede1")))
    for x in range(-40, 400, 20):
        commands.append(
            DrawPath(
                (
                    PathOp("M", (x, 240)),
                    PathOp("L", (x + 8, 240)),
                    PathOp("L", (x + 74, 410)),
                    PathOp("L", (x + 66, 410)),
                    PathOp("Z"),
                ),
                color("113e50", 0.17),
                clip=window,
            )
        )
    # A second local clip demonstrates independent save/restore state.
    commands.append(
        DrawPath(
            rectangle(-250, -100, 500, 200),
            color("168c9b", 0.75),
            transform=Transform(180, 323),
            clip=ellipse(0, 0, 112, 54),
        )
    )
    card = rounded(-47, -38, 94, 76, 10)
    commands.append(
        DrawPath(card, color("0b2034", 0.55), transform=Transform(173, 329, -0.28, 1.18, 0.9))
    )
    commands.append(
        DrawPath(
            card,
            orange,
            Stroke(color("fff3d1"), 2),
            transform=Transform(182, 319, math.pi / 9, 0.92, 1.02),
        )
    )
    commands.append(
        DrawPath(
            ellipse(0, 0, 18, 18), color("132c43", 0.85), transform=Transform(182, 319, 0, 1.2, 0.7)
        )
    )
    # Panel 3: miter/round/bevel joins, hard diagonals and per-path alpha over a checker.
    for i, join in enumerate(("miter", "round", "bevel")):
        x = 60 + i * 111
        path = (PathOp("M", (x - 21, 478)), PathOp("L", (x, 448)), PathOp("L", (x + 21, 478)))
        commands.append(DrawPath(path, stroke=Stroke(cyan, 10, join, "butt")))
    for row in range(4):
        for col in range(12):
            commands.append(
                DrawPath(
                    rectangle(36 + col * 24, 506 + row * 20, 24, 20),
                    color("d1dbd9" if (row + col) % 2 else "708591"),
                )
            )
    for i, alpha in enumerate((0.25, 0.5, 0.75)):
        commands.append(
            DrawPath(
                ellipse(87 + i * 93, 546, 34, 30),
                color("ef7446", alpha),
                Stroke(color("fff6db", 0.8), 1),
            )
        )
    commands.append(
        DrawPath(
            (
                PathOp("M", (36, 600)),
                PathOp("L", (140, 600)),
                PathOp("L", (140, 592)),
                PathOp("L", (324, 592)),
            ),
            stroke=Stroke(white, 1, "miter", "butt"),
        )
    )
    return tuple(commands)
