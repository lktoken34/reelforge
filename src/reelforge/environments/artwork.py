"""Last Light Orchard: original vector recipes in a 360 x 640 artboard.

No raster assets, native objects, mutable random stream or surface cache. Detail is
bounded by fixed loops. Palette is graded at authoring time, never per-pixel.
"""

import math
from dataclasses import replace

from reelforge.characters.rowan import path
from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import (
    Color,
    DrawPath,
    LinearGradient,
    Paint,
    Stroke,
    Transform,
    rectangle,
)


def polygon(points: tuple[tuple[float, float], ...], paint: Paint) -> DrawPath:
    return DrawPath(path(("M", *points[0]), *(("L", *p) for p in points[1:]), ("Z",)), paint)


def line(points: tuple[tuple[float, float], ...], paint: Paint, width: float = 1) -> DrawPath:
    return DrawPath(
        path(("M", *points[0]), *(("L", *p) for p in points[1:])),
        stroke=Stroke(paint, width),
    )


def gradient(a: Color, b: Color, y1: float, y2: float) -> LinearGradient:
    return LinearGradient((0, y1), (0, y2), ((0, a), (1, b)))


def placed(
    commands: tuple[DrawPath, ...], x: float, y: float, scale: float = 1
) -> tuple[DrawPath, ...]:
    return tuple(replace(c, transform=Transform(x, y, sx=scale, sy=scale)) for c in commands)


def barn() -> tuple[DrawPath, ...]:
    """Local three-quarter gambrel barn, origin at the near foundation corner."""
    c = [
        polygon(((-88, 2), (79, 11), (130, -26), (-33, -45)), color("142a2c", 0.35)),
        polygon(
            ((-80, 0), (26, 8), (26, -105), (-80, -111)),
            gradient(color("ac7950"), color("644735"), -100, 8),
        ),
        polygon(
            ((26, 8), (100, -22), (100, -116), (26, -105)),
            gradient(color("454b40"), color("253b37"), -116, 8),
        ),
        polygon(((-80, -111), (-64, -148), (-30, -173), (5, -143), (26, -105)), color("a67a53")),
    ]
    # Irregular siding, worn ends, seams and narrow reflected highlights.
    for i in range(17):
        x = -78 + i * 6.1
        bottom = 3 + (x + 80) * 0.07
        top = -108 if x < 18 else -104
        c.append(line(((x, top), (x + 0.8, bottom)), color("322f2b", 0.58), 0.65))
        c.append(
            line(
                ((x + 1.2, top + 3), (x + 1.8, bottom - 8 - i % 4 * 3)), color("d3a477", 0.24), 0.7
            )
        )
        for j in range(3):
            y = -93 + j * 32 + 8 * math.sin(i * 4 + j)
            c.append(line(((x + 2, y), (x + 3, y + 7)), color("d6a274", 0.19), 0.5))
    for i in range(12):
        x = 29 + i * 5.9
        c.append(
            line(((x, -105 - (x - 26) * 0.15), (x, 7 - (x - 26) * 0.4)), color("222c2a", 0.65), 0.8)
        )
    c.extend(
        [
            polygon(
                (
                    (-88, -111),
                    (-71, -153),
                    (-32, -182),
                    (43, -193),
                    (106, -123),
                    (28, -100),
                    (8, -144),
                    (-31, -173),
                    (-61, -149),
                    (-77, -110),
                ),
                color("263c3b"),
            ),
            polygon(((-32, -182), (43, -193), (81, -165), (8, -144)), color("52605a")),
            polygon(((8, -144), (81, -165), (106, -123), (28, -100)), color("374a47")),
            line(
                ((-87, -111), (-69, -152), (-32, -180), (7, -144), (27, -103)), color("d0a675"), 2
            ),
            line(((27, -103), (107, -124)), color("718076"), 1.5),
            line(((-31, -181), (43, -192)), color("879184"), 1),
        ]
    )
    for i in range(1, 10):
        k = i / 10
        c.append(
            line(
                ((8 + 73 * k, -144 - 21 * k), (28 + 78 * k, -101 - 23 * k)),
                color("172e2e", 0.7),
                0.7,
            )
        )
    for i in range(6):
        y = -150 + i * 6
        c.append(line(((-51, y), (-12, y + 1)), color("4a4033", 0.65), 1))
    c.extend(
        [
            DrawPath(rectangle(-61, -86, 64, 87), color("252f2c")),
            DrawPath(
                rectangle(-56, -82, 54, 82), gradient(color("101e21"), color("45392c"), -82, 0)
            ),
            polygon(((-57, -83), (-43, -85), (-43, 0), (-57, 1)), color("896343")),
            polygon(((-5, -82), (5, -83), (5, 3), (-5, 2)), color("614b38")),
            line(((-61, 1), (-61, -88), (4, -85), (4, 4)), color("c6a67b"), 2.6),
            polygon(((7, -77), (25, -72), (25, 5), (7, 3)), color("735840")),
            line(((8, -74), (23, 1)), color("bba07b"), 2),
            line(((23, -72), (9, 2)), color("ac9069"), 1.5),
            DrawPath(rectangle(-41, -146, 21, 23), color("3c4338")),
            line(
                ((-42, -122), (-42, -148), (-19, -148), (-19, -122), (-42, -122)),
                color("d5b17b"),
                1.5,
            ),
            line(((-31, -146), (-31, -124)), color("b29061"), 1),
            # Foundation stones and lantern bracket.
            polygon(((-82, 0), (27, 8), (27, 14), (-82, 5)), color("726d58")),
            line(((13, -90), (13, -104), (23, -104)), color("252e29"), 1.6),
            DrawPath(rectangle(17, -103, 7, 11), color("f2c783")),
            line(
                ((16, -104), (25, -104), (23, -107), (18, -107), (16, -104)), color("3c4031"), 1.5
            ),
        ]
    )
    for i in range(12):
        c.append(line(((-79 + i * 9, 1), (-79 + i * 9, 6)), color("343c34"), 0.7))
    return tuple(c)


