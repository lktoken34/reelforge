"""Moonlit Observatory Rooftop: original code-authored 2D/2.5D cinematic environment.

Pure vector geometry rendering via ReelForge DrawPath, PathOp, LinearGradient,
Color and Stroke primitives. Provides layered background, midground, and
foreground depth stages with dynamic contact shadow support.
"""

from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import (
    DrawPath,
    LinearGradient,
    PathOp,
    Stroke,
    finite,
)

# Environment Palette
SKY_TOP = color("060914")
SKY_MID = color("120f29")
SKY_HORIZON = color("24173d")

MOON_WHITE = color("f6f9ff")
MOON_SILVER = color("cddaf0")
WHITE = color("ffffff")
MOON_CRATER = color("adc2de", 0.42)
MOON_GLOW_1 = color("9ab9e8", 0.12)
MOON_GLOW_2 = color("7598cf", 0.06)

STAR_WHITE = color("ffffff")
STAR_PALE = color("d0e2ff", 0.65)

DISTANT_CITY = color("15172b")
DISTANT_WINDOW = color("ffd97d", 0.45)
MID_CITY = color("0e111f")
HAZE_VIOLET = color("281d3b", 0.60)

DOME_MAIN = color("161b2e")
DOME_DARK = color("0d101c")
DOME_RIM = color("6f84a6")
DOME_RIB = color("3d4b63")
TELESCOPE_BRONZE = color("4a5266")
TELESCOPE_HIGHLIGHT = color("9cb0cc")

RAIL_TOP = color("8ea3c4")
RAIL_DARK = color("1c2436")

ROOF_NEAR = color("111622")
ROOF_FAR = color("1c2433")
ROOF_LINE = color("0c0f17")
ROOF_MOONSHINE = color("7692ba", 0.18)


def path(*ops) -> tuple[PathOp, ...]:
    return tuple(PathOp(op[0], tuple(op[1:])) for op in ops)


def shape(outline, fill, *, stroke_color=None, stroke_width=1.0):
    stroke = Stroke(stroke_color, stroke_width) if stroke_color else None
    return DrawPath(outline, fill, stroke)


def line(outline, paint=RAIL_DARK, width=1.0, cap="round", join="round"):
    return DrawPath(outline, stroke=Stroke(paint, width, cap=cap, join=join))


def grad(c1, c2, start=(0, 0), end=(0, 100)):
    return LinearGradient(start, end, ((0.0, c1), (1.0, c2)))


def make_sky_layer() -> tuple[DrawPath, ...]:
    """Generates the nocturnal atmospheric gradient sky."""
    return (
        shape(
            path(
                ("M", 0, 0),
                ("L", 360, 0),
                ("L", 360, 480),
                ("L", 0, 480),
                ("Z",),
            ),
            LinearGradient(
                (180, 0),
                (180, 480),
                ((0.0, SKY_TOP), (0.55, SKY_MID), (1.0, SKY_HORIZON)),
            ),
        ),
    )


def make_starfield() -> tuple[DrawPath, ...]:
    """Scatters code-defined star specks across the upper heavens."""
    # Deterministic fixed star coordinates (x, y, radius, alpha)
    stars_data = (
        (25, 45, 1.2, 0.8),
        (48, 85, 0.9, 0.5),
        (82, 35, 1.5, 0.9),
        (115, 70, 0.8, 0.4),
        (138, 25, 1.1, 0.7),
        (165, 90, 0.7, 0.5),
        (195, 40, 1.3, 0.85),
        (220, 65, 0.8, 0.4),
        (35, 140, 1.0, 0.6),
        (70, 175, 0.7, 0.4),
        (110, 130, 1.2, 0.75),
        (145, 160, 0.9, 0.5),
        (15, 210, 0.8, 0.4),
        (55, 240, 1.1, 0.6),
        (95, 220, 0.7, 0.5),
        (320, 40, 1.4, 0.8),
        (345, 80, 0.9, 0.6),
        (335, 160, 1.1, 0.7),
        (350, 220, 0.8, 0.5),
        (180, 130, 0.7, 0.4),
    )
    cmds = []
    for x, y, r, a in stars_data:
        cmds.append(DrawPath(ellipse(x, y, r, r), color("ffffff", a)))
    return tuple(cmds)


