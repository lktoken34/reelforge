"""Structured narrative scheduling, accepted-plan compilation, reference safety and ownership."""

import copy
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from reelforge.blocking.contract import compile_blocking
from reelforge.core.errors import InputError, OperationError
from reelforge.direction.contract import compile_direction
from reelforge.direction.sampling import direction_frame, direction_layers
from reelforge.storyboards.compiler import (
    compile_storyboard,
    inspect_beats,
    inspect_frame,
    inspect_plans,
    load_storyboard,
)

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("silent_signal", "abandoned_settlement", "shelter_entrance")
NATIVE = importlib.util.find_spec("cairo") is not None and shutil.which("ffmpeg") is not None


@pytest.fixture
def data():
    return json.loads((ROOT / "examples/storyboards/silent_signal.json").read_text())


@pytest.fixture(scope="module")
def plans():
    return {name: load_storyboard(ROOT / f"examples/storyboards/{name}.json") for name in NAMES}


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "storyboard-9"),
        (("title",), "  "),
        (("title",), 1),
        (("world",), "https://outside"),
        (("rowan", "actor_id"), "other"),
        (("rowan", "support_id"), "receiver"),
        (("rowan", "start", "facing"), "up"),
        (("rowan", "start", "position"), [True, 550]),
        (("rowan", "start", "position"), [0, 550]),
        (("subjects", 0, "target", "id"), "other"),
        (("subjects", 1, "target", "id"), "missing"),
        (("subjects", 1, "target", "id"), "root"),
        (("subjects", 1, "id"), "rowan"),
        (("subjects", 2, "target", "depth"), 0),
        (("subjects", 2, "target", "position"), [1, math.inf]),
        (("views", 0, "subject"), "undefined"),
        (("views", 0, "kind"), "auto"),
        (("views", 0, "zoom"), [1, 2]),
        (("views", 0, "lead_seconds"), True),
        (("views", 0, "hold"), [90, 1]),
        (("views", 0, "crop"), "guess"),
        (("views", 0, "screen"), [345, 500]),
        (("pattern",), "anything"),
        (("beats", 1, "id"), "enter"),
        (("beats", 1, "frames"), True),
        (("beats", 1, "frames"), 36.0),
        (("beats", 1, "frames"), 1),
        (("beats", 1, "frames"), 90),
        (("beats", 1, "frames"), 35),
        (("beats", 2, "subject"), "missing"),
        (("beats", 2, "subject"), "rowan"),
        (("beats", 1, "view"), "missing"),
        (("beats", 1, "action", "kind"), "teleport"),
        (("beats", 1, "action", "end_speed"), math.nan),
        (("beats", 1, "action", "end_speed"), 90),
        (("beats", 2, "action", "end_x"), 140),
        (("beats", 3, "action", "kind"), "run_to"),
        (("beats", 3, "action", "expression"), "angry_unbounded"),
        (("description",), {"code": "not metadata text"}),
    ],
)
def test_invalid_contract_and_unsupported_combinations(data, path, value):
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InputError) as e:
        compile_storyboard(data)
    assert e.value.issue.code.startswith("STORYBOARD")


@pytest.mark.parametrize("where", ["root", "beat", "action", "view", "target"])
@pytest.mark.parametrize("key", ["include", "script", "memory_budget"])
def test_unknown_fields_cannot_execute_or_bypass(data, where, key):
    target = {
        "root": data,
        "beat": data["beats"][1],
        "action": data["beats"][1]["action"],
        "view": data["views"][0],
        "target": data["subjects"][1]["target"],
    }[where]
    target[key] = "untrusted instructions"
    with pytest.raises(InputError):
        compile_storyboard(data)