def tree(seed: int = 0) -> tuple[DrawPath, ...]:
    """Gnarled orchard apple tree; canopy lobes follow a fixed hashed phase."""
    c = [
        polygon(
            (
                (-5, 0),
                (-3, -42),
                (-13, -64),
                (-26, -75),
                (-20, -78),
                (-4, -65),
                (2, -87),
                (7, -88),
                (5, -57),
                (19, -71),
                (23, -69),
                (8, -47),
                (6, 0),
            ),
            color("3b4435"),
        ),
        line(((-2, -2), (1, -43), (-4, -61)), color("ad9b68", 0.45), 1.4),
    ]
    for i in range(23):
        a = i * 2.399 + seed
        r = math.sqrt((i + 0.5) / 23)
        x = math.cos(a) * 38 * r
        y = -86 + math.sin(a) * 24 * r
        base = ("344b3d", "485c42", "5e704b", "788052")[i % 4]
        c.append(DrawPath(ellipse(x, y, 14 + (i % 3) * 2, 13 + (i % 4)), color(base)))
        if i % 3 == 0:
            c.append(DrawPath(ellipse(x - 4, y - 5, 7, 3), color("adb17b", 0.22)))
    for i in range(9):
        x = math.sin(i * 13 + seed) * 31
        y = -88 + math.cos(i * 7) * 16
        c.append(DrawPath(ellipse(x, y, 1.5, 1.8), color("b0834e")))
    return tuple(c)


def fence() -> tuple[DrawPath, ...]:
    c = []
    for i in range(10):
        x = i * 23
        y = -i * 0.45
        c.extend(
            [
                polygon(
                    ((x - 2, y), (x - 2, y - 25), (x, y - 29), (x + 2, y - 26), (x + 3, y)),
                    color("777862"),
                ),
                line(((x - 1, y - 25), (x, y - 4)), color("c2b18a", 0.55), 0.9),
            ]
        )
    for y in (-20, -10):
        c.append(line(((0, y), (209, y - 4)), color("8d8c6c"), 2.5))
        c.append(line(((0, y - 1), (209, y - 5)), color("d1bf8d", 0.4), 0.6))
    return tuple(c)


def sky(warmth: float) -> tuple[DrawPath, ...]:
    c = [
        DrawPath(
            rectangle(-100, -100, 560, 850), gradient(color("142f3e"), color("e4bd88"), 0, 325)
        )
    ]
    for i in range(15, 0, -1):
        c.append(
            DrawPath(
                ellipse(122, 232, 13 + i * 5, 13 + i * 5), color("f8d99a", 0.009 + warmth * 0.002)
            )
        )
    c.append(DrawPath(ellipse(122, 232, 12, 12), color("f9dba0")))
    for j in range(5):
        y = 85 + j * 32
        c.append(
            DrawPath(
                path(
                    ("M", -60, y),
                    ("C", 40, y - 15, 110, y + 15, 205, y - 2),
                    ("C", 290, y - 20, 375, y - 4, 430, y - 16),
                    ("L", 430, y - 10),
                    ("C", 220, y + 11, 100, y + 8, -60, y + 8),
                    ("Z",),
                ),
                color("bfc0a4", 0.10),
            )
        )
    return tuple(c)


def hills(atmosphere: float) -> tuple[DrawPath, ...]:
    c = []
    for j, (y, paint) in enumerate(((293, "7c9188"), (317, "627f77"), (345, "49685f"))):
        c.append(
            DrawPath(
                path(
                    ("M", -100, y + 30),
                    ("C", -15, y - 68, 40, y - 15, 105, y - 29),
                    ("C", 188, y - 58, 238, y + 31, 310, y - 22),
                    ("C", 350, y - 41, 405, y - 19, 460, y - 29),
                    ("L", 460, 680),
                    ("L", -100, 680),
                    ("Z",),
                ),
                color(paint),
            )
        )
        for i in range(28):
            x = -70 + i * 20
            yy = y + 8 + math.sin(i * 0.7 + j) * 10
            c.append(polygon(((x, yy), (x + 4, yy - 15 - j * 2), (x + 9, yy)), color(paint)))
    c.append(
        DrawPath(
            rectangle(-100, 310, 560, 64),
            gradient(color("d9c69b", atmosphere * 0.20), color("a1b19a", 0), 310, 374),
        )
    )
    return tuple(c)


