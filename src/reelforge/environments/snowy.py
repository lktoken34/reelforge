"""Frost Peak: original snowy-mountain vector recipes in the shared 360 x 640 artboard.

Trusted code-authored recipes in the style of ``environments.artwork`` / ``polish``: pure
immutable ``DrawPath`` values, bounded fixed loops, a stateless integer mixer, no raster assets,
no native objects, no random stream, no per-pixel work. Art direction and ``seconds`` arrive like
the orchard recipes. Palette: deep navy shadow, cold cyan/blue snow, desaturated distant peaks and
one controlled warm amber reserved for the emergency beacon and the distant answering light.
"""

from __future__ import annotations

import math

from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import DrawPath, LinearGradient, PathOp, rectangle

from .artwork import gradient, line, polygon
from .polish import variation


def _P(kind, *pts):
    return PathOp(kind, tuple(pts))


# ---------------------------------------------------------------- palette
SHADOW = "0b1630"
NIGHT = "10224a"
PEAK_FAR = "41567f"
PEAK_MID = "32466e"
PEAK_NEAR = "26375c"
SNOW_LIT = "cfe0f4"
SNOW_MID = "9fb6d8"
SNOW_SHADE = "5b739e"
SNOW_DEEP = "3a4e7c"
PINE = "1d3350"
PINE_SNOW = "c3d6ef"
ROCK = "2b3450"
ROCK_LIT = "4a577a"
BEACON_WARM = "ff9a3c"
BEACON_CORE = "ffd58a"
BEACON_RED = "ff5436"


# ---------------------------------------------------------------- sky
def frost_sky(warmth: float, atmosphere: float) -> tuple[DrawPath, ...]:
    """Cold twilight: deep navy zenith to a pale cyan horizon, an aurora veil and faint stars."""
    c = [
        DrawPath(
            rectangle(-100, -100, 560, 850),
            LinearGradient(
                (0, -40),
                (0, 430),
                (
                    (0.0, color(SHADOW)),
                    (0.45, color(NIGHT)),
                    (0.8, color("29406e")),
                    (1.0, color("7f9ac2")),
                ),
            ),
        )
    ]
    for i in range(10, 0, -1):
        c.append(DrawPath(ellipse(262, 150, 9 + i * 5, 9 + i * 5), color("bcd2f2", 0.012)))
    c.append(DrawPath(ellipse(262, 150, 11, 11), color("dcebff", 0.9)))
    for j in range(3):
        y = 70 + j * 26
        hue = ("4de0c0", "6fd0ff", "9ad8ff")[j]
        c.append(
            DrawPath(
                (
                    _P("M", -80, y + 20),
                    _P("C", 40, y - 26, 150, y + 16, 240, y - 18),
                    _P("C", 320, y - 40, 400, y - 8, 460, y - 24),
                    _P("L", 460, y + 8),
                    _P("C", 360, y + 26, 250, y + 4, 150, y + 30),
                    _P("C", 70, y + 46, 10, y + 20, -80, y + 44),
                    _P("Z"),
                ),
                color(hue, 0.05 + atmosphere * 0.05),
            )
        )
    for i in range(46):
        x = variation(71, i) * 460 - 60
        y = variation(72, i) * 230
        r = 0.6 + variation(73, i) * 0.9
        c.append(DrawPath(ellipse(x, y, r, r), color("dce9ff", 0.35 + 0.4 * variation(74, i))))
    if warmth > 0:
        c.append(DrawPath(ellipse(262, 150, 30, 18), color("ffe6c0", warmth * 0.05)))
    return tuple(c)


# ---------------------------------------------------------------- peaks
def _ridge(y: float, amp: float, seed: int, paint) -> DrawPath:
    pts = [(-80, y + amp)]
    n = 9
    for i in range(n + 1):
        x = -80 + i * (540 / n)
        yy = y - amp * (0.3 + 0.9 * variation(seed, i)) * math.sin(i * 1.1 + seed * 0.3)
        pts.append((x, yy))
    pts.append((460, y + amp))
    pts.append((460, 680))
    pts.append((-80, 680))
    ops = [_P("M", *pts[0])] + [_P("L", *p) for p in pts[1:]] + [_P("Z")]
    return DrawPath(tuple(ops), paint)