def make_moon_layer() -> tuple[DrawPath, ...]:
    """Generates the glowing celestial moon with craters and aura."""
    mx, my, mr = 275.0, 120.0, 42.0
    return (
        # Outer celestial auras
        DrawPath(ellipse(mx, my, mr + 38, mr + 38), MOON_GLOW_2),
        DrawPath(ellipse(mx, my, mr + 20, mr + 20), MOON_GLOW_1),
        # Solid lunar body
        shape(
            ellipse(mx, my, mr, mr),
            LinearGradient(
                (mx - mr, my - mr),
                (mx + mr, my + mr),
                ((0.0, MOON_WHITE), (1.0, MOON_SILVER)),
            ),
            stroke_color=color("c8daf2", 0.5),
            stroke_width=1.0,
        ),
        # Subtle lunar maria / crater formations
        DrawPath(ellipse(mx - 14, my - 8, 11, 8), MOON_CRATER),
        DrawPath(ellipse(mx + 8, my + 14, 13, 10), MOON_CRATER),
        DrawPath(ellipse(mx - 6, my + 18, 9, 7), MOON_CRATER),
        DrawPath(ellipse(mx + 16, my - 12, 7, 6), MOON_CRATER),
    )


def make_city_skyline() -> tuple[DrawPath, ...]:
    """Generates two silhouette skyline tiers with glowing window specks and haze."""
    cmds = []

    # Layer 1: Distant City Tier
    dist_skyline = (
        ("M", 0, 440),
        ("L", 0, 340),
        ("L", 28, 340),
        ("L", 28, 310),
        ("L", 42, 310),
        ("L", 42, 340),
        ("L", 65, 340),
        ("L", 65, 325),
        ("L", 80, 325),
        ("L", 80, 355),
        ("L", 110, 355),
        ("L", 110, 295),
        ("L", 125, 295),
        ("L", 130, 270),
        ("L", 135, 295),
        ("L", 145, 295),
        ("L", 145, 360),
        ("L", 175, 360),
        ("L", 175, 320),
        ("L", 195, 320),
        ("L", 195, 360),
        ("L", 220, 360),
        ("L", 220, 305),
        ("L", 240, 305),
        ("L", 240, 350),
        ("L", 280, 350),
        ("L", 280, 330),
        ("L", 305, 330),
        ("L", 305, 355),
        ("L", 330, 355),
        ("L", 330, 315),
        ("L", 360, 315),
        ("L", 360, 440),
        ("Z",),
    )
    cmds.append(shape(path(*dist_skyline), DISTANT_CITY))

    # Tiny warm glowing windows on distant towers
    for wx, wy in (
        (34, 320),
        (34, 328),
        (118, 305),
        (118, 315),
        (118, 325),
        (185, 330),
        (185, 340),
        (228, 315),
        (228, 325),
        (290, 338),
    ):
        cmds.append(DrawPath(ellipse(wx, wy, 1.4, 2.0), DISTANT_WINDOW))

    # Layer 2: Midground City Tier (Darker, closer)
    mid_skyline = (
        ("M", 0, 455),
        ("L", 0, 385),
        ("L", 35, 385),
        ("L", 35, 365),
        ("L", 55, 365),
        ("L", 55, 395),
        ("L", 85, 395),
        ("L", 85, 350),
        ("L", 100, 350),
        ("L", 100, 390),
        ("L", 150, 390),
        ("L", 150, 340),
        ("L", 170, 340),
        ("L", 170, 395),
        ("L", 205, 395),
        ("L", 205, 370),
        ("L", 230, 370),
        ("L", 230, 400),
        ("L", 260, 400),
        ("L", 260, 355),
        ("L", 275, 355),
        ("L", 275, 395),
        ("L", 310, 395),
        ("L", 310, 365),
        ("L", 335, 365),
        ("L", 335, 400),
        ("L", 360, 400),
        ("L", 360, 455),
        ("Z",),
    )
    cmds.append(shape(path(*mid_skyline), MID_CITY))

    # Atmospheric fog haze across horizon
    cmds.append(
        shape(
            path(("M", 0, 390), ("L", 360, 390), ("L", 360, 460), ("L", 0, 460), ("Z",)),
            LinearGradient(
                (180, 390),
                (180, 460),
                ((0.0, color("281d3b", 0.0)), (0.6, HAZE_VIOLET), (1.0, color("1c2436", 0.8))),
            ),
        )
    )

    return tuple(cmds)