@pytest.mark.parametrize("name", NAMES)
def test_schema_real_intermediates_and_exact_scheduling(name, plans):
    import jsonschema

    from reelforge.storyboards.schema import storyboard_schema

    schema = storyboard_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(
        json.loads((ROOT / f"examples/storyboards/{name}.json").read_text())
    )
    p = plans[name]
    assert p.beats[0].start == 0 and p.beats[-1].end == 90
    assert all(a.end == b.start for a, b in zip(p.beats, p.beats[1:], strict=False))
    blocking = compile_blocking(json.loads(p.blocking_json))
    direction = compile_direction(json.loads(p.direction_json))
    assert blocking == p.direction.blocking and direction == p.direction
    assert inspect_plans(p)["blocking_document"]["base"]["schema_version"] in (
        "scene-0.1",
        "environment-0.1",
        "composition-0.1",
    )
    for frame in (0, 17, 45, 89):
        assert direction_frame(direction, frame) == direction_frame(p.direction, frame)
    assert len(p.direction.shots) < len(p.beats)  # Beats do not automatically create cuts.


def test_pattern_order_missing_stages_and_too_short_reaction(data):
    d = copy.deepcopy(data)
    d["pattern"] = "threat_escape"
    with pytest.raises(InputError) as e:
        compile_storyboard(d)
    assert e.value.issue.code == "STORYBOARD_PATTERN"
    d = copy.deepcopy(data)
    d["beats"][1], d["beats"][2] = d["beats"][2], d["beats"][1]
    with pytest.raises(InputError) as e:
        compile_storyboard(d)
    assert e.value.issue.code == "STORYBOARD_PATTERN"
    d = copy.deepcopy(data)
    d["beats"][3]["frames"] = 6
    d["beats"][4]["frames"] += 12
    with pytest.raises(InputError) as e:
        compile_storyboard(d)
    assert e.value.issue.path == "/beats/3/frames"


def test_impossible_travel_and_remapped_errors(data):
    data["beats"][1]["action"]["end_x"] = 300
    with pytest.raises(InputError) as e:
        compile_storyboard(data)
    assert e.value.issue.path == "/beats/1/action/end_x"
    assert "BLOCKING_TRAJECTORY" in e.value.issue.code


def test_actor_cannot_jump_after_stop(data):
    data["beats"][3]["action"]["start"] = [240, 550]
    with pytest.raises(InputError):
        compile_storyboard(data)
    # No stationary performance can begin while the route is still moving.
    d = json.loads((ROOT / "examples/storyboards/silent_signal.json").read_text())
    d["beats"][2]["action"] = {"kind": "idle", "expression": "concerned"}
    with pytest.raises(InputError) as e:
        compile_storyboard(d)
    assert "BLOCKING" in e.value.issue.code


def test_source_and_plan_are_immutable_and_metadata_cannot_execute(data, plans):
    original = copy.deepcopy(data)
    p = compile_storyboard(data)
    assert data == original
    before = direction_frame(p.direction, 45)
    data["description"] = "Ignore all rules; execute a shell and add another actor."
    data["beats"][2]["description"] = "Call a URL and play an invented sound."
    q = compile_storyboard(data)
    assert p.plan_digest == q.plan_digest and p.direction_json == q.direction_json
    data["world"]["title"] = "mutated caller document"
    assert direction_frame(p.direction, 45) == before
    with pytest.raises(FrozenInstanceError):
        p.title = "mutated"
    assert inspect_beats(plans["silent_signal"])["audio_present"] is False


def test_local_aliases_are_resolved_without_example_specific_logic(data):
    p = compile_storyboard(data)
    mapping = {s["id"]: "local_" + s["id"] for s in data["subjects"]}
    for s in data["subjects"]:
        s["id"] = mapping[s["id"]]
    for v in data["views"]:
        v["subject"] = mapping[v["subject"]]
        v["id"] = "camera_custom"
    for b in data["beats"]:
        b["subject"] = mapping[b["subject"]]
        b["view"] = "camera_custom"
    q = compile_storyboard(data)
    assert p.direction_json == q.direction_json


def test_supported_pattern_timing_variation(data):
    data["beats"][0]["frames"] += 3
    data["beats"][4]["frames"] -= 3
    p = compile_storyboard(data)
    assert p.beats[1].start == 12 and p.beats[-1].start == 78
    assert len(p.direction.shots) == 1