def frost_peaks(variant: str, atmosphere: float) -> tuple[DrawPath, ...]:
    """Layered snow-covered peaks with atmospheric perspective. Variants pick the depth band."""
    if variant == "far":
        bands = ((250, 44, 11, PEAK_FAR), (286, 54, 23, PEAK_MID))
        haze_y, haze_h = 250, 120
    else:
        bands = ((300, 70, 31, PEAK_MID), (330, 86, 47, PEAK_NEAR))
        haze_y, haze_h = 300, 110
    c: list[DrawPath] = []
    for y, amp, seed, paint in bands:
        c.append(_ridge(y, amp, seed, color(paint)))
    if variant != "far":
        for ax, ay in ((70, 268), (168, 250), (250, 262), (330, 256)):
            w = 34
            c.append(
                polygon(
                    ((ax - w, ay + 40), (ax, ay), (ax + w, ay + 40)),
                    gradient(color(SNOW_LIT), color(SNOW_SHADE), ay, ay + 44),
                )
            )
            c.append(
                polygon(((ax - w, ay + 40), (ax, ay), (ax - 4, ay + 40)), color(SNOW_LIT, 0.9))
            )
            c.append(
                polygon(((ax + 4, ay + 40), (ax, ay), (ax + w, ay + 40)), color(SNOW_SHADE, 0.7))
            )
            c.append(line(((ax - 6, ay + 10), (ax - 10, ay + 34)), color(PEAK_NEAR, 0.6), 1.2))
            c.append(line(((ax + 7, ay + 12), (ax + 12, ay + 36)), color(SHADOW, 0.5), 1.0))
    c.append(
        DrawPath(
            rectangle(-100, haze_y, 560, haze_h),
            gradient(
                color("9fb6d8", atmosphere * 0.30), color("9fb6d8", 0), haze_y, haze_y + haze_h
            ),
        )
    )
    return tuple(c)


# ---------------------------------------------------------------- ridge / ground
def frost_ridge(warmth: float, atmosphere: float, seconds: float) -> tuple[DrawPath, ...]:
    """Walkable snow ridge. Local origin (0, 0) is the standing point on the packed path.

    The surface is a continuous downslope that deepens from lit crust to blue shade and extends
    well below the frame, so no pale base strip is ever exposed. Wind-sculpted drifts, sastrugi
    and a line of footprints arriving from the left give the lower frame direction and purpose.
    """
    c = [
        DrawPath(
            (
                _P("M", -420, -8),
                _P("C", -200, -36, 140, -32, 420, -2),
                _P("L", 420, 520),
                _P("L", -420, 520),
                _P("Z"),
            ),
            LinearGradient(
                (0, -30),
                (0, 360),
                (
                    (0.0, color(SNOW_MID)),
                    (0.22, color("7f98c2")),
                    (0.6, color("4d639a")),
                    (1.0, color(SNOW_DEEP)),
                ),
            ),
        ),
        # Packed path the character walks on, receding to the right.
        DrawPath(
            (
                _P("M", -420, 4),
                _P("C", -200, -4, 150, 2, 420, -26),
                _P("L", 420, -8),
                _P("C", 180, 24, -120, 22, -420, 34),
                _P("Z"),
            ),
            gradient(color(SNOW_LIT), color("a8bfe2"), -26, 34),
        ),
    ]
    # Downslope drift crests: lit upper lip, blue lee side. Shapes, not a flat sheet.
    for i in range(9):
        bx = -360 + i * 90 + variation(310, i) * 30
        by = 52 + (i % 3) * 34 + variation(311, i) * 14
        w = 80 + variation(312, i) * 40
        c.append(
            DrawPath(
                (
                    _P("M", bx - w, by + 26),
                    _P("C", bx - w * 0.45, by - 18, bx + w * 0.4, by - 20, bx + w, by + 22),
                    _P("C", bx + w * 0.5, by + 10, bx - w * 0.5, by + 10, bx - w, by + 26),
                    _P("Z"),
                ),
                gradient(color(SNOW_LIT, 0.8), color(SNOW_SHADE, 0.55), by - 20, by + 26),
            )
        )
        c.append(
            line(
                ((bx - w, by + 24), (bx - 4, by - 14), (bx + w, by + 20)),
                color("e8f1ff", 0.35),
                1.0,
            )
        )
        c.append(
            DrawPath(
                (
                    _P("M", bx + w * 0.1, by + 6),
                    _P("C", bx + w * 0.5, by - 6, bx + w * 0.8, by + 4, bx + w, by + 22),
                    _P("L", bx + w * 0.2, by + 26),
                    _P("Z"),
                ),
                color(SNOW_DEEP, 0.28),
            )
        )
    # Footprints arriving along the path from the left (stops short of the start positions).
    for i in range(11):
        x = -330 + i * 24
        y = 12 + 3.5 * (1 if i % 2 else -1) + 0.012 * (x + 330)
        c.append(DrawPath(ellipse(x, y, 5.5, 2.2), color(SNOW_DEEP, 0.55)))
        c.append(DrawPath(ellipse(x - 0.8, y - 0.9, 4.6, 1.5), color("e8f1ff", 0.35)))
    for i in range(34):
        x = variation(320, i) * 840 - 420
        y = 4 + variation(321, i) ** 0.7 * 220
        s = 0.5 + y / 160
        c.append(line(((x, y), (x + 8 * s, y - 1.3 * s)), color("eaf2ff", 0.16), 0.7))
    if warmth > 0:
        c.append(DrawPath(ellipse(40, 6, 150, 20), color("ffce9a", warmth * 0.05)))
    return tuple(c)


