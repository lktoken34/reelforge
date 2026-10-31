"""Real FFmpeg smoke: encode, fully decode, count frames and compare decoded content."""

import shutil

import pytest

pytest.importorskip("cairo")

from reelforge.media.encoder import FFmpegEncoder
from reelforge.media.process import VideoError
from reelforge.media.verify import verify_video
from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.diagnostic import BACKGROUND, LOGICAL_SIZE
from reelforge.rendering.video_diagnostic import diagnostic_frame

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg/ffprobe not installed"
)


def test_real_encode_full_decode_and_repeat(tmp_path):
    renderer = CairoRenderer()
    results = []
    for repeat in range(2):
        output = tmp_path / f"repeat_{repeat}.mp4"
        with FFmpegEncoder(output, width=360, height=640, frames=12) as encoder:
            with renderer.surface(360, 640) as surface:
                for frame in range(12):
                    renderer.draw(
                        surface,
                        diagnostic_frame(frame, 12),
                        background=BACKGROUND,
                        logical_size=LOGICAL_SIZE,
                    )
                    encoder.write_surface(surface)
        assert not list(tmp_path.glob(".reelforge-encode-*"))
        report = verify_video(output, width=360, height=640, frames=12)
        assert report["decoded_frames"] == 12
        assert report["metadata"]["streams"][0]["codec_name"] == "h264"
        assert report["metadata"]["streams"][0]["pix_fmt"] == "yuv420p"
        assert encoder.returncode == 0
        assert report["mp4_top_level_boxes"].index("moov") < report["mp4_top_level_boxes"].index(
            "mdat"
        )
        with pytest.raises(VideoError) as caught:
            verify_video(output, width=360, height=640, frames=11)
        assert caught.value.code == "VIDEO_METADATA"
        results.append(report["decoded_rgb_sha256"])
    assert results[0] == results[1]
    assert renderer.allocated_bytes == renderer.active_surfaces == 0
