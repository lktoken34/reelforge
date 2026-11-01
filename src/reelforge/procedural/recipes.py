"""Original CPU vector construction. No orchard scenery recipe or native graphics imports."""

import math

from .drawing import Palette, Pen, blend, gradient, ink, path
from .planning import BOUNDS, sample


def tree(request, identity, *, simple=False, dry=False):
    dry = dry or request.family == "rocky_shelter"
    p = Pen(BOUNDS["tree"])
    pal = Palette(request)

    def v(channel):
        return sample(request, identity, channel)

    h = (300 + 105 * v("height")) * (0.9 + request.structure * 0.2)
    lean = (v("lean") - 0.5) * (12 + 35 * request.structure)
    shade = pal.dark if dry else blend(pal.wood, pal.dark, 0.55)
    p.poly(
        ((-8, 0), (-5, -h * 0.55), (lean - 3, -h), (lean + 3, -h), (6, -h * 0.4), (10, 0)), shade
    )
    p.line(((-3, -2), (0, -h * 0.55), (lean, -h * 0.94)), blend(pal.wood_light, pal.leaf, 0.3), 1.1)
    for i in range(5):
        yy = -h * (0.32 + i * 0.115)
        side = -1 if i % 2 else 1
        tip = (lean * 0.5 + side * (35 + 25 * v(f"branch_{i}")), yy - 37 - 24 * v(f"rise_{i}"))
        p.line(((1, yy + 20), (side * 20, yy), tip), shade, 3 - i * 0.35)
        if dry:
            continue
        if request.family == "woodland_trail":
            w = (75 - i * 8) * (0.8 + v(f"fan_{i}") * 0.4)
            points = (
                (lean * 0.7, yy - 88),
                (-w * 0.2, yy - 42),
                (-w, yy + 12),
                (-w * 0.6, yy + 8),
                (-w * 0.8, yy + 32),
                (lean * 0.5, yy + 20),
                (w * 0.9, yy + 23),
                (w * 0.65, yy + 5),
                (w, yy + 10),
                (w * 0.25, yy - 48),
            )
            points = tuple(
                (x + (v(f"edge_{i}_{j}") - 0.5) * 14, y + (v(f"edge_y_{i}_{j}") - 0.5) * 13)
                for j, (x, y) in enumerate(points)
            )
            shape = path(points)
            p.poly(points, gradient(blend(pal.leaf, pal.rim, 0.2), pal.leaf, yy - 80, yy + 35))
            p.line(
                ((lean * 0.7 - 4, yy - 80), (-w * 0.18, yy - 40), (-w * 0.7, yy + 3)),
                ink("bdc494", 0.23),
                2,
                clip=shape,
            )
            for j in range(4):
                xx = -w * 0.72 + j * w * 0.41 + v(f"sprig_{i}_{j}") * 9
                yy = yy - 18 + v(f"sprig_y_{i}_{j}") * 22
                p.poly(
                    (
                        (xx - 13, yy + 7),
                        (xx - 5, yy - 7),
                        (xx - 2, yy - 3),
                        (xx + 3, yy - 13),
                        (xx + 5, yy - 5),
                        (xx + 13, yy + 3),
                        (xx + 4, yy + 1),
                        (xx, yy + 9),
                    ),
                    blend(pal.leaf, pal.rim, 0.1 + 0.13 * v(f"needle_{i}_{j}")),
                )
        else:
            w = 40 + 17 * v(f"width_{i}")
            cx = tip[0] * 0.8
            cy = tip[1]
            pts = []
            for j in range(11):
                a = j * math.tau / 11
                r = 0.75 + 0.25 * v(f"leaf_{i}_{j}")
                pts.append((cx + math.cos(a) * w * r, cy + math.sin(a) * w * 0.55 * r))
            p.poly(pts, gradient(pal.rim, pal.leaf, cy - w * 0.5, cy + w * 0.5), True)
    if not simple and request.detail == "rich":
        for i in range(8):
            x = (v(f"bark_x{i}") - 0.5) * 10
            y = -h * v(f"bark_y{i}") * 0.7
            p.line(((x, y), (x + 1, y - 8)), ink("b5ac84", 0.22), 0.6)
    return p.result()


