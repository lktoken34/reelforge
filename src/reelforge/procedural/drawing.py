"""Small original vector primitives and bounded material rules shared by all families."""

from dataclasses import replace

from reelforge.rendering.diagnostic import ellipse
from reelforge.rendering.model import (
    Color,
    DrawPath,
    LinearGradient,
    PathOp,
    Stroke,
    Transform,
    rectangle,
)


def ink(value: str, alpha: float = 1) -> Color:
    return Color(*(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)), alpha)


def blend(a: Color, b: Color, t: float) -> Color:
    return Color(
        a.r * (1 - t) + b.r * t,
        a.g * (1 - t) + b.g * t,
        a.b * (1 - t) + b.b * t,
        a.a * (1 - t) + b.a * t,
    )


def gradient(a, b, y0, y1):
    return LinearGradient((0, y0), (0, y1), ((0, a), (1, b)))


def path(points, smooth=False):
    ops = [PathOp("M", tuple(points[0]))]
    if smooth:
        for i in range(len(points)):
            p, a, b, q = (points[(i + k) % len(points)] for k in (-1, 0, 1, 2))
            ops.append(
                PathOp(
                    "C",
                    (
                        a[0] + (b[0] - p[0]) * 0.14,
                        a[1] + (b[1] - p[1]) * 0.14,
                        b[0] - (q[0] - a[0]) * 0.14,
                        b[1] - (q[1] - a[1]) * 0.14,
                        *b,
                    ),
                )
            )
    else:
        ops.extend(PathOp("L", tuple(p)) for p in points[1:])
    return tuple(ops) + (PathOp("Z"),)


class Pen:
    def __init__(self, bound):
        self.bound = bound
        self.commands = []
        self.ops = 0

    def add(self, command):
        ops = len(command.path) + len(command.clip or ())
        if len(self.commands) + 1 > self.bound[0] or self.ops + ops > self.bound[1]:
            raise ValueError("Procedural recipe exceeded conservative expansion bound")
        self.commands.append(command)
        self.ops += ops

    def poly(self, points, fill, smooth=False, clip=None):
        self.add(DrawPath(path(points, smooth), fill, clip=clip))

    def line(self, points, color, width=1, clip=None):
        ops = (PathOp("M", tuple(points[0])),) + tuple(PathOp("L", tuple(p)) for p in points[1:])
        self.add(DrawPath(ops, stroke=Stroke(color, width), clip=clip))

    def rect(self, x, y, w, h, fill):
        self.add(DrawPath(rectangle(x, y, w, h), fill))

    def oval(self, x, y, rx, ry, fill):
        self.add(DrawPath(ellipse(x, y, rx, ry), fill))

    def placed(self, commands, x, y, scale=1):
        for c in commands:
            t = c.transform
            self.add(
                replace(
                    c,
                    transform=Transform(
                        x + t.tx * scale, y + t.ty * scale, t.rotation, t.sx * scale, t.sy * scale
                    ),
                )
            )

    def result(self):
        return tuple(self.commands)


class Palette:
    def __init__(self, request):
        self.warm = request.lighting == "dusk"
        family = request.family
        top = {
            "woodland_trail": "112c33",
            "settlement_street": "222e3c",
            "rocky_shelter": "222f40",
        }[family]
        bottom = {
            "woodland_trail": "9eae8f",
            "settlement_street": "be997b",
            "rocky_shelter": "ac9a85",
        }[family]
        self.sky_top = ink(top)
        self.sky_bottom = ink(bottom) if self.warm else ink("91a2a2")
        self.haze = blend(self.sky_bottom, ink("b4c2b9"), 0.4)
        self.dark = ink("122c31")
        self.leaf = ink("355647")
        self.rim = ink("a6b47b")
        self.wood = ink("716653")
        self.wood_light = ink("b6a183")
        self.stone = ink("68777b")
        self.stone_light = ink("b0aa91")
        self.ground = ink(
            {"woodland_trail": "344a3e", "settlement_street": "505452", "rocky_shelter": "5f665e"}[
                family
            ]
        )
        self.path = ink(
            {"woodland_trail": "8d8062", "settlement_street": "7d7970", "rocky_shelter": "938b76"}[
                family
            ]
        )
        self.fog = request.atmosphere

    def distant(self, color, depth):
        return blend(color, self.haze, (1 - depth) * (0.35 + 0.42 * self.fog))