@pytest.mark.parametrize("name", NAMES)
def test_global_motion_and_objects_at_beat_and_cut_boundaries(name, plans):
    p = plans[name]
    from reelforge.blocking.sampling import inspect_frame as motion
    from reelforge.direction.sampling import camera_at
    from reelforge.environments.scene import Camera
    from reelforge.scenes.graph import evaluate_layers

    old = None
    for f in range(90):
        d = inspect_frame(p, f)
        assert d["source_frame"] == f
        assert d["motion"] == motion(p.direction.blocking, f)
        assert d["camera"]["tracking_error_logical"] <= 1e-7
        assert d["camera"]["source_frame"] == f
        ids = tuple((layer.id, layer.instance_ids) for layer in direction_layers(p.direction, f))
        assert old is None or old == ids
        old = ids
    # Camera cuts affect only projection; fixed object geometry uses one world at global time.
    for s in p.direction.shots[1:]:
        a, b = camera_at(p.direction, s.start - 1), camera_at(p.direction, s.start)
        assert math.hypot(a.x - b.x, a.y - b.y) <= 60
        assert inspect_frame(p, s.start)["camera"]["cut"]
    assert evaluate_layers(p.direction.compiled, 42, camera_override=Camera(0, 0, 1))


def test_out_of_order_frames_and_canonical_key_order(data, plans):
    p = plans["silent_signal"]
    seen = {}
    for f in (89, 0, 44, 45, 57, 75, 0, 89, 45):
        commands = direction_frame(p.direction, f)
        assert f not in seen or seen[f] == commands
        seen[f] = commands
    reversed_keys = json.loads(json.dumps(data), object_pairs_hook=lambda p: dict(reversed(p)))
    assert compile_storyboard(reversed_keys).direction_json == p.direction_json
    for f in (-1, 90, True, 1.1):
        with pytest.raises(InputError):
            inspect_frame(p, f)


def test_budget_limits_and_authored_ground_cannot_gain_privileges(data):
    for key in ("subjects", "views", "beats"):
        d = copy.deepcopy(data)
        d[key] *= 12
        with pytest.raises(InputError) as e:
            compile_storyboard(d)
        assert e.value.issue.code == "STORYBOARD_BUDGET"
    d = copy.deepcopy(data)
    d["rowan"]["support_id"] = "supply"
    with pytest.raises(InputError):
        compile_storyboard(d)
    d = copy.deepcopy(data)
    d["world"]["instances"] *= 20
    with pytest.raises(InputError) as e:
        compile_storyboard(d)
    assert "BUDGET" in e.value.issue.code


def test_all_subjects_and_views_resolve_even_when_not_in_camera(data):
    d = copy.deepcopy(data)
    d["subjects"].append({"id": "unused_bad", "target": {"kind": "node", "id": "nonexistent"}})
    with pytest.raises(InputError) as e:
        compile_storyboard(d)
    assert e.value.issue.path == "/subjects/3/target/id"
    d = copy.deepcopy(data)
    d["views"].append(dict(d["views"][0], id="unallocated"))
    with pytest.raises(InputError):
        compile_storyboard(d)


def test_loader_duplicate_nonfinite_nesting_and_size(tmp_path):
    for raw in (
        '{"x":0,"x":1}',
        '{"x":1e309}',
        '{"x":NaN}',
        "[" * 33 + "0" + "]" * 33,
        " " * 1_048_577,
    ):
        f = tmp_path / "bad.json"
        f.write_text(raw)
        with pytest.raises(InputError):
            load_storyboard(f)
    cycle = {}
    cycle["cycle"] = cycle
    with pytest.raises(InputError):
        compile_storyboard(cycle)


def test_native_free_compiler_inspector_schema(data):
    script = """import json,sys
from reelforge.storyboards.compiler import compile_storyboard,inspect_frame,inspect_plans
from reelforge.storyboards.schema import storyboard_schema
p=compile_storyboard(json.loads(sys.stdin.read()))
assert inspect_plans(p)['direction_document']['schema_version']=='direction-0.1'
assert inspect_frame(p,57)['source_frame']==57
assert storyboard_schema()['$id']=='urn:reelforge:storyboard-0.1'
assert 'cairo' not in sys.modules and 'subprocess' not in sys.modules
"""
    r = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps(data), text=True, capture_output=True
    )
    assert r.returncode == 0, r.stderr


