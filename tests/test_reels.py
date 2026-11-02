"""Reel integration safety: strict input, metadata-only planning, single owner and native AV."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from threading import Event

import pytest
from jsonschema import Draft202012Validator

from reelforge.audio.registry import AudioRegistry
from reelforge.core.errors import InputError, OperationError
from reelforge.core.transaction import OwnedDirectory
from reelforge.reels import workflow
from reelforge.reels.contract import compile_reel, inspect_reel, load_reel, metadata_plan
from reelforge.reels.schema import reel_schema

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/audio"
NAMES = ("silent_signal", "abandoned_settlement", "shelter_entrance")
NATIVE = importlib.util.find_spec("cairo") is not None and shutil.which("ffmpeg") is not None


@pytest.fixture
def data():
    return json.loads((ROOT / "examples/reels/silent_signal.json").read_text())


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "reel-9"),
        (("title",), " "),
        (("title",), 1),
        (("title",), "x" * 121),
        (("storyboard",), None),
        (("audio",), None),
        (("audio", "sample_rate"), 44100),
        (("audio", "channels"), True),
        (("audio", "bitrate"), 64000),
        (("audio", "codec"), "mp3"),
        (("audio", "narration", "asset_id"), "../take.wav"),
        (("audio", "narration", "asset_id"), "https://a.wav"),
        (("audio", "narration", "start_frame"), 90),
        (("audio", "narration", "start_frame"), -1),
        (("audio", "narration", "start_frame"), True),
        (("audio", "narration", "start_frame"), 0.0),
        (("audio", "narration", "trim_start_frame"), 900),
        (("audio", "narration", "trim_end_frame"), 0),
        (("audio", "narration", "gain"), 0.81),
        (("audio", "narration", "gain"), True),
        (("audio", "narration", "gain"), float("nan")),
        (("audio", "narration", "gain"), "volume=1"),
        (("audio", "cues"), [{}] * 5),
        (("storyboard", "schema_version"), "story-0.2"),
    ],
)
def test_rejects_invalid_contract(data, path, value):
    d = data
    for key in path[:-1]:
        d = d[key]
    d[path[-1]] = value
    with pytest.raises(InputError):
        compile_reel(data)


@pytest.mark.parametrize("path", [(), ("audio",), ("audio", "narration"), ("storyboard",)])
def test_unknown_fields_rejected(data, path):
    d = data
    for key in path:
        d = d[key]
    d["shell"] = "echo unsafe"
    with pytest.raises(InputError):
        compile_reel(data)


def test_empty_audio_and_nested_error_path(data):
    data["audio"].update(narration=None, cues=[])
    with pytest.raises(InputError):
        compile_reel(data)
    data["audio"]["cues"] = json.loads((ROOT / "examples/reels/silent_signal.json").read_text())[
        "audio"
    ]["cues"]
    data["storyboard"]["beats"][0]["frames"] = -1
    with pytest.raises(InputError) as caught:
        compile_reel(data)
    assert caught.value.issue.path.startswith("/storyboard/beats")


@pytest.mark.parametrize("name", NAMES)
def test_schema_and_exact_accepted_storyboard(name):
    data = json.loads((ROOT / f"examples/reels/{name}.json").read_text())
    assert data["storyboard"] == json.loads(
        (ROOT / f"examples/storyboards/{name}.json").read_text()
    )
    Draft202012Validator.check_schema(reel_schema())
    Draft202012Validator(reel_schema()).validate(data)
    reel = compile_reel(data)
    assert type(reel.storyboard).__name__ == "Storyboard"
    assert type(reel.audio).__name__ == "AudioPlan"


@pytest.mark.parametrize("change", ["missing", "role", "trim", "overlap"])
def test_metadata_asset_admission(data, change):
    cue = data["audio"]["narration"]
    if change == "missing":
        cue["asset_id"] = "missing"
    elif change == "role":
        cue["asset_id"] = "diag_fence"
    elif change == "trim":
        cue["trim_end_frame"] = 900
    else:
        cue["gain"] = 0.8
        data["audio"]["cues"][0]["start_frame"] = 0
    with pytest.raises(InputError) as caught:
        metadata_plan(compile_reel(data), AudioRegistry(ASSETS))
    assert caught.value.issue.path == "/audio"


def test_inspection_is_metadata_only_and_cut_does_not_reset_audio(tmp_path, monkeypatch):
    (tmp_path / "registry.json").write_bytes((ASSETS / "registry.json").read_bytes())
    reel = load_reel(ROOT / "examples/reels/abandoned_settlement.json")
    import reelforge.audio.registry as module

    monkeypatch.setattr(module, "inspect_wav", lambda *a, **k: pytest.fail("media opened"))
    cues = metadata_plan(reel, AudioRegistry(tmp_path))
    assert not inspect_reel(reel, cues)["media_bytes_validated"]
    for f in (59, 60, 61, 89):
        r = inspect_reel(reel, cues, f)
        assert r["sample"] == f * 1600
        assert any(c["asset_id"] == "diag_suspense" for c in r["active_cues"])
    assert inspect_reel(reel, cues, 60)["visual"]["source_frame"] == 60
    with pytest.raises((InputError, ValueError)):
        inspect_reel(reel, cues, 90)


def test_planning_imports_no_native_or_process_modules():
    code = """