# ---------------------------------------------------------------- pines
def pine_snow(variant: str, breeze: float, seconds: float) -> tuple[DrawPath, ...]:
    """A snow-laden conifer. Origin at the trunk base; tiers stack upward."""
    tiers = {"tall": 5, "short": 3, "cluster": 4}.get(variant, 4)
    height = {"tall": 96, "short": 54, "cluster": 70}.get(variant, 70)
    c: list[DrawPath] = []
    c.append(polygon(((-3, 0), (3, 0), (2, -height * 0.5), (-2, -height * 0.5)), color("201a16")))
    step = height / (tiers + 1)
    sway = math.sin(seconds * 0.6) * breeze * 2.0
    for t in range(tiers):
        base_y = -step * (t + 1) * 0.9
        top_y = base_y - step * 1.5
        w = (tiers - t) * (height * 0.085) + 6
        tip = sway * (t + 1) / tiers
        c.append(polygon(((-w, base_y), (tip, top_y), (w, base_y)), color(PINE)))
        c.append(
            polygon(
                ((-w * 0.8, base_y - 1), (tip, top_y + 2), (w * 0.8, base_y - 1)),
                color(PINE_SNOW, 0.9),
            )
        )
        c.append(line(((-w, base_y), (tip, top_y)), color("e8f1ff", 0.5), 0.8))
    c.append(DrawPath(ellipse(sway, -height + 4, 5, 3), color(SNOW_LIT)))
    return tuple(c)


# ---------------------------------------------------------------- rocks
def frost_rocks(variant: str) -> tuple[DrawPath, ...]:
    """Exposed stone with snow ledges. 'cliff' is a tall outcrop; 'drift' a snow bank."""
    c: list[DrawPath] = []
    if variant == "cliff":
        c.append(
            polygon(
                ((-46, 2), (-30, -70), (2, -96), (34, -62), (48, 4)),
                gradient(color(ROCK_LIT), color(ROCK), -96, 4),
            )
        )
        for a, b in (((-30, -70), (-8, 0)), ((2, -96), (14, -8)), ((34, -62), (26, 0))):
            c.append(line((a, b), color(SHADOW, 0.55), 1.1))
        c.append(polygon(((-30, -70), (2, -96), (12, -84), (-18, -60)), color(SNOW_LIT, 0.85)))
        c.append(polygon(((-40, -8), (40, -4), (34, 6), (-44, 2)), color(SNOW_MID, 0.7)))
    else:
        c.append(
            DrawPath(
                (
                    _P("M", -90, 20),
                    _P("C", -60, -22, -10, -30, 30, -18),
                    _P("C", 70, -8, 96, 6, 100, 24),
                    _P("L", 100, 60),
                    _P("L", -90, 60),
                    _P("Z"),
                ),
                gradient(color(SNOW_LIT), color(SNOW_SHADE), -30, 40),
            )
        )
        c.append(line(((-80, 10), (-30, -22), (30, -16), (92, 16)), color("eef4ff", 0.5), 1.2))
        c.append(polygon(((-52, 18), (-40, 2), (-26, 16), (-34, 24)), color(ROCK)))
        c.append(polygon(((44, 22), (56, 8), (70, 20), (60, 28)), color(ROCK)))
    return tuple(c)


