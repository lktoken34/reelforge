"""Bounded orchard art direction. Pure vector recipes; no native objects or caches."""

import math
from dataclasses import replace

from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import (
    Color,
    DrawPath,
    LinearGradient,
    Paint,
    Transform,
    VectorPath,
    rectangle,
)

from .artwork import gradient, line, path, polygon


def variation(seed: int, index: int) -> float:
    """Stateless integer mixer: independent stable samples in [0, 1)."""
    n = ((seed & 0xFFFFFFFF) ^ ((index + 1) * 0x9E3779B9)) & 0xFFFFFFFF
    n = ((n ^ (n >> 16)) * 0x7FEB352D) & 0xFFFFFFFF
    n = ((n ^ (n >> 15)) * 0x846CA68B) & 0xFFFFFFFF
    return (n ^ (n >> 16)) / 4294967296


def crown(x: float, y: float, rx: float, ry: float, seed: int) -> VectorPath:
    """One torn-edged, asymmetrical closed silhouette, not overlapping circles."""
    points = []
    for i in range(22):
        a = i * math.tau / 22
        r = 0.76 + variation(seed, i) * 0.31
        points.append((x + math.cos(a) * rx * r, y + math.sin(a) * ry * r))
    ops = [("M", *points[0])]
    for i in range(len(points)):
        prev, a, b, after = (points[(i + k) % len(points)] for k in (-1, 0, 1, 2))
        ops.append(
            (
                "C",
                a[0] + (b[0] - prev[0]) * 0.17,
                a[1] + (b[1] - prev[1]) * 0.17,
                b[0] - (after[0] - a[0]) * 0.17,
                b[1] - (after[1] - a[1]) * 0.17,
                *b,
            )
        )
    return path(*ops, ("Z",))


def _tree_recipe(seed: int) -> tuple[DrawPath, ...]:
    def v(i: int) -> float:
        return variation(seed, i)

    lean = (v(0) - 0.5) * 20
    height = 78 + 23 * v(1)
    width = 32 + 13 * v(2)
    c = [
        polygon(
            (
                (-6, 1),
                (-3, -37),
                (lean - 9, -61),
                (lean - 24, -73),
                (lean - 20, -77),
                (lean - 3, -65),
                (lean + 5, -height),
                (lean + 9, -height + 2),
                (lean + 5, -55),
                (lean + 24, -70),
                (lean + 26, -65),
                (8, -43),
                (6, 0),
            ),
            color("303f35"),
        ),
        line(((-3, -2), (0, -39), (lean - 5, -60)), color("ac9870", 0.52), 1.1),
    ]
    # Broad shadow silhouette and seven independently shaped, overlapping bough masses.
    c.append(DrawPath(crown(lean, -height, width + 4, 29, seed), color("263f37")))
    for i in range(7):
        a = i * 2.399 + v(3) * math.tau
        x = lean + math.cos(a) * width * (0.18 + 0.46 * v(i + 8))
        y = -height + math.sin(a) * (10 + 9 * v(i + 20))
        sway = 0
        shape = crown(x + sway, y, 18 + 8 * v(i + 30), 13 + 7 * v(i + 40), seed + i * 31)
        c.append(DrawPath(shape, gradient(color("7d8756"), color("354b3b"), y - 19, y + 18)))
        # Fragmented upper-left rim follows the key-light direction, within the bough.
        rim = crown(x - 6 + sway, y - 9, 11, 4 + 3 * v(i + 60), seed + i)
        c.append(DrawPath(rim, color("d2ba79", 0.12), clip=shape))
        for j in range(4):
            xx, yy = x - 14 + 28 * v(80 + i * 4 + j), y - 9 + 18 * v(120 + i * 4 + j)
            c.append(
                polygon(
                    ((xx, yy), (xx + 3, yy - 2), (xx + 5, yy), (xx + 2, yy + 2)),
                    color(("a3a66b", "243d36", "6e8051")[j % 3], 0.3),
                )
            )
    for i in range(6):
        x, y = lean - 27 + 54 * v(180 + i), -height - 12 + 29 * v(200 + i)
        c.append(DrawPath(ellipse(x, y, 1.2, 1.5), color("b58b50", 0.75)))
    # Sparse dead twigs break the canopy boundary and imply an untended orchard.
    for i in range(3):
        x = lean - width + i * width
        c.append(
            line(
                ((x, -height - 12), (x - 4, -height - 22 - 5 * v(220 + i)), (x - 6, -height - 27)),
                color("3d4937"),
                0.75,
            )
        )
    return tuple(c)


