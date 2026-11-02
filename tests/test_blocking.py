"""Continuous trajectory, clock/contact invariants and safe blocking integration."""

import copy
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from threading import Event

import pytest

from reelforge.blocking.contract import compile_blocking, load_blocking
from reelforge.blocking.sampling import blocking_frame, inspect_frame, sample
from reelforge.core.errors import InputError, OperationError

ROOT = Path(__file__).resolve().parents[1]
NATIVE = importlib.util.find_spec("cairo") is not None and shutil.which("ffmpeg") is not None


@pytest.fixture
def data():
    return json.loads((ROOT / "examples/blocking/woodland_traversal.json").read_text())


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "blocking-9"),
        (("actor_id",), "unknown"),
        (("support_id",), "relay"),
        (("corridor",), "pathfinding"),
        (("camera",), "auto"),
        (("start", "position"), [0, 550]),
        (("start", "position"), [140, math.inf]),
        (("start", "position"), [True, 550]),
        (("start", "facing"), "up"),
        (("segments", 0, "start_frame"), 1),
        (("segments", 0, "end_frame"), 9.0),
        (("segments", 0, "id"), "../x"),
        (("segments", 0, "end_speed"), 1),
        (("segments", 1, "start_frame"), 8),
        (("segments", 1, "start_frame"), 10),
        (("segments", 1, "mode"), "jump"),
        (("segments", 1, "destination"), [180, 551]),
        (("segments", 1, "end_speed"), math.nan),
        (("segments", 1, "end_speed"), True),
        (("segments", 1, "end_speed"), 90),
        (("segments", 1, "facing"), "left"),
        (("segments", 1, "acting"), "react"),
        (("segments", 1, "expression"), "invented"),
        (("segments", 2, "end_speed"), 5),
        (("segments", 3, "destination"), [200, 550]),
        (("segments", 3, "end_frame"), 89),
    ],
)
def test_invalid_contract_and_conflicts(data, path, value):
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InputError) as e:
        compile_blocking(data)
    assert e.value.issue.code.startswith(("BLOCKING", "SCENE", "ENVIRONMENT", "GEOMETRY"))


@pytest.mark.parametrize("where", ["root", "start", "segment"])
@pytest.mark.parametrize(
    "key", ["python", "route_code", "gpu", "memory_budget", "include", "heightfield"]
)
def test_unknown_fields_cannot_execute_or_override_policy(data, where, key):
    target = data if where == "root" else data["start"] if where == "start" else data["segments"][1]
    target[key] = '__import__("os").system("anything")'
    with pytest.raises(InputError):
        compile_blocking(data)


def test_duplicates_limits_and_unannounced_stop(data):
    d = copy.deepcopy(data)
    d["segments"][1]["id"] = d["segments"][0]["id"]
    with pytest.raises(InputError):
        compile_blocking(d)
    d = copy.deepcopy(data)
    d["segments"] = d["segments"] * 4
    with pytest.raises(InputError):
        compile_blocking(d)
    d = copy.deepcopy(data)
    d["segments"][2]["mode"] = "idle"
    with pytest.raises(InputError):
        compile_blocking(d)


def test_reject_interior_overshoot_acceleration_and_bad_turns(data):
    d = copy.deepcopy(data)
    d["segments"][1]["destination"][0] = 140.1
    with pytest.raises(InputError) as e:
        compile_blocking(d)
    assert e.value.issue.code == "BLOCKING_TRAJECTORY"
    d = copy.deepcopy(data)
    d["segments"][1]["destination"][0] = 300
    with pytest.raises(InputError):
        compile_blocking(d)
    d = copy.deepcopy(data)
    d["segments"][3].update(mode="turn", facing="right")
    with pytest.raises(InputError):
        compile_blocking(d)


@pytest.mark.parametrize("name", ["woodland_traversal", "settlement_escape", "shelter_approach"])
def test_schema_examples_and_timeline(name):
    import jsonschema

    from reelforge.blocking.schema import blocking_schema

    d = json.loads((ROOT / f"examples/blocking/{name}.json").read_text())
    jsonschema.Draft202012Validator(blocking_schema()).validate(d)
    p = compile_blocking(d)
    assert p.segments[0].start == 0 and p.segments[-1].end == 90
    assert all(a.end == b.start for a, b in zip(p.segments, p.segments[1:], strict=False))
    assert p.compiled.path_allowance <= 4096 and p.compiled.operation_allowance <= 80000