def make_observatory_layer() -> tuple[DrawPath, ...]:
    """Generates the observatory dome and celestial telescope."""
    cmds = []
    # Dome Base Cylinder
    cmds.append(
        shape(
            path(
                ("M", 15, 415),
                ("L", 105, 415),
                ("L", 105, 460),
                ("L", 15, 460),
                ("Z",),
            ),
            grad(DOME_MAIN, DOME_DARK, start=(15, 415), end=(105, 460)),
            stroke_color=DOME_DARK,
            stroke_width=1.0,
        )
    )
    # Hemispherical Dome Top
    cmds.append(
        shape(
            path(
                ("M", 15, 415),
                ("C", 15, 355, 105, 355, 105, 415),
                ("Z",),
            ),
            LinearGradient(
                (60, 360),
                (60, 415),
                ((0.0, DOME_RIM), (0.35, DOME_MAIN), (1.0, DOME_DARK)),
            ),
            stroke_color=DOME_DARK,
            stroke_width=1.2,
        )
    )
    # Dome structural ribs
    cmds.append(
        line(path(("M", 38, 415), ("C", 40, 375, 60, 365, 60, 365)), paint=DOME_RIB, width=1.1)
    )
    cmds.append(
        line(path(("M", 82, 415), ("C", 80, 375, 60, 365, 60, 365)), paint=DOME_RIB, width=1.1)
    )

    # Telescope Slit / Shutter opening
    cmds.append(
        shape(
            path(("M", 52, 415), ("L", 52, 366), ("L", 68, 366), ("L", 68, 415), ("Z",)),
            color("080a12"),
        )
    )

    # Refractor Telescope barrel extending outward toward moon
    # Angled ~35 degrees up-right
    cmds.append(
        shape(
            path(
                ("M", 56, 395),
                ("L", 88, 355),
                ("L", 94, 360),
                ("L", 62, 400),
                ("Z",),
            ),
            LinearGradient(
                (56, 400),
                (94, 355),
                ((0.0, TELESCOPE_BRONZE), (0.6, TELESCOPE_HIGHLIGHT), (1.0, DOME_DARK)),
            ),
            stroke_color=DOME_DARK,
            stroke_width=1.0,
        )
    )
    # Telescope lens rim
    cmds.append(line(path(("M", 87, 354), ("L", 95, 361)), paint=WHITE, width=1.4))

    return tuple(cmds)