def rock(request, identity, *, large=False):
    p = Pen(BOUNDS["rock"])
    pal = Palette(request)

    def v(c):
        return sample(request, identity, c)

    w = 90 + 55 * v("width")
    h = ((135 if large else 65) + 85 * v("height")) * (0.75 + request.structure * 0.45)
    pts = (
        (-w * 0.6, 0),
        (-w * 0.73, -h * 0.35),
        (-w * 0.43, -h * 0.9),
        (-w * 0.08, -h),
        (w * 0.37, -h * 0.87),
        (w * 0.6, -h * 0.38),
        (w * 0.54, 0),
    )
    pts = tuple(
        (x * (0.88 + 0.22 * v(f"facet_x{i}")), y * (0.91 + 0.16 * v(f"facet_y{i}")))
        for i, (x, y) in enumerate(pts)
    )
    shape = path(pts)
    p.oval(0, 1, w * 0.6, 4, ink("132a2c", 0.22))
    p.poly(pts, gradient(pal.stone_light, pal.stone, -h, 0))
    p.poly(
        (pts[0], pts[2], (-w * 0.1, -h * 0.32), (w * 0.3, 0)),
        blend(pal.stone, pal.dark, 0.34),
        clip=shape,
    )
    p.poly(
        (pts[2], pts[3], pts[4], (w * 0.1, -h * 0.6), (-w * 0.1, -h * 0.32)),
        blend(pal.stone_light, ink("dac3a1"), 0.18),
        clip=shape,
    )
    p.poly(
        (pts[4], pts[5], pts[6], (-w * 0.1, -h * 0.32)), blend(pal.stone, pal.dark, 0.2), clip=shape
    )
    for i in range(3 if request.detail == "standard" else 7):
        x = (v(f"crack_x{i}") - 0.5) * w
        y = -h * (0.1 + 0.7 * v(f"crack_y{i}"))
        p.line(((x, y), (x - 8, y - 8), (x - 5, y - 19)), ink("253c40", 0.45), 0.7, clip=shape)
    for i in range(7):
        y = -h * (0.12 + i * 0.11)
        p.line(((-w * 0.65, y), (0, y - 3), (w * 0.6, y - 7)), ink("d4c5a7", 0.16), 1, clip=shape)
    for i in range(3):
        x = (v(f"chip{i}") - 0.5) * w * 0.9
        y = -h * (0.2 + 0.22 * i)
        p.poly(
            ((x, y), (x + 8, y - 3), (x + 12, y + 1), (x + 3, y + 5)),
            ink("a8aaa0", 0.25),
            clip=shape,
        )
    return p.result()


def doorway(p, x, y, w, h, pal, *, arch=False):
    if arch:
        from reelforge.rendering.model import DrawPath, PathOp

        shape = (
            PathOp("M", (x, y)),
            PathOp("L", (x, y - h * 0.72)),
            PathOp("C", (x, y - h * 1.08, x + w, y - h * 1.08, x + w, y - h * 0.72)),
            PathOp("L", (x + w, y)),
            PathOp("Z"),
        )
        p.add(DrawPath(shape, gradient(ink("071c22"), ink("182e32"), y - h, y)))
    else:
        p.rect(x, y - h, w, h, ink("14272d"))
    p.line(
        ((x - 3, y), (x - 3, y - h - 3), (x + w + 3, y - h - 3)),
        pal.wood_light if not arch else pal.stone_light,
        3,
    )
    p.line(((x + w + 3, y - h - 3), (x + w + 3, y)), ink("273b3d"), 4)


