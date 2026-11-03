"""Yellow Mellow V2 hierarchical 2.5D rig.

Coordinates are character units, Y down, ground at y = 0. ``pelvis_x`` and foot ``x`` values
are world positions along the ground; every other channel is *canonical*: authored as if the
character faces +X. A negative ``facing`` mirrors the canonical frame about the pelvis.

Upper body: forward kinematics through the accepted ``reelforge.characters.rig.Skeleton``
(pelvis -> spine -> chest -> neck -> head -> beanie, chest -> shoulder -> elbow -> wrist).
Legs: analytic two-bone IK from the hip to an ankle target derived from a ground-contact
``FootState`` (contact x, pivot lift, roll pitch). Planted feet are exact: the IK target is the
foot, and the pelvis height is softly limited so planted legs are never over-extended.

The near leg's knee bend direction blends with facing (outward in front view, forward in
three-quarter view). Between those the knee offset is foreshortened, which is the only
non-rigid limb behaviour; arm bones and torso segments stay rigid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace

from reelforge.characters.rig import Joint, Pose, Rigid, Skeleton
from reelforge.rendering.model import RenderError, finite

# --- Proportions (character units). Standing height 142.5 = 3.56 black-head heights. ---
ANKLE_HEIGHT = 5.5
THIGH = 22.0
SHIN = 21.0
LEG_MAX = (THIGH + SHIN) * 0.995
LEG_MIN = abs(THIGH - SHIN) + 7.0
HIP_DROP = 3.0
SPINE_BASE = 3.0
SPINE_LEN = 19.0
CHEST_LEN = 19.0
SHOULDER_RISE = 11.5
NECK_LEN = 15.0
BEANIE_OFFSET = 9.0
UPPER_ARM = 21.0
FOREARM = 20.0
HEAD_RX = 21.0
HEAD_RY = 20.0
STAND_HIP_ANKLE = 42.4
STAND_PELVIS = ANKLE_HEIGHT + STAND_HIP_ANKLE + HIP_DROP  # 50.9
STANDING_HEIGHT = 142.5
HEAD_HEIGHT = 2 * HEAD_RY

HAND_SHAPES = ("relaxed", "open", "fist", "point")
SIDES = ("near", "far")
# Side-relative arm values: positive shoulder raises the arm outward/up on that side.
SIDE_OUT = {"near": 1.0, "far": -1.0}

# Calibrated limits; values outside are clamped and reported by ``RigState.clamped``.
LIMITS = {
    "pelvis_height": (20.0, 95.0),
    "pelvis_tilt": (-0.35, 0.35),
    "spine": (-0.45, 0.6),
    "chest": (-0.35, 0.35),
    "neck": (-0.45, 0.45),
    "head": (-0.45, 0.45),
    "head_yaw": (-1.0, 1.0),
    "facing": (-1.0, 1.0),
    "squash": (-0.14, 0.14),
    "look_x": (-1.0, 1.0),
    "look_y": (-1.0, 1.0),
    "shoulder": (-1.9, 3.25),
    "elbow": (-2.5, 2.6),
    "wrist": (-1.1, 1.1),
    "pitch": (-0.6, 1.1),
    "lift": (0.0, 60.0),
}


def lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def smoothstep(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def shoulder_offsets(f: float) -> dict[str, float]:
    return {"near": -lerp(16.5, 13.5, f), "far": lerp(16.5, 11.0, f)}


def hip_offsets(f: float) -> dict[str, float]:
    return {"near": -lerp(6.5, 4.5, f), "far": lerp(6.5, 3.0, f)}


def shoe_extent(f: float) -> tuple[float, float]:
    """(heel, toe) distances from the ankle along the sole; symmetric in front view."""
    return lerp(8.3, 6.5, f), lerp(8.3, 12.0, f)


def knee_bend(side: str, f: float) -> float:
    """Signed knee offset scale; +1 bends toward canonical +X (forward / far side)."""
    if side == "far":
        return 1.0
    return -1.0 + 2.0 * smoothstep((f - 0.15) / 0.6)


@dataclass(frozen=True)
class ArmPose:
    """Side-relative arm angles (radians). Bones hang along +Y at zero.

    shoulder > 0 raises the arm outward on its own side (pi = straight up);
    elbow > 0 curls the forearm toward the top of the arm's arc; wrist likewise.
    """

    shoulder: float = 0.32
    elbow: float = -0.1
    wrist: float = 0.0
    hand: str = "relaxed"

    def __post_init__(self):
        finite(self.shoulder, self.elbow, self.wrist)
        if self.hand not in HAND_SHAPES:
            raise RenderError(f"Unknown hand shape {self.hand!r}; use {HAND_SHAPES}")


@dataclass(frozen=True)
class FootState:
    """World contact x (ankle x when flat), pivot height above ground and roll pitch.

    pitch > 0 lifts the heel around the ball of the foot; pitch < 0 lifts the toe around
    the heel. The pivot stays at (x + pivot offset, -lift), so a planted foot can roll
    without sliding.
    """

    x: float = 0.0
    lift: float = 0.0
    pitch: float = 0.0

    def __post_init__(self):
        finite(self.x, self.lift, self.pitch)
        if self.lift < -0.01:
            raise RenderError("Foot lift cannot be below the ground")


@dataclass(frozen=True)
class MellowPose:
    pelvis_x: float = 0.0
    pelvis_height: float = STAND_PELVIS
    pelvis_tilt: float = 0.0
    spine: float = 0.0
    chest: float = 0.0
    neck: float = 0.0
    head: float = 0.0
    head_yaw: float = 0.0
    facing: float = 0.25
    squash: float = 0.0
    look_x: float = 0.0
    look_y: float = 0.0
    near_arm: ArmPose = ArmPose()
    far_arm: ArmPose = ArmPose()
    near_foot: FootState = FootState(-6.5)
    far_foot: FootState = FootState(6.5)

    def __post_init__(self):
        finite(*(getattr(self, name) for name in BODY_CHANNELS))
        for name in ("near_arm", "far_arm"):
            if not isinstance(getattr(self, name), ArmPose):
                raise RenderError("Arms must be ArmPose values")
        for name in ("near_foot", "far_foot"):
            if not isinstance(getattr(self, name), FootState):
                raise RenderError("Feet must be FootState values")

    def with_(self, **changes) -> MellowPose:
        return replace(self, **changes)

    @property
    def sign(self) -> int:
        return 1 if self.facing >= 0 else -1

    def arm(self, side: str) -> ArmPose:
        return self.near_arm if side == "near" else self.far_arm

    def foot(self, side: str) -> FootState:
        return self.near_foot if side == "near" else self.far_foot


_LIMB_FIELDS = ("near_arm", "far_arm", "near_foot", "far_foot")
BODY_CHANNELS = tuple(f.name for f in fields(MellowPose) if f.name not in _LIMB_FIELDS)


def body_vector(pose: MellowPose) -> tuple[float, ...]:
    return tuple(getattr(pose, n) for n in BODY_CHANNELS)


def with_body(pose: MellowPose, vector: tuple[float, ...]) -> MellowPose:
    return replace(pose, **dict(zip(BODY_CHANNELS, vector, strict=True)))


def standing_pose(x: float = 0.0, facing: float = 0.25) -> MellowPose:
    """Neutral stance with feet under the hips for the given facing."""
    f = abs(facing)
    s = 1 if facing >= 0 else -1
    hips = hip_offsets(f)
    return MellowPose(
        pelvis_x=x,
        facing=facing,
        near_foot=FootState(x + s * hips["near"]),
        far_foot=FootState(x + s * hips["far"]),
    )


def stance_feet(pelvis_x: float, facing: float, width: float = 0.0) -> dict[str, float]:
    """World foot x for a stance centred on the pelvis; ``width`` adds outward spread."""
    f = abs(facing)
    s = 1 if facing >= 0 else -1
    hips = hip_offsets(f)
    return {
        "near": pelvis_x + s * (hips["near"] - width),
        "far": pelvis_x + s * (hips["far"] + width),
    }


def swing_arm(
    side: str, forward: float, flex: float, *, out: float = 0.12, wrist=0.0, hand="relaxed"
):
    """Sagittal (three-quarter) arm: ``forward`` swings toward the facing direction."""
    so = SIDE_OUT[side]
    return ArmPose(out - forward * so, -flex * so, -wrist * so, hand)


@dataclass(frozen=True)
class Secondary:
    """Follow-through offsets from the spring kernel; bounded and canonical."""

    beanie: float = 0.0
    pom_x: float = 0.0
    pom_y: float = 0.0
    strings: float = 0.0
    hem_x: float = 0.0
    hem_y: float = 0.0
    head_drop: float = 0.0
    sleeve: float = 0.0

    def __post_init__(self):
        finite(*(getattr(self, f.name) for f in fields(self)))


NO_SECONDARY = Secondary()


@dataclass(frozen=True)
class LegSolve:
    hip: tuple[float, float]
    knee: tuple[float, float]
    ankle: tuple[float, float]
    target: tuple[float, float]
    foot_angle: float
    reach_error: float
    bend: float

    def joint_angles(self) -> tuple[float, float]:
        """Equivalent hip and knee rotations (bone along +Y at zero) for reporting."""
        hip = math.atan2(-(self.knee[0] - self.hip[0]), self.knee[1] - self.hip[1])
        shin = math.atan2(-(self.ankle[0] - self.knee[0]), self.ankle[1] - self.knee[1])
        return hip, shin - hip


@dataclass(frozen=True)
class RigState:
    pose: MellowPose
    sign: int
    f: float
    joints: dict[str, Rigid]
    legs: dict[str, LegSolve]
    secondary: Secondary
    clamped: tuple[str, ...]
    pelvis_limited: float

    def world(self, point: tuple[float, float]) -> tuple[float, float]:
        """Canonical point -> world character units."""
        return self.pose.pelvis_x + self.sign * point[0], point[1]

    def sole_points(self, side: str) -> tuple[tuple[float, float], tuple[float, float]]:
        heel, toe = shoe_extent(self.f)
        leg = self.legs[side]
        frame = Rigid(leg.ankle[0], leg.ankle[1], leg.foot_angle)
        return frame.point((-heel, ANKLE_HEIGHT)), frame.point((toe, ANKLE_HEIGHT))


def pivot_local(pitch: float, f: float) -> tuple[float, float]:
    heel, toe = shoe_extent(f)
    # Roll about the sole end points so no part of the sole dips below the ground.
    if pitch > 0:
        return toe, ANKLE_HEIGHT
    return -heel, ANKLE_HEIGHT


def ankle_from_foot(foot: FootState, canonical_x: float, f: float) -> tuple[float, float]:
    """Ankle position for a foot whose flat-reference ankle is at canonical_x."""
    px, py = pivot_local(foot.pitch, f)
    c, s = math.cos(foot.pitch), math.sin(foot.pitch)
    pivot_x, pivot_y = canonical_x + px, -foot.lift
    return pivot_x + (c * -px - s * -py), pivot_y + (s * -px + c * -py)


def foot_from_ankle(ankle: tuple[float, float], pitch: float, pose: MellowPose) -> FootState:
    """Inverse of ``ankle_from_foot`` in world units: FK-posed legs become foot states."""
    f, s = abs(pose.facing), pose.sign
    px, py = pivot_local(pitch, f)
    c, sn = math.cos(pitch), math.sin(pitch)
    cx = (ankle[0] - pose.pelvis_x) * s
    pivot_x = cx + (c * px - sn * py)
    pivot_y = ankle[1] + (sn * px + c * py)
    return FootState(pose.pelvis_x + s * (pivot_x - px), max(0.0, -pivot_y), pitch)


def solve_two_bone(hip, target, upper=THIGH, lower=SHIN, bend=1.0):
    """Clamped analytic two-bone IK. Returns (knee, ankle, reach_error)."""
    dx, dy = target[0] - hip[0], target[1] - hip[1]
    d = math.hypot(dx, dy)
    ux, uy = (0.0, 1.0) if d < 1e-9 else (dx / d, dy / d)
    dc = clamp(d, LEG_MIN, LEG_MAX)
    ankle = (hip[0] + ux * dc, hip[1] + uy * dc)
    a = (upper * upper - lower * lower + dc * dc) / (2 * dc)
    h = math.sqrt(max(0.0, upper * upper - a * a))
    nx, ny = uy, -ux  # +X side of a downward bone
    knee = (hip[0] + ux * a + nx * h * bend, hip[1] + uy * a + ny * h * bend)
    return knee, ankle, abs(d - dc)


def _soft_limit(value: float, limit: float, knee: float = 1.0) -> float:
    """C1 soft minimum: identity well below the limit, asymptotic to it above."""
    start = limit - knee
    if value <= start:
        return value
    return limit - knee * math.exp(-(value - start) / knee)


def _clamp_pose(pose: MellowPose) -> tuple[MellowPose, tuple[str, ...]]:
    clamped = []
    body = {}
    for name in BODY_CHANNELS:
        value = getattr(pose, name)
        if name in LIMITS:
            lo, hi = LIMITS[name]
            limited = clamp(value, lo, hi)
            if abs(limited - value) > 1e-9:
                clamped.append(name)
            value = limited
        body[name] = value
    arms = {}
    for side in SIDES:
        arm = pose.arm(side)
        values = []
        for joint in ("shoulder", "elbow", "wrist"):
            lo, hi = LIMITS[joint]
            v = getattr(arm, joint)
            lim = clamp(v, lo, hi)
            if abs(lim - v) > 1e-9:
                clamped.append(f"{side}_{joint}")
            values.append(lim)
        arms[side + "_arm"] = ArmPose(*values, arm.hand)
    feet = {}
    for side in SIDES:
        foot = pose.foot(side)
        lo, hi = LIMITS["pitch"]
        pitch = clamp(foot.pitch, lo, hi)
        if abs(pitch - foot.pitch) > 1e-9:
            clamped.append(f"{side}_pitch")
        feet[side + "_foot"] = FootState(foot.x, max(0.0, foot.lift), pitch)
    return replace(pose, **body, **arms, **feet), tuple(clamped)


def build_skeleton(f: float, squash: float, head_drop: float = 0.0) -> Skeleton:
    stretch = 1 + squash
    sh = shoulder_offsets(f)
    joints = [
        Joint("pelvis", None),
        Joint("spine", "pelvis", (0, -SPINE_BASE)),
        Joint("chest", "spine", (0, -SPINE_LEN * stretch)),
        Joint("neck", "chest", (0, -CHEST_LEN * stretch)),
        Joint("head", "neck", (0, -(NECK_LEN - head_drop))),
        Joint("beanie", "head", (0, -BEANIE_OFFSET)),
    ]
    for side in SIDES:
        joints += [
            Joint(f"{side}_shoulder", "chest", (sh[side], -SHOULDER_RISE * stretch)),
            Joint(f"{side}_elbow", f"{side}_shoulder", (0, UPPER_ARM)),
            Joint(f"{side}_wrist", f"{side}_elbow", (0, FOREARM)),
        ]
    return Skeleton(tuple(joints))


def evaluate(pose: MellowPose, secondary: Secondary = NO_SECONDARY) -> RigState:
    """Solve the full rig for one pose. Pure and deterministic."""
    pose, clamped = _clamp_pose(pose)
    sign = pose.sign
    f = abs(pose.facing)
    tilt = pose.pelvis_tilt
    hips = hip_offsets(f)
    ankles = {}
    for side in SIDES:
        foot = pose.foot(side)
        ankles[side] = ankle_from_foot(foot, sign * (foot.x - pose.pelvis_x), f)
    # Soft pelvis height limit keeps every grounded or lifted foot reachable.
    height = pose.pelvis_height
    for side in SIDES:
        hx = hips[side]
        hip_x = math.cos(tilt) * hx - math.sin(tilt) * HIP_DROP
        rise = math.sin(tilt) * hx + math.cos(tilt) * HIP_DROP
        ax, ay = ankles[side]
        dx = ax - hip_x
        vertical = math.sqrt(max(1.0, LEG_MAX * LEG_MAX - dx * dx))
        limited_h = _soft_limit(height, rise - ay + vertical, 0.8)
        # Grounded feet bound the pelvis; a lifted swing foot fades out of the constraint.
        height = lerp(limited_h, height, smoothstep(pose.foot(side).lift / 4.0))
    limited = pose.pelvis_height - height
    skeleton = build_skeleton(f, pose.squash, secondary.head_drop)
    angles = [
        ("spine", pose.spine),
        ("chest", pose.chest),
        ("neck", pose.neck),
        ("head", pose.head),
        ("beanie", secondary.beanie),
    ]
    for side in SIDES:
        arm = pose.arm(side)
        so = SIDE_OUT[side]
        angles += [
            (f"{side}_shoulder", so * arm.shoulder),
            (f"{side}_elbow", so * arm.elbow),
            (f"{side}_wrist", so * arm.wrist),
        ]
    joints = skeleton.evaluate(Pose(Rigid(0.0, -height, tilt), tuple(angles)))
    pelvis = joints["pelvis"]
    legs = {}
    for side in SIDES:
        hip = pelvis.point((hips[side], HIP_DROP))
        knee, ankle, error = solve_two_bone(hip, ankles[side], bend=knee_bend(side, f))
        legs[side] = LegSolve(
            hip, knee, ankle, ankles[side], pose.foot(side).pitch, error, knee_bend(side, f)
        )
    return RigState(
        replace(pose, pelvis_height=height), sign, f, joints, legs, secondary, clamped, limited
    )
