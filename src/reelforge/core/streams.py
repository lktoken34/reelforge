"""Bounded synchronous POSIX writes. Borrowed buffers never enter a callback or queue."""

import math
import os
import selectors
import time
from threading import Event

from reelforge.core.errors import OperationError


class StreamError(OperationError):
    """Raw stream transfer failed or was interrupted."""


def check_interrupt(deadline: float, cancelled: Event | None) -> None:
    if cancelled is not None and cancelled.is_set():
        raise StreamError("CANCELLED", "Operation cancelled")
    if time.monotonic() >= deadline:
        raise StreamError("TIMEOUT", "Operation deadline exceeded")


def write_all(fd: int, data: memoryview, *, deadline: float, cancelled: Event | None = None) -> int:
    """Consume a borrowed view before return; only os.write sees individual slices."""
    if not math.isfinite(deadline):
        raise StreamError("TIMEOUT_CONFIG", "A finite absolute deadline is required")
    if data.itemsize != 1 or data.ndim != 1 or not data.c_contiguous:
        raise StreamError("PIPE_LAYOUT", "Raw transfer needs contiguous single-byte elements")
    if os.get_blocking(fd):
        raise StreamError("PIPE_MODE", "Raw transfer requires a nonblocking descriptor")
    written = 0
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_WRITE)
        while written < data.nbytes:
            check_interrupt(deadline, cancelled)
            if not selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                continue
            piece = data[written : written + 65536]
            try:
                count = os.write(fd, piece)
            except BlockingIOError:
                continue
            except BrokenPipeError as error:
                raise StreamError("BROKEN_PIPE", "Frame consumer closed its input") from error
            except OSError as error:
                raise StreamError("PIPE_IO", "Cannot write raw frame") from error
            finally:
                piece.release()
            if count <= 0:
                raise StreamError("BROKEN_PIPE", "Frame consumer made no progress")
            written += count
    return written