def building(request, identity):
    p = Pen(BOUNDS["building"])
    pal = Palette(request)

    def v(c):
        return sample(request, identity, c)

    w = 70 + 32 * v("width")
    h = 155 + 110 * v("height")
    roof = 20 + 35 * v("roof")
    wall = blend(ink(("897e6b", "787d79", "9a806b")[int(v("material") * 3)]), pal.wood, 0.22)
    front = ((-w * 0.5, 0), (w * 0.35, 0), (w * 0.35, -h), (-w * 0.5, -h))
    shape = path(front)
    p.poly(((-w * 0.55, 0), (w * 0.65, 0), (w * 0.95, 17), (-w * 0.3, 15)), ink("152e32", 0.28))
    p.poly(front, gradient(blend(wall, pal.wood_light, 0.27), wall, -h, 0))
    p.poly(
        ((w * 0.35, 0), (w * 0.7, -16), (w * 0.7, -h - 10), (w * 0.35, -h)),
        blend(wall, pal.dark, 0.48),
    )
    variant = int(v("roof_kind") * 3)
    if variant == 0:
        p.poly(
            ((-w * 0.58, -h), (0, -h - roof), (w * 0.4, -h)), blend(pal.wood_light, pal.stone, 0.4)
        )
        p.poly(
            ((0, -h - roof), (w * 0.33, -h - roof - 8), (w * 0.78, -h - 10), (w * 0.4, -h)),
            pal.dark,
        )
    else:
        p.poly(
            (
                (-w * 0.58, -h),
                (w * 0.32, -h - roof),
                (w * 0.76, -h - roof - 5),
                (w * 0.8, -h + 3),
                (-w * 0.58, -h + 5),
            ),
            blend(pal.stone, pal.dark, 0.55),
        )
    p.line(((-w * 0.48, -h + 2), (w * 0.33, -h + 2)), pal.wood_light, 1.4)
    # Board divisions and structural scars are finite local material detail.
    for i in range(6):
        xx = -w * 0.45 + i * w * 0.13
        p.line(((xx, -h + 6), (xx, 0)), ink("293b3b", 0.35), 0.7, clip=shape)
    for row in range(2):
        for col in range(2):
            x = -w * 0.39 + col * w * 0.38
            y = -h + 23 + row * h * 0.26
            p.rect(x, y, w * 0.2, 26, ink("182e33"))
            p.line(((x - 1, y + 27), (x - 1, y - 1), (x + w * 0.2 + 1, y - 1)), pal.wood_light, 1.4)
            p.poly(
                ((x + 2, y + 2), (x + w * 0.18, y + 5), (x + w * 0.1, y + 19)), ink("819b9f", 0.35)
            )
            if v(f"broken_{row}_{col}") < request.structure:
                p.line(((x, y + 24), (x + w * 0.2, y + 2)), pal.wood, 2)
    doorway(p, -w * 0.19, 0, w * 0.26, min(104, h * 0.4), pal)
    scars = 4 if request.detail == "standard" else 10
    for i in range(scars):
        xx = (v(f"scar_x{i}") - 0.5) * w * 0.75
        yy = -h * v(f"scar_y{i}")
        p.line(((xx, yy), (xx + 5, yy + 9), (xx + 2, yy + 14)), ink("26393a", 0.5), 0.8, clip=shape)
    if request.structure > 0.25:
        for i in range(2):
            xx = -w * 0.44 + i * w * 0.45
            yy = -h * (0.2 + 0.43 * v(f"peel_{i}"))
            patch = (
                (xx, yy),
                (xx + 6, yy - 7),
                (xx + 22, yy - 2),
                (xx + 20, yy + 18),
                (xx + 13, yy + 15),
                (xx + 3, yy + 23),
            )
            p.poly(patch, blend(pal.wood, pal.dark, 0.25), clip=shape)
            for j in range(3):
                p.line(
                    ((xx + 3, yy + j * 6), (xx + 18, yy + j * 6 - 1)),
                    ink("b69c7f", 0.45),
                    0.7,
                    clip=shape,
                )
        p.line(((-w * 0.48, -h - 2), (-w * 0.2, -h - 13)), pal.wood_light, 2)
    return p.result()