import sys
from pathlib import Path
from reelforge.reels.contract import load_reel,metadata_plan,inspect_reel
from reelforge.audio.registry import AudioRegistry
from reelforge.reels.schema import reel_schema
p=load_reel(Path('examples/reels/silent_signal.json'))
inspect_reel(p,metadata_plan(p,AudioRegistry(Path('assets/audio'))),45)
reel_schema()
assert 'cairo' not in sys.modules and 'subprocess' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Fault injection tests orchestrator behavior without repeating native renders."""

    def resolve(self, plan, frames, **kwargs):
        return real_resolve(self, plan, frames, validate_media=False)

    real_resolve = AudioRegistry.resolve
    monkeypatch.setattr(AudioRegistry, "resolve", resolve)

    def mix(resolved, frames, snapshots, output, **kwargs):
        output.write_bytes(b"pcm")
        return {"samples": 144000}

    def mux(video, pcm, output, frames, **kwargs):
        output.write_bytes(b"verified candidate")
        return []

    monkeypatch.setattr(workflow, "mix_pcm", mix)
    monkeypatch.setattr(workflow, "mux_audio", mux)
    monkeypatch.setattr(workflow, "verify_audio", lambda *a, **k: {"passed": True})
    monkeypatch.setattr(workflow, "verify_video", lambda *a, **k: {"decoded_rgb_sha256": ["same"]})
    monkeypatch.setattr(workflow, "stream_check", lambda *a, **k: {"exact_video_pts": True})

    def silent(plan, output, **kwargs):
        output.mkdir()
        (output / "scene.mp4").write_bytes(b"silent")
        return {"success": True, "verification": {"decoded_rgb_sha256": ["same"]}}

    return silent


def test_one_owner_publication_and_no_clobber(data, tmp_path, monkeypatch, fake_pipeline):
    made = []

    class Owner(OwnedDirectory):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            made.append(self)

    monkeypatch.setattr(workflow, "OwnedDirectory", Owner)
    output = tmp_path / "result"
    r = workflow.render_reel(
        compile_reel(data), output, registry_root=ASSETS, render_silent=fake_pipeline
    )
    assert r["success"] and len(made) == 1
    assert not made[0].path.exists()
    assert (output / "reel.mp4").read_bytes() == b"verified candidate"
    with pytest.raises(OperationError, match="new output"):
        workflow.render_reel(
            compile_reel(data), output, registry_root=ASSETS, render_silent=fake_pipeline
        )


@pytest.mark.parametrize(
    "stage", ["mix_pcm", "mux_audio", "verify_audio", "verify_video", "stream_check"]
)
def test_failed_stage_never_publishes(data, tmp_path, monkeypatch, fake_pipeline, stage):
    def fail(*a, **k):
        raise OperationError("INJECTED", stage)

    monkeypatch.setattr(workflow, stage, fail)
    r = workflow.render_reel(
        compile_reel(data), tmp_path / "result", registry_root=ASSETS, render_silent=fake_pipeline
    )
    assert not r["success"] and not r["published"] and not r["media_verified"]
    assert r["error"]["code"] == "INJECTED" and r["transaction_clean"]


@pytest.mark.parametrize(
    "stage", ["render", "mix_pcm", "mux_audio", "verify_audio", "verify_video", "stream_check"]
)
def test_cancellation_across_stages(data, tmp_path, monkeypatch, fake_pipeline, stage):
    event = Event()
    if stage == "render":
        original = fake_pipeline
    else:
        original = getattr(workflow, stage)

    def cancel(*a, **k):
        value = original(*a, **k)
        event.set()
        return value

    if stage == "render":
        renderer = cancel
    else:
        monkeypatch.setattr(workflow, stage, cancel)
        renderer = fake_pipeline
    r = workflow.render_reel(
        compile_reel(data),
        tmp_path / "result",
        registry_root=ASSETS,
        render_silent=renderer,
        cancelled=event,
    )
    assert not r["success"] and not r["published"] and r["transaction_clean"]


def test_cancelled_before_output(data, tmp_path, fake_pipeline):
    event = Event()
    event.set()
    with pytest.raises(OperationError):
        workflow.render_reel(
            compile_reel(data),
            tmp_path / "result",
            registry_root=ASSETS,
            render_silent=fake_pipeline,
            cancelled=event,
        )
    assert not (tmp_path / "result").exists()


def test_snapshot_hash_failure(data, tmp_path, monkeypatch, fake_pipeline):
    monkeypatch.setattr(workflow, "digest", lambda p: "incorrect")
    r = workflow.render_reel(
        compile_reel(data), tmp_path / "result", registry_root=ASSETS, render_silent=fake_pipeline
    )
    assert r["error"]["code"] == "AUDIO_CHANGED" and not r["published"]
    assert r["transaction_clean"]


@pytest.mark.parametrize("when", ["after_publish", "before_publish"])
def test_restoration_is_failure_not_a_sweep(data, tmp_path, monkeypatch, fake_pipeline, when):
    made = []

    class Restored(OwnedDirectory):
        def cleanup(self):
            super().cleanup()
            self.path.mkdir()
            (self.path / "foreign.txt").write_text("do not reacquire")
            made.append(self.path)

    monkeypatch.setattr(workflow, "OwnedDirectory", Restored)
    if when == "before_publish":

        def fail(*a, **k):
            raise OperationError("PRIMARY", "mix failed")

        monkeypatch.setattr(workflow, "mix_pcm", fail)
    r = workflow.render_reel(
        compile_reel(data), tmp_path / "result", registry_root=ASSETS, render_silent=fake_pipeline
    )
    assert not r["success"] and not r["transaction_clean"]
    assert r["cleanup_error"]["code"] == "TRANSACTION_CLEANUP"
    assert (made[0] / "foreign.txt").read_text() == "do not reacquire"
    assert r["published"] == (when == "after_publish")
    if when == "before_publish":
        assert r["error"]["code"] == "PRIMARY"


@pytest.mark.parametrize("kind", ["memory", "storage"])
def test_resource_refusal(data, tmp_path, monkeypatch, fake_pipeline, kind):
    def refuse(*a, **k):
        raise OperationError("RESOURCE", kind)

    monkeypatch.setattr(
        workflow, "preflight_memory" if kind == "memory" else "check_workspace", refuse
    )
    with pytest.raises(OperationError):
        workflow.render_reel(
            compile_reel(data),
            tmp_path / "result",
            registry_root=ASSETS,
            render_silent=fake_pipeline,
        )
    assert not (tmp_path / "result").exists()


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg")
def test_actual_audio_mix_mux_video_preservation(tmp_path):
    # Reuse accepted video proof for audio integration, not an additional render.
    source = ROOT / "artifacts/phase7a/proofs/silent_signal_video/scene.mp4"
    assert source.exists()
    from reelforge.media.verify import verify_video

    decoded = verify_video(source, width=720, height=1280, frames=90)

    def silent(plan, output, **kwargs):
        output.mkdir()
        shutil.copyfile(source, output / "scene.mp4")
        return {"success": True, "verification": decoded}

    r = workflow.render_reel(
        load_reel(ROOT / "examples/reels/silent_signal.json"),
        tmp_path / "result",
        registry_root=ASSETS,
        render_silent=silent,
    )
    assert r["success"], r
    assert r["audio_verification"]["effective_samples_per_channel"] == 144000
    assert r["audio_verification"]["h264_bitstream_unchanged"]
    assert r["verification"]["decoded_rgb_sha256"] == decoded["decoded_rgb_sha256"]


@pytest.mark.skipif(not NATIVE, reason="optional FFmpeg")
def test_full_registry_validation_still_requires_wav(tmp_path):
    (tmp_path / "registry.json").write_bytes((ASSETS / "registry.json").read_bytes())
    reel = load_reel(ROOT / "examples/reels/silent_signal.json")
    registry = AudioRegistry(tmp_path)
    assert metadata_plan(reel, registry)
    with pytest.raises(OperationError):
        registry.resolve(reel.audio, 90, workspace=tmp_path)


def test_publication_race_preserves_foreign_file(data, tmp_path, monkeypatch, fake_pipeline):
    output = tmp_path / "result"
    original = workflow.stream_check

    def race(*a, **k):
        result = original(*a, **k)
        (output / "reel.mp4").write_bytes(b"foreign")
        return result

    monkeypatch.setattr(workflow, "stream_check", race)
    r = workflow.render_reel(
        compile_reel(data), output, registry_root=ASSETS, render_silent=fake_pipeline
    )
    assert not r["success"] and not r["published"] and r["media_verified"]
    assert (output / "reel.mp4").read_bytes() == b"foreign"


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg")
@pytest.mark.parametrize("cancel", [False, True])
def test_borrowed_encoder_failure_reaps_without_owning_root(tmp_path, cancel):
    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    owner = OwnedDirectory(tmp_path, ".reelforge-audio-")
    video = owner.path / "video"
    stage = owner.path / "encode"
    video.mkdir()
    stage.mkdir()
    event = Event()
    encoder = FFmpegEncoder(
        video / "scene.mp4",
        width=720,
        height=1280,
        frames=2,
        staging_directory=stage,
        cancelled=event,
    )
    renderer = CairoRenderer()
    try:
        with pytest.raises(OperationError):
            with encoder:
                with renderer.surface(720, 1280) as surface:
                    renderer.draw(surface, (), background=color("243e49"), logical_size=(360, 640))
                    encoder.write_surface(surface)
                    if cancel:
                        event.set()
                        encoder.write_surface(surface)
        assert encoder.proc.poll() is not None and encoder.proc.stdin.closed
        assert encoder._transaction is None and owner.path.is_dir()
        assert not (video / "scene.mp4").exists()
    finally:
        owner.cleanup()
    owner.assert_absent()
