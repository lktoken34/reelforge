"""Process, byte-contract and publication failures must leave no live child or partial file."""

import os
import sys
import threading
import time
from dataclasses import replace

import pytest

pytest.importorskip("cairo")

from reelforge.core.streams import StreamError
from reelforge.media.encoder import FFmpegEncoder, frame_bytes
from reelforge.media.process import VideoError, run_bounded
from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.interface import PixelLayout
from reelforge.rendering.model import Color, RenderError
from reelforge.rendering.video_diagnostic import diagnostic_frame


@pytest.fixture
def fake_tool(tmp_path):
    def make(mode="success"):
        path = tmp_path / "fake-ffmpeg"
        path.write_text(
            f"#!{sys.executable}\n"
            + """import os,sys,time
from pathlib import Path
mode = """
            + repr(mode)
            + """
if '-encoders' in sys.argv:
    print(' V..... ' + ('other' if mode == 'no_codec' else 'libx264'))
    sys.exit(0)
if mode == 'early':
    os.write(2, b'encoder failed\\n')
    sys.exit(7)
if mode == 'broken':
    os.close(0)
    time.sleep(30)
if mode == 'hang':
    time.sleep(30)
if mode == 'logs':
    for _ in range(100):
        os.write(2, b'x'*4096)
while os.read(0, 65536):
    pass
if mode == 'finish_hang':
    time.sleep(30)
if mode == 'finish_error':
    sys.exit(9)
Path(sys.argv[-1]).write_bytes(b'fake-encoded-output')
"""
        )
        path.chmod(0o755)
        return str(path)

    return make


@pytest.fixture
def opaque_surface():
    renderer = CairoRenderer()
    with renderer.surface(360, 640) as surface:
        renderer.draw(surface, (), background=Color(0, 0, 0), logical_size=(360, 640))
        yield renderer, surface
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def assert_clean(encoder, output):
    assert not output.exists()
    assert not list(output.parent.glob(".reelforge-encode-*"))
    if encoder.proc is not None:
        assert encoder.proc.poll() is not None
        with pytest.raises(ProcessLookupError):
            os.kill(encoder.proc.pid, 0)


def test_missing_ffmpeg(tmp_path):
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(output, width=360, height=640, ffmpeg="no-such-reelforge-ffmpeg")
    with pytest.raises(VideoError) as caught:
        with encoder:
            pass
    assert caught.value.code == "FFMPEG_MISSING"
    assert_clean(encoder, output)


def test_required_codec_unavailable(tmp_path, fake_tool):
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(output, width=360, height=640, ffmpeg=fake_tool("no_codec"))
    with pytest.raises(VideoError) as caught:
        with encoder:
            pass
    assert caught.value.code == "ENCODER_UNAVAILABLE"
    assert_clean(encoder, output)


@pytest.mark.parametrize("dimensions", [(720, 640), (0, 640), (361, 640), (True, 640)])
def test_invalid_output_dimensions(tmp_path, dimensions):
    with pytest.raises(VideoError, match="360x640"):
        FFmpegEncoder(tmp_path / "out.mp4", width=dimensions[0], height=dimensions[1])


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"format": "RGB24"}, "FRAME_FORMAT"),
        ({"byte_order": "big"}, "FRAME_FORMAT"),
        ({"premultiplied": False}, "FRAME_FORMAT"),
        ({"stride": 1444}, "FRAME_STRIDE"),
        ({"width": 720}, "FRAME_DIMENSIONS"),
    ],
)
def test_layout_is_rejected_before_transfer(change, code):
    layout = replace(PixelLayout(360, 640, 1440, "ARGB32", "little", True), **change)
    with pytest.raises(VideoError) as caught:
        frame_bytes(layout, 360, 640)
    assert caught.value.code == code


def test_incorrect_frame_byte_count_aborts(tmp_path, fake_tool):
    class ShortSurface:
        layout = PixelLayout(360, 640, 1440, "ARGB32", "little", True)
        opaque = True
        closed = False

        def write_opaque_bgra(self, *args, **kwargs):
            return 12

    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(output, width=360, height=640, frames=1, ffmpeg=fake_tool())
    with pytest.raises(VideoError) as caught:
        with encoder:
            encoder.write_surface(ShortSurface())
    assert caught.value.code == "FRAME_BYTES"
    assert_clean(encoder, output)


