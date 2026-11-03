"""Episode contract, absolute clock, continuous encoder mapping and shared AV ownership."""

import copy
import json
import subprocess
import sys
from pathlib import Path
from threading import Event

import pytest
from jsonschema import Draft202012Validator

from reelforge.audio.registry import AudioRegistry
from reelforge.core.errors import InputError, OperationError
from reelforge.episodes.contract import compile_episode, frame_origin, inspect_episode, load_episode
from reelforge.episodes.schema import episode_schema
from reelforge.reels import workflow
from reelforge.reels.contract import metadata_plan

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/audio"


@pytest.fixture
def data():
    r = json.loads((ROOT / "examples/reels/silent_signal.json").read_text())
    return {
        "schema_version": "episode-0.1",
        "title": "test episode",
        "segments": [{"id": "first", "storyboard": r["storyboard"]}],
        "audio": r["audio"],
    }


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "episode-9"),
        (("title",), " "),
        (("title",), False),
        (("segments",), []),
        (("segments",), [{}] * 11),
        (("segments",), "include.json"),
        (("segments", 0, "id"), "../outside"),
        (("segments", 0, "storyboard"), None),
        (("audio",), None),
        (("audio", "narration", "start_frame"), 90),
        (("audio", "narration", "start_frame"), True),
        (("audio", "cues"), [{}] * 5),
        (("audio", "narration", "gain"), 0.81),
        (("audio", "narration", "asset_id"), "https://a.wav"),
    ],
)
def test_strict_episode_rejections(data, path, value):
    item = data
    for key in path[:-1]:
        item = item[key]
    item[path[-1]] = value
    with pytest.raises(InputError):
        compile_episode(data)


@pytest.mark.parametrize("level", ["root", "segment", "storyboard"])
def test_unknown_fields(data, level):
    item = (
        data
        if level == "root"
        else data["segments"][0]
        if level == "segment"
        else data["segments"][0]["storyboard"]
    )
    item["command"] = "shell"
    with pytest.raises(InputError):
        compile_episode(data)


def test_duplicate_ids_and_nested_error_path(data):
    data["segments"].append(copy.deepcopy(data["segments"][0]))
    with pytest.raises(InputError, match="unique"):
        compile_episode(data)
    data["segments"][1]["id"] = "next"
    data["segments"][1]["storyboard"]["beats"][0]["frames"] = -1
    with pytest.raises(InputError) as caught:
        compile_episode(data)
    assert caught.value.issue.path.startswith("/segments/1/storyboard/beats")


@pytest.mark.parametrize("count", [1, 5, 10])
def test_bounds_and_global_audio(data, count):
    data["segments"] = [
        {"id": f"segment_{i}", "storyboard": data["segments"][0]["storyboard"]}
        for i in range(count)
    ]
    data["audio"]["narration"]["start_frame"] = count * 90 - 1
    plan = compile_episode(data)
    assert plan.frames == count * 90
    cues = metadata_plan(plan, AudioRegistry(ASSETS), plan.frames)
    assert cues[0].cue.start_frame == plan.frames - 1 and cues[0].output_samples == 1600
    for frame in (0, 89, plan.frames - 1):
        segment, local = frame_origin(plan, frame)
        assert segment.id == f"segment_{frame // 90}" and local == frame % 90
    with pytest.raises(InputError):
        frame_origin(plan, plan.frames)
    with pytest.raises(InputError):
        frame_origin(plan, True)


def test_schema_demo_and_cross_cut_sound():
    d = json.loads((ROOT / "examples/episodes/relay_to_shelter.json").read_text())
    Draft202012Validator.check_schema(episode_schema())
    Draft202012Validator(episode_schema()).validate(d)
    plan = compile_episode(d)
    before = inspect_episode(plan, AudioRegistry(ASSETS), 269)
    after = inspect_episode(plan, AudioRegistry(ASSETS), 270)
    assert before["local_frame"] == 89 and after["local_frame"] == 0
    assert before["segment_id"] != after["segment_id"]
    assert before["global_sample"] == 269 * 1600 and after["global_sample"] == 270 * 1600
    assert [c["asset_id"] for c in before["active_cues"]] == ["diag_suspense"]
    assert before["active_cues"] == after["active_cues"]
    assert after["editorial_cuts"] == [90, 180, 270, 360]
    assert not after["acting_continuity_across_segments"]
    # Semantic validation checks the actual requested episode length, not schema's maximum.
    d["audio"]["cues"][0]["start_frame"] = 899
    with pytest.raises(InputError):
        compile_episode(d)


