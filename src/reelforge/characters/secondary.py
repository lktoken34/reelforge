"""Bounded analytical follow-through signals. No integration, state or physics engine."""

import math
from dataclasses import dataclass

from reelforge.rendering.model import RenderError, finite

from .rig import Rigid


@dataclass(frozen=True)
class SecondaryMotion:
    bag_angle: float = 0
    bag_y: float = 0
    hat_angle: float = 0
    hat_y: float = 0
    strap_sag: float = 0
    gaze: float = 0

    def __post_init__(self):
        finite(self.bag_angle, self.bag_y, self.hat_angle, self.hat_y, self.strap_sag, self.gaze)
        if (
            abs(self.bag_angle) > 0.14
            or abs(self.bag_y) > 2
            or abs(self.hat_angle) > 0.055
            or abs(self.hat_y) > 1
            or abs(self.strap_sag) > 2
            or abs(self.gaze) > 1
        ):
            raise RenderError("Secondary transforms exceed calibrated bounds")


def follow_through(cycles: float, energy: float, *, gaze=0.0) -> SecondaryMotion:
    finite(cycles, energy, gaze)
    if not 0 <= energy <= 1:
        raise RenderError("Secondary energy must be 0..1")
    p = math.tau * cycles
    return SecondaryMotion(
        0.10 * energy * math.sin(p - 0.7),
        0.9 * energy * math.sin(2 * p - 1.1),
        0.035 * energy * math.sin(2 * p - 0.8),
        0.45 * energy * math.sin(2 * p - 1.2),
        1.2 * energy * math.sin(p - 1),
        gaze,
    )


def around(pivot: tuple[float, float], angle: float, dy=0.0) -> Rigid:
    return Rigid(pivot[0], pivot[1] + dy, angle).compose(Rigid(-pivot[0], -pivot[1]))


def settling_response(seconds: float) -> float:
    """C1 onset and decaying recoil response; evaluated analytically, never integrated."""
    finite(seconds)
    if not 0 <= seconds <= 900:
        raise RenderError("Scaled settle time must be 0..900")
    u = max(0.0, seconds - 0.12)
    return (1 - math.exp(-12 * u)) * math.exp(-4 * u) * math.sin(10 * u)


def preset_secondary(preset, seconds: float) -> SecondaryMotion:
    finite(seconds)
    if not 0 <= seconds <= 600:
        raise RenderError("Secondary time must be 0..600")
    t = seconds * preset.speed
    if preset.action in ("idle", "look_around", "react"):
        gaze = (
            math.sin(t * 1.7) * 0.9 * preset.intensity
            if preset.action == "look_around"
            else 0.45
            if preset.action == "react"
            else 0.12 * math.sin(t * 0.8)
        )
        base = follow_through(t / 3, 0.12 * preset.intensity, gaze=gaze)
        if preset.action == "react":
            pulse = settling_response(t) * preset.intensity
            return SecondaryMotion(
                base.bag_angle + 0.10 * pulse,
                base.bag_y + 1.1 * pulse,
                base.hat_angle - 0.04 * pulse,
                base.hat_y - 0.7 * pulse,
                base.strap_sag + 1.2 * pulse,
                gaze,
            )
        return base
    return follow_through(
        t / (0.95 if preset.action == "walk" else 0.60),
        (0.5 if preset.action == "walk" else 1) * preset.intensity,
    )


def cubic_attachment(points: tuple[tuple[float, float], ...], u: float) -> Rigid:
    """Position/orientation for hardware attached along a deforming cubic ribbon."""
    finite(u)
    if len(points) != 4 or not 0 <= u <= 1:
        raise RenderError("Cubic attachment needs four points and u in [0,1]")
    for point in points:
        if len(point) != 2:
            raise RenderError("Cubic points must have two coordinates")
        finite(*point)
    a, b, c, d = points
    v = 1 - u
    x = v**3 * a[0] + 3 * v * v * u * b[0] + 3 * v * u * u * c[0] + u**3 * d[0]
    y = v**3 * a[1] + 3 * v * v * u * b[1] + 3 * v * u * u * c[1] + u**3 * d[1]
    dx = 3 * v * v * (b[0] - a[0]) + 6 * v * u * (c[0] - b[0]) + 3 * u * u * (d[0] - c[0])
    dy = 3 * v * v * (b[1] - a[1]) + 6 * v * u * (c[1] - b[1]) + 3 * u * u * (d[1] - c[1])
    if math.hypot(dx, dy) < 1e-8:
        raise RenderError("Degenerate cubic attachment tangent")
    return Rigid(x, y, math.atan2(dy, dx))