# Exactly the five authored trees; immutable vector values only, no growth or native surfaces.
TREE_CATALOG = tuple((seed, _tree_recipe(seed)) for seed in (-15, 43, 98, 360, 407))


def tree(seed: int, warmth: float, breeze: float, seconds: float) -> tuple[DrawPath, ...]:
    base = next((commands for key, commands in TREE_CATALOG if key == seed), None)
    if base is None:  # Trusted recipe study only; scene data cannot choose seeds.
        base = _tree_recipe(seed)
    c = list(base)
    for i in range(7):
        sway = math.sin(seconds * 0.7 + i + seed) * breeze * 0.7
        for j in range(6):
            index = 3 + i * 6 + j
            command = base[index]
            c[index] = replace(
                command,
                transform=Transform(tx=sway),
                fill=color("d2ba79", 0.12 + warmth * 0.13) if j == 1 else command.fill,
            )
    return tuple(c)


def sky(warmth: float) -> tuple[DrawPath, ...]:
    c = [
        DrawPath(
            rectangle(-100, -100, 560, 850), gradient(color("173743"), color("d8b27c"), 15, 321)
        )
    ]
    # Continuous authored storm shelf: asymmetrical erosion, broad gradient falloff.
    for i in range(4):
        y = 18 + i * 17
        cloud = path(
            ("M", -100, -80),
            ("L", 460, -80),
            ("L", 460, y - 25),
            ("C", 381, y + 20, 341, y - 5, 290, y + 21),
            ("C", 259, y + 45, 222, y + 15, 193, y + 40),
            ("C", 154, y + 56, 135, y + 34, 101, y + 64),
            ("C", 56, y + 83, 22, y + 48, -34, y + 88),
            ("L", -100, y + 85),
            ("Z",),
        )
        c.append(
            DrawPath(cloud, gradient(color("102b38", 0.48), color("738078", 0.02), y - 36, y + 85))
        )
    c.append(
        DrawPath(
            path(
                ("M", -60, 127),
                ("C", 12, 105, 58, 133, 101, 118),
                ("C", 134, 98, 158, 121, 205, 102),
                ("C", 246, 82, 297, 103, 425, 75),
                ("L", 425, 100),
                ("C", 319, 117, 270, 110, 220, 130),
                ("C", 165, 145, 121, 126, 73, 148),
                ("C", 25, 162, -13, 141, -60, 153),
                ("Z",),
            ),
            gradient(color("79908b", 0.26), color("b2a789", 0.025), 100, 154),
        )
    )
    for i in range(7):
        x, y = -35 + i * 68, 165 + 21 * math.sin(i * 1.8)
        c.append(
            DrawPath(
                path(
                    ("M", x - 60, y),
                    ("C", x - 12, y - 9, x + 15, y + 8, x + 85, y - 7),
                    ("C", x + 42, y + 10, x - 3, y + 5, x - 60, y),
                    ("Z",),
                ),
                color("d8ba8e", 0.055 + warmth * 0.035),
            )
        )
    for i in range(12, 0, -1):
        c.append(
            DrawPath(
                ellipse(122, 232, 12 + i * 6, 12 + i * 4), color("f6d49a", 0.008 + warmth * 0.003)
            )
        )
    c.append(DrawPath(ellipse(122, 232, 11, 11), color("f5d39a")))
    for i in range(3):
        c.append(
            DrawPath(
                polygon(
                    (
                        (112 + i * 4, 225),
                        (128 + i * 3, 230),
                        (360 + i * 35, 510),
                        (276 + i * 27, 510),
                    ),
                    color("ffffff"),
                ).path,
                gradient(color("eed29c", warmth * 0.025), color("eed29c", 0), 230, 490),
            )
        )
    # A few distant birds give scale and a quiet directional cue without an animation system.
    for x, y, s in ((218, 172, 1), (231, 165, 0.75), (241, 178, 0.6)):
        c.append(
            line(
                ((x - 4 * s, y), (x, y + 1.5 * s), (x + 4 * s, y - s)), color("324c50", 0.65), 0.65
            )
        )
    return tuple(c)