def test_metadata_only_without_native_modules(tmp_path):
    (tmp_path / "registry.json").write_bytes((ASSETS / "registry.json").read_bytes())
    code = """
import sys
from pathlib import Path
from reelforge.episodes.contract import load_episode,inspect_episode
from reelforge.audio.registry import AudioRegistry
p=load_episode(Path('examples/episodes/relay_to_shelter.json'))
r=inspect_episode(p,AudioRegistry(Path(sys.argv[1])),270)
assert r['global_sample']==432000 and not r['media_bytes_validated']
assert 'cairo' not in sys.modules and 'subprocess' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=ROOT, check=True)


@pytest.fixture
def fake_pipeline(monkeypatch):
    calls = []
    real = AudioRegistry.resolve
    monkeypatch.setattr(
        AudioRegistry, "resolve", lambda self, p, f, **k: real(self, p, f, validate_media=False)
    )

    def mix(cues, frames, snapshots, output, **kwargs):
        calls.append(("mix", frames))
        output.write_bytes(b"pcm")
        return {"samples": frames * 1600}

    def mux(video, pcm, output, frames, **kwargs):
        calls.append(("mux", frames))
        output.write_bytes(b"verified")
        return []

    def audio(video, final, ref, decoded, cues, frames, **kwargs):
        calls.append(("audio_verify", frames))
        return {"passed": True}

    def verify(path, **kwargs):
        calls.append(("video_verify", kwargs["frames"]))
        return {"decoded_rgb_sha256": ["same"]}

    def streams(path, event, frames):
        calls.append(("stream_verify", frames))
        return {"exact_video_pts": True}

    monkeypatch.setattr(workflow, "mix_pcm", mix)
    monkeypatch.setattr(workflow, "mux_audio", mux)
    monkeypatch.setattr(workflow, "verify_audio", audio)
    monkeypatch.setattr(workflow, "verify_video", verify)
    monkeypatch.setattr(workflow, "stream_check", streams)

    def renderer(plan, output, **kwargs):
        calls.append(("render_once", plan.frames))
        output.mkdir()
        (output / "scene.mp4").write_bytes(b"video")
        return {"success": True, "verification": {"decoded_rgb_sha256": ["same"]}}

    return calls, renderer


def test_episode_uses_one_render_one_mix_and_global_length(tmp_path, fake_pipeline):
    calls, renderer = fake_pipeline
    plan = load_episode(ROOT / "examples/episodes/relay_to_shelter.json")
    output = tmp_path / "job"
    result = workflow.render_av(
        plan,
        output,
        frames=plan.frames,
        visual_plan=plan,
        render_silent=renderer,
        registry_root=ASSETS,
        contract_version="episode-0.1",
    )
    assert result["success"] and result["contract"] == "episode-0.1" and result["frames"] == 450
    assert calls == [
        (name, 450)
        for name in ("render_once", "mix", "mux", "audio_verify", "video_verify", "stream_verify")
    ]
    assert result["mix"]["samples"] == 720000
    assert result["transaction_clean"]
    with pytest.raises(OperationError):
        workflow.render_av(
            plan,
            output,
            frames=plan.frames,
            visual_plan=plan,
            render_silent=renderer,
            registry_root=ASSETS,
        )


def test_episode_cancel_and_tmp_workspace_are_not_bypassed(tmp_path, fake_pipeline):
    _, renderer = fake_pipeline
    plan = load_episode(ROOT / "examples/episodes/relay_to_shelter.json")
    event = Event()
    event.set()
    with pytest.raises(OperationError, match="cancelled"):
        workflow.render_av(
            plan,
            tmp_path / "cancelled",
            frames=450,
            visual_plan=plan,
            render_silent=renderer,
            registry_root=ASSETS,
            cancelled=event,
        )
    with pytest.raises(OperationError) as caught:
        workflow.render_av(
            plan,
            Path("/tmp/never-create-reelforge-episode"),
            frames=450,
            visual_plan=plan,
            render_silent=renderer,
            registry_root=ASSETS,
        )
    assert caught.value.code == "WORKSPACE_TMP"