def make_railing_and_floor() -> tuple[DrawPath, ...]:
    """Generates the rooftop floor with perspective seams and metal perimeter railing."""
    cmds = []

    # 1. Rooftop safety railing
    rail_y_top = 445.0
    rail_y_mid = 458.0
    rail_y_base = 472.0

    # Stanchions / vertical posts
    for rx in range(15, 355, 38):
        cmds.append(
            line(path(("M", rx, rail_y_top), ("L", rx, rail_y_base)), paint=RAIL_DARK, width=2.0)
        )
        # Moonlight rim on top cap of post
        cmds.append(DrawPath(ellipse(rx, rail_y_top, 1.8, 1.2), RAIL_TOP))

    # Horizontal rails
    cmds.append(
        line(path(("M", 0, rail_y_mid), ("L", 360, rail_y_mid)), paint=RAIL_DARK, width=1.5)
    )
    cmds.append(line(path(("M", 0, rail_y_top), ("L", 360, rail_y_top)), paint=RAIL_TOP, width=2.0))

    # 2. Rooftop floor slab
    cmds.append(
        shape(
            path(
                ("M", 0, rail_y_base),
                ("L", 360, rail_y_base),
                ("L", 360, 640),
                ("L", 0, 640),
                ("Z",),
            ),
            LinearGradient(
                (180, rail_y_base),
                (180, 640),
                ((0.0, ROOF_FAR), (0.45, color("161d2a")), (1.0, ROOF_NEAR)),
            ),
        )
    )

    # Perspective tile lines (receding toward central vanishing point)
    # Horizontal seams
    for hy in (488, 508, 532, 562, 600, 640):
        cmds.append(line(path(("M", 0, hy), ("L", 360, hy)), paint=ROOF_LINE, width=1.2))
        # Subtle moonlight edge highlight on tiles
        cmds.append(
            line(path(("M", 0, hy + 1), ("L", 360, hy + 1)), paint=ROOF_MOONSHINE, width=0.8)
        )

    # Perspective diagonal seams
    vp_x, vp_y = 180.0, 390.0
    for bx in (-40, 30, 100, 180, 260, 330, 400):
        # Ray from vanishing point to bottom
        dx = bx - vp_x
        dy = 640.0 - vp_y
        # Start at rail_y_base
        t_start = (rail_y_base - vp_y) / dy
        x_start = vp_x + t_start * dx
        cmds.append(
            line(path(("M", x_start, rail_y_base), ("L", bx, 640)), paint=ROOF_LINE, width=1.0)
        )

    return tuple(cmds)


def make_contact_shadow(
    char_x: float = 180.0,
    char_y: float = 530.0,
    scale: float = 1.0,
    alpha: float = 0.45,
) -> tuple[DrawPath, ...]:
    """Renders soft realistic vector contact shadows on the rooftop pavers."""
    finite(char_x, char_y, scale, alpha)
    clamped_alpha = max(0.0, min(1.0, alpha))
    if clamped_alpha < 0.02:
        return ()

    rx_far = 14.0 * scale
    ry_far = 3.6 * scale
    rx_near = 16.0 * scale
    ry_near = 4.0 * scale

    shadow_col = color("04060a", clamped_alpha)
    shadow_soft = color("04060a", clamped_alpha * 0.45)

    return (
        # Soft outer penumbra
        DrawPath(ellipse(char_x - 7, char_y + 1, rx_far * 1.35, ry_far * 1.35), shadow_soft),
        DrawPath(ellipse(char_x + 7, char_y + 1, rx_near * 1.35, ry_near * 1.35), shadow_soft),
        # Darker core umbra
        DrawPath(ellipse(char_x - 7, char_y + 1, rx_far, ry_far), shadow_col),
        DrawPath(ellipse(char_x + 7, char_y + 1, rx_near, ry_near), shadow_col),
    )


# Pre-assembled static environment layers (everything behind the character)
STATIC_ENVIRONMENT: tuple[DrawPath, ...] = (
    make_sky_layer()
    + make_starfield()
    + make_moon_layer()
    + make_city_skyline()
    + make_observatory_layer()
    + make_railing_and_floor()
)


def draw_observatory_rooftop(
    shadow_scale: float = 1.0,
    shadow_alpha: float = 0.45,
    char_x: float = 180.0,
    ground_y: float = 530.0,
) -> tuple[DrawPath, ...]:
    """Returns all environment drawing commands including dynamic contact shadows."""
    shadows = make_contact_shadow(char_x, ground_y, shadow_scale, shadow_alpha)
    return STATIC_ENVIRONMENT + shadows
