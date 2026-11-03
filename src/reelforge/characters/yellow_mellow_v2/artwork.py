"""Code-authored vector artwork for Yellow Mellow V2.

All geometry is generated from a solved ``RigState`` in canonical character space and placed
with one final ``Transform`` (stage position, character scale, mirror). The hoodie is skinned
between the spine and chest frames, sleeves and hands follow the arm bones, shorts cuffs
follow the thighs and shoes roll with the solved foot. No raster input, sprites or tracing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from reelforge.characters.rig import Rigid
from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import DrawPath, LinearGradient, PathOp, Stroke, Transform

from .expressions import FaceState
from .rig import (
    ANKLE_HEIGHT,
    CHEST_LEN,
    HEAD_RX,
    HEAD_RY,
    SIDE_OUT,
    SPINE_LEN,
    RigState,
    lerp,
    shoe_extent,
    smoothstep,
)

# --- Palette (V1 identity colours, refined) ---
INK = color("0d0f12")
HEAD_BLACK = color("0b0c0f")
HEAD_SHEEN = color("2a3140", 0.55)
RIM = color("b5cdf5", 0.62)
EDGE = color("34436a", 0.85)
WHITE = color("ffffff")
EYE_GLOW = color("dcebff", 0.22)
GOLD_HI = color("ffd659")
GOLD = color("f5b821")
GOLD_MID = color("e8a815")
GOLD_SHADOW = color("c98c0c")
GOLD_DARK = color("8e5e05")
GOLD_FOLD = color("b37a08", 0.55)
RED_HI = color("ff5a4f")
RED = color("dc2626")
RED_MID = color("bf1d1d")
RED_DARK = color("8c1212")
RED_LINE = color("6e0c0c")
RED_RIB = color("ff7b70", 0.55)
SHORTS = color("2b2e35")
SHORTS_DARK = color("1a1c21")
SHOE = color("17191e")
SHOE_HI = color("4a5263", 0.6)
MOUTH = color("3a1517")
TONGUE = color("d0535e")


FRONT_VIEW_LIMIT = 0.45  # below this facing magnitude the far arm draws in front of the torso


def P(*ops) -> tuple[PathOp, ...]:
    return tuple(PathOp(op[0], tuple(float(v) for v in op[1:])) for op in ops)


def map_ops(ops, fn) -> tuple[PathOp, ...]:
    """Apply a point mapping to every coordinate pair of a path."""
    out = []
    for op in ops:
        pts = op.points
        mapped = []
        for i in range(0, len(pts), 2):
            mapped.extend(fn((pts[i], pts[i + 1])))
        out.append(PathOp(op.kind, tuple(mapped)))
    return tuple(out)


def rigid_ops(frame: Rigid, ops) -> tuple[PathOp, ...]:
    return map_ops(ops, frame.point)


def fill(ops, paint, stroke=None, width=1.0, clip=None) -> DrawPath:
    return DrawPath(ops, paint, Stroke(stroke, width) if stroke is not None else None, clip=clip)


def stroke(ops, paint, width=1.0, cap="round") -> DrawPath:
    return DrawPath(ops, stroke=Stroke(paint, width, "round", cap))


def vgrad(top, bottom, *stops) -> LinearGradient:
    return LinearGradient(top, bottom, tuple(stops))


@dataclass(frozen=True)
class Placement:
    """Where canonical character space lands in logical frame units."""

    x: float
    ground_y: float
    scale: float
    sign: int

    def transform(self) -> Transform:
        return Transform(self.x, self.ground_y, 0.0, self.sign * self.scale, self.scale)


# ---------------------------------------------------------------- limbs
def limb(points, width, *, edge=True) -> tuple[DrawPath, ...]:
    ops = [("M", *points[0])] + [("L", *p) for p in points[1:]]
    path = P(*ops)
    out = []
    if edge:
        out.append(stroke(path, EDGE, width + 1.5))
    out.append(stroke(path, INK, width))
    return tuple(out)


def leg_commands(state: RigState, side: str) -> tuple[DrawPath, ...]:
    leg = state.legs[side]
    cmds = list(limb((leg.hip, leg.knee, leg.ankle), 3.0))
    cmds += shoe_commands(state, side)
    return tuple(cmds)


def shorts_cuff(state: RigState, side: str) -> tuple[DrawPath, ...]:
    leg = state.legs[side]
    hx, hy = leg.hip
    kx, ky = leg.knee
    d = math.hypot(kx - hx, ky - hy) or 1.0
    ux, uy = (kx - hx) / d, (ky - hy) / d
    nx, ny = uy, -ux
    outward = 1.0 if (hx > 0) else -1.0
    if nx * outward < 0:
        nx, ny = -nx, -ny
    top_w, bot_w, length = 5.6, 5.0, 9.5
    top = (hx - ux * 3.5, hy - uy * 3.5)
    end = (hx + ux * length, hy + uy * length)
    quad = P(
        ("M", top[0] + nx * top_w, top[1] + ny * top_w),
        ("L", end[0] + nx * bot_w, end[1] + ny * bot_w),
        (
            "C",
            end[0] + ux * 1.2,
            end[1] + uy * 1.2,
            end[0] + ux * 1.2,
            end[1] + uy * 1.2,
            end[0] - nx * bot_w,
            end[1] - ny * bot_w,
        ),
        ("L", top[0] - nx * top_w, top[1] - ny * top_w),
        ("Z",),
    )
    stripe = P(
        ("M", top[0] + nx * (top_w - 1.1), top[1] + ny * (top_w - 1.1)),
        ("L", end[0] + nx * (bot_w - 1.0), end[1] + ny * (bot_w - 1.0)),
    )
    hem = P(
        ("M", end[0] + nx * bot_w * 0.95, end[1] + ny * bot_w * 0.95),
        ("L", end[0] - nx * bot_w * 0.95, end[1] - ny * bot_w * 0.95),
    )
    return (
        DrawPath(quad, SHORTS, Stroke(EDGE, 2.0)),
        fill(quad, SHORTS, SHORTS_DARK, 0.9),
        stroke(hem, SHORTS_DARK, 1.0),
        stroke(stripe, WHITE, 0.95),
    )


def shorts_body(state: RigState) -> tuple[DrawPath, ...]:
    pelvis = state.joints["pelvis"]
    body = rigid_ops(
        pelvis,
        P(
            ("M", -14.5, -6),
            ("L", 14.5, -6),
            ("C", 15.5, -1, 15.5, 3, 15, 7),
            ("L", 3, 8.5),
            ("C", 1.5, 6, -1.5, 6, -3, 8.5),
            ("L", -15, 7),
            ("C", -15.5, 3, -15.5, -1, -14.5, -6),
            ("Z",),
        ),
    )
    return (fill(body, SHORTS, SHORTS_DARK, 0.9),)


def shoe_commands(state: RigState, side: str) -> tuple[DrawPath, ...]:
    heel, toe = shoe_extent(state.f)
    leg = state.legs[side]
    frame = Rigid(leg.ankle[0], leg.ankle[1], leg.foot_angle)
    s = ANKLE_HEIGHT
    shape = P(
        ("M", -heel + 2.5, s),
        ("C", -heel - 0.6, s, -heel - 1.2, 1.2, -heel + 1.0, -1.4),
        ("C", -heel + 3.0, -3.6, -2.0, -3.8, 1.5, -3.0),
        ("C", toe - 3.5, -2.6, toe + 1.6, -0.4, toe + 0.6, 3.0),
        ("C", toe + 0.1, s, toe - 1.5, s, toe - 2.8, s),
        ("Z",),
    )
    sole = P(("M", -heel + 1.8, s - 0.45), ("L", toe - 1.6, s - 0.45))
    light = 1.0 if state.sign > 0 else -1.0  # moonlight from world +X
    shine_x = toe - 4.0 if light > 0 else -heel + 3.5
    shine = ellipse(shine_x, -1.0, 2.6, 1.0)
    return (
        DrawPath(rigid_ops(frame, shape), SHOE, Stroke(EDGE, 2.2)),
        DrawPath(rigid_ops(frame, shape), SHOE, Stroke(INK, 0.9)),
        stroke(rigid_ops(frame, sole), WHITE, 1.5, cap="round"),
        fill(rigid_ops(frame, shine), SHOE_HI),
    )


def sleeve_commands(state: RigState, side: str) -> tuple[DrawPath, ...]:
    sh = state.joints[f"{side}_shoulder"]
    sway = state.secondary.sleeve * (1 if side == "near" else -1)
    # Slim raglan sleeve: rounded cap inside the hoodie edge, tapering to a ribbed cuff.
    tube = P(
        ("M", -4.9, 0.0),
        ("C", -5.2, 4.0, -4.5 + sway, 8.0, -3.9 + sway, 10.6),
        ("L", 3.9 + sway, 10.6),
        ("C", 4.5 + sway, 8.0, 5.2, 4.0, 4.9, 0.0),
        ("C", 4.4, -4.6, -4.4, -4.6, -4.9, 0.0),
        ("Z",),
    )
    cuff = P(
        ("M", -4.2 + sway, 9.8),
        ("L", 4.2 + sway, 9.8),
        ("C", 4.4 + sway, 11.0, 4.2 + sway, 12.2, 3.7 + sway, 12.8),
        ("L", -3.7 + sway, 12.8),
        ("C", -4.2 + sway, 12.2, -4.4 + sway, 11.0, -4.2 + sway, 9.8),
        ("Z",),
    )
    fold = P(("M", -2.8, 4.6), ("C", -0.8, 5.8, 1.2, 5.6, 3.0, 4.0))
    paint = vgrad(sh.point((0, -4)), sh.point((0, 12)), (0.0, GOLD), (1.0, GOLD_MID))
    elbow = state.joints[f"{side}_elbow"]
    wrist = state.joints[f"{side}_wrist"]
    stick_start = sh.point((0, 11.5))
    cmds = list(limb((stick_start, (elbow.x, elbow.y), (wrist.x, wrist.y)), 2.7))
    cmds += [
        fill(rigid_ops(sh, tube), paint, GOLD_DARK, 0.95),
        stroke(rigid_ops(sh, fold), GOLD_FOLD, 0.7),
        fill(rigid_ops(sh, cuff), GOLD_SHADOW, GOLD_DARK, 0.85),
    ]
    for x in (-2.4, -0.8, 0.8, 2.4):
        rib = P(("M", x + sway, 10.3), ("L", x + sway, 12.3))
        cmds.append(stroke(rigid_ops(sh, rib), GOLD_DARK, 0.4))
    return tuple(cmds)


def hand_commands(state: RigState, side: str) -> tuple[DrawPath, ...]:
    arm = state.pose.arm(side)
    w = state.joints[f"{side}_wrist"]
    thumb = SIDE_OUT[side]
    shapes = []
    if arm.hand == "open":
        shapes.append(ellipse(0, 5.4, 5.0, 6.0))
        shapes.append(ellipse(thumb * 4.9, 2.6, 2.2, 2.6))
    elif arm.hand == "fist":
        shapes.append(ellipse(0, 4.4, 4.6, 4.6))
        shapes.append(ellipse(thumb * 3.0, 2.6, 2.0, 2.0))
    elif arm.hand == "point":
        shapes.append(ellipse(0, 4.4, 4.4, 4.6))
        shapes.append(
            P(
                ("M", -1.5, 6),
                ("L", -1.5, 12.5),
                ("C", -1.5, 14.6, 1.5, 14.6, 1.5, 12.5),
                ("L", 1.5, 6),
                ("Z",),
            )
        )
        shapes.append(ellipse(thumb * 3.1, 2.4, 1.9, 2.0))
    else:
        shapes.append(ellipse(0, 4.8, 4.5, 5.3))
        shapes.append(ellipse(thumb * 3.6, 2.5, 2.0, 2.4))
    cmds = [DrawPath(rigid_ops(w, s), INK, Stroke(EDGE, 1.8)) for s in shapes]
    cmds += [DrawPath(rigid_ops(w, s), INK) for s in shapes]
    return tuple(cmds)


def arm_commands(state: RigState, side: str) -> tuple[DrawPath, ...]:
    return sleeve_commands(state, side) + hand_commands(state, side)


# ---------------------------------------------------------------- torso
def _skin(state: RigState, squash: float):
    spine = state.joints["spine"]
    chest = state.joints["chest"]
    stretch = 1 + squash
    widen = 1 - 0.55 * squash
    hem_x, hem_y = state.secondary.hem_x, state.secondary.hem_y

    def mapping(p):
        x, y = p[0] * widen, p[1] * stretch
        if p[1] > 0:  # hem follow-through
            x += hem_x * (p[1] / 8.0)
            y += hem_y * (p[1] / 8.0)
        w = smoothstep((-p[1] - 10.0) / 16.0)
        a = spine.point((x, y))
        b = chest.point((x, y + SPINE_LEN * stretch))
        return lerp(a[0], b[0], w), lerp(a[1], b[1], w)

    return mapping


def torso_commands(state: RigState) -> tuple[DrawPath, ...]:
    pose = state.pose
    f = state.f
    light = 1.0 if state.sign > 0 else -1.0
    skin = _skin(state, pose.squash)
    shift = 3.2 * f
    outline = P(
        ("M", -20.5, 6.0),
        ("C", -23.2, -2.0, -23.8, -14.0, -21.6, -24.0),
        ("C", -20.6, -30.0, -19.0, -34.5, -14.0, -36.8),
        ("C", -8.0, -39.0, 8.0, -39.0, 14.0, -36.8),
        ("C", 19.0, -34.5, 20.6, -30.0, 21.6, -24.0),
        ("C", 23.8, -14.0, 23.2, -2.0, 20.5, 6.0),
        ("C", 12.0, 8.8, -12.0, 8.8, -20.5, 6.0),
        ("Z",),
    )
    body = map_ops(outline, skin)
    top = skin((0, -38))
    bottom = skin((0, 8))
    paint = vgrad(top, bottom, (0.0, GOLD_HI), (0.35, GOLD), (0.8, GOLD_MID), (1.0, GOLD_SHADOW))
    cmds = [
        DrawPath(body, GOLD, Stroke(EDGE, 2.4)),
        fill(body, paint, GOLD_DARK, 1.15),
    ]
    # Away-from-light side shading and the visible side panel in three-quarter view.
    dark = -light
    side_w = 5.0 + 4.0 * f
    shade = P(
        ("M", dark * 21.0, -26.0),
        ("C", dark * 23.0, -16.0, dark * 23.0, -4.0, dark * 20.3, 5.6),
        (
            "C",
            dark * (20.3 - side_w * 0.8),
            6.6,
            dark * (20.3 - side_w),
            6.4,
            dark * (21 - side_w),
            4.0,
        ),
        ("C", dark * (22.0 - side_w), -6.0, dark * (22.0 - side_w), -16.0, dark * 21.0, -26.0),
        ("Z",),
    )
    cmds.append(fill(map_ops(shade, skin), color("b07a06", 0.42)))
    glow = P(
        ("M", light * 14.5, -35.5),
        ("C", light * 19.5, -33.0, light * 21.5, -26.0, light * 21.6, -18.0),
        ("C", light * 19.6, -24.0, light * 17.5, -30.0, light * 14.5, -35.5),
        ("Z",),
    )
    cmds.append(fill(map_ops(glow, skin), color("fff1b8", 0.55)))
    # Fabric folds (subtle).
    for ops in (
        P(
            ("M", -15.5 + shift, -21.0),
            ("C", -13.0 + shift, -18.5, -12.0 + shift, -16.0, -12.5 + shift, -13.5),
        ),
        P(
            ("M", 15.5 + shift, -21.0),
            ("C", 13.0 + shift, -18.5, 12.0 + shift, -16.0, 12.5 + shift, -13.5),
        ),
        P(("M", -17.5, 0.5), ("C", -15.0, -1.5, -13.5, -1.0, -12.0, 1.5)),
    ):
        cmds.append(stroke(map_ops(ops, skin), GOLD_FOLD, 0.85))
    # Ribbed hem band.
    band = P(
        ("M", -20.8, 1.6),
        ("C", -12.0, 4.4, 12.0, 4.4, 20.8, 1.6),
        ("L", 20.5, 6.0),
        ("C", 12.0, 8.8, -12.0, 8.8, -20.5, 6.0),
        ("Z",),
    )
    cmds.append(fill(map_ops(band, skin), GOLD_SHADOW, GOLD_DARK, 0.9))
    for i in range(-9, 10):
        x = i * 2.15
        y0 = 1.6 + 2.8 * (1 - (x / 21.0) ** 2)
        tick = P(("M", x, y0 + 0.6), ("L", x, y0 + 3.6))
        cmds.append(stroke(map_ops(tick, skin), GOLD_DARK, 0.4))
    # Kangaroo pocket.
    pocket = P(
        ("M", -9.5 + shift, -13.5),
        ("L", 9.5 + shift, -13.5),
        ("C", 11.0 + shift, -9.0, 12.8 + shift, -4.0, 13.4 + shift, 0.6),
        ("C", 6.0 + shift, 1.6, -6.0 + shift, 1.6, -13.4 + shift, 0.6),
        ("C", -12.8 + shift, -4.0, -11.0 + shift, -9.0, -9.5 + shift, -13.5),
        ("Z",),
    )
    pocket_paint = vgrad(skin((0, -14)), skin((0, 2)), (0.0, GOLD_MID), (1.0, GOLD_SHADOW))
    cmds.append(fill(map_ops(pocket, skin), pocket_paint, GOLD_DARK, 1.0))
    for sgn in (-1, 1):
        opening = P(
            ("M", sgn * 9.5 + shift, -13.0),
            ("C", sgn * 9.0 + shift, -8.5, sgn * 10.5 + shift, -4.0, sgn * 13.0 + shift, 0.0),
        )
        cmds.append(stroke(map_ops(opening, skin), GOLD_DARK, 1.2))
    seam = P(("M", -8.8 + shift, -12.3), ("L", 8.8 + shift, -12.3))
    cmds.append(stroke(map_ops(seam, skin), color("ffe08a", 0.6), 0.6))
    cmds += drawstring_commands(state, skin, shift)
    return tuple(cmds)


def drawstring_commands(state, skin, shift) -> list[DrawPath]:
    out = []
    swing = state.secondary.strings
    for sgn in (-1, 1):
        x0 = sgn * 3.6 + shift
        start = skin((x0, -35.0))
        length = 14.0
        ang = swing + sgn * 0.05
        end = (start[0] - math.sin(ang) * length, start[1] + math.cos(ang) * length)
        mid = (start[0] - math.sin(ang * 0.5) * length * 0.55, start[1] + length * 0.55)
        ops = P(("M", *start), ("C", *mid, *mid, *end))
        out.append(stroke(ops, color("e9edf2"), 1.5))
        out.append(fill(ellipse(end[0], end[1] + 1.1, 1.05, 1.7), WHITE, INK, 0.45))
        out.append(fill(ellipse(start[0], start[1] + 0.3, 1.2, 1.2), color("8e5e05")))
    return out


def hood_commands(state: RigState) -> tuple[DrawPath, ...]:
    chest = state.joints["chest"]
    stretch = 1 + state.pose.squash
    y = -CHEST_LEN * stretch + 2.0
    hood = P(
        ("M", -16.5, y + 2.0),
        ("C", -17.5, y - 6.5, -9.0, y - 9.0, 0.0, y - 9.0),
        ("C", 9.0, y - 9.0, 17.5, y - 6.5, 16.5, y + 2.0),
        ("C", 10.0, y + 5.5, -10.0, y + 5.5, -16.5, y + 2.0),
        ("Z",),
    )
    inner = P(
        ("M", -11.5, y + 0.5),
        ("C", -10.5, y - 5.0, 10.5, y - 5.0, 11.5, y + 0.5),
        ("C", 6.0, y + 2.5, -6.0, y + 2.5, -11.5, y + 0.5),
        ("Z",),
    )
    return (
        fill(rigid_ops(chest, hood), GOLD_MID, GOLD_DARK, 1.0),
        fill(rigid_ops(chest, inner), color("9a6606")),
    )


# ---------------------------------------------------------------- head
def head_commands(state: RigState, face: FaceState) -> tuple[DrawPath, ...]:
    head = state.joints["head"]
    pose = state.pose
    s = pose.squash
    rx, ry = HEAD_RX * (1 - 0.22 * s), HEAD_RY * (1 + 0.22 * s)
    light = 1.0 if state.sign > 0 else -1.0
    shell = rigid_ops(head, ellipse(0, 0, rx, ry))
    cmds = [
        DrawPath(shell, HEAD_BLACK, Stroke(EDGE, 2.6)),
        DrawPath(shell, HEAD_BLACK),
    ]
    sheen = P(
        ("M", light * (rx - 4.5), -6.0),
        ("C", light * (rx - 1.8), 0.0, light * (rx - 2.5), 8.0, light * (rx - 7.0), 13.5),
        ("C", light * (rx - 4.6), 6.0, light * (rx - 4.0), 0.0, light * (rx - 4.5), -6.0),
        ("Z",),
    )
    cmds.append(fill(rigid_ops(head, sheen), HEAD_SHEEN))
    rim = []
    for i in range(13):
        a = -0.9 + i * (1.75 / 12)
        rim.append((light * (rx - 0.9) * math.cos(a), (ry - 0.9) * math.sin(a)))
    rim_ops = P(("M", *rim[0]), *[("L", *p) for p in rim[1:]])
    cmds.append(stroke(rigid_ops(head, rim_ops), RIM, 1.25))
    cmds += face_commands(state, face, head, rx, ry)
    return tuple(cmds)


def face_commands(state: RigState, face: FaceState, head: Rigid, rx: float, ry: float):
    pose = state.pose
    f = state.f
    dx = 4.6 * f + 5.0 * pose.head_yaw
    look_x, look_y = pose.look_x * 2.6, pose.look_y * 1.9
    out = []
    eye_y = 2.6 + look_y
    o = face.eye_open
    for side, base in (("near", -7.3 * (1 - 0.12 * f)), ("far", 7.3 * (1 - 0.22 * f))):
        cx = dx + base + look_x
        squeeze = 1 - 0.18 * f if side == "far" else 1.0
        erx, ery = 3.35 * face.eye_scale * squeeze, 4.9 * face.eye_scale
        out += eye_commands(head, cx, eye_y, erx, ery, o, face)
        # brows
        asym = face.brow_asym if side == "far" else -0.35 * face.brow_asym
        by = eye_y - ery - 2.7 - face.brow_raise - asym
        inner = 1.0 if side == "near" else -1.0  # direction toward face centre
        tilt = face.brow_tilt
        half = 3.7 * squeeze
        ix, ox = cx + inner * half, cx - inner * half
        iy, oy = by - tilt * 4.0, by + tilt * 4.0 * 0.4
        mid_y = (iy + oy) / 2 - 1.0
        brow = P(("M", ox, oy), ("C", lerp(ox, ix, 0.35), mid_y, lerp(ox, ix, 0.7), mid_y, ix, iy))
        out.append(stroke(rigid_ops(head, brow), WHITE, 1.9))
    out += mouth_commands(head, dx * 0.92 + look_x * 0.5, 12.6 + look_y * 0.4, face)
    return out


def eye_commands(head, cx, cy, erx, ery, o, face: FaceState):
    out = []
    closed = 1 - o
    top_cut = cy - ery + 2 * ery * max(0.5 * closed * 1.15, 0.42 * face.upper_lid)
    bottom_cut = cy + ery - 2 * ery * (0.5 * closed * 0.85)
    if top_cut >= bottom_cut - 0.9:
        # Closed eye: a soft arc ("^" when smiling, flat otherwise).
        arc = 1.6 * face.lower_lid - 0.6
        y = (top_cut + bottom_cut) / 2
        ops = P(
            ("M", cx - erx, y + 0.4),
            ("C", cx - erx * 0.4, y - arc, cx + erx * 0.4, y - arc, cx + erx, y + 0.4),
        )
        out.append(stroke(rigid_ops(head, ops), WHITE, 1.6))
        return out
    cheek = 2.4 * ery * 0.55 * face.lower_lid
    clip = P(
        ("M", cx - erx - 2, top_cut),
        ("L", cx + erx + 2, top_cut),
        ("L", cx + erx + 2, bottom_cut),
        (
            "C",
            cx + erx * 0.5,
            bottom_cut - cheek * 1.35,
            cx - erx * 0.5,
            bottom_cut - cheek * 1.35,
            cx - erx - 2,
            bottom_cut,
        ),
        ("Z",),
    )
    clip_w = rigid_ops(head, clip)
    out.append(fill(rigid_ops(head, ellipse(cx, cy, erx * 1.5, ery * 1.32)), EYE_GLOW, clip=clip_w))
    out.append(fill(rigid_ops(head, ellipse(cx, cy, erx, ery)), WHITE, clip=clip_w))
    out.append(
        fill(
            rigid_ops(head, ellipse(cx - erx * 0.25, cy - ery * 0.38, erx * 0.32, ery * 0.22)),
            color("ffffff"),
            clip=clip_w,
        )
    )
    if face.upper_lid > 0.05 and closed < 0.5:
        lid = P(("M", cx - erx - 0.4, top_cut + 0.2), ("L", cx + erx + 0.4, top_cut + 0.2))
        out.append(stroke(rigid_ops(head, lid), color("e8eef8"), 0.9))
    return out


def mouth_commands(head, mx, my, face: FaceState):
    c = face.mouth_curve
    w = 4.5 * face.mouth_width * (1 - 0.35 * face.mouth_round)
    o = face.mouth_open
    if o < 0.06:
        ops = P(
            ("M", mx - w, my - c * 1.7),
            ("C", mx - w * 0.4, my + c * 1.5, mx + w * 0.4, my + c * 1.5, mx + w, my - c * 1.7),
        )
        return [stroke(rigid_ops(head, ops), WHITE, 1.25)]
    r = face.mouth_round
    depth = 0.8 + o * 4.6
    yc = my - c * 1.5 * (1 - r)
    # D-shape (smile) and O-shape share topology so they blend smoothly.
    top_d = yc + c * 0.4
    bot_d = yc + depth * 1.25 + c * 0.6
    h = depth * 0.5 + 0.6
    top_o, bot_o = my - 1.33 * h + h, my + 1.33 * h + h
    yc_o = my + h
    ycc = lerp(yc, yc_o, r)
    t_y = lerp(top_d, top_o, r)
    b_y = lerp(bot_d, bot_o, r)
    tx = lerp(0.45, 1.0, r)
    bx = lerp(0.85, 1.0, r)
    shape = P(
        ("M", mx - w, ycc),
        ("C", mx - w * tx, t_y, mx + w * tx, t_y, mx + w, ycc),
        ("C", mx + w * bx, b_y, mx - w * bx, b_y, mx - w, ycc),
        ("Z",),
    )
    sw = rigid_ops(head, shape)
    out = [fill(sw, MOUTH)]
    if o > 0.35:
        tongue = ellipse(mx, lerp(bot_d, bot_o, r) - depth * 0.35, w * 0.55, depth * 0.32)
        out.append(fill(rigid_ops(head, tongue), TONGUE, clip=sw))
    out.append(DrawPath(sw, stroke=Stroke(WHITE, 1.0)))
    return out


def beanie_commands(state: RigState) -> tuple[DrawPath, ...]:
    b = state.joints["beanie"]
    f = state.f
    light = 1.0 if state.sign > 0 else -1.0
    sec = state.secondary
    shift = 2.6 * f + 3.0 * state.pose.head_yaw
    crown = P(
        ("M", -20.6, -8.0),
        ("C", -21.5, -17.5, -12.5, -23.6, 0.0, -23.8),
        ("C", 12.5, -23.6, 21.5, -17.5, 20.6, -8.0),
        ("Z",),
    )
    crown_paint = vgrad(
        b.point((0, -24)), b.point((0, -8)), (0.0, RED_HI), (0.45, RED), (1.0, RED_MID)
    )
    cmds = [
        DrawPath(rigid_ops(b, crown), RED, Stroke(EDGE, 2.4)),
        fill(rigid_ops(b, crown), crown_paint, RED_LINE, 1.0),
    ]
    for i in range(-4, 5):
        x0 = i * 4.3 + shift * 0.6
        ops = P(
            ("M", x0, -8.6),
            ("C", x0 * 1.02, -15.0, x0 * 0.7, -20.0, x0 * 0.25 + shift * 0.3, -23.0),
        )
        cmds.append(stroke(rigid_ops(b, ops), RED_RIB if i % 2 else color("a51717", 0.7), 0.8))
    hl = P(
        ("M", light * 8.0, -21.5),
        ("C", light * 14.5, -19.5, light * 18.5, -15.0, light * 19.0, -10.5),
        ("C", light * 15.5, -14.0, light * 12.0, -18.0, light * 8.0, -21.5),
        ("Z",),
    )
    cmds.append(fill(rigid_ops(b, hl), color("ffb3a8", 0.55)))
    # Thick folded brim with shadow under the fold.
    cmds.append(
        fill(
            rigid_ops(
                b,
                P(
                    ("M", -20.6, -9.6),
                    ("C", -10, -12.4, 10, -12.4, 20.6, -9.6),
                    ("L", 20.4, -7.6),
                    ("C", 10, -10.0, -10, -10.0, -20.4, -7.6),
                    ("Z",),
                ),
            ),
            color("5e0a0a", 0.55),
        )
    )
    brim = P(
        ("M", -22.6, -8.6),
        ("C", -12.0, -11.2, 12.0, -11.2, 22.6, -8.6),
        ("C", 23.6, -5.2, 23.4, -1.6, 22.4, 0.6),
        ("C", 12.0, -1.6, -12.0, -1.6, -22.4, 0.6),
        ("C", -23.4, -1.6, -23.6, -5.2, -22.6, -8.6),
        ("Z",),
    )
    brim_paint = vgrad(
        b.point((0, -10)), b.point((0, 1)), (0.0, RED_HI), (0.5, RED), (1.0, RED_DARK)
    )
    cmds.append(DrawPath(rigid_ops(b, brim), RED, Stroke(EDGE, 2.4)))
    cmds.append(fill(rigid_ops(b, brim), brim_paint, RED_LINE, 1.1))
    for i in range(-10, 11):
        x = i * 2.1 + shift * 0.4
        if abs(x) > 21.5:
            continue
        sag = 2.5 * (1 - (x / 22.6) ** 2)
        ops = P(("M", x, -8.4 - sag + 1.3), ("L", x, -0.2 - sag * 0.85))
        cmds.append(stroke(rigid_ops(b, ops), RED_LINE if i % 2 else RED_RIB, 0.55))
    edge = P(("M", -21.5, -8.2), ("C", -11.0, -10.7, 11.0, -10.7, 21.5, -8.2))
    cmds.append(stroke(rigid_ops(b, edge), color("ff9c90", 0.75), 0.8))
    # Pom-pom with lag.
    px, py = sec.pom_x * 0.8 + shift * 0.2, -25.6 + sec.pom_y
    cmds.append(DrawPath(rigid_ops(b, ellipse(px, py, 4.8, 4.5)), RED, Stroke(EDGE, 2.0)))
    cmds.append(fill(rigid_ops(b, ellipse(px, py, 4.8, 4.5)), RED_MID, RED_LINE, 0.8))
    for k in range(6):
        a = k * math.pi / 3
        tuft = ellipse(px + 2.4 * math.cos(a), py + 2.2 * math.sin(a), 1.6, 1.5)
        cmds.append(fill(rigid_ops(b, tuft), RED if k % 2 else RED_HI))
    cmds.append(
        fill(rigid_ops(b, ellipse(px + light * 1.6, py - 1.6, 1.6, 1.2)), color("ffc2b8", 0.7))
    )
    return tuple(cmds)


# ---------------------------------------------------------------- assembly
def character_commands(
    state: RigState, face: FaceState, placement: Placement
) -> tuple[DrawPath, ...]:
    """Painter's order: far arm, legs, shorts, hoodie, near arm, hood, head, beanie.

    The near arm sits in front of the hoodie but behind the head, so raised hands never
    cover the face.
    """
    parts: list[DrawPath] = []
    front_view = state.f < FRONT_VIEW_LIMIT
    if not front_view:
        parts += arm_commands(state, "far")
    parts += leg_commands(state, "far")
    parts += leg_commands(state, "near")
    parts += shorts_cuff(state, "far")
    parts += shorts_cuff(state, "near")
    parts += shorts_body(state)
    parts += torso_commands(state)
    if front_view:
        # Facing the camera both arms are in front of the hoodie.
        parts += arm_commands(state, "far")
    parts += arm_commands(state, "near")
    parts += hood_commands(state)
    parts += head_commands(state, face)
    parts += beanie_commands(state)
    t = placement.transform()
    return tuple(
        replace(c, transform=t) if c.clip is None else replace(c, transform=t) for c in parts
    )


def contact_shadows(
    state: RigState, placement: Placement, *, alpha: float = 0.5
) -> tuple[DrawPath, ...]:
    """Soft ground shadows under each foot and the body, fading with height."""
    out = []
    s = placement.scale
    pelvis_h = state.pose.pelvis_height
    body_air = max(0.0, pelvis_h - 50.9)
    k = max(0.25, 1 - body_air / 70)
    out.append(
        DrawPath(
            ellipse(placement.x, placement.ground_y + 1.2, 25 * s * k, 4.6 * s * k),
            color("03050a", alpha * 0.45 * k),
        )
    )
    for side in ("near", "far"):
        heel, toe = state.sole_points(side)
        lowest = max(heel[1], toe[1])
        height = max(0.0, -lowest)
        fade = max(0.0, 1 - height / 26)
        if fade <= 0.02:
            continue
        cx = (heel[0] + toe[0]) / 2
        wx = placement.x + placement.sign * s * cx
        out.append(
            DrawPath(
                ellipse(wx, placement.ground_y + 0.8, 11.5 * s * (0.7 + 0.3 * fade), 2.2 * s),
                color("02030a", alpha * 0.8 * fade),
            )
        )
    return tuple(out)