@pytest.mark.parametrize(("mode", "code"), [("early", "ENCODER_EXIT"), ("broken", "BROKEN_PIPE")])
def test_early_exit_and_broken_pipe(tmp_path, fake_tool, opaque_surface, mode, code):
    _, surface = opaque_surface
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(output, width=360, height=640, frames=1, ffmpeg=fake_tool(mode))
    with pytest.raises((VideoError, StreamError)) as caught:
        with encoder:
            if mode == "early":
                encoder.proc.wait(timeout=2)
            encoder.write_surface(surface)
    assert caught.value.code == code
    assert_clean(encoder, output)
    assert not surface.closed  # Encoder borrows the surface; caller still owns it.
    assert surface.pixel_rgba8_premultiplied(0, 0) == (0, 0, 0, 255)


@pytest.mark.parametrize("mode", ["hang", "finish_hang"])
def test_write_and_finalize_deadlines(tmp_path, fake_tool, opaque_surface, mode):
    _, surface = opaque_surface
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(
        output,
        width=360,
        height=640,
        frames=1,
        timeout=0.5,
        frame_timeout=0.2,
        ffmpeg=fake_tool(mode),
    )
    started = time.monotonic()
    with pytest.raises(StreamError) as caught:
        with encoder:
            encoder.write_surface(surface)
    assert caught.value.code == "TIMEOUT"
    assert time.monotonic() - started < 4
    assert_clean(encoder, output)


def test_encoder_nonzero_after_eof(tmp_path, fake_tool, opaque_surface):
    _, surface = opaque_surface
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(
        output, width=360, height=640, frames=1, ffmpeg=fake_tool("finish_error")
    )
    with pytest.raises(VideoError) as caught:
        with encoder:
            encoder.write_surface(surface)
    assert caught.value.code == "ENCODER_EXIT"
    assert encoder.returncode == 9
    assert_clean(encoder, output)


def test_failed_publication(tmp_path, fake_tool, opaque_surface, monkeypatch):
    _, surface = opaque_surface

    def fail(*args):
        raise PermissionError("fixture publication denied")

    monkeypatch.setattr(os, "link", fail)
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(output, width=360, height=640, frames=1, ffmpeg=fake_tool())
    with pytest.raises(VideoError) as caught:
        with encoder:
            encoder.write_surface(surface)
    assert caught.value.code == "OUTPUT_IO"
    assert_clean(encoder, output)


def test_cancelled_blocked_write_and_cleanup(tmp_path, fake_tool, opaque_surface):
    _, surface = opaque_surface
    output = tmp_path / "out.mp4"
    cancel = threading.Event()
    encoder = FFmpegEncoder(
        output, width=360, height=640, frames=1, cancelled=cancel, ffmpeg=fake_tool("hang")
    )
    with pytest.raises(StreamError) as caught:
        with encoder:
            timer = threading.Timer(0.1, cancel.set)
            timer.start()
            try:
                encoder.write_surface(surface)
            finally:
                timer.join()
    assert caught.value.code == "CANCELLED"
    assert_clean(encoder, output)


def test_keyboard_interrupt_preserves_existing_output_and_releases_surface(tmp_path, fake_tool):
    output = tmp_path / "out.mp4"
    output.write_bytes(b"original")
    encoder = FFmpegEncoder(
        output, width=360, height=640, frames=1, overwrite=True, ffmpeg=fake_tool("hang")
    )
    renderer = CairoRenderer()
    with pytest.raises(KeyboardInterrupt):
        with encoder:
            with renderer.surface(360, 640):
                raise KeyboardInterrupt
    assert output.read_bytes() == b"original"
    assert encoder.proc.poll() is not None
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    assert not list(tmp_path.glob(".reelforge-encode-*"))


def test_count_mismatch_never_publishes(tmp_path, fake_tool, opaque_surface):
    _, surface = opaque_surface
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(output, width=360, height=640, frames=2, ffmpeg=fake_tool())
    with pytest.raises(VideoError) as caught:
        with encoder:
            encoder.write_surface(surface)
    assert caught.value.code == "FRAME_COUNT"
    assert_clean(encoder, output)


