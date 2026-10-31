"""Immutable rigid 2D hierarchy with explicit artwork pivots; no native backend dependency."""

import math
from dataclasses import dataclass

from reelforge.rendering.model import RenderError, finite


@dataclass(frozen=True)
class Rigid:
    x: float = 0
    y: float = 0
    angle: float = 0

    def __post_init__(self):
        finite(self.x, self.y, self.angle)

    def point(self, point: tuple[float, float]) -> tuple[float, float]:
        c, s = math.cos(self.angle), math.sin(self.angle)
        x, y = point
        return self.x + c * x - s * y, self.y + s * x + c * y

    def compose(self, child: "Rigid") -> "Rigid":
        x, y = self.point((child.x, child.y))
        return Rigid(x, y, self.angle + child.angle)


@dataclass(frozen=True)
class Joint:
    name: str
    parent: str | None
    attachment: tuple[float, float] = (0, 0)
    pivot: tuple[float, float] = (0, 0)
    rest_angle: float = 0

    def __post_init__(self):
        if (
            not isinstance(self.name, str)
            or not self.name
            or len(self.attachment) != 2
            or len(self.pivot) != 2
        ):
            raise RenderError("Joint needs a name and two-coordinate attachment/pivot")
        finite(*self.attachment, *self.pivot, self.rest_angle)


@dataclass(frozen=True)
class Skeleton:
    joints: tuple[Joint, ...]

    def __post_init__(self):
        seen = set()
        if not isinstance(self.joints, tuple) or not 1 <= len(self.joints) <= 64:
            raise RenderError("Skeleton needs 1..64 ordered joints")
        for index, joint in enumerate(self.joints):
            if not isinstance(joint, Joint):
                raise RenderError("Skeleton entries must be Joint values")
            if joint.name in seen or (index == 0) != (joint.parent is None):
                raise RenderError("Use one root and unique joint names")
            if joint.parent is not None and joint.parent not in seen:
                raise RenderError(
                    "Parents must precede children; cycles/disconnected roots forbidden"
                )
            seen.add(joint.name)

    def evaluate(self, pose: "Pose") -> dict[str, Rigid]:
        angles = dict(pose.angles)
        if len(angles) != len(pose.angles) or set(angles) - {j.name for j in self.joints}:
            raise RenderError("Pose has duplicate or unknown joints")
        result = {}
        for joint in self.joints:
            angle = joint.rest_angle + angles.get(joint.name, 0)
            finite(angle)
            parent = pose.root if joint.parent is None else result[joint.parent]
            local = Rigid(*joint.attachment, angle).compose(Rigid(-joint.pivot[0], -joint.pivot[1]))
            result[joint.name] = parent.compose(local)
        return result


@dataclass(frozen=True)
class Pose:
    root: Rigid = Rigid()
    angles: tuple[tuple[str, float], ...] = ()

    def __post_init__(self):
        if not isinstance(self.root, Rigid) or not isinstance(self.angles, tuple):
            raise RenderError("Use an immutable root and angle tuple")
        for name, value in self.angles:
            if not isinstance(name, str):
                raise RenderError("Joint names must be strings")
            finite(value)


def two_bone(dx: float, dy: float, upper: float, lower: float) -> tuple[float, float]:
    """Knee bends toward positive X. Angles relative to a bone drawn along positive Y."""
    finite(dx, dy, upper, lower)
    distance = math.hypot(dx, dy)
    if min(upper, lower) <= 0 or not abs(upper - lower) < distance < upper + lower:
        raise RenderError("Foot target outside the two-bone reach annulus")
    bend = math.acos(max(-1, min(1, (distance**2 - upper**2 - lower**2) / (2 * upper * lower))))
    aim = math.atan2(dy, dx) - math.atan2(lower * math.sin(bend), upper + lower * math.cos(bend))
    return aim - math.pi / 2, bend