def _ground_recipe(warmth: float) -> tuple[DrawPath, ...]:
    c = [
        DrawPath(
            path(
                ("M", -100, 398),
                ("C", 75, 375, 229, 400, 460, 380),
                ("L", 460, 750),
                ("L", -100, 750),
                ("Z",),
            ),
            gradient(color("656f52"), color("1f3734"), 386, 660),
        ),
        DrawPath(
            path(
                ("M", 228, 403),
                ("C", 203, 451, 103, 492, 85, 640),
                ("L", 310, 690),
                ("C", 185, 498, 235, 450, 246, 402),
                ("Z",),
            ),
            gradient(color("ad956c"), color("5a6650"), 400, 640),
        ),
    ]
    for i in range(10):
        top = 30 + i * 15
        bottom = -280 + i * 45
        c.append(
            polygon(
                ((top, 410), (top + 5, 410), (bottom + 34, 670), (bottom, 670)),
                color("243d32", 0.42 + 0.18 * variation(31, i)),
            )
        )
        # Broken beds, missing plants and off-axis clumps preserve intentional cultivation.
        for j in range(12):
            v = variation(i + 60, j)
            if v < 0.24:
                continue
            u = (j + 0.4 + v * 0.65) / 12
            x = top * (1 - u) + (bottom + 15) * u
            y = 410 + u * u * 250
            if x > 65 + (640 - y) * 0.45:
                continue
            s = (0.4 + u * 1.8) * (0.65 + v * 0.7)
            c.append(DrawPath(crown(x, y, 3 * s, 1.6 * s, i * 17 + j), color("182f2b", 0.4)))
            c.append(
                line(
                    (
                        (x - 3 * s, y - 4 * s),
                        (x, y),
                        (x + 2 * s, y - 6 * s),
                        (x + 5 * s, y - 3 * s),
                    ),
                    color(("8f9760", "b3a771", "697e4d")[j % 3], 0.45),
                    0.7 + u,
                )
            )
    for i in range(90):
        x = -45 + variation(97, i) * 470
        y = 416 + variation(98, i) ** 0.8 * 245
        s = 0.3 + (y - 410) / 150
        if x > 85 + (640 - y) * 0.5 and x < 210:
            # Worn path: shallow ruts, stones and a few fallen leaves.
            c.append(line(((x, y), (x + 4 * s, y - s)), color("cfb78b", 0.23), 0.8))
        else:
            c.append(
                line(
                    ((x - 2 * s, y - 3 * s), (x, y), (x + 2 * s, y - 5 * s)),
                    color("849164", 0.37),
                    0.6 + s * 0.3,
                )
            )
    # Same upper-left key: orchard/barn shadows fall to the lower right with layered penumbra.
    for x, y, w, h in (
        (-15, 413, 38, 65),
        (42, 419, 31, 62),
        (96, 414, 28, 44),
        (302, 411, 59, 79),
    ):
        for k in range(3):
            c.append(
                DrawPath(
                    path(
                        ("M", x - w, y),
                        ("C", x, y - 8, x + w, y, x + w + h, y + h),
                        ("C", x + h, y + h + 8 + k * 3, x - w / 2, y + 10, x - w, y),
                        ("Z",),
                    ),
                    gradient(color("173737", 0.07 + warmth * 0.035), color("173737", 0), y, y + h),
                )
            )
    for i in range(14):
        x = 120 + variation(11, i) * 205
        y = 437 + variation(12, i) * 155
        c.append(DrawPath(ellipse(x, y, 1.5, 0.65), color("c29a60", 0.5)))
    return tuple(c)


TERRAIN = _ground_recipe(0)


def ground(warmth: float) -> tuple[DrawPath, ...]:
    # Last 26 commands are twelve cast-shadow gradients followed by fourteen fallen leaves.
    c = list(TERRAIN)
    for index in range(len(c) - 26, len(c) - 14):
        command = c[index]
        paint = command.fill
        c[index] = replace(
            command,
            fill=replace(
                paint, stops=((0, color("173737", 0.07 + warmth * 0.035)), (1, color("173737", 0)))
            ),
        )
    return tuple(c)


