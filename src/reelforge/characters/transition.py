"""A bounded idle/walk/run contact controller. Analytical phase; no per-frame history."""

import math
from dataclasses import dataclass

from reelforge.rendering.model import RenderError, finite

from .contact import FootPlacement, ease, foot_roll, plant_feet
from .presets import (
    RUN_CYCLE,
    RUN_STRIDE,
    SKELETON,
    WALK_CYCLE,
    WALK_STRIDE,
    CharacterPreset,
    blend,
    sample_pose,
)
from .rig import Pose, Rigid
from .secondary import SecondaryMotion, follow_through


def integrated_step(t, start, duration):
    u = (t - start) / duration
    if u <= 0:
        return 0.0
    if u >= 1:
        return t - start - duration / 2
    return duration * (u**3 - 0.5 * u**4)


@dataclass(frozen=True)
class LocomotionClock:
    walk_start: float = 0.85
    run_start: float = 2.85
    ramp: float = 0.30

    def __post_init__(self):
        finite(self.walk_start, self.run_start, self.ramp)
        if not 0.1 <= self.ramp <= 0.8 or not 0 <= self.walk_start < self.run_start - self.ramp:
            raise RenderError("Contact clock needs ordered, separated starts and a .1.. .8s ramp")

    def active(self, t):
        return ease((t - self.walk_start) / self.ramp)

    def running(self, t):
        return ease((t - self.run_start) / self.ramp)

    def cycles(self, t):
        return integrated_step(t, self.walk_start, self.ramp) / WALK_CYCLE + (
            1 / RUN_CYCLE - 1 / WALK_CYCLE
        ) * integrated_step(t, self.run_start, self.ramp)

    def distance(self, t):
        return WALK_STRIDE / WALK_CYCLE * integrated_step(t, self.walk_start, self.ramp) + (
            RUN_STRIDE / RUN_CYCLE - WALK_STRIDE / WALK_CYCLE
        ) * integrated_step(t, self.run_start, self.ramp)

    def time_at(self, phase):
        if phase <= 0:
            return self.walk_start + phase * WALK_CYCLE
        low, high = self.walk_start, self.run_start + phase * WALK_CYCLE + 2
        for _ in range(48):
            mid = (low + high) / 2
            if self.cycles(mid) < phase:
                low = mid
            else:
                high = mid
        return (low + high) / 2


CLOCK = LocomotionClock()


def step(clock, start, hip):
    a, b = clock.time_at(start), clock.time_at(start + 1)
    running = clock.running((a + b) / 2)
    duty = 0.62 - 0.24 * running
    stride = WALK_STRIDE + (RUN_STRIDE - WALK_STRIDE) * clock.running(a)
    anchor = (9 if hip > 0 else -9) if start <= 0 else clock.distance(a) + hip + stride * duty / 2
    return anchor, duty, 19 + 12 * running


def contact_targets(seconds: float, clock: LocomotionClock = CLOCK, *, stepper=step):
    finite(seconds)
    if not 0 <= seconds <= 600:
        raise RenderError("Contact time must be 0..600")
    cycles = clock.cycles(seconds)
    feet = []
    for offset, hip in ((0, 7), (0.5, -7)):
        k = math.floor(cycles + offset)
        p = cycles + offset - k
        start = k - offset
        anchor, duty, lift = stepper(clock, start, hip)
        pitch, pivot, state = foot_roll(p, duty, seeded=start <= 0)
        if p < duty:
            x, y = anchor, 0
        else:
            next_anchor, _, _ = stepper(clock, start + 1, hip)
            u = (p - duty) / (1 - duty)
            x = anchor + (next_anchor - anchor) * ease(u)
            y = lift * math.sin(math.pi * u) ** 2 * (1 + 0.18 * math.sin(math.tau * u))
        feet.append(FootPlacement(x, y, pitch, pivot, state))
    return tuple(feet)


def transition_pose(seconds: float, clock: LocomotionClock = CLOCK, *, feet=None):
    finite(seconds)
    if not 0 <= seconds <= 600:
        raise RenderError("Transition time must be 0..600")
    cycles = clock.cycles(seconds)
    activity = clock.active(seconds)
    running = clock.running(seconds)
    idle = sample_pose(CharacterPreset(), seconds, travel=False)
    walk = sample_pose(CharacterPreset(action="walk"), (cycles % 1) * WALK_CYCLE, travel=False)
    run = sample_pose(CharacterPreset(action="run"), (cycles % 1) * RUN_CYCLE, travel=False)
    body = blend(blend(idle, walk, activity), run, running)
    distance = clock.distance(seconds)
    body = Pose(Rigid(body.root.x + distance, body.root.y), body.angles)
    planted = plant_feet(body, contact_targets(seconds, clock) if feet is None else feet, SKELETON)
    return Pose(Rigid(planted.root.x - distance, planted.root.y), planted.angles), distance


def transition_secondary(seconds: float, clock: LocomotionClock = CLOCK):
    finite(seconds)
    if not 0 <= seconds <= 600:
        raise RenderError("Secondary transition time must be 0..600")
    activity = clock.active(seconds)
    idle = follow_through(seconds / 3, 0.12)
    moving = follow_through(clock.cycles(seconds), 0.5 + 0.5 * clock.running(seconds))
    values = [
        getattr(idle, key) + (getattr(moving, key) - getattr(idle, key)) * activity
        for key in ("bag_angle", "bag_y", "hat_angle", "hat_y", "strap_sag")
    ]
    return SecondaryMotion(*values, 0.2 * math.sin(seconds * 0.8))