def test_success_drains_bounded_logs_and_publishes_once(tmp_path, fake_tool, opaque_surface):
    _, surface = opaque_surface
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(output, width=360, height=640, frames=1, ffmpeg=fake_tool("logs"))
    with encoder:
        encoder.write_surface(surface)
        assert not output.exists()
    assert output.read_bytes() == b"fake-encoded-output"
    assert encoder.returncode == 0
    assert len(encoder.stderr_tail.encode()) <= 16384
    assert not list(tmp_path.glob(".reelforge-encode-*"))
    with pytest.raises(VideoError, match="reused"):
        with encoder:
            pass


def test_transparent_surface_rejected(tmp_path, fake_tool):
    renderer = CairoRenderer()
    output = tmp_path / "out.mp4"
    encoder = FFmpegEncoder(output, width=360, height=640, frames=1, ffmpeg=fake_tool())
    with pytest.raises(VideoError) as caught:
        with encoder:
            with renderer.surface(360, 640) as surface:
                renderer.draw(surface, (), background=Color(0, 0, 0, 0.5), logical_size=(360, 640))
                encoder.write_surface(surface)
    assert caught.value.code == "FRAME_ALPHA"
    assert renderer.active_surfaces == 0
    assert_clean(encoder, output)


def test_raw_transfer_never_accepts_an_unproven_surface():
    renderer = CairoRenderer()
    with renderer.surface(360, 640) as surface:
        with pytest.raises(RenderError, match="opaque"):
            surface.write_opaque_bgra(-1, deadline=time.monotonic() + 1)


def test_raw_pipe_times_out_without_consumer_and_surface_remains_valid(opaque_surface):
    _, surface = opaque_surface
    read_fd, write_fd = os.pipe()
    os.set_blocking(write_fd, False)
    try:
        with pytest.raises(StreamError) as caught:
            surface.write_opaque_bgra(write_fd, deadline=time.monotonic() + 0.1)
        assert caught.value.code == "TIMEOUT"
        assert not surface.closed
        assert surface.pixel_sha256()
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_bounded_tool_output_and_timeout():
    with pytest.raises(VideoError) as caught:
        run_bounded([sys.executable, "-c", "print('x'*50000)"], max_bytes=128)
    assert caught.value.code == "TOOL_OUTPUT_LIMIT"
    with pytest.raises(StreamError) as caught:
        run_bounded([sys.executable, "-c", "import time;time.sleep(30)"], timeout=0.1)
    assert caught.value.code == "TIMEOUT"


def test_diagnostic_is_pure_and_moves_in_frame_order_or_out_of_order():
    first, middle, last = [diagnostic_frame(i) for i in (0, 75, 149)]
    assert first != middle != last
    assert diagnostic_frame(0) == first
    assert diagnostic_frame(149) == last
    assert diagnostic_frame(75) == middle
    with pytest.raises(RenderError):
        diagnostic_frame(150)


def test_raw_transfer_is_exact_bgra_after_opaque_alpha_compositing(opaque_surface):
    from reelforge.rendering.model import DrawPath, rectangle

    renderer, surface = opaque_surface
    renderer.draw(
        surface,
        (DrawPath(rectangle(0, 0, 360, 640), Color(1, 0, 0, 0.5)),),
        background=Color(0, 0, 1),
        logical_size=(360, 640),
    )
    read_fd, write_fd = os.pipe()
    os.set_blocking(write_fd, False)
    observed = {"count": 0, "prefix": b""}

    def consume():
        while data := os.read(read_fd, 8192):
            if not observed["prefix"]:
                observed["prefix"] = data[:4]
            observed["count"] += len(data)

    reader = threading.Thread(target=consume)
    reader.start()
    try:
        assert surface.write_opaque_bgra(write_fd, deadline=time.monotonic() + 3) == 360 * 640 * 4
    finally:
        os.close(write_fd)
        reader.join(timeout=2)
        os.close(read_fd)
    assert not reader.is_alive()
    assert observed == {"count": 360 * 640 * 4, "prefix": bytes((127, 0, 128, 255))}
    assert not surface.closed