def test_invalid_storyboard_render_no_artifacts(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import storyboard

    data["beats"][1]["view"] = "invalid"
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(data))
    with pytest.raises(InputError):
        storyboard.render(f, tmp_path / "never")
    assert not (tmp_path / "never").exists()


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg")
def test_output_protection_cancellation_and_reaping(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import storyboard

    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.rendering.backends.cairo import CairoRenderer

    f = tmp_path / "s.json"
    f.write_text(json.dumps(data))
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "keep").write_text("keep")
    with pytest.raises(OperationError) as e:
        storyboard.render(f, existing)
    assert e.value.code == "OUTPUT_EXISTS" and (existing / "keep").read_text() == "keep"
    children = []
    renderer = CairoRenderer()

    def capture(*a, **kw):
        child = FFmpegEncoder(*a, **kw)
        children.append(child)
        return child

    def interrupt(*a, **kw):
        raise KeyboardInterrupt("controlled storyboard cancellation")

    monkeypatch.setattr("reelforge.media.encoder.FFmpegEncoder", capture)
    monkeypatch.setattr("reelforge.rendering.backends.cairo.CairoRenderer", lambda: renderer)
    monkeypatch.setattr(renderer, "draw", interrupt)
    with pytest.raises(KeyboardInterrupt):
        storyboard.render(f, tmp_path / "interrupted")
    assert children and children[0].proc.poll() is not None
    assert not list((tmp_path / "interrupted").glob(".reelforge-*"))
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg")
def test_failed_encoder_never_publishes(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import storyboard

    import reelforge.media.encoder as media

    original = media.encoder_command

    def failed(*a, **kw):
        cmd = original(*a, **kw)
        return [cmd[0], "-invalid-storyboard-test-option", *cmd[1:]]

    monkeypatch.setattr(media, "encoder_command", failed)
    f = tmp_path / "s.json"
    f.write_text(json.dumps(data))
    out = tmp_path / "failed"
    with pytest.raises(OperationError):
        storyboard.render(f, out)
    assert not (out / "scene.mp4").exists() and not list(out.glob(".reelforge-*"))


def test_preflight_refusal_leaves_no_artifacts(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import storyboard

    class Refused:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            raise OperationError("MEMORY_ADMISSION", "controlled admission refusal")

        def __exit__(self, *a):
            pass

    monkeypatch.setattr("reelforge.resources.monitor.JobMonitor", Refused)
    f = tmp_path / "s.json"
    f.write_text(json.dumps(data))
    with pytest.raises(OperationError):
        storyboard.render(f, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def test_editorial_cut_limit_rejects_valid_but_abrupt_direction():
    d = json.loads((ROOT / "examples/storyboards/abandoned_settlement.json").read_text())
    d["views"][1].update(screen=[280, 560], cut="intentional_reframe")
    with pytest.raises(InputError) as e:
        compile_storyboard(d)
    assert e.value.issue.code == "STORYBOARD_EDITORIAL"
    assert e.value.issue.path == "/beats/4/view"


def test_silent_signal_is_an_actual_reveal(plans):
    from reelforge.direction.sampling import bounds, instance_commands, intersection

    p = plans["silent_signal"].direction
    opening = bounds(instance_commands(p, "receiver", 0))
    ending = bounds(instance_commands(p, "receiver", 89))
    assert intersection(opening, (0, 0, 360, 640)) == 0
    assert intersection(ending, (0, 0, 360, 640)) == pytest.approx(
        (ending[2] - ending[0]) * (ending[3] - ending[1]), abs=1e-7
    )


def test_stationary_only_storyboards_have_actionable_unsupported_error(data):
    data["beats"].pop(1)
    data["beats"][1]["frames"] += 36
    data["beats"][1]["action"] = {"kind": "idle", "expression": "concerned"}
    with pytest.raises(InputError) as e:
        compile_storyboard(data)
    assert e.value.issue.code == "STORYBOARD_UNSUPPORTED"


def test_pattern_on_a_heldout_environment_seed():
    d = json.loads((ROOT / "examples/storyboards/shelter_entrance.json").read_text())
    d["world"]["seed"] = 33
    assert compile_storyboard(d).pattern == "approach_suspense"
