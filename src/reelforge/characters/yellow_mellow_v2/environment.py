"""Moonlit Observatory adapter with a horizontally panning camera.

Reuses the V1 environment layers unchanged (sky, stars, moon, skyline, observatory) and
offsets them with depth-consistent parallax. The railing and perspective floor are redrawn
with the V1 palette and layout so floor seams move with the character's ground line, which
keeps planted feet visually locked to the tiles while the camera pans. At ``camera_x = 0``
the layout matches V1 apart from a slightly stronger horizon glow for head readability.
"""

from __future__ import annotations

from dataclasses import replace

from reelforge.characters.yellow_mellow import environment as v1
from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import DrawPath, LinearGradient, PathOp, Transform, finite

VP_X, VP_Y = 180.0, 390.0
RAIL_TOP, RAIL_MID, RAIL_BASE = 445.0, 458.0, 472.0
SEAMS = (488, 508, 532, 562, 600, 640)
# The dome stands just behind the railing (railing parallax ~0.37 for ground_y 575).
OBSERVATORY_PARALLAX = 0.35
SEAM_PATTERN = (70, 70, 80, 80, 70, 70)  # V1 diagonal seam spacing at the bottom edge


def _depth_parallax(y: float, ground_y: float) -> float:
    return max(0.0, (y - VP_Y) / (ground_y - VP_Y))


def _shift(commands, dx: float) -> tuple[DrawPath, ...]:
    if abs(dx) < 1e-9:
        return tuple(commands)
    return tuple(
        replace(c, transform=Transform(c.transform.tx + dx, c.transform.ty)) for c in commands
    )


def _tiled(commands, dx: float, period: float = 360.0) -> tuple[DrawPath, ...]:
    """Repeat a 0..period wide layer so a parallax shift never exposes empty sky."""
    base = dx % period
    out = []
    for k in (-1, 0):
        out.extend(_shift(commands, base + k * period))
    return tuple(out)


_SKY = v1.make_sky_layer()
_STARS = v1.make_starfield()
_MOON = v1.make_moon_layer()
_CITY = v1.make_city_skyline()
_OBSERVATORY = v1.make_observatory_layer()


def horizon_glow() -> tuple[DrawPath, ...]:
    """Readability polish: faint moonlit haze behind head height (lighting only)."""
    return (
        DrawPath(
            (
                PathOp("M", (0, 200)),
                PathOp("L", (360, 200)),
                PathOp("L", (360, 470)),
                PathOp("L", (0, 470)),
                PathOp("Z"),
            ),
            LinearGradient(
                (180, 200),
                (180, 470),
                (
                    (0.0, color("3b4a7a", 0.0)),
                    (0.55, color("3b4a7a", 0.16)),
                    (1.0, color("2a2f55", 0.05)),
                ),
            ),
        ),
        DrawPath(ellipse(275, 120, 120, 120), color("9ab9e8", 0.035)),
    )


def railing_and_floor(camera_x: float, ground_y: float) -> tuple[DrawPath, ...]:
    cmds = []
    rail_p = _depth_parallax(RAIL_MID, ground_y)
    off = -camera_x * rail_p
    start = 15 + (off % 38) - 38
    x = start
    while x <= 400:
        cmds.append(
            v1.line(v1.path(("M", x, RAIL_TOP), ("L", x, RAIL_BASE)), paint=v1.RAIL_DARK, width=2.0)
        )
        cmds.append(DrawPath(ellipse(x, RAIL_TOP, 1.8, 1.2), v1.RAIL_TOP))
        x += 38
    cmds.append(
        v1.line(v1.path(("M", -20, RAIL_MID), ("L", 380, RAIL_MID)), paint=v1.RAIL_DARK, width=1.5)
    )
    cmds.append(
        v1.line(v1.path(("M", -20, RAIL_TOP), ("L", 380, RAIL_TOP)), paint=v1.RAIL_TOP, width=2.0)
    )
    cmds.append(
        v1.shape(
            v1.path(
                ("M", 0, RAIL_BASE), ("L", 360, RAIL_BASE), ("L", 360, 640), ("L", 0, 640), ("Z",)
            ),
            LinearGradient(
                (180, RAIL_BASE),
                (180, 640),
                ((0.0, v1.ROOF_FAR), (0.45, color("161d2a")), (1.0, v1.ROOF_NEAR)),
            ),
        )
    )
    # Moonlight pool on the deck in front of the railing (subtle, improves foot contrast).
    for rx, ry, a in ((230, 60, 0.018), (190, 46, 0.022), (150, 34, 0.025)):
        cmds.append(DrawPath(ellipse(200, 585, rx, ry), color("7692ba", a)))
    for hy in SEAMS:
        cmds.append(v1.line(v1.path(("M", 0, hy), ("L", 360, hy)), paint=v1.ROOF_LINE, width=1.2))
        cmds.append(
            v1.line(
                v1.path(("M", 0, hy + 1), ("L", 360, hy + 1)), paint=v1.ROOF_MOONSHINE, width=0.8
            )
        )
    # Perspective seams: anchored on the ground line so tiles move exactly with the feet.
    g_scale = (640.0 - VP_Y) / (ground_y - VP_Y)
    bottom = [-40.0]
    for i in range(40):
        bottom.append(bottom[-1] + SEAM_PATTERN[i % len(SEAM_PATTERN)])
    period = sum(SEAM_PATTERN)
    # V1 bottom positions expressed on the ground line, then shifted by the camera.
    shift = -camera_x
    for bx in bottom:
        ground_x = VP_X + (bx - VP_X) / g_scale + shift
        for k in range(-3, 4):
            gx = ground_x + k * period / g_scale
            bottom_x = VP_X + (gx - VP_X) * g_scale
            if not -900 <= bottom_x <= 1260:
                continue
            t0 = (RAIL_BASE - VP_Y) / (640.0 - VP_Y)
            x0 = VP_X + t0 * (bottom_x - VP_X)
            if -60 <= x0 <= 420:
                cmds.append(
                    v1.line(
                        v1.path(("M", x0, RAIL_BASE), ("L", bottom_x, 640)),
                        paint=v1.ROOF_LINE,
                        width=1.0,
                    )
                )
    return tuple(_dedupe(cmds))


def _dedupe(cmds):
    seen = set()
    out = []
    for c in cmds:
        key = (c.path, c.fill, c.stroke)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def observatory_background(camera_x: float = 0.0, ground_y: float = 575.0) -> tuple[DrawPath, ...]:
    """All environment layers behind the character for one camera position."""
    finite(camera_x, ground_y)
    return (
        _SKY
        + _STARS
        + _MOON
        + horizon_glow()
        + _tiled(_CITY, -camera_x * 0.10)
        + _shift(_OBSERVATORY, -camera_x * OBSERVATORY_PARALLAX)
        + railing_and_floor(camera_x, ground_y)
    )


def screen_parallax(layer: str) -> float:
    return {"sky": 0.0, "city": 0.10, "observatory": OBSERVATORY_PARALLAX, "ground": 1.0}[layer]


__all__ = ["observatory_background", "railing_and_floor", "horizon_glow", "screen_parallax"]