def ground() -> tuple[DrawPath, ...]:
    c = [
        DrawPath(
            path(
                ("M", -100, 398),
                ("C", 75, 375, 229, 400, 460, 380),
                ("L", 460, 750),
                ("L", -100, 750),
                ("Z",),
            ),
            gradient(color("788064"), color("2b403a"), 386, 660),
        ),
        DrawPath(
            path(
                ("M", 228, 403),
                ("C", 203, 451, 103, 492, 85, 640),
                ("L", 310, 690),
                ("C", 185, 498, 235, 450, 246, 402),
                ("Z",),
            ),
            gradient(color("b49c73"), color("6b6b50"), 400, 640),
        ),
    ]
    # Cultivated beds fan toward the vanishing point and remain behind the path.
    for i in range(10):
        x = -280 + i * 45
        c.append(
            polygon(
                ((30 + i * 15, 410), (36 + i * 15, 410), (x + 35, 670), (x, 670)),
                color("263f36", 0.65),
            )
        )
        for j in range(11):
            u = (j + 1) / 12
            xx = (30 + i * 15) * (1 - u) + (x + 15) * u
            yy = 410 + u * u * 250
            if xx < 65 + (640 - yy) * 0.45:
                c.append(
                    line(
                        ((xx - 3 * u, yy - 5 * u), (xx, yy), (xx + 4 * u, yy - 6 * u)),
                        color("a1a071", 0.45),
                        0.7 + u,
                    )
                )
    for i in range(90):
        x = (i * 137.23) % 470 - 55
        y = 416 + (i * 29.7) % 245
        c.append(line(((x, y), (x + 2 + (y - 400) / 80, y - 0.3)), color("c4b38a", 0.13), 0.6))
    c.extend(
        [
            DrawPath(
                path(("M", 260, 405), ("L", 355, 404), ("L", 460, 510), ("L", 304, 496), ("Z",)),
                gradient(color("173c3b", 0.42), color("173c3b", 0), 405, 510),
            ),
            DrawPath(
                path(("M", -40, 414), ("L", 98, 410), ("L", 40, 494), ("L", -80, 522), ("Z",)),
                gradient(color("1c3f3d", 0.28), color("1c3f3d", 0), 410, 522),
            ),
            DrawPath(
                path(
                    ("M", 215, 421),
                    ("C", 220, 454, 173, 491, 158, 528),
                    ("L", 178, 530),
                    ("C", 180, 480, 239, 444, 239, 418),
                    ("Z",),
                ),
                gradient(color("f0c786", 0.13), color("c6bb85", 0), 418, 530),
            ),
        ]
    )
    return tuple(c)


def foreground(breeze: float, seconds: float) -> tuple[DrawPath, ...]:
    c = []
    # Broken frame: left trunk, overhead bough, corner bracken; central action stays legible.
    c.append(
        polygon(
            (
                (-70, 700),
                (-28, 450),
                (-17, 230),
                (-25, 110),
                (-46, -40),
                (-8, -40),
                (8, 101),
                (3, 225),
                (-1, 366),
                (2, 516),
                (-3, 700),
            ),
            color("102b2d"),
        )
    )
    c.append(
        DrawPath(
            path(
                ("M", -23, 112),
                ("C", 65, 77, 105, 52, 169, -30),
                ("L", 150, -40),
                ("C", 85, 37, 36, 56, -30, 67),
                ("Z",),
            ),
            color("122d2e"),
        )
    )
    for i in range(53):
        a = i * 2.399
        x = -5 + (i * 31) % 190
        y = 25 + math.sin(i * 7) * 45 - x * 0.3
        sway = math.sin(seconds * 1.1 + i) * breeze * 1.5
        c.append(
            DrawPath(
                ellipse(x + sway, y, 15 + 6 * math.sin(a), 7),
                color("142f30"),
                transform=Transform(rotation=0),
            )
        )
    for side in (0, 1):
        for i in range(42):
            x = (-40 + i * 3.2) if side == 0 else 305 + i * 3
            y = 640 + math.sin(i) * 23
            h = 20 + (i * 17) % 67
            bend = math.sin(seconds * 0.9 + i * 0.7) * breeze * 3
            c.append(
                DrawPath(
                    path(
                        ("M", x - 2, y),
                        ("C", x - 3, y - h * 0.5, x - 8 + bend, y - h, x - 12 + bend, y - h),
                        ("C", x - 3, y - h + 4, x + 2, y - 9, x + 3, y),
                        ("Z",),
                    ),
                    color("122f30"),
                )
            )
    return tuple(c)
