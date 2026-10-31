"""Headless native-resolution Cairo backend. No external assets, caches or model calls."""

import hashlib
import sys
from pathlib import Path
from typing import Self

import cairo

from reelforge.rendering.interface import PixelLayout, Surface
from reelforge.rendering.model import (
    Color,
    DrawPath,
    Paint,
    RenderError,
    SurfaceBudgetError,
    VectorPath,
    finite,
)


class _OwnedSurface:
    """One owner, no exported memoryviews, explicit finish and reference release."""

    def __init__(self, owner: "CairoRenderer", layout: PixelLayout):
        self._owner = owner
        self._layout = layout
        self._native = cairo.ImageSurface(cairo.FORMAT_ARGB32, layout.width, layout.height)

    @property
    def layout(self) -> PixelLayout:
        return self._layout

    @property
    def closed(self) -> bool:
        return self._native is None

    def _open(self) -> cairo.ImageSurface:
        if self._native is None:
            raise RenderError("Surface is closed")
        return self._native

    def close(self) -> None:
        if self._native is not None:
            try:
                self._native.finish()
            finally:
                self._native = None
                self._owner._release(self._layout.size_bytes)

    def __enter__(self) -> Self:
        self._open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        # Convenience fallback; callers must use with/close, not depend on collection timing.
        if getattr(self, "_native", None) is not None:
            self.close()

    def pixel_rgba8_premultiplied(self, x: int, y: int) -> tuple[int, int, int, int]:
        native = self._open()
        if (
            type(x) is not int
            or type(y) is not int
            or not (0 <= x < self.layout.width and 0 <= y < self.layout.height)
        ):
            raise RenderError("Pixel coordinate is outside the surface")
        native.flush()
        view = native.get_data()
        try:
            offset = y * self.layout.stride + x * 4
            word = int.from_bytes(view[offset : offset + 4], sys.byteorder)
            return (word >> 16 & 255, word >> 8 & 255, word & 255, word >> 24 & 255)
        finally:
            view.release()

    def pixel_sha256(self) -> str:
        native = self._open()
        native.flush()
        view = native.get_data()
        try:
            header = (
                f"ARGB32:{self.layout.width}:{self.layout.height}:"
                f"{self.layout.stride}:{sys.byteorder}:premultiplied\n"
            ).encode("ascii")
            digest = hashlib.sha256(header)
            digest.update(view)  # No full-frame bytes copy; view never leaves this method.
            return digest.hexdigest()
        finally:
            view.release()

    def write_png(self, path: Path) -> None:
        self._open().write_to_png(str(path))


