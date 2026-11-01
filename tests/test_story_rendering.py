"""Real story streaming, cut decoding and error/cancellation lifecycle through accepted adapters."""

import importlib.util
import shutil
from pathlib import Path

import pytest

from reelforge.stories.contract import load_story, validate_story

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("cairo") is None or not shutil.which("ffmpeg"),
    reason="optional Cairo/FFmpeg",
)


def short_story():
    data = load_story(Path("examples/stories/last_farm.json")).to_data()
    data["shots"] = data["shots"][:2]
    for i, s in enumerate(data["shots"]):
        s.update(start_frame=i * 30, end_frame=(i + 1) * 30)
    data["output"]["frames"] = 60
    return validate_story(data)


@pytest.fixture
def worker(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import render_story

    return render_story


def test_real_continuous_story_encode_decode_and_repeat(tmp_path, worker, monkeypatch):
    from reelforge.media import encoder as media

    original = media.FFmpegEncoder
    encoders = []

    def tracked(*args, **kwargs):
        obj = original(*args, **kwargs)
        encoders.append(obj)
        return obj

    monkeypatch.setattr(media, "FFmpegEncoder", tracked)
    story = short_story()
    first = worker.render(story, tmp_path / "first")
    second = worker.render(story, tmp_path / "repeat")
    assert len(encoders) == 2  # One continuous encoder per entire timeline, not per shot.
    assert all(e.frames_written == 60 and e.proc.poll() == 0 for e in encoders)
    assert first["verification"]["decoded_frames"] == first["frames_written"] == 60
    assert first["verification"]["metadata"]["streams"][0]["avg_frame_rate"] == "30/1"
    assert first["source_surface_sha256"] == second["source_surface_sha256"]
    assert (
        first["verification"]["decoded_rgb_sha256"] == second["verification"]["decoded_rgb_sha256"]
    )
    assert len(first["source_surface_sha256"]) == 60
    assert first["blank_source_frames"] == []
    assert first["cut_boundaries"][0]["frame"] == 30
    assert first["cut_boundaries"][0]["before_sha256"] != first["cut_boundaries"][0]["after_sha256"]
    assert first["per_shot_timings"]["quiet_orchard"]["frames"] == 30
    assert first["per_shot_timings"]["rowan_notices"]["frames"] == 30
    assert not list((tmp_path / "first").glob("*.png"))
    for report in (first, second):
        assert report["whole_job_memory"]["job_budget_bytes"] == 256 * 1024**2
        assert report["whole_job_memory"]["reserve_bytes"] == 64 * 1024**2
        assert report["whole_job_memory"]["memory_policy"] == "strict"
        assert report["live_surfaces_after"] == report["allocated_surface_bytes_after"] == 0
        assert report["transaction_clean"]
        assert report["encoder_exit_status"] == 0
        assert report["stream_types"] == ["video"]
        assert not report["memory_observability"]["oom_events_changed"]


@pytest.mark.parametrize("error", [RuntimeError("injected geometry failure"), KeyboardInterrupt()])
def test_mid_story_failure_or_cancel_reaps_child_and_surface(tmp_path, worker, monkeypatch, error):
    from reelforge.media import encoder as media
    from reelforge.rendering.backends import cairo as backend

    original_encoder, original_renderer = media.FFmpegEncoder, backend.CairoRenderer
    renderer = original_renderer()
    encoders = []

    def tracked(*args, **kwargs):
        obj = original_encoder(*args, **kwargs)
        encoders.append(obj)
        return obj

    def fail(story, frame):
        if frame == 2:
            raise error
        return original_frame(story, frame)

    original_frame = worker.story_frame
    monkeypatch.setattr(media, "FFmpegEncoder", tracked)
    monkeypatch.setattr(backend, "CairoRenderer", lambda: renderer)
    monkeypatch.setattr(worker, "story_frame", fail)
    with pytest.raises(type(error)):
        worker.render(short_story(), tmp_path / "failed")
    assert len(encoders) == 1 and encoders[0].proc.poll() is not None
    assert not (tmp_path / "failed/story.mp4").exists()
    assert not list((tmp_path / "failed").glob(".reelforge-encode-*"))
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_encoder_write_failure_uses_existing_atomic_cleanup(tmp_path, worker, monkeypatch):
    from reelforge.media import encoder as media
    from reelforge.media.process import VideoError
    from reelforge.rendering.backends import cairo as backend

    original_encoder = media.FFmpegEncoder
    renderer = backend.CairoRenderer()
    encoders = []

    def tracked(*args, **kwargs):
        obj = original_encoder(*args, **kwargs)
        encoders.append(obj)
        original_write = obj.write_surface

        def failed_write(surface):
            if obj.frames_written == 2:
                raise VideoError("INJECTED_WRITE", "encoder write failure")
            return original_write(surface)

        obj.write_surface = failed_write
        return obj

    monkeypatch.setattr(media, "FFmpegEncoder", tracked)
    monkeypatch.setattr(backend, "CairoRenderer", lambda: renderer)
    with pytest.raises(VideoError):
        worker.render(short_story(), tmp_path / "encoder-failed")
    assert encoders[0].proc.poll() is not None
    assert not (tmp_path / "encoder-failed/story.mp4").exists()
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_default_source_has_exact_boundaries_and_no_accidental_duplicates():
    # Reconstruct only boundary samples, never a frame sequence in RAM.
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color
    from reelforge.stories.sampling import story_frame

    renderer = CairoRenderer()
    story = load_story(Path("examples/stories/last_farm.json"))
    hashes = {}
    with renderer.surface(360, 640) as surface:
        for f in (119, 120, 239, 240, 359, 120):
            renderer.draw(
                surface, story_frame(story, f), background=color("243e49"), logical_size=(360, 640)
            )
            value = surface.pixel_sha256()
            assert hashes.setdefault(f, value) == value
    assert hashes[119] != hashes[120]
    assert hashes[239] != hashes[240]
    assert len(hashes) == 5
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