@pytest.mark.parametrize("name", ["woodland_traversal", "settlement_escape", "shelter_approach"])
def test_continuous_position_velocity_pose_and_phase(name):
    p = load_blocking(ROOT / f"examples/blocking/{name}.json")
    eps = 1e-6
    for a, b in zip(p.segments, p.segments[1:], strict=False):
        assert a.position(a.end / 30) == pytest.approx(b.position(b.start / 30), abs=1e-10)
        assert a.velocity(a.end / 30) == pytest.approx(b.velocity(b.start / 30), abs=1e-10)
        t = b.start / 30
        pa = sample(p, t - eps)[2]
        pb = sample(p, t + eps)[2]
        assert math.hypot(pa.root.x - pb.root.x, pa.root.y - pb.root.y) < 0.005
        assert max(abs(dict(pa.angles).get(k, 0) - v) for k, v in pb.angles) < 0.001
    for c in p.clocks:
        for i in range(1, 20):
            t = c.start + (c.end - c.start) * i / 20
            derivative = (c.cycles(t + eps) - c.cycles(t - eps)) / (2 * eps)
            assert derivative == pytest.approx(
                c.speed(t) * c.inverse_stride(t) * c.factor, abs=2e-5
            )
            assert (c.distance(t + 1e-7) - c.distance(t - 1e-7)) / (2e-7) == pytest.approx(
                c.speed(t), abs=2e-5
            )
        assert 0.7 <= c.factor <= 1.3
        if c.stopped:
            assert c.total_cycles % 1 == pytest.approx(0.56, abs=1e-9)


@pytest.mark.parametrize("name", ["woodland_traversal", "settlement_escape", "shelter_approach"])
def test_planted_foot_world_and_camera_compensated_contact(name):
    p = load_blocking(ROOT / f"examples/blocking/{name}.json")
    anchors = {}
    for frame in range(90):
        d = inspect_frame(p, frame)
        for foot in d["contacts"]:
            if foot["error"] is None:
                continue
            assert foot["error"] < 1e-7
            assert math.dist(foot["screen"], foot["expected_screen"]) < 1e-7
            if d["mode"] == "turn":
                continue
            key = (d["facing"], foot["side"], foot["cycle_start"], foot["state"])
            if key in anchors:
                assert math.dist(foot["world"], anchors[key]) < 1e-7
            anchors[key] = foot["world"]
    assert anchors


def test_stops_hold_both_feet_and_turn_is_stationary():
    p = load_blocking(ROOT / "examples/blocking/shelter_approach.json")
    for f in range(66, 90):
        d = inspect_frame(p, f)
        assert d["position"] == [210, 470] and abs(d["velocity"]) < 1e-10
        assert all(c["state"] == "flat" for c in d["contacts"])
        assert sorted(round(c["world"][0], 8) for c in d["contacts"]) == [205.77, 214.23]


def test_out_of_order_evaluation_has_identical_geometry(data):
    p = compile_blocking(data)
    seen = {}
    for f in (89, 0, 45, 65, 66, 9, 8, 89, 0, 45):
        commands = blocking_frame(p, f)
        assert f not in seen or seen[f] == commands
        seen[f] = commands
    with pytest.raises(InputError):
        inspect_frame(p, 90)


def test_native_free_inspector_and_duplicate_json(tmp_path, data):
    f = tmp_path / "input.json"
    f.write_text('{"x":0,"x":1}')
    with pytest.raises(InputError):
        load_blocking(f)
    script = """import json,sys
from reelforge.blocking.contract import compile_blocking
from reelforge.blocking.sampling import inspect_frame
p=compile_blocking(json.loads(sys.stdin.read()));print(json.dumps(inspect_frame(p,45)))
assert 'cairo' not in sys.modules
assert 'subprocess' not in sys.modules
"""
    r = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps(data), capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr


def test_decorative_geometry_and_wrong_parallax_cannot_support(data):
    d = copy.deepcopy(data)
    d["support_id"] = "supply"
    with pytest.raises(InputError):
        compile_blocking(d)
    # Endpoint centers fit this injected plane, while the boot sweep does not.
    from dataclasses import replace

    from reelforge.blocking.sampling import validate_contacts

    plan = compile_blocking(data)
    with pytest.raises(InputError) as e:
        validate_contacts(replace(plan, support=(140, 435, 187, 640)))
    assert e.value.issue.code == "BLOCKING_SUPPORT"


