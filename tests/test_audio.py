"""Audio syntax, trusted registration, PCM grid, real AAC sync and failure transactions."""

import copy
import importlib.util
import json
import shutil
import struct
import sys
import threading
import wave
from dataclasses import asdict
from pathlib import Path

import pytest

from reelforge.audio.registry import AudioRegistry, digest, inspect_wav, register_asset
from reelforge.core.errors import InputError, OperationError
from reelforge.stories.contract import load_story, validate_story

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/audio"
EXAMPLE = ROOT / "examples/stories/last_farm_audio.json"
NATIVE = importlib.util.find_spec("cairo") is not None and shutil.which("ffmpeg") is not None


@pytest.fixture
def audio_data():
    return json.loads(EXAMPLE.read_text())


@pytest.mark.parametrize(
    "path,value",
    [
        (("codec",), "mp3"),
        (("sample_rate",), 44100),
        (("channels",), 1),
        (("bitrate",), 256000),
        (("channels",), True),
        (("narration", "asset_id"), "../private.wav"),
        (("narration", "asset_id"), "https://site/audio.wav"),
        (("narration", "start_frame"), 360),
        (("narration", "start_frame"), -1),
        (("narration", "start_frame"), 9.0),
        (("narration", "start_frame"), False),
        (("narration", "trim_start_frame"), -1),
        (("narration", "trim_end_frame"), 0),
        (("narration", "trim_end_frame"), True),
        (("narration", "gain"), float("nan")),
        (("narration", "gain"), float("inf")),
        (("narration", "gain"), True),
        (("narration", "gain"), 0),
        (("narration", "gain"), 0.81),
        (("narration", "gain"), "volume=1"),
        (("cues",), [{}] * 5),
    ],
)
def test_audio_syntax_rejects_invalid_fields(audio_data, path, value):
    target = audio_data["audio"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InputError) as caught:
        validate_story(audio_data)
    assert caught.value.issue.path.startswith("/audio")


def test_versioning_and_explicit_silence(audio_data):
    old = load_story(ROOT / "examples/stories/last_farm.json")
    assert old.audio is None and "audio" not in old.to_data()
    enabled = validate_story(audio_data)
    assert enabled.to_data() == audio_data
    audio_data["schema_version"] = "story-0.1"
    with pytest.raises(InputError):
        validate_story(audio_data)
    audio_data["schema_version"] = "story-0.2"
    audio_data["audio"] = None
    assert validate_story(audio_data).audio is None


@pytest.mark.parametrize("where", [(), ("narration",), ("cues", 0)])
def test_audio_unknown_fields_cannot_override_commands(audio_data, where):
    target = audio_data["audio"]
    for key in where:
        target = target[key]
    target["ffmpeg"] = "python -c bad"
    with pytest.raises(InputError):
        validate_story(audio_data)


def test_empty_audio_requires_explicit_disable(audio_data):
    audio_data["audio"].update(narration=None, cues=[])
    with pytest.raises(InputError):
        validate_story(audio_data)


