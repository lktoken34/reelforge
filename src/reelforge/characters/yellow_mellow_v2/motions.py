"""Reusable, parameterised motion presets for Yellow Mellow V2.

Every preset is a ``Clip`` built from the *actual* previous pose (``ClipStart``), so actions
chain without snapping to a default pose. Clips have an explicit duration in frames, use
PCHIP keys or analytic curves with explicit easing, and only expose bounded numeric/enum
parameters. Agents select presets through ``character.ActionRequest``; they never author
joint maths.

Coordinate reminders: side-relative arm values (``shoulder`` > 0 raises outward), canonical
body channels (positive spine leans toward the facing direction), world foot x.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from reelforge.rendering.model import RenderError, finite

from .expressions import FaceState, adjust, blend_faces
from .rig import (
    STAND_PELVIS,
    ArmPose,
    FootState,
    MellowPose,
    clamp,
    hip_offsets,
    lerp,
    smoothstep,
    stance_feet,
    swing_arm,
)
from .transitions import (
    Key,
    KeyTrack,
    blend,
    ease_in,
    ease_out,
    feet_mid,
    feet_xs,
    settle,
    settle_feet,
    smootherstep,
    window,
)

REST_ARM = ArmPose(0.3, -0.12, 0.05)
TAU = math.tau


@dataclass(frozen=True)
class ClipStart:
    pose: MellowPose
    face: FaceState


class Clip:
    """Base clip. ``pose(t)`` is valid for 0 <= t <= duration; t is in frames."""

    name = "clip"

    def __init__(self, start: ClipStart, duration: int):
        if type(duration) is not int or duration < 2:
            raise RenderError("Clip duration must be an integer >= 2 frames")
        self.start = start
        self.duration = duration

    def pose(self, t: float) -> MellowPose:
        raise NotImplementedError

    def face(self, t: float, base: FaceState) -> FaceState:
        return base

    def blinks(self) -> tuple[float, ...]:
        """Clip-requested blink onsets in local frames."""
        return ()

    def suppress_blinks(self, t: float) -> bool:
        return False

    def end_pose(self) -> MellowPose:
        return self.pose(self.duration)


# ---------------------------------------------------------------- helpers
def upright(start: MellowPose, **changes) -> MellowPose:
    """Neutral standing body that keeps start feet, pelvis x and facing."""
    base = replace(
        start,
        pelvis_height=STAND_PELVIS,
        pelvis_tilt=0.0,
        spine=0.0,
        chest=0.0,
        neck=0.0,
        head=0.0,
        head_yaw=0.0,
        squash=0.0,
        look_x=0.0,
        look_y=0.0,
        near_arm=REST_ARM,
        far_arm=REST_ARM,
        pelvis_x=feet_mid(start),
        # Feet keep their world x but settle flat (rolling about the locked pivot).
        near_foot=FootState(start.near_foot.x),
        far_foot=FootState(start.far_foot.x),
    )
    return replace(base, **changes)


def arms(pose: MellowPose, near: ArmPose | None = None, far: ArmPose | None = None):
    return replace(pose, near_arm=near or pose.near_arm, far_arm=far or pose.far_arm)


def feet_at(pose: MellowPose, xs: dict[str, float], pitch=0.0, lift=0.0) -> MellowPose:
    return replace(
        pose,
        near_foot=FootState(xs["near"], lift, pitch),
        far_foot=FootState(xs["far"], lift, pitch),
    )


def world_dir_to_canonical(direction: str, pose: MellowPose) -> float:
    if direction not in ("left", "right"):
        raise RenderError("Direction must be 'left' or 'right'")
    return (1.0 if direction == "right" else -1.0) * pose.sign


def _pick_side(hand: str) -> str:
    if hand not in ("near", "far"):
        raise RenderError("hand must be 'near' or 'far'")
    return hand


class KeyedClip(Clip):
    """PCHIP keyframes + optional additive overlay + optional foot settling plan."""

    def __init__(
        self,
        start: ClipStart,
        duration: int,
        keys: list[tuple[float, MellowPose]],
        *,
        overlay: Callable[[float, MellowPose], MellowPose] | None = None,
        stance: dict[str, float] | None = None,
        stance_begin: float = 0.0,
        face_fn: Callable[[float, FaceState], FaceState] | None = None,
        blink_frames: tuple[float, ...] = (),
        no_blink: tuple[float, float] | None = None,
    ):
        super().__init__(start, duration)
        frames = [0.0] + [float(k) for k, _ in keys]
        if frames[-1] > duration + 1e-9:
            raise RenderError("Keys extend beyond the clip duration")
        self.track = KeyTrack([Key(0.0, start.pose)] + [Key(float(f), p) for f, p in keys])
        self.overlay = overlay
        self.stance = stance
        self.stance_begin = stance_begin
        self.face_fn = face_fn
        self._blinks = blink_frames
        self._no_blink = no_blink
        self._start_feet = feet_xs(start.pose)

    def pose(self, t: float) -> MellowPose:
        t = clamp(t, 0.0, float(self.duration))
        p = self.track.sample(t)
        if self.stance is not None:
            states, weight = settle_feet(self._start_feet, self.stance, t, begin=self.stance_begin)
            start_mid = sum(self._start_feet.values()) / 2
            target_mid = sum(self.stance.values()) / 2
            # Keys hold pelvis_x relative to the target mid; carry it while the feet settle.
            offset = p.pelvis_x - lerp(
                start_mid, target_mid, smoothstep(t / max(1.0, self.duration))
            )
            progress = sum(abs(states[s].x - self._start_feet[s]) for s in states) / max(
                1e-6, sum(abs(self.stance[s] - self._start_feet[s]) for s in states)
            )
            mid = lerp(start_mid, target_mid, clamp(progress, 0, 1))
            half = abs(states["far"].x - states["near"].x) / 2
            p = replace(
                p,
                near_foot=states["near"],
                far_foot=states["far"],
                pelvis_x=mid + offset + weight * half * 0.55 * p.sign,
            )
        if self.overlay is not None:
            p = self.overlay(t, p)
        return p

    def face(self, t, base):
        return self.face_fn(t, base) if self.face_fn else base

    def blinks(self):
        return self._blinks

    def suppress_blinks(self, t):
        return self._no_blink is not None and self._no_blink[0] <= t <= self._no_blink[1]


# ---------------------------------------------------------------- basic
def breathing(t: float, p: MellowPose, amount: float = 1.0, period: float = 72.0) -> MellowPose:
    b = math.sin(TAU * t / period)
    inhale = 0.5 - 0.5 * math.cos(TAU * t / period)
    return replace(
        p,
        squash=p.squash + 0.014 * inhale * amount,
        chest=p.chest - 0.012 * b * amount,
        pelvis_height=p.pelvis_height - 0.35 * (1 - inhale) * amount,
        head=p.head + 0.02 * math.sin(TAU * t / period - 0.8) * amount,
        near_arm=replace(p.near_arm, shoulder=p.near_arm.shoulder + 0.03 * inhale * amount),
        far_arm=replace(p.far_arm, shoulder=p.far_arm.shoulder + 0.03 * inhale * amount),
        pelvis_x=p.pelvis_x + 0.5 * math.sin(TAU * t / 130) * amount * p.sign,
        pelvis_tilt=p.pelvis_tilt + 0.012 * math.sin(TAU * t / 130) * amount,
    )


def idle(start: ClipStart, duration: int, *, energy: float = 1.0, blink: bool = True) -> Clip:
    finite(energy)
    if not 0 <= energy <= 2:
        raise RenderError("idle energy must be 0..2")
    rest = upright(start.pose, facing=start.pose.facing)
    settle_at = min(14.0, duration * 0.6)
    keys = [(settle_at, rest), (float(duration), rest)]
    return KeyedClip(
        start,
        duration,
        keys,
        overlay=lambda t, p: breathing(t, p, energy),
        blink_frames=(min(duration - 7.0, 3.0),) if blink else (),
    )


def blink(start: ClipStart, duration: int) -> Clip:
    return idle(start, duration, blink=True)


def look(start: ClipStart, duration: int, *, direction: str = "right", amount: float = 1.0) -> Clip:
    finite(amount)
    if not 0 <= amount <= 1:
        raise RenderError("look amount must be 0..1")
    p0 = start.pose
    d = world_dir_to_canonical(direction, p0) * amount
    f = abs(p0.facing)
    new_f = clamp(f + 0.32 * d, 0.05, 1.0) * p0.sign
    eyes = replace(upright(p0), look_x=d, look_y=-0.1, facing=p0.facing)
    turned = replace(
        eyes,
        facing=new_f,
        head_yaw=0.45 * d,
        neck=0.05 * d,
        head=0.06 * d,
        chest=0.03 * d,
    )
    d1 = min(4.0, duration * 0.25)
    d2 = min(12.0, duration * 0.75)
    keys = [(d1, eyes), (d2, turned), (float(duration), turned)]
    return KeyedClip(start, duration, keys, overlay=lambda t, p: breathing(t, p, 0.6))


def head_tilt(start: ClipStart, duration: int, *, angle: float = 0.22) -> Clip:
    finite(angle)
    if abs(angle) > 0.4:
        raise RenderError("head tilt angle must be within +/-0.4 rad")
    p0 = start.pose
    tilt = replace(p0, head=angle, neck=angle * 0.35, look_y=-0.15)
    a = min(10.0, duration * 0.4)
    return KeyedClip(
        start,
        duration,
        [(a, tilt), (float(duration), tilt)],
        overlay=lambda t, p: breathing(t, p, 0.7),
    )


# ---------------------------------------------------------------- upper body
def wave(
    start: ClipStart,
    duration: int,
    *,
    hand: str = "far",
    waves: float = 2.0,
    lower: bool = False,
) -> Clip:
    side = _pick_side(hand)
    finite(waves)
    if not 0.5 <= waves <= 6:
        raise RenderError("waves must be 0.5..6")
    p0 = upright(start.pose)
    other = "near" if side == "far" else "far"
    raise_at = min(11.0, duration * 0.3)
    end_wave = duration - (9.0 if lower else 1.0)
    up_arm = ArmPose(2.15, 0.85, 0.2, "open")
    lean = 0.05 if side == "far" else -0.05
    up = arms(p0, **{side: up_arm, other: ArmPose(0.26, -0.18, 0.05)})
    up = replace(
        up,
        head=0.07 * (1 if side == "far" else -1),
        neck=0.03,
        spine=lean * 0.5,
        pelvis_tilt=-lean * 0.6,
        look_y=-0.15,
    )
    antic = arms(p0, **{side: ArmPose(0.15, -0.4, 0.0, "relaxed")})
    keys = [(raise_at * 0.3, antic), (raise_at, up), (end_wave, up)]
    if lower:
        keys.append((float(duration), arms(p0, **{side: ArmPose(0.45, -0.2, 0.1)})))
    else:
        keys.append((float(duration), up))
    span = max(1.0, end_wave - raise_at)

    def overlay(t, p):
        p = breathing(t, p, 0.6)
        env = smoothstep((t - raise_at * 0.8) / 4) * (1 - smoothstep((t - end_wave + 2) / 4))
        ph = TAU * waves * (t - raise_at) / span
        a = p.arm(side)
        a = replace(
            a,
            elbow=a.elbow + 0.42 * math.sin(ph) * env,
            wrist=a.wrist + 0.38 * math.sin(ph - 1.1) * env,
            shoulder=a.shoulder + 0.05 * math.sin(ph - 0.4) * env,
        )
        sway = 0.035 * math.sin(ph - 0.6) * env
        return replace(p, **{f"{side}_arm": a}, head=p.head + sway, chest=p.chest + sway * 0.4)

    return KeyedClip(start, duration, keys, overlay=overlay)


def hands_up(start: ClipStart, duration: int, *, lower: bool = False, toes: bool = True) -> Clip:
    p0 = upright(start.pose)
    a = min(6.0, duration * 0.2)
    peak = min(a + 11.0, duration * 0.6)

    def dip(arm: ArmPose) -> ArmPose:
        # Anticipation dips the arm; an already raised arm only sinks a little.
        w = 1.0 if arm.shoulder < 1.0 else 0.25
        return ArmPose(lerp(arm.shoulder, 0.12, w), lerp(arm.elbow, -0.35, w), arm.wrist, arm.hand)

    crouch = replace(
        arms(p0, dip(start.pose.near_arm), dip(start.pose.far_arm)),
        pelvis_height=STAND_PELVIS - 2.2,
        squash=-0.035,
    )
    up_near = ArmPose(2.42, 0.2, 0.3, "open")
    up_far = ArmPose(2.42, 0.2, 0.3, "open")
    up = arms(p0, up_near, up_far)
    up = replace(
        up,
        squash=0.05,
        look_y=-0.45,
        head=0.0,
        neck=0.0,
        chest=-0.03,
        pelvis_height=STAND_PELVIS + (1.6 if toes else 0.0),
    )
    if toes:
        up = feet_at(up, feet_xs(p0), pitch=0.2)
    keys = [(a, crouch), (peak, up)]
    if lower:
        keys += [(duration * 0.75, up), (float(duration), p0)]
    else:
        keys += [(float(duration), replace(up, squash=0.03))]

    def overlay(t, p):
        # Near arm lags the far arm by ~2 frames (overlapping action); wiggle at the top.
        lag = 0.25 * math.sin(math.pi * window(t, a, peak)) * (1 - window(t, peak, peak + 3))
        hold = window(t, peak - 2, peak + 2) * (1 - window(t, duration - 4, duration))
        wig = 0.18 * math.sin(TAU * (t - peak) / 7) * hold
        return replace(
            p,
            near_arm=replace(
                p.near_arm, shoulder=p.near_arm.shoulder - lag, wrist=p.near_arm.wrist + wig
            ),
            far_arm=replace(p.far_arm, wrist=p.far_arm.wrist - wig),
        )

    def face(t, base):
        return adjust(
            base, eye_scale=0.12 * window(t, a, peak), brow_raise=0.8 * window(t, a, peak)
        )

    return KeyedClip(start, duration, keys, overlay=overlay, face_fn=face)


def hands_down(start: ClipStart, duration: int) -> Clip:
    """Lower raised arms naturally: elbows lead, hands follow, a small overshoot settles."""
    p0 = start.pose
    rest = upright(p0)
    mid = arms(
        replace(rest, squash=0.0, look_y=-0.1, pelvis_height=STAND_PELVIS - 0.6),
        ArmPose(1.45, 1.1, 0.35, "relaxed"),
        ArmPose(1.45, 1.1, 0.35, "relaxed"),
    )
    past = arms(rest, ArmPose(0.18, -0.32, -0.1), ArmPose(0.18, -0.32, -0.1))
    m = duration * 0.38
    keys = [(m, mid), (duration * 0.72, past), (float(duration), rest)]
    return KeyedClip(start, duration, keys, overlay=lambda t, p: breathing(t, p, 0.5))


def point(
    start: ClipStart,
    duration: int,
    *,
    hand: str = "far",
    elevation: float = 0.95,
    lower: bool = False,
) -> Clip:
    """Point toward the facing side with the elbow straightened; other hand on hip."""
    side = _pick_side(hand)
    finite(elevation)
    if not -0.6 <= elevation <= 1.4:
        raise RenderError("elevation must be -0.6..1.4 rad above horizontal")
    p0 = start.pose
    other = "near" if side == "far" else "far"
    raise_at = min(9.0, duration * 0.3)
    shoulder = math.pi / 2 + elevation
    if side == "near":
        shoulder = -(math.pi / 2 + elevation) + 0.0  # near arm points across the body
    pointing = ArmPose(clamp(shoulder, -1.85, 3.2), 0.04, 0.08, "point")
    hip = ArmPose(0.8, -1.3, 0.2, "fist")
    body = replace(
        p0,
        near_arm=p0.near_arm,
        far_arm=p0.far_arm,
        spine=0.06,
        chest=0.02,
        head=-0.12,
        neck=0.04,
        pelvis_height=STAND_PELVIS - 0.5,
    )
    reach = arms(body, **{side: pointing, other: hip})
    antic = arms(body, **{side: ArmPose(0.9, 1.0, 0.3, "fist")})
    keys = [(raise_at * 0.55, antic), (raise_at, reach)]
    hold_end = duration - (8.0 if lower else 0.0)
    keys.append((hold_end, replace(reach, head=-0.18, spine=0.07)))
    if lower:
        keys.append((float(duration), arms(body, **{side: ArmPose(0.5, -0.2), other: REST_ARM})))

    def overlay(t, p):
        pulse = 0.08 * math.sin(math.pi * window(t, raise_at, raise_at + 8)) ** 2
        tap = 0.05 * math.sin(TAU * window(t, raise_at + 10, raise_at + 22))
        a = p.arm(side)
        return breathing(
            t, replace(p, **{f"{side}_arm": replace(a, shoulder=a.shoulder + pulse + tap)}), 0.5
        )

    return KeyedClip(start, duration, keys, overlay=overlay)


def surprise(start: ClipStart, duration: int) -> Clip:
    """Arms fly open with a small recoil hop-back of the pelvis and wide eyes."""
    p0 = upright(start.pose)
    open_arms = arms(
        replace(p0, pelvis_height=STAND_PELVIS + 1.0, squash=0.06, spine=-0.08, look_y=-0.2),
        ArmPose(1.35, 0.55, 0.3, "open"),
        ArmPose(1.35, 0.55, 0.3, "open"),
    )
    flinch = replace(
        p0,
        pelvis_height=STAND_PELVIS - 3.0,
        squash=-0.06,
        near_arm=ArmPose(0.5, 1.2, 0.2, "fist"),
        far_arm=ArmPose(0.5, 1.2, 0.2, "fist"),
    )
    keys = [
        (min(4.0, duration * 0.2), flinch),
        (min(10.0, duration * 0.5), open_arms),
        (float(duration), replace(open_arms, squash=0.02, pelvis_height=STAND_PELVIS)),
    ]

    def face(t, base):
        return adjust(base, eye_scale=0.15 * window(t, 2, 8))

    return KeyedClip(start, duration, keys, face_fn=face)


def stretch(
    start: ClipStart, duration: int, *, toes: bool = True, eyes_closed: bool = True
) -> Clip:
    p0 = upright(start.pose)
    reach = arms(
        replace(
            p0,
            squash=0.075,
            chest=-0.04,
            look_y=-0.6,
            pelvis_height=STAND_PELVIS + (2.2 if toes else 0),
        ),
        ArmPose(2.55, -0.05, 0.6, "open"),
        ArmPose(2.55, -0.05, 0.6, "open"),
    )
    if toes:
        reach = feet_at(reach, feet_xs(p0), pitch=0.32)
    mid = arms(replace(p0, squash=0.02), ArmPose(1.9, 0.7, 0.2), ArmPose(1.9, 0.7, 0.2))
    a = duration * 0.3
    b = duration * 0.55
    c = duration * 0.78
    after = arms(
        replace(p0, squash=0.01), ArmPose(2.2, 0.45, 0.3, "open"), ArmPose(2.2, 0.45, 0.3, "open")
    )
    keys = [(a, mid), (b, reach), (c, replace(reach, squash=0.07)), (float(duration), after)]

    def overlay(t, p):
        shake = 0.04 * math.sin(TAU * t / 5.5) * window(t, b - 2, b + 1) * (1 - window(t, c - 2, c))
        return replace(
            p,
            near_arm=replace(p.near_arm, shoulder=p.near_arm.shoulder + shake),
            far_arm=replace(p.far_arm, shoulder=p.far_arm.shoulder + shake),
        )

    def face(t, base):
        if not eyes_closed:
            return base
        closed = window(t, a, b) * (1 - window(t, c, c + 4))
        return adjust(
            base,
            eye_open=-0.95 * closed,
            lower_lid=0.6 * closed,
            mouth_open=0.35 * closed,
            mouth_round=0.6 * closed,
        )

    return KeyedClip(
        start,
        duration,
        keys,
        overlay=overlay,
        face_fn=face,
        no_blink=(a, c + 4) if eyes_closed else None,
    )


# ---------------------------------------------------------------- full body (keyed)
def crouch(start: ClipStart, duration: int, *, depth: float = 14.0, hold: bool = True) -> Clip:
    finite(depth)
    if not 2 <= depth <= 22:
        raise RenderError("crouch depth must be 2..22 units")
    p0 = upright(start.pose)
    low = arms(
        replace(
            p0, pelvis_height=STAND_PELVIS - depth, squash=-0.05, spine=0.05, neck=0.05, look_y=0.25
        ),
        ArmPose(0.75, 0.45, 0.2),
        ArmPose(0.75, 0.45, 0.2),
    )
    a = duration * (0.55 if hold else 0.45)
    keys = [(a, low), (float(duration), low if hold else p0)]
    return KeyedClip(start, duration, keys)


def squat(start: ClipStart, duration: int, *, depth: float = 17.0, reps: int = 1) -> Clip:
    finite(depth)
    if not 4 <= depth <= 22 or type(reps) is not int or not 1 <= reps <= 4:
        raise RenderError("squat depth 4..22 units and 1..4 reps")
    p0 = upright(start.pose)
    low = arms(
        replace(
            p0,
            pelvis_height=STAND_PELVIS - depth,
            squash=-0.05,
            spine=0.06,
            chest=-0.02,
            look_y=0.1,
        ),
        ArmPose(1.3, 0.25, 0.1, "open"),
        ArmPose(1.3, 0.25, 0.1, "open"),
    )
    keys = []
    per = duration / reps
    for r in range(reps):
        base = r * per
        keys.append((base + per * 0.45, low))
        keys.append((base + per * 0.6, replace(low, pelvis_height=low.pelvis_height + 1.2)))
        keys.append(
            (
                base + per * (0.97 if r == reps - 1 else 1.0),
                p0 if r == reps - 1 else replace(p0, pelvis_height=STAND_PELVIS - 1.0),
            )
        )
    keys[-1] = (float(duration), p0)
    return KeyedClip(start, duration, keys)


def recover(start: ClipStart, duration: int, *, wobble: float = 1.0) -> Clip:
    """Regain balance: arms windmill out, pelvis sways and damps, feet regather."""
    finite(wobble)
    if not 0 <= wobble <= 2:
        raise RenderError("recover wobble must be 0..2")
    p0 = start.pose
    stance = stance_feet(feet_mid(p0), p0.facing)
    rest = upright(p0, pelvis_x=sum(stance.values()) / 2)
    out = arms(
        replace(rest, pelvis_height=STAND_PELVIS - 2.0),
        ArmPose(1.4, 0.4, 0.2, "open"),
        ArmPose(1.4, 0.4, 0.2, "open"),
    )
    keys = [(duration * 0.3, out), (float(duration), rest)]

    def overlay(t, p):
        u = t / duration
        damp = (1 - u) ** 2
        sway = math.sin(TAU * 1.6 * u) * damp * wobble
        return replace(
            p,
            pelvis_tilt=p.pelvis_tilt + 0.06 * sway,
            spine=p.spine + 0.08 * sway,
            near_arm=replace(p.near_arm, shoulder=p.near_arm.shoulder + 0.35 * sway),
            far_arm=replace(p.far_arm, shoulder=p.far_arm.shoulder - 0.35 * sway),
            head=p.head - 0.05 * sway,
        )

    def face(t, base):
        return adjust(base, brow_tilt=0.3 * (1 - t / duration), eye_scale=0.08 * (1 - t / duration))

    return KeyedClip(start, duration, keys, overlay=overlay, stance=stance, face_fn=face)


def confident(start: ClipStart, duration: int) -> Clip:
    p0 = start.pose
    f = clamp(abs(p0.facing) + 0.1, 0.0, 0.45) * p0.sign
    pose = upright(
        p0,
        facing=f,
        chest=-0.05,
        spine=-0.02,
        head=0.1,
        neck=0.03,
        look_x=0.15,
        near_arm=ArmPose(0.8, -1.3, 0.25, "fist"),
        far_arm=ArmPose(0.8, -1.3, 0.25, "fist"),
    )
    a = min(10.0, duration * 0.5)
    return KeyedClip(
        start,
        duration,
        [(a, pose), (float(duration), pose)],
        overlay=lambda t, p: breathing(t, p, 0.6),
    )


def turn(start: ClipStart, duration: int, *, to: str = "front") -> Clip:
    return TurnClip(start, duration, to)


class TurnClip(Clip):
    """Facing change on planted feet; mirrors near/far channels when crossing the front."""

    name = "turn"

    def __init__(self, start: ClipStart, duration: int, to: str):
        super().__init__(start, duration)
        p0 = start.pose
        targets = {"front": 0.2 * p0.sign, "left": -0.9, "right": 0.9}
        if to not in targets:
            raise RenderError("turn 'to' must be front, left or right")
        self.f0, self.f1 = p0.facing, targets[to]
        self.rest = upright(p0)

    def pose(self, t):
        u = smoothstep(t / self.duration)
        p0 = self.start.pose
        f = lerp(self.f0, self.f1, u)
        base = blend(p0, replace(self.rest, facing=p0.facing), smoothstep(min(1.0, 2 * u)))
        dip = -1.2 * math.sin(math.pi * u)
        p = replace(
            base,
            facing=f if abs(f) > 1e-4 else 1e-4 * (1 if self.f1 >= 0 else -1),
            pelvis_height=base.pelvis_height + dip,
            look_x=0.6 * math.copysign(1, self.f1 - self.f0) * p0.sign * math.sin(math.pi * u),
        )
        if (p.facing >= 0) != (p0.facing >= 0):
            p = swap_sides(p)
        return p


def swap_sides(p: MellowPose) -> MellowPose:
    """Re-label near/far after a mirror so physical limbs keep their world positions."""
    return replace(
        p,
        near_arm=p.far_arm,
        far_arm=p.near_arm,
        near_foot=p.far_foot,
        far_foot=p.near_foot,
        look_x=-p.look_x,
    )


# ---------------------------------------------------------------- jump
G = 0.85  # character units / frame^2


def hermite(p0, m0, p1, m1, h, s):
    s2, s3 = s * s, s * s * s
    return (
        (2 * s3 - 3 * s2 + 1) * p0
        + (s3 - 2 * s2 + s) * h * m0
        + (-2 * s3 + 3 * s2) * p1
        + (s3 - s2) * h * m1
    )


class JumpClip(Clip):
    """Anticipation crouch, push-off, ballistic flight, toe-first landing and absorption."""

    name = "jump"

    def __init__(self, start, duration, *, height=26.0, crouch=13.0, travel=0.0, land_depth=None):
        super().__init__(start, duration)
        finite(height, crouch, travel)
        if not 6 <= height <= 45 or not 4 <= crouch <= 20 or abs(travel) > 40:
            raise RenderError("jump height 6..45, crouch 4..20, travel within +/-40 units")
        p0 = start.pose
        self.rest = upright(p0)
        self.h0 = self.rest.pelvis_height
        self.ant = 14.0
        self.push = 5.0
        self.v0 = math.sqrt(2 * G * height)
        self.flight = 2 * self.v0 / G
        self.h_to = STAND_PELVIS + 2.6
        self.h_c = self.h0 - crouch
        self.h_min = STAND_PELVIS - (land_depth if land_depth is not None else crouch * 0.95)
        self.absorb = max(3.0, 2 * (self.h_to - self.h_min) / self.v0)
        self.t_to = self.ant + self.push
        self.t_land = self.t_to + self.flight
        self.t_low = self.t_land + self.absorb
        if self.t_low + 6 > duration:
            raise RenderError(f"jump needs at least {math.ceil(self.t_low + 6)} frames")
        self.travel = travel * p0.sign
        self.feet0 = feet_xs(p0)
        r = self.rest
        self.arm_track = KeyTrack(
            [
                Key(0, p0),
                Key(self.ant * 0.35, arms(r, ArmPose(0.45, -0.25), ArmPose(0.45, -0.25))),
                Key(self.ant, arms(r, ArmPose(0.2, -0.55, -0.2), ArmPose(0.2, -0.55, -0.2))),
                Key(
                    self.t_to + 3,
                    arms(r, ArmPose(2.25, 0.12, 0.2, "open"), ArmPose(2.25, 0.12, 0.2, "open")),
                ),
                Key(
                    self.t_to + self.flight * 0.5,
                    arms(r, ArmPose(2.42, 0.28, 0.35, "open"), ArmPose(2.42, 0.28, 0.35, "open")),
                ),
                Key(
                    self.t_land,
                    arms(r, ArmPose(1.75, 0.3, 0.2, "open"), ArmPose(1.75, 0.3, 0.2, "open")),
                ),
                Key(
                    self.t_low + 1,
                    arms(r, ArmPose(1.05, 0.55, 0.3, "open"), ArmPose(1.05, 0.55, 0.3, "open")),
                ),
                Key(float(duration), r),
            ]
        )

    def _height(self, t):
        if t <= self.ant:
            u = t / self.ant
            # tiny rise before dropping (anticipation of the anticipation)
            return (
                self.h0
                + 0.8 * math.sin(math.pi * min(1, u * 3)) * (u < 1 / 3)
                + (self.h_c - self.h0) * smoothstep((u - 0.15) / 0.85)
            )
        if t <= self.t_to:
            return hermite(self.h_c, 0.0, self.h_to, self.v0, self.push, (t - self.ant) / self.push)
        if t <= self.t_land:
            tau = t - self.t_to
            return self.h_to + self.v0 * tau - 0.5 * G * tau * tau
        if t <= self.t_low:
            return hermite(
                self.h_to, -self.v0, self.h_min, 0.0, self.absorb, (t - self.t_land) / self.absorb
            )
        u = window(t, self.t_low, self.duration)
        return lerp(self.h_min, STAND_PELVIS, settle(u, 0.06, 1.6))

    def pose(self, t):
        t = clamp(t, 0.0, float(self.duration))
        p = self.arm_track.sample(t)
        h = self._height(t)
        prog = smootherstep(window(t, self.t_to, self.t_land))
        xs = {s: self.feet0[s] + self.travel * prog for s in self.feet0}
        if t < self.t_to:
            pitch = 0.55 * ease_in(window(t, self.ant + 1.0, self.t_to), 1.6)
            lift = 0.0
        elif t < self.t_land:
            tau = t - self.t_to
            u = tau / self.flight
            tuck = 13.0 * math.sin(math.pi * u) ** 1.4
            lift = max(0.0, h - self.h_to + tuck)
            pitch = lerp(0.55, 0.18, smoothstep(u * 1.3)) + 0.12 * math.sin(math.pi * u)
        else:
            lift = 0.0
            pitch = 0.18 * (1 - ease_out(window(t, self.t_land, self.t_land + 3.5)))
        squash = self._squash(t)
        body = replace(
            p,
            pelvis_x=sum(xs.values()) / 2,
            pelvis_height=h,
            squash=squash,
            spine=0.04 * smoothstep(window(t, 2, self.ant)) * (1 - window(t, self.ant, self.t_to)),
            neck=0.06 * (window(t, 2, self.ant) - window(t, self.ant, self.t_to))
            + 0.05 * math.sin(math.pi * window(t, self.t_land, self.t_low + 4)),
            look_y=0.3 * window(t, 2, self.ant) * (1 - window(t, self.ant, self.t_to))
            - 0.35 * math.sin(math.pi * window(t, self.t_to, self.t_land)),
            facing=lerp(
                self.start.pose.facing, 0.25 * self.start.pose.sign, smoothstep(t / self.ant)
            ),
            near_foot=FootState(xs["near"], lift, pitch),
            far_foot=FootState(xs["far"], lift, pitch),
        )
        return body

    def _squash(self, t):
        if t <= self.ant:
            return -0.07 * smoothstep(t / self.ant)
        if t <= self.t_to:
            return lerp(-0.07, 0.09, smoothstep((t - self.ant) / self.push))
        if t <= self.t_land:
            u = (t - self.t_to) / self.flight
            return 0.09 * (1 - smoothstep(u * 2)) + 0.04 * smoothstep((u - 0.6) / 0.4)
        if t <= self.t_low:
            return lerp(
                0.04, -0.11, ease_out(window(t, self.t_land, self.t_land + self.absorb * 0.6))
            )
        u = window(t, self.t_low, self.duration)
        return -0.11 * (1 - settle(u, 0.25, 1.3))

    def face(self, t, base):
        air = math.sin(math.pi * window(t, self.t_to - 2, self.t_land))
        impact = math.sin(math.pi * window(t, self.t_land, self.t_low + 4))
        prep = window(t, 1, self.ant) * (1 - window(t, self.ant, self.t_to))
        f = adjust(base, brow_tilt=-0.35 * prep, upper_lid=0.25 * prep, brow_raise=-0.8 * prep)
        f = adjust(
            f,
            eye_scale=0.25 * air,
            brow_raise=2.4 * air,
            mouth_open=0.5 * air,
            mouth_round=0.6 * air,
        )
        return adjust(f, eye_open=-0.55 * impact, lower_lid=0.45 * impact, mouth_curve=0.3 * impact)

    def suppress_blinks(self, t):
        return self.ant - 2 <= t <= self.t_low + 5


def jump(start, duration, **params):
    return JumpClip(start, duration, **params)


def land(start: ClipStart, duration: int, *, depth: float = 12.0) -> Clip:
    """Impact absorption from the current pose (use after a fall or a custom air pose)."""
    finite(depth)
    if not 3 <= depth <= 20:
        raise RenderError("land depth must be 3..20")
    p0 = start.pose
    rest = upright(p0)
    rest = feet_at(rest, feet_xs(p0))
    low = arms(
        replace(rest, pelvis_height=STAND_PELVIS - depth, squash=-0.1, neck=0.05),
        ArmPose(1.1, 0.55, 0.3, "open"),
        ArmPose(1.1, 0.55, 0.3, "open"),
    )
    a = min(6.0, duration * 0.3)
    return KeyedClip(start, duration, [(a, low), (float(duration), rest)])


# ---------------------------------------------------------------- jumping jacks
class JumpingJackClip(Clip):
    name = "jumping_jack"

    def __init__(self, start, duration, *, reps=3, width=12.0, hop=3.2):
        super().__init__(start, duration)
        finite(width, hop)
        if type(reps) is not int or not 1 <= reps <= 8 or not 4 <= width <= 14 or not 1 <= hop <= 8:
            raise RenderError("jumping_jack reps 1..8, width 4..14, hop 1..8")
        p0 = start.pose
        self.reps = reps
        self.prep = 6.0
        self.end = 4.0
        self.half = (duration - self.prep - self.end) / (2 * reps)
        if self.half < 4.5:
            raise RenderError("jumping_jack needs >= 9 frames per rep plus 10")
        self.f1 = 0.12 * p0.sign
        self.width = width
        self.hop = hop
        self.center = feet_mid(p0)
        self.stances = []
        out = stance_feet(self.center, self.f1, width)
        inn = stance_feet(self.center, self.f1, 0.0)
        cur = feet_xs(p0)
        for k in range(2 * reps):
            nxt = out if k % 2 == 0 else inn
            self.stances.append((cur, nxt))
            cur = nxt
        self.rest = upright(p0)

    def _half(self, t):
        k = int((t - self.prep) // self.half)
        k = max(0, min(2 * self.reps - 1, k))
        u = clamp((t - self.prep - k * self.half) / self.half, 0.0, 1.0)
        return k, u

    def pose(self, t):
        t = clamp(t, 0.0, float(self.duration))
        p0 = self.start.pose
        turn_u = smoothstep(t / (self.prep + self.half))
        facing = lerp(p0.facing, self.f1, turn_u)
        if t < self.prep:
            u = t / self.prep
            dip = -2.4 * math.sin(math.pi * u * 0.5)
            p = blend(p0, replace(self.rest, facing=p0.facing), smoothstep(u))
            return replace(
                p,
                facing=facing,
                pelvis_height=STAND_PELVIS + dip,
                squash=-0.03 * math.sin(math.pi * u),
                pelvis_x=feet_mid(p0),
            )
        k, u = self._half(t)
        a, b = self.stances[k]
        going_out = k % 2 == 0
        lift_u = window(u, 0.12, 0.62)
        air = 0.0 < lift_u < 1.0
        xs = {s: lerp(a[s], b[s], smootherstep(lift_u)) for s in a}
        lift = self.hop * math.sin(math.pi * lift_u) if air else 0.0
        stance_w = abs(xs["far"] - xs["near"])
        base = STAND_PELVIS - 0.18 * max(0.0, stance_w - 13.0)
        pre = -2.0 * math.sin(math.pi * window(u, 0.0, 0.12))
        post = -2.6 * math.sin(math.pi * window(u, 0.62, 1.0))
        if k == 0:
            pre = -2.4 + 2.4 * smoothstep(window(u, 0.0, 0.12)) - 0.0
        h = base + lift + 1.5 * math.sin(math.pi * lift_u) + pre + post
        arm_u = smoothstep(window(u, 0.0, 1.0))
        up = ArmPose(2.5, 0.35, 0.4, "open")
        down = REST_ARM if k == 0 else ArmPose(0.28, -0.1, 0.05, "relaxed")

        def arm(x, y):
            return ArmPose(
                lerp(x.shoulder, y.shoulder, arm_u),
                lerp(x.elbow, y.elbow, arm_u),
                lerp(x.wrist, y.wrist, arm_u),
                y.hand if arm_u > 0.5 else x.hand,
            )

        if going_out:
            near = arm(down, up)
            far = arm(down, up)
        else:
            end = REST_ARM if k == 2 * self.reps - 1 else ArmPose(0.28, -0.1, 0.05)
            near = arm(up, end)
            far = arm(up, end)
        pitch = 0.25 * math.sin(math.pi * lift_u) if air else 0.0
        sq = 0.04 * math.sin(math.pi * lift_u) - 0.05 * math.sin(math.pi * window(u, 0.62, 1.0))
        if t > self.duration - self.end:
            v = window(t, self.duration - self.end, self.duration)
            h = lerp(h, STAND_PELVIS, smoothstep(v))
        return replace(
            self.rest,
            facing=facing,
            pelvis_x=sum(xs.values()) / 2,
            pelvis_height=h,
            squash=sq,
            neck=0.03 * math.sin(math.pi * lift_u),
            look_y=-0.1,
            near_arm=near,
            far_arm=far,
            near_foot=FootState(xs["near"], lift, pitch),
            far_foot=FootState(xs["far"], lift, pitch),
        )


def jumping_jack(start, duration, **params):
    return JumpingJackClip(start, duration, **params)


# ---------------------------------------------------------------- dance
def dance(
    start: ClipStart,
    duration: int,
    *,
    beats: int = 4,
    beat_frames: float = 8.0,
    finish: str = "confident",
) -> Clip:
    if type(beats) is not int or not 1 <= beats <= 12:
        raise RenderError("dance beats must be 1..12")
    finite(beat_frames)
    if not 5 <= beat_frames <= 15:
        raise RenderError("beat_frames must be 5..15")
    if finish not in ("confident", "none"):
        raise RenderError("finish must be 'confident' or 'none'")
    groove = beats * beat_frames + 2
    if groove + (8 if finish == "confident" else 0) > duration:
        raise RenderError("dance duration too short for the requested beats")
    p0 = start.pose
    rest = upright(p0, facing=clamp(abs(p0.facing), 0.15, 0.4) * p0.sign)
    keys = []
    for k in range(beats):
        side = 1 if k % 2 == 0 else -1
        up_arm = ArmPose(2.35, 0.95, 0.3, "fist")
        low_arm = ArmPose(0.7, -1.05, 0.2, "fist")
        pose = replace(
            rest,
            pelvis_x=rest.pelvis_x + 2.2 * side * p0.sign,
            pelvis_tilt=-0.07 * side,
            chest=0.06 * side,
            head=-0.1 * side,
            look_x=0.3 * side,
            near_arm=up_arm if side < 0 else low_arm,
            far_arm=up_arm if side > 0 else low_arm,
            near_foot=FootState(p0.near_foot.x, 0.0, 0.32 if side > 0 else 0.0),
            far_foot=FootState(p0.far_foot.x, 0.0, 0.32 if side < 0 else 0.0),
        )
        keys.append((2 + k * beat_frames + beat_frames * 0.5, pose))
    if finish == "confident":
        pose = upright(
            p0,
            facing=clamp(abs(p0.facing) + 0.12, 0.2, 0.45) * p0.sign,
            chest=-0.05,
            head=0.1,
            neck=0.03,
            look_x=0.2,
            pelvis_height=STAND_PELVIS + 0.4,
            near_arm=ArmPose(0.95, -1.55, 0.3, "fist"),
            far_arm=ArmPose(0.95, -1.55, 0.3, "fist"),
        )
        keys.append((min(duration - 2.0, groove + 9.0), pose))
        keys.append((float(duration), replace(pose, head=0.12)))
    else:
        keys.append((float(duration), rest))

    def overlay(t, p):
        if t <= groove:
            bounce = abs(math.sin(math.pi * (t - 2) / beat_frames)) if t > 2 else 0.0
            h = p.pelvis_height - 2.8 * (1 - bounce) * window(t, 0, 4)
            return replace(
                p, pelvis_height=h, squash=p.squash - 0.04 * (1 - bounce) * window(t, 0, 4)
            )
        u = window(t, groove, groove + 9)
        return replace(
            p,
            pelvis_height=p.pelvis_height - 3.0 * math.sin(math.pi * u),
            squash=p.squash - 0.05 * math.sin(math.pi * u),
        )

    def face(t, base):
        f = adjust(base, mouth_open=0.3 * (1 - window(t, groove, groove + 6)))
        if finish == "confident":
            w = window(t, groove + 2, groove + 10)
            f = adjust(f, lower_lid=0.15 * w, brow_asym=1.3 * w, mouth_curve=0.15 * w)
        return f

    return KeyedClip(start, duration, keys, overlay=overlay, face_fn=face)


# ---------------------------------------------------------------- locomotion
WALK_SPEED = 1.55  # units / frame (46.5 units/s)
RUN_SPEED = 3.3
TRAVEL_FACING = 0.92


@dataclass(frozen=True)
class LocoSegment:
    gait: str  # walk | run | start_walk | stop
    frames: int
    speed: float = 1.0
    stop: bool = False
    expression: str | None = None


@dataclass
class _Track:
    t: list[float] = field(default_factory=list)
    d: list[float] = field(default_factory=list)
    phi: list[float] = field(default_factory=list)
    v: list[float] = field(default_factory=list)
    g: list[float] = field(default_factory=list)


def _stride(v: float, g: float) -> float:
    walk = 7.0 + 17.5 * smoothstep(min(1.0, v / WALK_SPEED)) + 4.0 * max(0.0, v / WALK_SPEED - 1)
    run = 12.0 + 21.0 * min(1.0, v / RUN_SPEED)
    return lerp(walk, run, g)


def _duty(v: float, g: float) -> float:
    walk = lerp(0.9, 0.6, smoothstep(v / WALK_SPEED))
    return lerp(walk, 0.32, g)


class LocomotionClip(Clip):
    """Walk/run with planned footsteps, a continuous phase clock and exact planted feet.

    Consecutive locomotion requests are merged into one clip so phase, speed and foot
    anchors remain continuous across walk -> run -> stop.
    """

    name = "locomotion"

    def __init__(self, start: ClipStart, segments: list[LocoSegment], direction: str):
        total = sum(s.frames for s in segments)
        super().__init__(start, total)
        if not segments or not segments[-1].stop and segments[-1].gait != "stop":
            raise RenderError("A locomotion sequence must end with stop=True or a 'stop' action")
        p0 = start.pose
        self.dir = 1 if direction == "right" else -1
        if direction not in ("left", "right"):
            raise RenderError("locomotion direction must be 'left' or 'right'")
        self.segments = segments
        self.sign0 = p0.sign
        self.turning = self.sign0 != self.dir or abs(p0.facing) < 0.7
        self.turn_frames = 9.0 if self.turning else 0.0
        self.f_travel = TRAVEL_FACING * self.dir
        self.start_feet = {"A": p0.near_foot.x, "B": p0.far_foot.x}
        self.x0 = p0.pelvis_x
        roles = {"A": "near", "B": "far"}
        if self.dir != self.sign0:
            roles = {"A": "far", "B": "near"}
        hips = hip_offsets(TRAVEL_FACING)
        # A foot's lateral offset relative to the pelvis in the travel frame.
        self.bias = {k: self.dir * hips[r] for k, r in roles.items()}
        self.rest = upright(p0)
        self._build_profile()
        self._integrate()
        self._terminate()

    # -- speed profile
    def _build_profile(self):
        keys = [(0.0, 0.0, 0.0)]
        t = 0.0
        v = 0.0
        g = 0.0
        launch = self.turn_frames * 0.9
        for i, seg in enumerate(self.segments):
            s0, s1 = t, t + seg.frames
            begin = max(s0, launch) if i == 0 else s0
            if seg.gait == "stop":
                keys.append((begin, v, g))
                keys.append((s1 - 3, 0.0, 0.0))
                v, g = 0.0, 0.0
            else:
                target_v = (RUN_SPEED if seg.gait == "run" else WALK_SPEED) * seg.speed
                target_g = 1.0 if seg.gait == "run" else 0.0
                ramp = min(20.0 if seg.gait != "run" else 16.0, (s1 - begin) * 0.45)
                keys.append((begin, v, g))
                keys.append((begin + ramp, target_v, target_g))
                v, g = target_v, target_g
                if seg.stop:
                    stop_len = min(26.0, seg.frames * 0.45)
                    keys.append((s1 - stop_len - 3, v, g))
                    keys.append((s1 - 3, 0.0, 0.0))
                    v, g = 0.0, 0.0
            t = s1
        keys.append((float(self.duration), 0.0, 0.0))
        clean = []
        for k in keys:
            if clean and k[0] <= clean[-1][0] + 1e-6:
                clean[-1] = (clean[-1][0], k[1], k[2])
            else:
                clean.append(k)
        self.keys = clean

    def _speed(self, t):
        keys = self.keys
        if t <= keys[0][0]:
            return keys[0][1], keys[0][2]
        for (t0, v0, g0), (t1, v1, g1) in zip(keys, keys[1:], strict=False):
            if t <= t1:
                u = smoothstep((t - t0) / (t1 - t0))
                return lerp(v0, v1, u), lerp(g0, g1, u)
        return keys[-1][1], keys[-1][2]

    def _integrate(self):
        tr = _Track()
        dt = 0.25
        n = int(self.duration / dt) + 1
        d = 0.0
        phi = _duty(0.0, 0.0) - 0.03  # foot A is about to lift
        for i in range(n):
            t = i * dt
            v, g = self._speed(t)
            tr.t.append(t)
            tr.d.append(d)
            tr.phi.append(phi)
            tr.v.append(v)
            tr.g.append(g)
            vm, gm = self._speed(t + dt / 2)
            d += vm * dt
            phi += (vm / _stride(vm, gm)) * dt / 2 if vm > 1e-6 else 0.0
        self.tr = tr
        self.phi0 = tr.phi[0]

    def _terminate(self):
        """Nudge the phase so that both feet are planted when the speed reaches zero."""
        tr = self.tr
        stop_t = self.keys[-2][0] if len(self.keys) > 1 else self.duration
        decel_start = (
            max(k[0] for k in self.keys if k[1] > 0) if any(k[1] > 0 for k in self.keys) else 0
        )
        for _ in range(3):
            end_phi = tr.phi[-1]
            best = None
            for j in range(0, 200):
                cand = end_phi + j * 0.005
                if all(self._state_at_phi(cand, foot)[0] == "stance" for foot in ("A", "B")):
                    margin_ok = all(
                        self._state_at_phi(cand + e, foot)[0] == "stance"
                        for foot in ("A", "B")
                        for e in (-0.01,)
                    )
                    if margin_ok:
                        best = cand
                        break
            if best is None or best - end_phi < 1e-9:
                break
            delta = best - end_phi
            for i, t in enumerate(tr.t):
                tr.phi[i] += delta * smootherstep(window(t, decel_start, stop_t))

    # -- phase / time lookups
    def _t_at_phi(self, phi):
        tr = self.tr
        if phi <= tr.phi[0]:
            return 0.0
        if phi >= tr.phi[-1]:
            return float(self.duration)
        i = bisect.bisect_left(tr.phi, phi)
        p0, p1 = tr.phi[i - 1], tr.phi[i]
        if p1 - p0 < 1e-12:
            return tr.t[i]
        return lerp(tr.t[i - 1], tr.t[i], (phi - p0) / (p1 - p0))

    def _at(self, arr, t):
        tr = self.tr
        x = clamp(t, 0.0, tr.t[-1]) / 0.25
        i = int(x)
        if i >= len(arr) - 1:
            return arr[-1]
        return lerp(arr[i], arr[i + 1], x - i)

    def _offset(self, foot):
        return 0.0 if foot == "A" else 0.5

    def _cycle_duty(self, foot, n):
        t_land = self._t_at_phi(n - self._offset(foot))
        v = self._at(self.tr.v, t_land)
        g = self._at(self.tr.g, t_land)
        return _duty(v, g), g

    def _state_at_phi(self, phi, foot):
        q = phi + self._offset(foot)
        n = math.floor(q)
        p = q - n
        beta, _ = self._cycle_duty(foot, n)
        return ("stance" if p < beta else "swing"), n, p, beta

    def _anchor(self, foot, n):
        landing_phi = n - self._offset(foot)
        if landing_phi <= self.phi0 + 1e-9:
            return self.start_feet[foot]
        beta, _ = self._cycle_duty(foot, n)
        t_mid = self._t_at_phi(landing_phi + beta / 2)
        return self.x0 + self.dir * self._at(self.tr.d, t_mid) + self.bias[foot]

    def _foot(self, t, foot):
        phi = self._at(self.tr.phi, t)
        state, n, p, beta = self._state_at_phi(phi, foot)
        _, g = self._cycle_duty(foot, n)
        toe_max = lerp(0.45, 0.75, g)
        land_pitch = lerp(-0.26, 0.06, g)
        landed_here = (n - self._offset(foot)) > self.phi0 + 1e-9
        if state == "stance":
            x = self._anchor(foot, n)
            off = min(0.14, beta * 0.35)
            pitch = 0.0
            v_now = self._at(self.tr.v, t)
            if landed_here and p < 0.09:
                pitch = land_pitch * (1 - smoothstep(p / 0.09)) * min(1.0, v_now / 0.6)
            if p > beta - off:
                v = self._at(self.tr.v, t)
                if v > 0.05:
                    pitch = toe_max * smoothstep((p - beta + off) / off) * min(1.0, v / 0.6)
            return FootState(x, 0.0, pitch), 0.0
        u = (p - beta) / (1 - beta)
        a, b = self._anchor(foot, n), self._anchor(foot, n + 1)
        x = lerp(a, b, smootherstep(u))
        step_len = abs(b - a)
        height = lerp(5.5, 13.0, g) * min(1.0, step_len / 18.0 + 0.25)
        # Running feet leave and clear the ground quickly so the flight phase reads.
        shaped = lerp(u, u**0.7, g)
        lift = height * math.sin(math.pi * shaped) ** lerp(1.2, 0.8, g)
        v = self._at(self.tr.v, t)
        start_pitch = toe_max * min(1.0, v / 0.6) if v > 0.05 else 0.0
        pitch = lerp(start_pitch, land_pitch, smoothstep(u)) + 0.25 * g * math.sin(math.pi * u)
        return FootState(x, lift, pitch), lift

    def pose(self, t):
        t = clamp(t, 0.0, float(self.duration))
        tr = self.tr
        d = self._at(tr.d, t)
        v = self._at(tr.v, t)
        g = self._at(tr.g, t)
        phi = self._at(tr.phi, t)
        vn = min(1.2, v / WALK_SPEED)
        acc = (self._at(tr.v, t + 2) - self._at(tr.v, t - 2)) / 4
        feet = {k: self._foot(t, k)[0] for k in ("A", "B")}
        # facing: turn first, then hold travel facing
        if self.turning:
            u = smoothstep(t / self.turn_frames)
            facing = lerp(self.start.pose.facing, self.f_travel, u)
            if abs(facing) < 1e-4:
                facing = 1e-4 * self.dir
        else:
            facing = lerp(self.start.pose.facing, self.f_travel, smoothstep(t / 6))
        sign = 1 if facing >= 0 else -1
        same = sign == self.sign0
        near_k, far_k = ("A", "B") if same else ("B", "A")
        pelvis_x = self.x0 + self.dir * d
        walk_h = STAND_PELVIS - 0.9 * vn + 0.8 * vn * math.cos(4 * math.pi * (phi - 0.3))
        run_h = STAND_PELVIS - 3.4 - 2.2 * math.cos(4 * math.pi * (phi - 0.18))
        h = lerp(walk_h, run_h, g)
        lean = (0.035 + 0.15 * g) * min(1.0, vn) + clamp(acc * 2.2, -0.1, 0.12)
        # Arm counter-swing from the actual foot positions (opposite arm to leg).
        half = max(4.0, _stride(v, g) / 2)
        arms_out = {}
        for k in ("A", "B"):
            rel = (feet[k].x - pelvis_x) * self.dir - self.bias[k] * self.dir
            fwd_leg = clamp(rel / half, -1.3, 1.3)
            amp = lerp(0.42, 0.85, g) * min(1.0, vn * 1.2)
            # Same-side arm swings opposite to its leg (left leg forward = right arm forward).
            swing = -fwd_leg * amp
            flex = lerp(0.3 + 0.25 * max(0.0, swing), 1.55, g)
            arms_out[k] = (swing, flex)
        roles = {"near": near_k, "far": far_k}
        arm_poses = {}
        for role, k in roles.items():
            swing, flex = arms_out[k]
            if role == "near" and swing > 0:
                swing *= 0.65  # near arm swings across the body in 3/4 view; keep it readable
            arm_poses[role] = swing_arm(
                role, swing, flex, out=lerp(0.3, 0.38, g), hand="fist" if g > 0.5 else "relaxed"
            )
        loco = replace(
            self.rest,
            facing=facing,
            pelvis_x=pelvis_x,
            pelvis_height=h,
            pelvis_tilt=0.035 * math.sin(TAU * phi) * min(1.0, vn),
            spine=lean,
            chest=-0.25 * lean + 0.03 * math.sin(TAU * phi) * vn,
            neck=-0.15 * lean,
            head=-0.3 * lean + 0.02 * math.sin(4 * math.pi * phi) * vn,
            squash=(-0.035 * math.cos(4 * math.pi * (phi - 0.18))) * g,
            look_x=0.45 * smoothstep(t / 6),
            near_arm=arm_poses["near"],
            far_arm=arm_poses["far"],
            near_foot=feet[near_k],
            far_foot=feet[far_k],
        )
        # Blend the upper body in from the start pose (feet/pelvis stay exact).
        w = smoothstep(t / max(6.0, self.turn_frames + 2))
        if w < 1:
            start = self.start.pose
            if (start.facing >= 0) != (loco.facing >= 0):
                start = swap_sides(start)
            start = replace(
                start,
                facing=loco.facing,
                pelvis_x=loco.pelvis_x,
                near_foot=loco.near_foot,
                far_foot=loco.far_foot,
            )
            loco = blend(start, loco, w)
            loco = replace(loco, near_foot=feet[near_k], far_foot=feet[far_k])
        return loco

    def segment_at(self, t: float) -> LocoSegment:
        acc = 0
        for seg in self.segments:
            acc += seg.frames
            if t < acc:
                return seg
        return self.segments[-1]

    def face(self, t, base):
        g = self._at(self.tr.g, t)
        return adjust(base, mouth_open=0.15 * g)


LOCOMOTION_ACTIONS = ("walk", "run", "start_walk", "stop")

PRESETS: dict[str, Callable[..., Clip]] = {
    "idle": idle,
    "blink": blink,
    "look": look,
    "head_tilt": head_tilt,
    "wave": wave,
    "hands_up": hands_up,
    "hands_down": hands_down,
    "point": point,
    "surprise": surprise,
    "stretch": stretch,
    "crouch": crouch,
    "squat": squat,
    "jump": jump,
    "land": land,
    "recover": recover,
    "jumping_jack": jumping_jack,
    "dance": dance,
    "confident": confident,
    "turn": turn,
}

PRESET_DOCS = {
    "idle": "Breathing, weight sway and a natural blink. params: energy 0..2, blink bool",
    "blink": "Idle with a forced blink.",
    "look": "Eyes lead, then head and body turn. params: direction left|right, amount 0..1",
    "head_tilt": "Settling head tilt. params: angle +/-0.4 rad",
    "wave": "One-hand wave with wrist lag. params: hand near|far, waves 0.5..6, lower bool",
    "hands_up": "Anticipation dip, staggered raise on toes. params: lower bool, toes bool",
    "hands_down": "Elbow-led lowering with overshoot settle.",
    "point": "Point with straight elbow, other hand on hip. params: hand, elevation, lower",
    "surprise": "Flinch then arms fly open, eyes widen.",
    "stretch": "Rise on toes, arms overhead, eyes closed. params: toes, eyes_closed",
    "crouch": "Crouch on planted feet. params: depth 2..22, hold bool",
    "squat": "Squat and stand, arms out for balance. params: depth 4..22, reps 1..4",
    "jump": "Anticipation, ballistic flight, toe landing, absorption. params: height, crouch,"
    " travel, land_depth",
    "land": "Impact absorption from the current pose. params: depth 3..20",
    "recover": "Balance recovery with damped sway and foot regathering. params: wobble 0..2",
    "jumping_jack": "Hopping jumping jacks. params: reps 1..8, width 4..14, hop 1..8",
    "dance": "Beat bounces, hip sway, alternating fist pumps, confident finish. params: beats,"
    " beat_frames, finish",
    "confident": "Hands on hips, chest out.",
    "turn": "Turn on planted feet. params: to front|left|right",
    "walk": "Walk (merged with neighbouring locomotion). params: direction, speed 0.5..1.4,"
    " stop bool",
    "run": "Run with flight phase (merged). params: direction, speed 0.6..1.3, stop bool",
    "start_walk": "Accelerate from standing into a walk; must be followed by walk/run/stop.",
    "stop": "Decelerate to a planted stop (ends a locomotion sequence).",
}


def blend_face_track(prev: FaceState, target: FaceState, t: float, frames: float = 8.0):
    return blend_faces(prev, target, smoothstep(t / frames))