# ---------------------------------------------------------------- beacon prop
BEACON_TILT = 0.10  # the housing sits canted in the drift (radians, clockwise in Y-down)
_BC, _BS = math.cos(BEACON_TILT), math.sin(BEACON_TILT)
BUTTON_LOCAL = (0.0, -25.0)  # the activation button centre before tilt


def _bt(x: float, y: float) -> tuple[float, float]:
    return x * _BC - y * _BS, x * _BS + y * _BC


# Public registered activation socket: asset-local position of the button centre.
BEACON_SOCKET = _bt(*BUTTON_LOCAL)


def _bpoly(points, paint) -> DrawPath:
    return polygon(tuple(_bt(x, y) for x, y in points), paint)


def _bline(points, paint, width) -> DrawPath:
    return line(tuple(_bt(x, y) for x, y in points), paint, width)


def _bellipse(cx, cy, rx, ry, paint) -> DrawPath:
    x, y = _bt(cx, cy)
    return DrawPath(ellipse(x, y, rx, ry), paint)


def beacon(variant: str, warmth: float, seconds: float) -> tuple[DrawPath, ...]:
    """Emergency signal beacon. Origin at the base on the snow; y up is negative.

    A canted steel housing with a hazard-orange band, a glass lamp dome, an antenna and a
    recessed control panel carrying one large red activation button (``BEACON_SOCKET``).
    'buried' is half sunk in a drift with snow over its lower body and lamp cap but the panel and
    button clear; 'active' has the lamp lit, a signal beam and the button glowing.
    """
    active = variant == "active"
    pulse = 0.65 + 0.35 * math.sin(seconds * 5.0)
    c: list[DrawPath] = []
    # Splayed stakes and cast shadow on the snow.
    c.append(_bline(((-15, -6), (-27, 5)), color("2a3144"), 2.6))
    c.append(_bline(((15, -6), (27, 5)), color("1f2535"), 2.6))
    c.append(DrawPath(ellipse(4, 4, 38, 7), color(SHADOW, 0.35)))
    # Housing body with lit left face and shaded right edge.
    c.append(
        _bpoly(
            ((-17, -4), (17, -4), (17, -50), (-17, -50)),
            gradient(color("7a86a2"), color("3c455c"), -50, -4),
        )
    )
    c.append(_bpoly(((10, -4), (17, -4), (17, -50), (10, -50)), color(SHADOW, 0.35)))
    c.append(_bpoly(((-17, -50), (-14, -50), (-14, -4), (-17, -4)), color("c5d2ee", 0.45)))
    # Hazard-orange band so the object reads as emergency equipment at a glance.
    c.append(_bpoly(((-17, -50), (17, -50), (17, -42), (-17, -42)), color("e0652e")))
    for i in range(5):
        x = -17 + i * 8
        c.append(
            _bpoly(((x, -42), (x + 4, -42), (x + 8, -50), (x + 4, -50)), color("2a1a14", 0.75))
        )
    # Recessed control panel with a rimmed red button, the single activation point.
    c.append(_bpoly(((-12, -38), (12, -38), (12, -13), (-12, -13)), color("141a2a")))
    c.append(
        _bline(((-12, -38), (12, -38), (12, -13), (-12, -13), (-12, -38)), color("8d9bbb"), 1.0)
    )
    c.append(_bpoly(((-8, -35), (8, -35), (8, -33), (-8, -33)), color("cfd8ec", 0.7)))
    for dx in (-6, 0, 6):
        c.append(_bellipse(dx, -31, 1.1, 1.1, color("4b5672")))
    c.append(_bellipse(0, -25, 8.5, 8.5, color("e8f1ff", 0.9 if not active else 0.6)))
    c.append(_bellipse(0, -25, 7, 7, color("232b40")))
    if active:
        c.append(_bellipse(0, -25, 5.2, 5.2, color("ffb04a")))
        c.append(_bellipse(0, -25, 2.6, 2.6, color("fff2d6")))
    else:
        c.append(_bellipse(0, -25, 5.2, 5.2, color("d83a2e")))
        c.append(_bellipse(-1.4, -26.6, 2.0, 1.3, color("ff9d8c", 0.85)))
        # Soft standby ring so the eye lands on the control.
        c.append(_bellipse(0, -25, 11, 11, color(BEACON_RED, 0.10 + 0.06 * pulse)))
    # Lamp dome and antenna.
    dome = (
        gradient(color(BEACON_CORE), color(BEACON_WARM), -64, -50)
        if active
        else gradient(color("4a5368"), color("20252f"), -64, -50)
    )
    x0, y0 = _bt(0, -50)
    c.append(DrawPath(ellipse(x0, y0, 13, 11), dome))
    c.append(_bline(((8, -58), (12, -92)), color("6a7590"), 1.6))
    tip = _bt(12, -92)
    c.append(
        DrawPath(ellipse(tip[0], tip[1], 2.2, 2.2), color(BEACON_RED if not active else "fff4df"))
    )
    if active:
        lamp = _bt(0, -52)
        for i in range(8, 0, -1):
            c.append(
                DrawPath(
                    ellipse(lamp[0], lamp[1], 8 + i * 6, 8 + i * 6),
                    color(BEACON_CORE if warmth >= 0.5 else BEACON_WARM, 0.04 * pulse),
                )
            )
        c.append(DrawPath(ellipse(lamp[0], lamp[1], 6, 5), color("fff4df")))
        c.append(
            polygon(
                (
                    (lamp[0] - 5, lamp[1] - 4),
                    (lamp[0] + 5, lamp[1] - 4),
                    (lamp[0] + 22, -190),
                    (lamp[0] - 22, -190),
                ),
                gradient(color(BEACON_CORE, 0.42 * pulse), color(BEACON_CORE, 0.0), -190, lamp[1]),
            )
        )
        c.append(DrawPath(ellipse(0, 4, 52, 13), color(BEACON_WARM, 0.20 * pulse)))
    else:
        c.append(_bellipse(0, -52, 2.6, 2.6, color(BEACON_RED, 0.35 + 0.25 * pulse)))
    # Drift: snow over the lower body and a cap on the dome, panel and button left clear.
    # The base feathers out into the surrounding snow (alpha falls to zero below the surface)
    # so the mound reads as part of the ground, never as a flat-bottomed block.
    drift = [
        _P("M", -70, 14),
        _P("C", -48, -4, -30, -18, -17, -22),
        _P("C", -12, -18, -8, -10, 0, -9),
        _P("C", 8, -9, 14, -14, 20, -18),
        _P("C", 36, -14, 56, 0, 74, 14),
        _P("C", 40, 22, -36, 22, -70, 14),
        _P("Z"),
    ]
    c.append(
        DrawPath(
            tuple(drift),
            LinearGradient(
                (0, -22),
                (0, 22),
                (
                    (0.0, color(SNOW_LIT)),
                    (0.55, color(SNOW_MID, 0.95)),
                    (1.0, color(SNOW_MID, 0.0)),
                ),
            ),
        )
    )
    c.append(line(((-56, 6), (-34, -10), (-17, -21)), color("f2f7ff", 0.7), 1.4))
    c.append(line(((20, -17), (40, -8), (60, 6)), color("f2f7ff", 0.45), 1.2))
    if not active:
        # Snow still lying on the shoulder and dome; blown clear once the beacon fires.
        c.append(
            _bpoly(((-17, -50), (-3, -53), (4, -50), (-4, -47), (-17, -46)), color(SNOW_LIT, 0.95))
        )
        c.append(_bellipse(-6, -60, 7.5, 3.2, color(SNOW_LIT, 0.95)))
    return tuple(c)


