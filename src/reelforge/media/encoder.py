"""Bounded single-frame BGRA pipe to CPU libx264; no drawing or Cairo imports."""

import math
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from types import TracebackType
from typing import Self

from reelforge.core.streams import check_interrupt
from reelforge.core.transaction import OwnedDirectory
from reelforge.rendering.interface import PixelLayout, Surface

from .process import VideoError, run_bounded, stop_process

SUPPORTED_SIZES = {(360, 640), (720, 1280)}


def frame_bytes(layout: PixelLayout, width: int, height: int) -> int:
    if (layout.width, layout.height) != (width, height):
        raise VideoError("FRAME_DIMENSIONS", "Frame dimensions differ from encoder target")
    if (layout.format, layout.byte_order, layout.premultiplied) != ("ARGB32", "little", True):
        raise VideoError("FRAME_FORMAT", "Only little-endian premultiplied ARGB32 is supported")
    if layout.stride != width * 4:
        raise VideoError("FRAME_STRIDE", "Only tightly packed four-byte pixels are supported")
    return width * height * 4


def encoder_command(
    executable: str, width: int, height: int, frames: int, output: Path
) -> list[str]:
    return [
        executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-nostdin",
        "-max_alloc",
        "67108864",
        "-threads",
        "1",
        "-filter_threads",
        "1",
        "-filter_complex_threads",
        "1",
        "-f",
        "rawvideo",
        "-pixel_format",
        "bgra",
        "-video_size",
        f"{width}x{height}",
        "-framerate",
        "30",
        "-i",
        "pipe:0",
        "-an",
        "-sn",
        "-dn",
        "-frames:v",
        str(frames),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-threads:v",
        "1",
        "-x264-params",
        "threads=1:lookahead_threads=1:sync-lookahead=0:rc-lookahead=0:bframes=0:ref=1",
        "-profile:v",
        "main",
        "-level:v",
        "3.1",
        "-crf",
        "20",
        "-vf",
        "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
        "-pix_fmt",
        "yuv420p",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-color_range",
        "tv",
        "-tag:v",
        "avc1",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        "-n",
        str(output),
    ]