def make_wav(path, *, rate=48000, channels=1, width=2, frames=4800, zero=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setparams((channels, width, rate, frames, "NONE", "not compressed"))
        for n in range(0, frames, 1024):
            count = min(1024, frames - n)
            sample = (
                b"\0" * width
                if zero
                else (struct.pack("<h", 1000) if width == 2 else b"\1" * width)
            )
            w.writeframesraw(sample * channels * count)
    return path


def raw_registry(tmp_path, path):
    asset = {
        "id": "take",
        "role": "narration",
        "file": "take.wav",
        "sha256": digest(path),
        "size_bytes": path.stat().st_size,
        "sample_rate": 48000,
        "channels": 1,
        "samples": 4800,
    }
    (tmp_path / "registry.json").write_text(
        json.dumps({"schema_version": "audio-assets-0.1", "assets": [asset]})
    )
    return asset


@pytest.mark.skipif(not NATIVE, reason="optional FFmpeg")
@pytest.mark.parametrize("rate,channels", [(16000, 1), (24000, 2), (44100, 1), (48000, 2)])
def test_registration_supports_bounded_rates_and_channels(tmp_path, rate, channels):
    source = make_wav(tmp_path / "source.wav", rate=rate, channels=channels, frames=rate // 10)
    asset = register_asset(tmp_path / "registry", source, "spoken_take", "narration")
    assert asset.sample_rate == rate and asset.channels == channels
    assert (tmp_path / "registry/spoken_take.wav").read_bytes() == source.read_bytes()
    assert AudioRegistry(tmp_path / "registry").assets["spoken_take"] == asset
    with pytest.raises(OperationError):
        register_asset(tmp_path / "registry", source, "spoken_take", "narration")


@pytest.mark.parametrize(
    "kwargs", [{"rate": 22050}, {"channels": 3}, {"width": 4}, {"frames": 48000 * 31}]
)
def test_invalid_wav_metadata_rejected_before_decoder(tmp_path, kwargs):
    source = make_wav(tmp_path / "invalid.wav", **kwargs)
    with pytest.raises(OperationError):
        inspect_wav(source, "narration")


def test_malformed_truncated_and_unsupported_media(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not wav" * 10)
    with pytest.raises(OperationError):
        inspect_wav(bad, "sfx")
    path = make_wav(tmp_path / "valid.wav")
    path.write_bytes(path.read_bytes()[:-2])
    with pytest.raises(OperationError):
        inspect_wav(path, "sfx")
    mp3 = tmp_path / "file.mp3"
    mp3.write_bytes(b"not a supported format")
    with pytest.raises(OperationError):
        inspect_wav(mp3, "sfx")


def test_registry_rejects_traversal_and_symlinks(tmp_path):
    source = make_wav(tmp_path / "take.wav")
    record = raw_registry(tmp_path, source)
    data = json.loads((tmp_path / "registry.json").read_text())
    data["assets"][0]["file"] = "../take.wav"
    (tmp_path / "registry.json").write_text(json.dumps(data))
    with pytest.raises(OperationError):
        AudioRegistry(tmp_path)
    raw_registry(tmp_path, source)
    other = tmp_path / "other.wav"
    source.rename(other)
    source.symlink_to(other)
    plan = load_story(EXAMPLE).audio
    cue = asdict(plan.narration)
    cue.update(asset_id="take", start_frame=0)
    from reelforge.stories.audio_contract import audio_from_data

    audio = audio_from_data(
        {
            "sample_rate": 48000,
            "channels": 2,
            "codec": "aac",
            "bitrate": 128000,
            "narration": cue,
            "cues": [],
        },
        30,
    )
    with pytest.raises(OperationError):
        AudioRegistry(tmp_path).resolve(audio, 30)
    assert record["file"] == "take.wav"


@pytest.mark.skipif(not NATIVE, reason="optional FFmpeg")
@pytest.mark.parametrize(
    "problem", ["unknown", "missing", "changed", "metadata", "role", "trim", "silent"]
)
def test_audio_asset_resolution_failures(tmp_path, audio_data, problem):
    root = tmp_path / "registry"
    root.mkdir()
    shutil.copytree(ASSETS, root, dirs_exist_ok=True)
    data = copy.deepcopy(audio_data)
    registry = json.loads((root / "registry.json").read_text())
    if problem == "unknown":
        data["audio"]["narration"]["asset_id"] = "unregistered"
    if problem == "missing":
        (root / "diag_opening.wav").unlink()
    if problem == "changed":
        path = root / "diag_opening.wav"
        b = bytearray(path.read_bytes())
        b[-4] ^= 1
        path.write_bytes(b)
    if problem == "metadata":
        registry["assets"][0]["sample_rate"] = 48000
        (root / "registry.json").write_text(json.dumps(registry))
    if problem == "role":
        data["audio"]["narration"]["asset_id"] = "diag_fence"
    if problem == "trim":
        data["audio"]["narration"]["trim_end_frame"] = 37
    if problem == "silent":
        asset = registry["assets"][0]
        path = make_wav(root / "diag_opening.wav", rate=24000, frames=28800, zero=True)
        asset["sha256"] = digest(path)
        asset["size_bytes"] = path.stat().st_size
        (root / "registry.json").write_text(json.dumps(registry))
    story = validate_story(data)
    with pytest.raises(OperationError):
        AudioRegistry(root).resolve(story.audio, 360)


@pytest.mark.skipif(not NATIVE, reason="optional FFmpeg")
def test_overlap_gain_and_asset_end_bounds(audio_data):
    data = copy.deepcopy(audio_data)
    data["audio"]["cues"][0].update(start_frame=9, gain=0.4)
    story = validate_story(data)
    with pytest.raises(OperationError, match="gains"):
        AudioRegistry(ASSETS).resolve(story.audio, 360)
    data = copy.deepcopy(audio_data)
    data["audio"]["narration"].update(trim_start_frame=35, trim_end_frame=None, start_frame=359)
    data["audio"]["cues"] = []
    resolved = AudioRegistry(ASSETS).resolve(validate_story(data).audio, 360)
    assert resolved[0].output_samples == 1600
    assert resolved[0].trim_end_frame == 36


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    if not NATIVE:
        pytest.skip("optional Cairo/FFmpeg")
    sys.path.insert(0, str(ROOT / "tools"))
    from render_story import render

    data = load_story(ROOT / "examples/stories/last_farm.json").to_data()
    data["shots"] = data["shots"][:1]
    data["shots"][0]["end_frame"] = 30
    data["output"]["frames"] = 30
    story = validate_story(data)
    directory = tmp_path_factory.mktemp("audio-silent-template")
    report = render(story, directory)
    return directory, report


@pytest.fixture
def workflow(tmp_path, template, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import render_audio_story as driver

    directory, report = template
    data = load_story(EXAMPLE).to_data()
    data["shots"] = data["shots"][:1]
    data["shots"][0]["end_frame"] = 30
    data["output"]["frames"] = 30
    data["audio"]["narration"].update(start_frame=1, gain=0.3)
    data["audio"]["cues"][0].update(start_frame=15, gain=0.1)
    data["audio"]["cues"][1].update(start_frame=24, gain=0.2)
    story = validate_story(data)
    calls = []

    def silent(s, out):
        calls.append(s)
        assert s.audio is None and s.schema_version == "story-0.1"
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(directory / "story.mp4", out / "story.mp4")
        (out / "report.json").write_text(json.dumps(report))
        return report

    def run(out):
        return driver.render_with_audio(story, out, render_silent=silent, registry_root=ASSETS)

    return driver, story, run, calls


def test_real_pcm_mix_aac_mux_repeat_and_clock(tmp_path, audio_data):
    if not NATIVE:
        pytest.skip("optional Cairo/FFmpeg")
    import subprocess

    data = copy.deepcopy(audio_data)
    data["shots"] = data["shots"][:1]
    data["shots"][0]["end_frame"] = data["output"]["frames"] = 30
    data["audio"]["narration"].update(start_frame=1, gain=0.3)
    data["audio"]["cues"][0].update(start_frame=15, gain=0.1)
    data["audio"]["cues"][1].update(start_frame=24, gain=0.2)
    manifest = tmp_path / "story.json"
    manifest.write_text(json.dumps(data))
    reports = []
    for name in ("first", "repeat"):
        directory = tmp_path / name
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/render_story.py"),
                str(manifest),
                "--output-dir",
                str(directory),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        reports.append(json.loads((directory / "report.json").read_text()))
    first, second = reports
    for report in (first, second):
        verify = report["audio_verification"]
        assert report["stream_types"] == ["video", "audio"]
        assert report["verification"]["decoded_frames"] == 30
        assert verify["effective_samples_per_channel"] == 48000
        assert 0 <= verify["terminal_padding_samples"] <= 1024
        assert verify["decoded_audio_clock_gapless"] and verify["h264_bitstream_unchanged"]
        assert verify["video_pts_unchanged"]
        assert abs(verify["first_audible_error_samples"]) <= 1024
        assert abs(verify["last_audible_error_samples"]) <= 1024
        assert report["mix"]["statistics"]["peak"] <= 0.9
        assert (
            report["temporary_storage"]["sampled_peak_bytes"]
            <= report["temporary_storage"]["preflight_estimate_bytes"]
        )
        assert report["whole_job_memory"]["job_budget_bytes"] == 256 * 1024**2
        assert report["whole_job_memory"]["reserve_bytes"] == 64 * 1024**2
        assert report["whole_job_memory"]["memory_policy"] == "strict"
        assert report["live_surfaces_after"] == report["allocated_surface_bytes_after"] == 0
        assert report["transaction_clean"]
    assert first["mix"]["statistics"]["sha256"] == second["mix"]["statistics"]["sha256"]
    assert (
        first["audio_verification"]["decoded_pcm"]["sha256"]
        == second["audio_verification"]["decoded_pcm"]["sha256"]
    )
    for name in ("first", "repeat"):
        assert not list((tmp_path / name).glob(".reelforge-audio-*"))


def test_existing_output_is_protected_before_work(tmp_path, workflow):
    _, _, run, calls = workflow
    output = tmp_path / "existing"
    output.mkdir()
    (output / "story.mp4").write_bytes(b"previous success")
    with pytest.raises(OperationError, match="Successful output"):
        run(output)
    assert calls == [] and (output / "story.mp4").read_bytes() == b"previous success"


@pytest.mark.parametrize("stage", ["mix", "mux", "verify"])
def test_unexpected_stage_failure_removes_private_mp4(tmp_path, workflow, monkeypatch, stage):
    driver, _, run, _ = workflow
    function = {"mix": "mix_pcm", "mux": "mux_audio", "verify": "verify_audio"}[stage]

    def fail(*args, **kwargs):
        if stage == "verify":
            # Candidate exists, but may not be published before successful verification.
            assert args[1].exists()
        raise OperationError("INJECTED_AUDIO", "unexpected FFmpeg/verification failure")

    monkeypatch.setattr(driver, function, fail)
    out = tmp_path / "failed"
    with pytest.raises(OperationError):
        run(out)
    assert not (out / "story.mp4").exists()
    assert not list(out.glob(".reelforge-audio-*"))


def test_audio_cancellation_reaps_actual_child_and_removes_candidate(
    tmp_path, workflow, monkeypatch
):
    from reelforge.media import process

    driver, _, run, _ = workflow
    original = process.subprocess.Popen
    children = []

    def capture(*args, **kwargs):
        proc = original(*args, **kwargs)
        children.append(proc)
        return proc

    monkeypatch.setattr(process.subprocess, "Popen", capture)

    def interrupted(*args, **kwargs):
        event = kwargs["cancelled"]
        timer = threading.Timer(0.05, event.set)
        timer.start()
        try:
            process.run_bounded(
                [sys.executable, "-c", "import time;time.sleep(30)"], timeout=2, cancelled=event
            )
        finally:
            timer.cancel()

    monkeypatch.setattr(driver, "mix_pcm", interrupted)
    out = tmp_path / "cancelled"
    with pytest.raises(OperationError):
        run(out)
    assert children and all(proc.poll() is not None for proc in children)
    assert not (out / "story.mp4").exists() and not list(out.glob(".reelforge-audio-*"))


def test_keyboard_interrupt_cleans_transaction(tmp_path, workflow, monkeypatch):
    driver, _, run, _ = workflow

    def stop(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(driver, "mux_audio", stop)
    out = tmp_path / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        run(out)
    assert not (out / "story.mp4").exists() and not list(out.glob(".reelforge-audio-*"))


def test_disk_preflight_prevents_render(tmp_path, workflow, monkeypatch):
    driver, _, run, calls = workflow

    def no_space(*args, **kwargs):
        raise OperationError("DISK_PREFLIGHT", "insufficient workspace space")

    monkeypatch.setattr(driver, "check_workspace", no_space)
    out = tmp_path / "full"
    with pytest.raises(OperationError):
        run(out)
    assert calls == [] and not (out / "story.mp4").exists()


def test_resource_cancellation_at_final_exit_cannot_publish(tmp_path, workflow, monkeypatch):
    driver, _, run, _ = workflow
    original = driver.JobMonitor

    class LateCancel(original):
        def __exit__(self, *args):
            super().__exit__(*args)
            self.cancelled.set()

    monkeypatch.setattr(driver, "JobMonitor", LateCancel)
    out = tmp_path / "late-cancel"
    with pytest.raises(OperationError, match="cancelled"):
        run(out)
    assert not (out / "story.mp4").exists() and not list(out.glob(".reelforge-audio-*"))


def test_racing_output_protection(tmp_path, workflow, monkeypatch):
    driver, _, run, _ = workflow
    original = driver.mux_audio
    out = tmp_path / "racing"

    def race(*args, **kwargs):
        result = original(*args, **kwargs)
        (out / "story.mp4").write_bytes(b"another successful writer")
        return result

    monkeypatch.setattr(driver, "mux_audio", race)
    with pytest.raises(FileExistsError):
        run(out)
    assert (out / "story.mp4").read_bytes() == b"another successful writer"
    assert not list(out.glob(".reelforge-audio-*"))


def test_process_failure_is_not_silent_fallback(monkeypatch):
    from reelforge.audio import processing

    monkeypatch.setattr(processing, "run_bounded", lambda *a, **k: (9, b"", b"FFmpeg failed"))
    with pytest.raises(OperationError, match="FFmpeg failed"):
        processing.command(["ffmpeg"])


def test_pcm_blocks_are_bounded_and_reject_nonfinite(tmp_path):
    from reelforge.audio.processing import blocks, pcm_stats

    path = tmp_path / "samples.f32"
    path.write_bytes(struct.pack("<ff", 0.1, -0.1) * 20000)
    assert all(len(b) <= 16384 for b in blocks(path))
    assert pcm_stats(path)["samples_per_channel"] == 20000
    path.write_bytes(struct.pack("<ff", float("nan"), 0))
    with pytest.raises(OperationError):
        pcm_stats(path)


def test_safe_invalid_audio_cli(tmp_path):
    import subprocess

    data = load_story(EXAMPLE).to_data()
    data["audio"]["narration"]["start_frame"] = 360
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    out = tmp_path / "should-not-exist"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/render_story.py"), str(path), "--output-dir", str(out)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2 and not out.exists()
    assert json.loads(result.stdout)["issue"]["path"] == "/audio/narration/start_frame"


@pytest.mark.skipif(not NATIVE, reason="optional FFmpeg")
@pytest.mark.parametrize("rate,channels", [(16000, 1), (44100, 2)])
def test_exact_pcm_frame_grid_trim_channel_conversion_and_padding(tmp_path, rate, channels):
    from reelforge.audio.processing import blocks, mix_pcm
    from reelforge.stories.audio_contract import audio_from_data

    source = make_wav(tmp_path / "constant.wav", rate=rate, channels=channels, frames=rate // 2)
    root = tmp_path / "registry"
    register_asset(root, source, "constant", "narration")
    plan = audio_from_data(
        {
            "sample_rate": 48000,
            "channels": 2,
            "codec": "aac",
            "bitrate": 128000,
            "narration": {
                "asset_id": "constant",
                "start_frame": 5,
                "trim_start_frame": 2,
                "trim_end_frame": 8,
                "gain": 0.4,
            },
            "cues": [],
        },
        30,
    )
    resolved = AudioRegistry(root).resolve(plan, 30)
    output = tmp_path / "mix.f32"
    mixed = mix_pcm(resolved, 30, {"constant": root / "constant.wav"}, output)
    assert mixed["samples"] == 48000
    assert all(value == 0 for b in blocks(output, end=5 * 1600) for value in b)
    assert all(value == 0 for b in blocks(output, start=11 * 1600) for value in b)
    with output.open("rb") as f:
        f.seek(6 * 1600 * 8)
        left, right = struct.unpack("<ff", f.read(8))
    assert left == pytest.approx(1000 / 32768 * 0.4, abs=1e-6)
    assert right == pytest.approx(left, abs=1e-6)
    # Extending beyond the video is deterministically clipped, never stretches video.
    data = asdict(plan)
    data["cues"] = []
    data["narration"]["start_frame"] = 28
    clipped = AudioRegistry(root).resolve(audio_from_data(data, 30), 30)
    assert clipped[0].output_samples == 2 * 1600
    clipfile = tmp_path / "clipped.f32"
    assert mix_pcm(clipped, 30, {"constant": root / "constant.wav"}, clipfile)["samples"] == 48000
    assert all(v == 0 for b in blocks(clipfile, end=28 * 1600) for v in b)


def test_incomplete_minimum_frame_and_compressed_wav_are_rejected(tmp_path):
    short = make_wav(tmp_path / "short.wav", rate=16000, frames=533)
    with pytest.raises(OperationError):
        inspect_wav(short, "sfx")
    path = make_wav(tmp_path / "compressed.wav")
    data = bytearray(path.read_bytes())
    data[20:22] = struct.pack("<H", 6)
    path.write_bytes(data)
    with pytest.raises(OperationError):
        inspect_wav(path, "sfx")


@pytest.mark.skipif(not NATIVE, reason="optional FFmpeg")
def test_actual_ffmpeg_failure_reaps_process(monkeypatch):
    from reelforge.audio.processing import command
    from reelforge.media import process

    original = process.subprocess.Popen
    children = []

    def capture(*args, **kwargs):
        p = original(*args, **kwargs)
        children.append(p)
        return p

    monkeypatch.setattr(process.subprocess, "Popen", capture)
    with pytest.raises(OperationError):
        command(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "anullsrc",
                "-af",
                "reelforge_unsupported_filter",
                "-t",
                ".01",
                "-f",
                "null",
                "-",
            ]
        )
    assert children and all(p.poll() is not None for p in children)


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg")
def test_story02_explicit_null_uses_original_silent_path(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import render_story

    data = load_story(ROOT / "examples/stories/last_farm.json").to_data()
    data.update(schema_version="story-0.2", audio=None)
    data["shots"] = data["shots"][:1]
    data["shots"][0]["end_frame"] = 30
    data["output"]["frames"] = 30
    report = render_story.render(validate_story(data), tmp_path / "silent02")
    assert report["stream_types"] == ["video"]
    assert report["story"]["audio"] is None and report["verification"]["decoded_frames"] == 30