# ---------------------------------------------------------------- distant answering light
def answer_light(seconds: float) -> tuple[DrawPath, ...]:
    """A distant response signal on a far ridge: a pulsing white-gold point and thin beam."""
    pulse = 0.55 + 0.45 * math.sin(seconds * 4.0)
    c: list[DrawPath] = []
    for i in range(7, 0, -1):
        c.append(DrawPath(ellipse(0, 0, 3 + i * 4, 3 + i * 4), color("ffe9c2", 0.045 * pulse)))
    c.append(DrawPath(ellipse(0, 0, 3.4, 3.4), color("fff6e2")))
    c.append(line(((-14, 0), (14, 0)), color("fff1d0", 0.55 * pulse), 0.9))
    c.append(line(((0, -14), (0, 14)), color("fff1d0", 0.55 * pulse), 0.9))
    c.append(
        polygon(
            ((-1.5, -2), (1.5, -2), (7, -70), (-7, -70)),
            gradient(color("ffeccc", 0.30 * pulse), color("ffeccc", 0.0), -70, 0),
        )
    )
    return tuple(c)


# ---------------------------------------------------------------- foreground
def frost_foreground(variant: str, breeze: float, seconds: float) -> tuple[DrawPath, ...]:
    """Foreground framing authored in absolute artboard units (place the node at the anchor).

    Two shaded snow drifts anchor the lower corners and leave the centre open; a soft bottom
    gradient settles the frame. Geometry runs well past the bottom edge so no base strip shows.
    ``storm`` adds a dense, longer, brighter field of wind-driven snow streaks.
    """
    c: list[DrawPath] = []
    # Left drift: lit rim, blue lee face, a dark rock peeking through.
    c.append(
        DrawPath(
            (
                _P("M", -260, 940),
                _P("L", -260, 600),
                _P("C", -140, 560, -20, 566, 70, 596),
                _P("C", 120, 614, 150, 650, 190, 700),
                _P("L", 190, 940),
                _P("Z"),
            ),
            gradient(color("8aa3cc"), color("34476f"), 570, 760),
        )
    )
    c.append(line(((-240, 598), (-90, 566), (40, 584), (110, 606)), color("e8f1ff", 0.55), 1.6))
    c.append(polygon(((-30, 596), (-8, 578), (22, 594), (10, 610)), color(ROCK)))
    c.append(polygon(((-30, 596), (-8, 578), (-2, 590)), color(ROCK_LIT, 0.8)))
    # Right drift, lower and softer so the two corners do not mirror each other.
    c.append(
        DrawPath(
            (
                _P("M", 600, 940),
                _P("L", 600, 628),
                _P("C", 500, 604, 400, 616, 330, 650),
                _P("C", 300, 668, 290, 700, 270, 760),
                _P("L", 270, 940),
                _P("Z"),
            ),
            gradient(color("7f98c2"), color("2e4068"), 610, 780),
        )
    )
    c.append(line(((580, 630), (470, 612), (380, 632), (322, 654)), color("e8f1ff", 0.45), 1.4))
    # Bottom settle: translucent deepening, not an opaque slab.
    c.append(
        DrawPath(
            rectangle(-300, 640, 900, 360),
            gradient(color(SHADOW, 0.0), color(SHADOW, 0.55), 640, 860),
        )
    )
    storm = variant == "storm"
    count, length, alpha, width = (90, 46, 0.26, 1.2) if storm else (26, 22, 0.12, 0.9)
    drift = 60 if storm else 24
    for i in range(count):
        bx = variation(401, i) * 460 - 60 + seconds * drift * 2 + math.sin(i) * breeze * drift
        bx = bx % 480 - 60
        by = variation(402, i) * 620
        ln = 10 + variation(403, i) * length
        a = 0.08 + alpha * variation(404, i)
        c.append(line(((bx, by), (bx + ln, by + ln * 0.22)), color("e9f2ff", a), width))
    return tuple(c)


__all__ = [
    "frost_sky",
    "frost_peaks",
    "frost_ridge",
    "pine_snow",
    "frost_rocks",
    "beacon",
    "answer_light",
    "frost_foreground",
    "BEACON_SOCKET",
]