def entrance(request, identity):
    p = Pen(BOUNDS["entrance"])
    pal = Palette(request)
    p.poly(
        ((-83, 4), (-70, -133), (-48, -163), (58, -151), (79, -118), (83, 4)),
        gradient(pal.stone_light, pal.stone, -160, 0),
    )
    p.poly(((58, -151), (79, -118), (83, 4), (57, 0), (51, -121)), blend(pal.stone, pal.dark, 0.5))
    p.poly(
        ((-70, -133), (-48, -163), (58, -151), (51, -121)),
        blend(pal.stone_light, ink("dbc095"), 0.25),
    )
    p.line(((-68, -127), (-45, -148), (48, -137)), ink("e3cfaa", 0.55), 2)
    doorway(p, -38, 0, 76, 119, pal, arch=True)
    p.rect(-42, -123, 86, 9, blend(pal.stone, pal.dark, 0.2))
    p.rect(35, -109, 3, 105, ink("d7b77b", 0.48 if pal.warm else 0.15))
    for i in range(5):
        y = -25 - i * 22
        p.line(((-67, y), (-45, y - 3)), ink("36494a", 0.5), 1)
        p.line(((48, y), (68, y - 5)), ink("35494a", 0.5), 1)
    p.line(((-78, 6), (83, 6)), ink("c9bc99", 0.65), 2)
    return p.result()


def sky(plan):
    p = Pen(BOUNDS["sky"])
    pal = Palette(plan.request)
    r = plan.request
    p.rect(-80, -80, 520, 800, gradient(pal.sky_top, pal.sky_bottom, 0, plan.horizon + 30))
    if pal.warm:
        x = 55 + 85 * sample(r, "sky", "sun")
        p.oval(x, plan.horizon - 85, 18, 18, ink("edcd99", 0.75))
    for i in range(5):
        y = 80 + i * 35 + sample(r, "sky", f"cloud{i}") * 20
        p.poly(
            ((-70, y), (45, y - 9), (160, y + 5), (370, y - 16), (430, y + 2), (160, y + 18)),
            ink("b8b9a0", 0.045),
        )
    return p.result()


def backdrop(plan):
    p = Pen(BOUNDS["backdrop"])
    pal = Palette(plan.request)
    for band in range(3):
        y = plan.horizon - 100 + band * 44
        pts = [(-80, 700), (-80, y)]
        for i in range(11):
            xx = -60 + i * 48
            yy = y - 45 * sample(plan.request, f"ridge_{band}", str(i))
            pts.append((xx, yy))
        pts.extend(((470, y + 30), (470, 700)))
        p.poly(
            pts,
            pal.distant(
                pal.stone if plan.request.family == "rocky_shelter" else pal.leaf, 0.1 + band * 0.12
            ),
            plan.request.family != "rocky_shelter",
        )
    return p.result()