class CairoRenderer:
    """Single-threaded adapter; budget accounts for all simultaneously open owned targets."""

    def __init__(self, max_surface_bytes: int = 32 * 1024 * 1024):
        if type(max_surface_bytes) is not int or max_surface_bytes <= 0:
            raise SurfaceBudgetError("Surface budget must be a positive integer")
        self.max_surface_bytes = max_surface_bytes
        self.allocated_bytes = 0
        self.active_surfaces = 0

    def surface(self, width: int, height: int) -> Surface:
        if any(type(v) is not int or not 1 <= v <= 4096 for v in (width, height)):
            raise SurfaceBudgetError("Target dimensions must be integers within [1, 4096]")
        stride = cairo.Format.ARGB32.stride_for_width(width)
        layout = PixelLayout(width, height, stride, "ARGB32", sys.byteorder, True)
        if layout.size_bytes > self.max_surface_bytes - self.allocated_bytes:
            raise SurfaceBudgetError("Requested live surfaces exceed the byte budget")
        # Allocation succeeds before counters change; failed native allocation reserves nothing.
        target = _OwnedSurface(self, layout)
        self.allocated_bytes += layout.size_bytes
        self.active_surfaces += 1
        return target

    def _release(self, size_bytes: int) -> None:
        self.allocated_bytes -= size_bytes
        self.active_surfaces -= 1

    def draw(
        self,
        target: Surface,
        commands: tuple[DrawPath, ...],
        *,
        background: Color,
        logical_size: tuple[float, float],
    ) -> None:
        if not isinstance(target, _OwnedSurface) or target._owner is not self:
            raise RenderError("Target must belong to this backend instance")
        native = target._open()
        if not isinstance(commands, tuple) or len(commands) > 4096:
            raise RenderError("Expected at most 4096 immutable drawing commands")
        if any(not isinstance(cmd, DrawPath) for cmd in commands):
            raise RenderError("Expected trusted DrawPath commands, not arbitrary graphics data")
        if not isinstance(background, Color) or len(logical_size) != 2:
            raise RenderError("Expected Color background and two logical dimensions")
        finite(*logical_size)
        if any(v <= 0 for v in logical_size):
            raise RenderError("Logical dimensions must be positive")
        context = cairo.Context(native)
        try:
            context.set_antialias(cairo.ANTIALIAS_GRAY)
            context.set_tolerance(0.1)
            context.set_operator(cairo.OPERATOR_SOURCE)
            self._paint(context, background)
            context.paint()  # Clear every pixel, including transparent backgrounds on reuse.
            context.set_operator(cairo.OPERATOR_OVER)
            context.scale(
                target.layout.width / logical_size[0], target.layout.height / logical_size[1]
            )
            for command in commands:  # Tuple order is the complete painter's order.
                self._draw_path(context, command)
        finally:
            context = None  # Release target-retaining context before surface.close().

    @staticmethod
    def _path(context: cairo.Context, path: VectorPath) -> None:
        context.new_path()
        for op in path:
            if op.kind == "M":
                context.move_to(*op.points)
            elif op.kind == "L":
                context.line_to(*op.points)
            elif op.kind == "C":
                context.curve_to(*op.points)
            else:
                context.close_path()

    @staticmethod
    def _paint(context: cairo.Context, paint: Paint) -> None:
        if isinstance(paint, Color):
            context.set_source_rgba(paint.r, paint.g, paint.b, paint.a)
        else:
            gradient = cairo.LinearGradient(*paint.start, *paint.end)
            gradient.set_extend(cairo.EXTEND_PAD)
            for offset, color in paint.stops:
                gradient.add_color_stop_rgba(offset, color.r, color.g, color.b, color.a)
            context.set_source(gradient)

    def _draw_path(self, context: cairo.Context, command: DrawPath) -> None:
        context.save()
        try:
            t = command.transform
            context.translate(t.tx, t.ty)
            context.rotate(t.rotation)
            context.scale(t.sx, t.sy)
            context.set_fill_rule(cairo.FILL_RULE_WINDING)
            if command.clip is not None:
                self._path(context, command.clip)
                context.clip()  # Clip is in the same local coordinates as this path.
            self._path(context, command.path)
            if command.fill is not None:
                self._paint(context, command.fill)
                if command.stroke is not None:
                    context.fill_preserve()
                else:
                    context.fill()
            if command.stroke is not None:
                s = command.stroke
                self._paint(context, s.paint)
                context.set_line_width(s.width)
                context.set_line_join(
                    {
                        "miter": cairo.LINE_JOIN_MITER,
                        "round": cairo.LINE_JOIN_ROUND,
                        "bevel": cairo.LINE_JOIN_BEVEL,
                    }[s.join]
                )
                context.set_line_cap(
                    {
                        "butt": cairo.LINE_CAP_BUTT,
                        "round": cairo.LINE_CAP_ROUND,
                        "square": cairo.LINE_CAP_SQUARE,
                    }[s.cap]
                )
                context.set_miter_limit(s.miter_limit)
                context.stroke()
        finally:
            context.restore()
            context.new_path()  # Cairo paths are not part of save/restore state.


def backend_versions() -> dict[str, str]:
    """Report native versions without exporting a Cairo-specific object."""
    return {"pycairo": cairo.version, "cairo": cairo.cairo_version_string()}
