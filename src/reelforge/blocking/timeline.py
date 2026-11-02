"""Absolute-time Hermite travel and exact polynomial distance/stride integration."""

import math
from dataclasses import dataclass, replace

from reelforge.characters.contact import ease
from reelforge.characters.presets import RUN_STRIDE, WALK_CYCLE, WALK_STRIDE


def polynomial(c: tuple, x: float) -> float:
    return sum(v * x**i for i, v in enumerate(c))


def integral(c: tuple, x: float) -> float:
    return sum(v * x ** (i + 1) / (i + 1) for i, v in enumerate(c))


def multiply(a: tuple, b: tuple) -> tuple:
    result = [0.0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            result[i + j] += x * y
    return tuple(result)


@dataclass(frozen=True)
class Segment:
    id: str
    start: int
    end: int
    mode: str
    x0: float
    x1: float
    y: float
    v0: float
    v1: float
    facing: str
    acting: str
    expression: str
    run0: float
    run1: float

    @property
    def duration(self):
        return (self.end - self.start) / 30

    @property
    def coefficients(self):
        d = self.x1 - self.x0
        T = self.duration
        return (
            self.x0,
            T * self.v0,
            3 * d - T * (2 * self.v0 + self.v1),
            -2 * d + T * (self.v0 + self.v1),
        )

    def u(self, t):
        return min(1.0, max(0.0, (t - self.start / 30) / self.duration))

    def position(self, t):
        return polynomial(self.coefficients, self.u(t))

    def velocity(self, t):
        a = self.coefficients
        u = self.u(t)
        return (a[1] + 2 * a[2] * u + 3 * a[3] * u * u) / self.duration

    def running(self, t):
        return self.run0 + (self.run1 - self.run0) * ease(self.u(t))

    def phase_polynomial(self, scale):
        sign = 1 if self.facing == "right" else -1
        c = self.coefficients
        velocity = (sign * c[1] / scale, 2 * sign * c[2] / scale, 3 * sign * c[3] / scale)
        dr = self.run1 - self.run0
        inv = (
            1 / WALK_STRIDE + self.run0 * (1 / RUN_STRIDE - 1 / WALK_STRIDE),
            0.0,
            3 * dr * (1 / RUN_STRIDE - 1 / WALK_STRIDE),
            -2 * dr * (1 / RUN_STRIDE - 1 / WALK_STRIDE),
        )
        return multiply(velocity, inv)


@dataclass(frozen=True)
class RouteClock:
    """Clock protocol for the accepted transition_pose/contact_targets controller."""

    segments: tuple[Segment, ...]
    scale: float
    factor: float
    raw_cycles: tuple[float, ...]
    stopped: bool
    steps: tuple = ()

    @property
    def start(self):
        return self.segments[0].start / 30

    @property
    def end(self):
        return self.segments[-1].end / 30

    @property
    def origin(self):
        return self.segments[0].x0

    @property
    def sign(self):
        return 1 if self.segments[0].facing == "right" else -1

    @property
    def total_cycles(self):
        return sum(self.raw_cycles) * self.factor

    @property
    def total_distance(self):
        return abs(self.segments[-1].x1 - self.origin) / self.scale

    def segment(self, t):
        return next((s for s in self.segments if t < s.end / 30), self.segments[-1])

    def cycles(self, t):
        if t <= self.start:
            return 0.0
        if t >= self.end:
            extra = (
                0
                if self.stopped
                else (t - self.end)
                * abs(self.segments[-1].v1)
                / self.scale
                * self.inverse_stride(t)
                * self.factor
            )
            return self.total_cycles + extra
        total = 0.0
        for s, raw in zip(self.segments, self.raw_cycles, strict=True):
            if t >= s.end / 30:
                total += raw
            else:
                total += integral(s.phase_polynomial(self.scale), s.u(t))
                break
        return total * self.factor

    def distance(self, t):
        if t <= self.start:
            return 0.0
        if t >= self.end:
            return self.total_distance + (
                0 if self.stopped else (t - self.end) * abs(self.segments[-1].v1) / self.scale
            )
        return self.sign * (self.segment(t).position(t) - self.origin) / self.scale

    def speed(self, t):
        if t < self.start:
            return 0.0
        if t >= self.end:
            return 0.0 if self.stopped else abs(self.segments[-1].v1) / self.scale
        return abs(self.segment(t).velocity(t)) / self.scale

    def active(self, t):
        anticipation = (
            0.12 * math.sin(math.pi * ease((t - self.start + 0.10) / 0.10)) ** 2
            if self.start - 0.10 < t < self.start
            else 0.0
        )
        return max(anticipation, min(1.0, self.speed(t) / (WALK_STRIDE / WALK_CYCLE)))

    def running(self, t):
        if t <= self.start:
            return 0.0
        if t >= self.end:
            return 0.0 if self.stopped else self.segments[-1].run1
        return self.segment(t).running(t)

    def inverse_stride(self, t):
        return (1 - self.running(t)) / WALK_STRIDE + self.running(t) / RUN_STRIDE

    def time_at(self, phase):
        if phase <= 0:
            return self.start + phase * WALK_CYCLE
        if phase >= self.total_cycles:
            if self.stopped:
                return self.end + (phase - self.total_cycles) * WALK_CYCLE
            rate = self.speed(self.end) * self.inverse_stride(self.end) * self.factor
            return self.end + (phase - self.total_cycles) / max(rate, 1e-9)
        low, high = self.start, self.end
        for _ in range(48):
            mid = (low + high) / 2
            if self.cycles(mid) < phase:
                low = mid
            else:
                high = mid
        return (low + high) / 2

    def contact_step(self, start, hip):
        if self.steps:
            found = next((row[2:] for row in self.steps if row[0] == start and row[1] == hip), None)
            if found is not None:
                return found
        if start <= 0:
            return (9 if hip > 0 else -9), 0.62, 19.0
        # Both final stances land at the same idle footprint, with a walk double-support duty.
        last_near = math.floor(self.total_cycles)
        if self.stopped and start >= last_near + (0.5 if hip < 0 else 0) - 1e-10:
            return self.total_distance + (9 if hip > 0 else -9), 0.62, 19.0
        a, b = self.time_at(start), self.time_at(start + 1)
        running = self.running((a + b) / 2)
        duty = 0.62 - 0.24 * running
        stride = 1 / (self.inverse_stride(a) * self.factor)
        return self.distance(a) + hip + stride * duty / 2, duty, 19 + 12 * running


def route_step(clock: RouteClock, start, hip):
    return clock.contact_step(start, hip)


def make_clock(segments: tuple[Segment, ...], scale: float) -> RouteClock:
    raw = tuple(integral(s.phase_polynomial(scale), 1.0) for s in segments)
    stopped = segments[-1].v1 == 0
    total = sum(raw)
    terminal = max(1.56, math.floor(total - 0.56 + 0.5) + 0.56) if stopped else total
    clock = RouteClock(segments, scale, terminal / total, raw, stopped)
    steps = tuple(
        (i / 2, hip, *clock.contact_step(i / 2, hip))
        for i in range(-1, 2 * math.ceil(clock.total_cycles) + 5)
        for hip in (7, -7)
    )
    return replace(clock, steps=steps)