def ground(plan):
    r = plan.request
    pal = Palette(r)
    p = Pen(BOUNDS["ground"])
    h = plan.horizon
    pts = (
        [(-90, 700), (-90, h + 26)]
        + [(i * 45, h + 12 + sample(r, "terrain", str(i)) * 16) for i in range(11)]
        + [(460, 700)]
    )
    p.poly(pts, gradient(blend(pal.ground, pal.haze, 0.25), pal.ground, h, 680))
    left = []
    right = []
    for i in range(12):
        y = h + 18 + (680 - h - 18) * i / 11
        x = plan.path_x(y)
        w = plan.half_width(y)
        left.append((x - w, y))
        right.append((x + w, y))
    p.poly(
        tuple(left + list(reversed(right))),
        gradient(blend(pal.path, pal.haze, 0.2), pal.path, h, 670),
        True,
    )
    for side in (-1, 1):
        p.line(
            tuple(
                (plan.path_x(y) + side * plan.half_width(y), y)
                for y in (h + 30, 400, 460, 530, 640)
            ),
            ink("c5b491", 0.17),
            1,
        )
    if r.family == "rocky_shelter":
        x = plan.vanishing_x + 22
        p.poly(
            ((x - 36, 425), (x + 35, 425), (x + 58, 482), (x - 55, 482)),
            ink("d8bc83", 0.11 if pal.warm else 0.04),
        )
    count = 25 + 10 * r.density + (10 if r.detail == "rich" else 0)
    for i in range(count):
        y = h + 35 + (640 - h - 35) * sample(r, f"ground_{i}", "y")
        center = plan.path_x(y)
        w = plan.half_width(y)
        side = -1 if sample(r, f"ground_{i}", "side") < 0.5 else 1
        x = center + side * (w + 15 + sample(r, f"ground_{i}", "x") * 135)
        height = 3 + (y - h) * 0.028
        if r.family == "settlement_street" and i % 3 != 0:
            p.line(((x, y), (x + 7, y - 3), (x + 10, y + 2)), ink("222f30", 0.52), 0.8)
        else:
            scale = height / 12 * (0.65 + 0.55 * sample(r, f"ground_{i}", "size"))
            local = (
                (-1, 0),
                (-1, -0.4),
                (-8, -0.3),
                (-4, -0.65),
                (-7, -0.9),
                (-1, -0.7),
                (1, -1.3),
                (3, -0.7),
                (9, -0.9),
                (5, -0.4),
                (10, -0.25),
                (2, -0.35),
                (1, 0),
            )
            p.poly(
                tuple((x + dx * scale, y + dy * height) for dx, dy in local),
                blend(pal.leaf, pal.rim, 0.1 + 0.2 * sample(r, f"ground_{i}", "tone")),
            )
    for i in range(10 if r.detail == "standard" else 20):
        y = h + 45 + (630 - h - 45) * sample(r, f"track_{i}", "y")
        x = plan.path_x(y) + (sample(r, f"track_{i}", "x") - 0.5) * plan.half_width(y)
        if r.family == "settlement_street":
            center = plan.path_x(y)
            half = plan.half_width(y)
            p.line(
                (
                    (center - half * 0.92, y),
                    (center - half * 0.1, y - 4),
                    (center + half * 0.87, y - 2),
                ),
                ink("d2c7b4", 0.2),
                1,
            )
        else:
            p.line(((x - 3, y), (x + 4, y - 1)), ink("d9c6a1", 0.16), 1)
    # Ground asset origin is the explicit support-plane anchor, not the original farm floor.
    out = Pen(BOUNDS["ground"])
    out.placed(p.result(), -180, -510)
    return out.result()


def distance(plan):
    p = Pen(BOUNDS["distance"])
    pal = Palette(plan.request)
    r = plan.request
    if r.family == "woodland_trail":
        for i in range(17):
            x = -20 + i * 25
            y = plan.horizon + 40
            h = 80 + sample(r, f"distant_{i}", "height") * 100
            c = pal.distant(pal.leaf, 0.35)
            p.poly(((x - 3, y), (x - 2, y - h), (x + 2, y - h), (x + 4, y)), c)
            p.poly(((x, y - h - 15), (x - 18, y - h * 0.3), (x + 21, y - h * 0.35)), c)
    elif r.family == "settlement_street":
        for i in range(7):
            x = -15 + i * 59
            y = plan.horizon + 37
            h = 55 + sample(r, f"distant_{i}", "height") * 85
            c = pal.distant(pal.stone, 0.32)
            p.rect(x, y - h, 38, h, c)
            p.poly(((x - 3, y - h), (x + 17, y - h - 25), (x + 42, y - h)), c)
    else:
        for i in range(5):
            x = -30 + i * 95
            y = plan.horizon + 70
            h = 90 + sample(r, f"distant_{i}", "height") * 65
            p.poly(
                (
                    (x - 45, y),
                    (x - 37, y - h * 0.6),
                    (x, y - h),
                    (x + 45, y - h * 0.7),
                    (x + 64, y),
                ),
                pal.distant(pal.stone, 0.36),
            )
    p.rect(
        -80,
        plan.horizon - 4,
        520,
        65,
        gradient(
            ink("bac2b0", 0.22 * r.atmosphere),
            ink("bac2b0", 0),
            plan.horizon - 4,
            plan.horizon + 61,
        ),
    )
    return p.result()