def test_legacy_scene_base_and_changed_direction_route(data):
    d = copy.deepcopy(data)
    d["base"] = json.loads((ROOT / "examples/scenes/rural_outpost.json").read_text())
    actor = next(n for n in d["base"]["nodes"] if n["kind"] == "character")
    actor["transform"]["scale"] = 0.47
    d["actor_id"] = actor["id"]
    d["support_id"] = actor["ground_id"]
    d["camera"] = "locked"
    assert compile_blocking(d)
    d = copy.deepcopy(data)
    d["start"].update(position=[230, 550], facing="left")
    for s in d["segments"]:
        s["destination"][0] = 370 - s["destination"][0]
        s["facing"] = "left"
    assert compile_blocking(d)


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg integration")
def test_output_protection_cancellation_and_encoder_cleanup(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import blocking as tool

    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.rendering.backends.cairo import CairoRenderer

    f = tmp_path / "motion.json"
    f.write_text(json.dumps(data))
    out = tmp_path / "existing"
    out.mkdir()
    (out / "keep").write_bytes(b"keep")
    with pytest.raises(OperationError) as e:
        tool.render(f, out)
    assert e.value.code == "OUTPUT_EXISTS" and (out / "keep").read_bytes() == b"keep"
    children = []
    renderer = CairoRenderer()

    def capture(*a, **kw):
        child = FFmpegEncoder(*a, **kw)
        children.append(child)
        return child

    def interrupted(*a, **kw):
        raise KeyboardInterrupt("controlled blocking interruption")

    monkeypatch.setattr("reelforge.media.encoder.FFmpegEncoder", capture)
    monkeypatch.setattr("reelforge.rendering.backends.cairo.CairoRenderer", lambda: renderer)
    monkeypatch.setattr(renderer, "draw", interrupted)
    with pytest.raises(KeyboardInterrupt):
        tool.render(f, tmp_path / "interrupted")
    assert children[0].proc.poll() is not None and not list(
        (tmp_path / "interrupted").glob(".reelforge-*")
    )
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_invalid_routes_leave_no_artifacts(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import blocking as tool

    data["segments"][1]["destination"][1] = 600
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(data))
    with pytest.raises(InputError):
        tool.render(f, tmp_path / "never" / "out")
    assert not (tmp_path / "never").exists()


def test_reversal_after_stop_and_turn_has_no_teleport(data):
    d = copy.deepcopy(data)
    template = d["segments"][1]

    def seg(name, a, b, mode, x, speed, facing):
        return dict(
            template,
            id=name,
            start_frame=a,
            end_frame=b,
            mode=mode,
            destination=[x, 550],
            end_speed=speed,
            facing=facing,
            acting="look_around" if mode == "turn" else "none",
        )

    d["segments"] = [
        seg("out", 0, 27, "walk", 168.5, 40, "right"),
        seg("stop_a", 27, 39, "stop", 176.5, 0, "right"),
        seg("turn", 39, 51, "turn", 176.5, 0, "left"),
        seg("back", 51, 78, "walk", 148, 40, "left"),
        seg("stop_b", 78, 90, "stop", 140, 0, "left"),
    ]
    p = compile_blocking(d)
    assert len(p.clocks) == 2
    for c in p.clocks:
        assert c.total_cycles >= 1.56
    assert sample(p, 3.0)[5] == pytest.approx(140)


def test_running_stop_uses_calibrated_double_support():
    d = json.loads((ROOT / "examples/blocking/settlement_escape.json").read_text())
    d["camera"] = "locked"
    d["segments"][2].update(end_frame=72, destination=[252, 550])
    d["segments"].append(
        dict(
            d["segments"][2],
            id="stop",
            start_frame=72,
            end_frame=90,
            mode="stop",
            destination=[276, 550],
            end_speed=0,
        )
    )
    p = compile_blocking(d)
    assert all(f.state == "flat" for f in sample(p, 3.0)[3])


def test_turn_ground_contact_set_and_justified_label_exchange():
    p = load_blocking(ROOT / "examples/blocking/shelter_approach.json")
    for f in range(66, 84):
        d = inspect_frame(p, f)
        assert d["turn_contact_set_error_world"] < 1e-7
        # +/-9 rig-unit idle footprint; mirroring exchanges near/far depth labels.
        assert d["turn_side_label_exchange_world"] == pytest.approx(18 * p.scale, abs=1e-7)


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg")
def test_ffmpeg_failure_does_not_publish_or_leak(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import blocking as tool

    import reelforge.media.encoder as media

    original = media.encoder_command

    def fail(*a, **kw):
        command = original(*a, **kw)
        return [command[0], "-invalid-blocking-test-option", *command[1:]]

    monkeypatch.setattr(media, "encoder_command", fail)
    f = tmp_path / "b.json"
    f.write_text(json.dumps(data))
    out = tmp_path / "failure"
    with pytest.raises(OperationError):
        tool.render(f, out)
    assert not (out / "scene.mp4").exists() and not list(out.glob(".reelforge-*"))


def test_resource_cancel_rejects_before_frame_allocation(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import blocking as tool

    class Cancel:
        def __init__(self, **kw):
            self.cancelled = Event()
            self.cancelled.set()

        def __enter__(self):
            raise OperationError("BLOCKING_RESOURCE", "controlled preflight cancellation")

        def __exit__(self, *a):
            pass

    monkeypatch.setattr("reelforge.resources.monitor.JobMonitor", Cancel)
    f = tmp_path / "b.json"
    f.write_text(json.dumps(data))
    with pytest.raises(OperationError):
        tool.render(f, tmp_path / "cancelled")
    assert not (tmp_path / "cancelled").exists()
