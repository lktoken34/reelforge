"""Similarity transforms preserve existing local paths, clips, gradients and strokes."""

import math
from dataclasses import dataclass, replace

from reelforge.rendering.model import DrawPath, Transform


@dataclass(frozen=True)
class Placement:
    x: float = 0
    y: float = 0
    scale: float = 1
    angle: float = 0  # clockwise radians in the renderer's Y-down coordinates

    def point(self, x: float, y: float) -> tuple[float, float]:
        c, s = math.cos(self.angle), math.sin(self.angle)
        return self.x + self.scale * (c * x - s * y), self.y + self.scale * (s * x + c * y)

    def compose(self, child: "Placement") -> "Placement":
        x, y = self.point(child.x, child.y)
        return Placement(x, y, self.scale * child.scale, self.angle + child.angle)

    def command(self, command: DrawPath) -> DrawPath:
        t = command.transform
        x, y = self.point(t.tx, t.ty)
        return replace(
            command,
            transform=Transform(
                x, y, self.angle + t.rotation, self.scale * t.sx, self.scale * t.sy
            ),
        )
