"""Easing, pose blending, monotone keyframe interpolation and foot-settling steps.

Keyframes are interpolated per channel with PCHIP (monotone cubic Hermite): C1 continuous,
no overshoot between keys, and zero velocity at clip ends so consecutive clips join without
snapping. Hand shapes switch at the middle of a key segment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from reelforge.rendering.model import RenderError, finite

from .rig import (
    BODY_CHANNELS,
    ArmPose,
    FootState,
    MellowPose,
    body_vector,
    clamp,
    lerp,
    smoothstep,
    with_body,
)


def ease_in_out(u: float) -> float:
    return smoothstep(u)


def smootherstep(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return u * u * u * (u * (6 * u - 15) + 10)


def ease_out(u: float, power: float = 2.0) -> float:
    u = clamp(u, 0.0, 1.0)
    return 1 - (1 - u) ** power


def ease_in(u: float, power: float = 2.0) -> float:
    u = clamp(u, 0.0, 1.0)
    return u**power


def ease_out_back(u: float, overshoot: float = 1.4) -> float:
    u = clamp(u, 0.0, 1.0) - 1
    return 1 + u * u * ((overshoot + 1) * u + overshoot)


def settle(u: float, amount: float = 0.12, cycles: float = 1.5) -> float:
    """0 -> 1 with a decaying overshoot (follow-through) that ends exactly at 1."""
    u = clamp(u, 0.0, 1.0)
    base = smoothstep(min(1.0, u * 1.6))
    wobble = amount * math.sin(math.pi * cycles * u) * (1 - u) ** 2 if u > 0 else 0
    return base + wobble * smoothstep(u * 3)


def window(t: float, start: float, end: float) -> float:
    """Normalised position of t inside [start, end], clamped."""
    if end <= start:
        return 1.0 if t >= end else 0.0
    return clamp((t - start) / (end - start), 0.0, 1.0)


# ---------------------------------------------------------------- pose vectors
ARM_JOINTS = ("shoulder", "elbow", "wrist")
FOOT_FIELDS = ("x", "lift", "pitch")


def pose_vector(p: MellowPose) -> tuple[float, ...]:
    values = list(body_vector(p))
    for arm in (p.near_arm, p.far_arm):
        values += [getattr(arm, j) for j in ARM_JOINTS]
    for foot in (p.near_foot, p.far_foot):
        values += [getattr(foot, j) for j in FOOT_FIELDS]
    return tuple(values)


def from_vector(v, hands: tuple[str, str]) -> MellowPose:
    n = len(BODY_CHANNELS)
    base = with_body(MellowPose(), tuple(v[:n]))
    a = v[n:]
    near = ArmPose(a[0], a[1], a[2], hands[0])
    far = ArmPose(a[3], a[4], a[5], hands[1])
    feet = a[6:]
    nf = FootState(feet[0], max(0.0, feet[1]), feet[2])
    ff = FootState(feet[3], max(0.0, feet[4]), feet[5])
    return replace(base, near_arm=near, far_arm=far, near_foot=nf, far_foot=ff)


def blend(a: MellowPose, b: MellowPose, u: float) -> MellowPose:
    """Channel-wise blend. Facing signs must match (turns are authored by clips)."""
    finite(u)
    u = clamp(u, 0.0, 1.0)
    if a.sign != b.sign and min(abs(a.facing), abs(b.facing)) > 1e-6:
        raise RenderError("Cannot blend poses with opposite facing; author a turn instead")
    va, vb = pose_vector(a), pose_vector(b)
    hands = (
        (a.near_arm.hand if u < 0.5 else b.near_arm.hand),
        (a.far_arm.hand if u < 0.5 else b.far_arm.hand),
    )
    return from_vector(tuple(x + (y - x) * u for x, y in zip(va, vb, strict=True)), hands)


def add_arm(arm: ArmPose, shoulder=0.0, elbow=0.0, wrist=0.0, hand=None) -> ArmPose:
    return ArmPose(arm.shoulder + shoulder, arm.elbow + elbow, arm.wrist + wrist, hand or arm.hand)


# ---------------------------------------------------------------- keyframes
@dataclass(frozen=True)
class Key:
    frame: float
    pose: MellowPose


def _pchip_slopes(times, values):
    n = len(times)
    if n < 2:
        return [0.0] * n
    h = [times[i + 1] - times[i] for i in range(n - 1)]
    d = [(values[i + 1] - values[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    for k in range(1, n - 1):
        if d[k - 1] == 0 or d[k] == 0 or (d[k - 1] > 0) != (d[k] > 0):
            m[k] = 0.0
        else:
            w1 = 2 * h[k] + h[k - 1]
            w2 = h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    return m


class KeyTrack:
    """PCHIP interpolation over a sequence of full poses."""

    def __init__(self, keys: list[Key]):
        if len(keys) < 1:
            raise RenderError("A key track needs at least one key")
        frames = [k.frame for k in keys]
        if any(b <= a for a, b in zip(frames, frames[1:], strict=False)):
            raise RenderError("Key frames must strictly increase")
        signs = {k.pose.sign for k in keys if abs(k.pose.facing) > 1e-6}
        if len(signs) > 1:
            raise RenderError("Keyed clips cannot change facing sign; use a turn clip")
        self.keys = keys
        self.frames = frames
        self.vectors = [pose_vector(k.pose) for k in keys]
        channels = len(self.vectors[0])
        self.slopes = [_pchip_slopes(frames, [v[c] for v in self.vectors]) for c in range(channels)]

    def sample(self, t: float) -> MellowPose:
        keys, frames = self.keys, self.frames
        if len(keys) == 1 or t <= frames[0]:
            return keys[0].pose
        if t >= frames[-1]:
            return keys[-1].pose
        i = 0
        while frames[i + 1] < t:
            i += 1
        t0, t1 = frames[i], frames[i + 1]
        h = t1 - t0
        s = (t - t0) / h
        h00 = 2 * s**3 - 3 * s**2 + 1
        h10 = s**3 - 2 * s**2 + s
        h01 = -2 * s**3 + 3 * s**2
        h11 = s**3 - s**2
        a, b = self.vectors[i], self.vectors[i + 1]
        out = []
        for c in range(len(a)):
            m0, m1 = self.slopes[c][i], self.slopes[c][i + 1]
            out.append(h00 * a[c] + h10 * h * m0 + h01 * b[c] + h11 * h * m1)
        pa, pb = keys[i].pose, keys[i + 1].pose
        hands = (
            pa.near_arm.hand if s < 0.5 else pb.near_arm.hand,
            pa.far_arm.hand if s < 0.5 else pb.far_arm.hand,
        )
        return from_vector(out, hands)


# ---------------------------------------------------------------- feet
def step_foot(start_x: float, end_x: float, u: float, *, height: float = 4.0) -> FootState:
    """A small in-place step (lift, carry, place) with a gentle toe roll."""
    u = clamp(u, 0.0, 1.0)
    dist = abs(end_x - start_x)
    lift = height * min(1.0, 0.35 + dist / 8.0) * math.sin(math.pi * u) ** 1.3
    pitch = (
        0.22 * math.sin(math.pi * min(1.0, u * 1.4)) * (1 - u) - 0.12 * math.sin(math.pi * u) * u
    )
    return FootState(lerp(start_x, end_x, smootherstep(u)), lift, pitch)


def settle_feet(
    start: dict[str, float],
    target: dict[str, float],
    t: float,
    *,
    begin: float = 0.0,
    step_frames: float = 9.0,
    threshold: float = 1.2,
    height: float = 4.0,
) -> tuple[dict[str, FootState], float]:
    """Step feet from ``start`` to ``target`` one at a time; returns states and weight shift.

    The foot with the larger error steps first; a foot within ``threshold`` stays planted
    exactly. The returned weight value (-1 near .. +1 far) tells the caller which leg holds
    the body so the pelvis can shift over the support foot.
    """
    order = sorted(start, key=lambda s: -abs(target[s] - start[s]))
    states = {}
    weight = 0.0
    slot = 0
    for side in order:
        err = target[side] - start[side]
        if abs(err) < threshold:
            states[side] = FootState(start[side])
            continue
        s0 = begin + slot * step_frames * 0.75
        u = window(t, s0, s0 + step_frames)
        states[side] = step_foot(start[side], target[side], u, height=height)
        lifted = math.sin(math.pi * u)
        weight += (-1 if side == "far" else 1) * lifted  # support moves to the other foot
        slot += 1
    return states, clamp(weight, -1.0, 1.0)


def feet_xs(pose: MellowPose) -> dict[str, float]:
    return {"near": pose.near_foot.x, "far": pose.far_foot.x}


def feet_mid(pose: MellowPose) -> float:
    return (pose.near_foot.x + pose.far_foot.x) / 2
