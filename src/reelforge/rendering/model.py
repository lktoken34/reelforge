"""Small immutable drawing vocabulary for trusted Python, never episode JSON."""

import math
from dataclasses import dataclass
from typing import Literal


class RenderError(ValueError):
    """Invalid trusted drawing data, unsupported operation or invalid surface state."""


class SurfaceBudgetError(RenderError):
    """Requested live target surfaces exceed the explicit allocation budget."""


def finite(*values: float) -> None:
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or abs(value) > 1_000_000
        or not math.isfinite(value)
        for value in values
    ):
        raise RenderError("Drawing values must be finite numbers within +/-1000000")


@dataclass(frozen=True)
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0

    def __post_init__(self) -> None:
        finite(self.r, self.g, self.b, self.a)
        if any(not 0 <= v <= 1 for v in (self.r, self.g, self.b, self.a)):
            raise RenderError("Color channels must be in [0, 1]")


@dataclass(frozen=True)
class LinearGradient:
    start: tuple[float, float]
    end: tuple[float, float]
    stops: tuple[tuple[float, Color], ...]

    def __post_init__(self) -> None:
        if len(self.start) != 2 or len(self.end) != 2:
            raise RenderError("Gradient endpoints need two coordinates")
        finite(*self.start, *self.end)
        if self.start == self.end:
            raise RenderError("Gradient endpoints must differ")
        if not isinstance(self.stops, tuple) or not 2 <= len(self.stops) <= 16:
            raise RenderError("Gradient requires 2..16 immutable stops")
        previous = -1.0
        for offset, color in self.stops:
            finite(offset)
            if not previous < offset <= 1 or offset < 0 or not isinstance(color, Color):
                raise RenderError("Gradient stops must increase strictly within [0, 1]")
            previous = offset


Paint = Color | LinearGradient


@dataclass(frozen=True)
class PathOp:
    kind: Literal["M", "L", "C", "Z"]
    points: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        arity = {"M": 2, "L": 2, "C": 6, "Z": 0}
        if self.kind not in arity or not isinstance(self.points, tuple):
            raise RenderError("Unsupported path operation; use immutable M/L/C/Z commands")
        if len(self.points) != arity[self.kind]:
            raise RenderError("Wrong coordinate count for path operation")
        finite(*self.points)


VectorPath = tuple[PathOp, ...]


def check_path(path: VectorPath) -> None:
    if not isinstance(path, tuple) or not 1 <= len(path) <= 4096:
        raise RenderError("Path needs 1..4096 immutable operations")
    if any(not isinstance(op, PathOp) for op in path) or path[0].kind != "M":
        raise RenderError("Path must contain PathOp values and start with M")


def rectangle(x: float, y: float, width: float, height: float) -> VectorPath:
    finite(x, y, width, height)
    if width <= 0 or height <= 0:
        raise RenderError("Rectangle dimensions must be positive")
    return (
        PathOp("M", (x, y)),
        PathOp("L", (x + width, y)),
        PathOp("L", (x + width, y + height)),
        PathOp("L", (x, y + height)),
        PathOp("Z"),
    )


@dataclass(frozen=True)
class Transform:
    """Local point maps as translation * rotation * scale; radians, clockwise in Y-down."""

    tx: float = 0
    ty: float = 0
    rotation: float = 0
    sx: float = 1
    sy: float = 1

    def __post_init__(self) -> None:
        finite(self.tx, self.ty, self.rotation, self.sx, self.sy)
        if not 0.001 <= abs(self.sx) <= 1000 or not 0.001 <= abs(self.sy) <= 1000:
            raise RenderError("Transform scale magnitude must be within [0.001, 1000]")


@dataclass(frozen=True)
class Stroke:
    paint: Paint
    width: float = 1
    join: Literal["miter", "round", "bevel"] = "round"
    cap: Literal["butt", "round", "square"] = "round"
    miter_limit: float = 10

    def __post_init__(self) -> None:
        finite(self.width, self.miter_limit)
        if self.width <= 0 or self.miter_limit < 1:
            raise RenderError("Stroke width must be positive; miter limit must be >= 1")
        if not isinstance(self.paint, (Color, LinearGradient)):
            raise RenderError("Unsupported stroke paint")
        if self.join not in ("miter", "round", "bevel") or self.cap not in (
            "butt",
            "round",
            "square",
        ):
            raise RenderError("Unsupported stroke join/cap")


@dataclass(frozen=True)
class DrawPath:
    path: VectorPath
    fill: Paint | None = None
    stroke: Stroke | None = None
    transform: Transform = Transform()
    clip: VectorPath | None = None

    def __post_init__(self) -> None:
        check_path(self.path)
        if self.clip is not None:
            check_path(self.clip)
        if self.fill is None and self.stroke is None:
            raise RenderError("DrawPath requires fill or stroke")
        if self.fill is not None and not isinstance(self.fill, (Color, LinearGradient)):
            raise RenderError("Unsupported fill paint")
        if self.stroke is not None and not isinstance(self.stroke, Stroke):
            raise RenderError("Expected Stroke")
        if not isinstance(self.transform, Transform):
            raise RenderError("Expected Transform")