def barn_light(warmth: float) -> tuple[DrawPath, ...]:
    """Local barn coordinates; lantern at (20,-98), door threshold (-56..-2,0)."""
    c = []
    wall = path(("M", -80, -111), ("L", 26, -105), ("L", 26, 8), ("L", -80, 0), ("Z",))
    c.extend(
        (
            DrawPath(
                path(
                    ("M", -80, -110),
                    ("L", 25, -104),
                    ("L", 25, -91),
                    ("C", -8, -96, -43, -94, -80, -100),
                    ("Z",),
                ),
                color("122e31", 0.36),
            ),
            DrawPath(
                path(("M", -80, -108), ("L", -62, -106), ("L", -63, 0), ("L", -80, -1), ("Z",)),
                gradient(color("ebc080", warmth * 0.25), color("ebc080", 0), -100, 0),
            ),
            DrawPath(
                path(("M", 28, -99), ("L", 100, -119), ("L", 100, -23), ("L", 28, 7), ("Z",)),
                gradient(color("102e34", 0.34), color("102e34", 0.08), -100, 5),
            ),
        )
    )
    wall += path(("M", -56, 0), ("L", -2, 0), ("L", -2, -82), ("L", -56, -82), ("Z",))
    # Gradients are clipped to opaque wall, so light never fills the dark doorway.
    for i in range(7, 0, -1):
        c.append(
            DrawPath(
                ellipse(20, -98, 8 + i * 5, 10 + i * 6), color("f4c47a", warmth * 0.035), clip=wall
            )
        )
    c.append(line(((-79, -108), (-79, -1)), color("f3ce8c", 0.18 + warmth * 0.25), 1.5))
    c.append(line(((5, -82), (5, 2)), color("edbe75", warmth * 0.7), 1.8))
    c.append(polygon(((-41, 0), (-2, 2), (-2, -2), (-41, -3)), color("d6a663", warmth * 0.45)))
    # Sparse nails, repairs and chipped shingles add construction cues rather than noise.
    for i in range(9):
        x = -73 + i * 10
        c.append(line(((x, -96), (x + 1.2, -96)), color("172d2b", 0.7), 0.7))
    c.append(polygon(((-75, -36), (-65, -35), (-65, -3), (-74, -4)), color("6d6349", 0.6)))
    c.append(line(((-73, -30), (-67, -7)), color("ccac78", 0.4), 0.8))
    for i in range(6):
        x = 12 + i * 12
        c.append(line(((x, -144 - i * 3), (x + 12, -145 - i * 3)), color("a0a185", 0.3), 0.6))
    for i in range(18):
        x = -77 + variation(323, i) * 98
        y = -99 + variation(324, i) * 90
        if -61 < x < 5 and y > -89:
            continue
        c.append(
            line(((x, y), (x + 0.3, y + 2 + 5 * variation(325, i))), color("e5bd83", 0.24), 0.65)
        )
    for i in range(5):
        y = -71 + i * 13
        c.append(
            DrawPath(
                path(
                    ("M", -80, y),
                    ("C", -66, y + 4, -57, y + 14, -46, y + 11),
                    ("L", -47, y + 15),
                    ("C", -62, y + 16, -71, y + 8, -80, y + 7),
                    ("Z",),
                ),
                color("193a36", 0.14),
                clip=wall,
            )
        )
    return tuple(c)


def ground_light(
    left: tuple[float, float], right: tuple[float, float], warmth: float
) -> tuple[DrawPath, ...]:
    """Projected threshold corners supplied in the ground plane; soft footprint on the path."""
    lx, ly = left
    rx, ry = right
    c = []
    for k in range(4):
        footprint = path(
            ("M", lx, ly),
            ("L", rx, ry),
            ("C", rx - 8, ry + 25, 224 + k * 2, 470, 202 + k * 3, 492 + k * 2),
            ("L", 138 - k * 3, 479 + k * 2),
            ("C", 167, 453, lx + 3, ly + 16, lx, ly),
            ("Z",),
        )
        c.append(
            DrawPath(
                footprint, gradient(color("ebbd79", warmth * 0.16), color("d6bd83", 0), ly, 500)
            )
        )
    return tuple(c)