class FFmpegEncoder:
    """One-use encoder transaction. No final path is exposed until successful completion."""

    def __init__(
        self,
        output: Path,
        *,
        width: int,
        height: int,
        frames: int = 150,
        timeout: float = 60,
        frame_timeout: float = 5,
        cancelled: threading.Event | None = None,
        ffmpeg: str = "ffmpeg",
        overwrite: bool = False,
        staging_directory: Path | None = None,
    ):
        if (
            type(width) is not int
            or type(height) is not int
            or (width, height) not in SUPPORTED_SIZES
        ):
            raise VideoError("OUTPUT_DIMENSIONS", "Use 360x640 or 720x1280")
        if type(frames) is not int or not 1 <= frames <= 1800:
            raise VideoError("FRAME_COUNT", "Use 1..1800 frames at the fixed 30 fps")
        if any(not math.isfinite(v) or v <= 0 for v in (timeout, frame_timeout)):
            raise VideoError("TIMEOUT_CONFIG", "Timeouts must be positive and finite")
        self.output = Path(output)
        if self.output.suffix.lower() != ".mp4":
            raise VideoError("OUTPUT_CONTAINER", "Output must have .mp4 extension")
        self.width, self.height, self.frames = width, height, frames
        self.timeout, self.frame_timeout = timeout, frame_timeout
        self.cancelled, self.ffmpeg, self.overwrite = cancelled, ffmpeg, overwrite
        self.proc: subprocess.Popen | None = None
        self.returncode: int | None = None
        self.frames_written = 0
        self.command: list[str] = []
        self.staging_directory = staging_directory
        self._temporary: OwnedDirectory | None = None
        self._transaction: OwnedDirectory | None = None
        self._reader: threading.Thread | None = None
        self._log = bytearray()
        self._lock = threading.Lock()
        self._used = False
        self._finished = False

    @property
    def stderr_tail(self) -> str:
        with self._lock:
            return bytes(self._log).decode("utf-8", errors="replace")

    def _read_stderr(self) -> None:
        try:
            while data := self.proc.stderr.read(4096):
                with self._lock:
                    self._log.extend(data)
                    del self._log[:-16384]
        except OSError:
            pass

    def __enter__(self) -> Self:
        if self._used:
            raise VideoError("ENCODER_STATE", "Encoder instances cannot be reused")
        self._used = True
        self._deadline = time.monotonic() + self.timeout
        try:
            check_interrupt(self._deadline, self.cancelled)
            executable = shutil.which(self.ffmpeg)
            if executable is None:
                raise VideoError("FFMPEG_MISSING", "FFmpeg executable is unavailable")
            rc, listing, err = run_bounded(
                [executable, "-hide_banner", "-encoders"],
                timeout=min(10, self.timeout),
                cancelled=self.cancelled,
            )
            if rc or not any(
                len(row := line.split()) > 1 and row[1] == b"libx264"
                for line in listing.splitlines()
            ):
                raise VideoError("ENCODER_UNAVAILABLE", "FFmpeg does not provide libx264")
            if self.output.exists() and not self.overwrite:
                raise VideoError("OUTPUT_EXISTS", "Output exists; explicit overwrite is required")
            if not self.output.parent.is_dir():
                raise VideoError("OUTPUT_DIRECTORY", "Create the output directory before encoding")
            if self.staging_directory is None:
                self._temporary = OwnedDirectory(
                    self.output.parent, ".reelforge-encode-", files=frozenset({"pending.mp4"})
                )
                self._transaction = self._temporary
                self._pending = self._temporary.path / "pending.mp4"
            else:
                stage = self.staging_directory
                if (
                    stage.is_symlink()
                    or not stage.is_dir()
                    or any(stage.iterdir())
                    or stage.parent.resolve() != self.output.parent.parent.resolve()
                ):
                    raise VideoError(
                        "ENCODER_STAGING", "Borrow an empty sibling stage in the job root"
                    )
                self._pending = stage / "pending.mp4"
            self.command = encoder_command(
                executable, self.width, self.height, self.frames, self._pending
            )
            self.proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0,
                start_new_session=True,
            )
            os.set_blocking(self.proc.stdin.fileno(), False)
            self._reader = threading.Thread(
                target=self._read_stderr, name="ffmpeg-stderr", daemon=True
            )
            self._reader.start()
            return self
        except BaseException:
            self.abort()
            raise

    def write_surface(self, surface: Surface) -> None:
        if self.proc is None or self._finished:
            raise VideoError("ENCODER_STATE", "Encoder is not active")
        try:
            check_interrupt(self._deadline, self.cancelled)
            if self.frames_written >= self.frames:
                raise VideoError("FRAME_COUNT", "Too many input frames")
            if self.proc.poll() is not None:
                raise VideoError("ENCODER_EXIT", f"Encoder exited early ({self.proc.returncode})")
            if surface.closed:
                raise VideoError("FRAME_CLOSED", "Input surface is closed")
            expected = frame_bytes(surface.layout, self.width, self.height)
            if not surface.opaque:
                raise VideoError("FRAME_ALPHA", "MP4 input must have a proven opaque background")
            count = surface.write_opaque_bgra(
                self.proc.stdin.fileno(),
                deadline=min(self._deadline, time.monotonic() + self.frame_timeout),
                cancelled=self.cancelled,
            )
            if type(count) is not int or count != expected:
                raise VideoError("FRAME_BYTES", f"Expected {expected} bytes, received {count}")
            self.frames_written += 1
        except BaseException:
            self.abort()
            raise

    def finish(self) -> None:
        if self.proc is None or self._finished:
            raise VideoError("ENCODER_STATE", "Encoder is not active")
        try:
            if self.frames_written != self.frames:
                raise VideoError("FRAME_COUNT", "Input frame count differs from declared count")
            self.proc.stdin.close()
            while self.proc.poll() is None:
                check_interrupt(self._deadline, self.cancelled)
                time.sleep(0.01)
            check_interrupt(self._deadline, self.cancelled)
            self.returncode = self.proc.returncode
            self._finish_reader()
            if self.returncode != 0:
                raise VideoError(
                    "ENCODER_EXIT", f"Encoder exited {self.returncode}: {self.stderr_tail[-2048:]}"
                )
            if not self._pending.is_file() or self._pending.stat().st_size == 0:
                raise VideoError("OUTPUT_EMPTY", "Encoder produced no output")
            with self._pending.open("rb") as handle:
                os.fsync(handle.fileno())
            if self.overwrite:
                os.replace(self._pending, self.output)
            else:
                # Atomic no-clobber publication in the same filesystem; closes exists() race.
                os.link(self._pending, self.output)
            self._finished = True
        except OSError as error:
            raise VideoError("OUTPUT_IO", "Cannot publish encoded output") from error
        finally:
            self.abort()

    def _finish_reader(self) -> None:
        if self._reader is not None:
            self._reader.join(timeout=1)
            if self._reader.is_alive():
                raise VideoError("STDERR_TIMEOUT", "Encoder stderr reader did not finish")

    def abort(self) -> None:
        try:
            if self.proc is not None:
                if self.proc.poll() is None or not self._finished:
                    stop_process(self.proc)
                self.returncode = self.proc.returncode
                if not self.proc.stdin.closed:
                    self.proc.stdin.close()
                self._finish_reader()
                self.proc.stderr.close()
        finally:
            if self._temporary is not None:
                owner, self._temporary = self._temporary, None
                owner.cleanup()

    def confirm_cleanup(self) -> None:
        """Verify absence without deleting/reacquiring a completed transaction's path."""
        if self._transaction is not None:
            self._transaction.assert_absent()

    def __exit__(
        self, exc_type: type | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        if exc_type is None and not self._finished:
            self.finish()
        else:
            self.abort()
