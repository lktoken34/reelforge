"""Backend-neutral owned-surface boundary; no native graphics objects escape."""

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol, Self

from .model import Color, DrawPath


@dataclass(frozen=True)
class PixelLayout:
    width: int
    height: int
    stride: int
    format: str
    byte_order: str
    premultiplied: bool

    @property
    def size_bytes(self) -> int:
        return self.stride * self.height


class Surface(Protocol):
    @property
    def layout(self) -> PixelLayout: ...
    @property
    def closed(self) -> bool: ...
    @property
    def opaque(self) -> bool: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc: object) -> None: ...
    def pixel_rgba8_premultiplied(self, x: int, y: int) -> tuple[int, int, int, int]: ...
    def pixel_sha256(self) -> str: ...
    def write_png(self, path: Path) -> None: ...
    def write_opaque_bgra(
        self, fd: int, *, deadline: float, cancelled: Event | None = None
    ) -> int: ...


class Renderer(Protocol):
    def surface(self, width: int, height: int) -> Surface: ...
    def draw(
        self,
        target: Surface,
        commands: tuple[DrawPath, ...],
        *,
        background: Color,
        logical_size: tuple[float, float],
    ) -> None: ...