def grade_character(
    commands: tuple[DrawPath, ...], warmth: float, atmosphere: float
) -> tuple[DrawPath, ...]:
    """Material-space cool fill and directional warm edge; preserves geometry/rig transforms."""

    def shade(paint: Paint) -> Paint:
        if isinstance(paint, Color):
            # Global dusk exposure, warmer on the source-facing material, cool ambient in shade.
            return Color(
                min(1, paint.r * 0.76 + 0.055 * warmth),
                min(1, paint.g * 0.82 + 0.04),
                min(1, paint.b * 0.84 + 0.055 * atmosphere),
                paint.a,
            )
        return replace(paint, stops=tuple((u, shade(p)) for u, p in paint.stops))

    out = []
    for command in commands:
        fill = shade(command.fill) if command.fill else None
        if isinstance(fill, Color) and fill.a > 0.5:
            # Object-local x extent; use the same path as clip by filling only its silhouette.
            xs = [op.points[i] for op in command.path for i in range(0, len(op.points), 2)]
            lo, hi = min(xs), max(xs)
            if hi - lo > 1:
                rim = Color(
                    min(1, fill.r + 0.12 * warmth), min(1, fill.g + 0.065 * warmth), fill.b, fill.a
                )
                fill = LinearGradient((lo, 0), (hi, 0), ((0, rim), (0.25, fill), (1, fill)))
        stroke = (
            replace(command.stroke, paint=shade(command.stroke.paint)) if command.stroke else None
        )
        out.append(replace(command, fill=fill, stroke=stroke))
    return tuple(out)


def foreground_detail(breeze: float, seconds: float) -> tuple[DrawPath, ...]:
    c = []
    # Right-side bare bough balances the heavy left trunk, leaving the doorway clear.
    c.append(
        DrawPath(
            path(
                ("M", 401, 105),
                ("C", 350, 112, 327, 172, 302, 186),
                ("L", 316, 180),
                ("C", 343, 159, 355, 138, 401, 134),
                ("Z",),
            ),
            color("122e32"),
        )
    )
    c.append(
        DrawPath(
            path(
                ("M", -12, 84),
                ("C", 51, 86, 94, 119, 156, 106),
                ("C", 181, 99, 185, 86, 203, 81),
                ("C", 190, 96, 183, 111, 160, 114),
                ("C", 105, 137, 48, 98, -12, 101),
                ("Z",),
            ),
            color("153234"),
        )
    )
    c.append(line(((20, 91), (55, 98), (90, 113)), color("8b8e6a", 0.16), 0.8))
    for i in range(9):
        x = 31 + i * 16
        y = 96 + 18 * math.sin((x - 20) / 160 * math.pi)
        c.append(
            DrawPath(crown(x, y, 9 + variation(901, i) * 7, 5, 701 + i), color("193738", 0.95))
        )
    for i in range(19):
        x = 311 + variation(222, i) * 98
        y = 133 + (380 - x) * 0.43 + variation(223, i) * 25
        c.append(
            DrawPath(
                crown(x + math.sin(seconds * 0.8 + i) * breeze, y, 12, 5, i + 80),
                color("193536", 0.94),
            )
        )
    for side in (0, 1):
        for i in range(10):
            x = (5 + i * 7) if side == 0 else 316 + i * 6
            y = 594 + variation(52, i) * 60
            c.append(line(((x, y), (x - 3, y - 17), (x - 8, y - 28)), color("233e39"), 1))
            for j in range(3):
                c.append(
                    polygon(
                        ((x - 2, y - 7 - j * 6), (x - 16, y - 16 - j * 6), (x - 7, y - 17 - j * 6)),
                        color("294339"),
                    )
                )
    return tuple(c)


def haze(atmosphere: float) -> tuple[DrawPath, ...]:
    return (
        DrawPath(
            path(
                ("M", -80, 355),
                ("C", 52, 344, 187, 372, 440, 344),
                ("L", 440, 400),
                ("C", 200, 379, 54, 390, -80, 382),
                ("Z",),
            ),
            gradient(color("cfbe94", atmosphere * 0.32), color("b1bea2", 0), 350, 397),
        ),
    )
