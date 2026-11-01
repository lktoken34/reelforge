"""Small reusable planar foot-contact solve, independent of character artwork/backend."""

import math
from dataclasses import dataclass

from reelforge.rendering.model import RenderError, finite

from .rig import Pose, Rigid, Skeleton, two_bone


@dataclass(frozen=True)
class FootPlacement:
    x: float
    lift: float = 0
    pitch: float = 0
    pivot_x: float = 0
    state: str = "flat"

    def __post_init__(self):
        finite(self.x, self.lift, self.pitch, self.pivot_x)
        if not 0 <= self.lift <= 45 or abs(self.pitch) > 0.8 or not -8 <= self.pivot_x <= 19:
            raise RenderError("Foot placement outside calibrated contact limits")
        if self.state not in ("heel", "flat", "toe", "swing"):
            raise RenderError("Unknown foot contact state")

    def ankle(self):
        c, s = math.cos(self.pitch), math.sin(self.pitch)
        x = self.x + self.pivot_x - (self.pivot_x * c - 10 * s)
        y = -self.lift - (self.pivot_x * s + 10 * c)
        # Keep both ends of the boot sole out of the floor, including airborne roll.
        return x, y - max(0, y + max(-8 * s + 10 * c, 19 * s + 10 * c))


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def foot_roll(phase, duty, *, seeded=False, toe=0.26):
    """Heel/flat/toe contact, then a C1 airborne roll back to heel strike."""
    width = 0.05
    if phase < duty:
        if phase < width and not seeded:
            return -0.16 * (1 - ease(phase / width)), -8.0, "heel"
        if phase > duty - width:
            return toe * ease((phase - duty + width) / width), 19.0, "toe"
        return 0.0, 0.0, "flat"
    u = (phase - duty) / (1 - duty)
    return (
        toe * (1 - ease(u)) - 0.16 * ease(u) - 0.38 * math.sin(math.pi * u) ** 2,
        19 - 27 * ease(u),
        "swing",
    )


def plant_feet(
    pose: Pose, feet: tuple[FootPlacement, FootPlacement], skeleton: Skeleton, lengths=(42.0, 45.0)
) -> Pose:
    """Re-solve legs after body posing. Flat calibrated floor; rigid root has no rotation."""
    if abs(pose.root.angle) > 1e-10:
        raise RenderError("Planar locomotion contact requires an unrotated root")
    worlds = skeleton.evaluate(pose)
    upper, lower = lengths
    limit = upper + lower - 0.25
    ankles = [foot.ankle() for foot in feet]
    offsets = [worlds[s + "_thigh"].x - pose.root.x for s in ("near", "far")]
    low = max(x - offset - limit + 0.01 for (x, _), offset in zip(ankles, offsets, strict=True))
    high = min(x - offset + limit - 0.01 for (x, _), offset in zip(ankles, offsets, strict=True))
    if low > high:
        raise RenderError("Foot placements cannot be reached by this skeleton")
    root_x = max(low, min(high, pose.root.x))
    root_y = pose.root.y
    for (x, y), offset in zip(ankles, offsets, strict=True):
        dx = x - root_x - offset
        bound = y - math.sqrt(max(0.01, limit * limit - dx * dx))
        # C1 smooth maximum: at most .125 units below the exact reach projection.
        gap = abs(root_y - bound)
        root_y = max(root_y, bound) + (max(0.0, 0.5 - gap) ** 2) / 2
    angles = dict(pose.angles)
    for side, (x, y), offset, foot in zip(("near", "far"), ankles, offsets, feet, strict=True):
        a, b = two_bone(x - root_x - offset, y - root_y, upper, lower)
        angles.update({side + "_thigh": a, side + "_shin": b, side + "_foot": foot.pitch - a - b})
    return Pose(Rigid(root_x, root_y), tuple(sorted(angles.items())))