def foreground(plan):
    r = plan.request
    pal = Palette(r)
    p = Pen(BOUNDS["foreground"])
    if r.family == "woodland_trail":
        for bank, x in (("left", -145 + 120 * r.framing), ("right", 505 - 120 * r.framing)):
            commands = tree(r, "framing_" + bank, simple=True)
            # Reuse the same structural tree primitive with a cool foreground grade.
            from dataclasses import replace

            commands = tuple(
                replace(
                    c,
                    fill=pal.dark if c.fill else None,
                    stroke=replace(c.stroke, paint=pal.dark) if c.stroke else None,
                )
                for c in commands
            )
            p.placed(commands, x, 680, 1.6)
    elif r.family == "settlement_street":
        x = -50 + 46 * r.framing
        p.poly(((x, 640), (x + 15, 640), (x + 18, 125), (x + 2, 116)), pal.dark)
        p.poly(((-40, 100), (45, 120), (125, 97), (139, 108), (44, 141), (-40, 122)), pal.dark)
        p.poly(((355, 640), (373, 640), (372, 390), (356, 394)), pal.dark)
        p.poly(((344, 400), (393, 392), (392, 438), (344, 442)), pal.dark)
    else:
        for bank, x in (("left", -80 + 50 * r.framing), ("right", 440 - 50 * r.framing)):
            from dataclasses import replace

            from reelforge.rendering.model import Color

            def cool(paint):
                if isinstance(paint, Color):
                    return blend(paint, pal.dark, 0.68)
                return replace(paint, stops=tuple((u, cool(c)) for u, c in paint.stops))

            shaded = tuple(
                replace(
                    c,
                    fill=cool(c.fill) if c.fill else None,
                    stroke=replace(c.stroke, paint=cool(c.stroke.paint)) if c.stroke else None,
                )
                for c in rock(r, "framing_" + bank, large=True)
            )
            p.placed(shaded, x, 680, 1.5)
        p.line(((-160, 410), (-65, 280), (24, 177), (35, 120), (52, 84)), pal.dark, 5)
        p.line(((25, 177), (74, 156), (90, 130)), pal.dark, 2)
    return p.result()


def prop(request, identity):
    p = Pen(BOUNDS["prop"])
    pal = Palette(request)
    if "barrel" in identity:
        p.rect(-12, -30, 24, 30, gradient(pal.wood_light, pal.wood, -30, 0))
        p.oval(0, -30, 12, 4, pal.wood_light)
        p.oval(0, -30, 9, 2, pal.dark)
        for x in (-8, -3, 3, 8):
            p.line(((x, -28), (x, 0)), pal.dark, 0.7)
        for y in (-22, -7):
            p.line(((-12, y), (12, y)), pal.stone, 2)
    else:
        p.poly(((-18, 0), (19, 0), (19, -26), (-18, -26)), pal.wood)
        p.poly(((19, 0), (28, -8), (28, -31), (19, -26)), pal.dark)
        p.poly(((-18, -26), (-9, -32), (28, -31), (19, -26)), pal.wood_light)
        for y in (-19, -9):
            p.line(((-17, y), (18, y)), ink("293c39"), 0.8)
        p.line(((-15, -24), (16, -2)), pal.wood_light, 3)
    return p.result()


def geometry(plan, obj):
    kind = obj.recipe
    r = plan.request
    if kind == "tree":
        return tree(r, obj.id)
    if kind == "building":
        return building(r, obj.id)
    if kind == "rock":
        return rock(r, obj.id, large=True)
    if kind == "prop":
        return prop(r, obj.id)
    if kind == "entrance":
        return entrance(r, obj.id)
    return {
        "sky": sky,
        "ground": ground,
        "backdrop": backdrop,
        "distance": distance,
        "foreground": foreground,
    }[kind](plan)
