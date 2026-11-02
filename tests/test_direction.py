"""Camera solve, cut timing, unchanged motion, bounds, determinism and renderer ownership."""

import copy
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from reelforge.blocking.sampling import inspect_frame as inspect_motion
from reelforge.core.errors import InputError, OperationError
from reelforge.direction.contract import TRACKING_TOLERANCE, compile_direction, load_direction
from reelforge.direction.sampling import (
    actor_override,
    camera_at,
    camera_state,
    direction_frame,
    direction_layers,
    inspect_frame,
    shot_at,
    target_at,
)
from reelforge.scenes.graph import evaluate_layers

ROOT = Path(__file__).resolve().parents[1]
NATIVE = importlib.util.find_spec("cairo") is not None and shutil.which("ffmpeg") is not None
NAMES = ("woodland_suspense", "settlement_escape", "shelter_discovery")


@pytest.fixture
def data():
    return json.loads((ROOT / "examples/direction/woodland_suspense.json").read_text())


@pytest.fixture(scope="module")
def plans():
    return {n: load_direction(ROOT / f"examples/direction/{n}.json") for n in NAMES}


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "direction-1.0"),
        (("title",), " "),
        (("base",), "../scene"),
        (("shots",), []),
        (("shots", 0, "start_frame"), 1),
        (("shots", 0, "end_frame"), 24.0),
        (("shots", 0, "end_frame"), 7),
        (("shots", 1, "start_frame"), 23),
        (("shots", 1, "start_frame"), 25),
        (("shots", 2, "end_frame"), 89),
        (("shots", 1, "id"), "establish"),
        (("shots", 0, "id"), "../pan"),
        (("shots", 0, "behavior"), "python"),
        (("shots", 0, "zoom"), [1, 2]),
        (("shots", 0, "zoom"), [True, 1]),
        (("shots", 0, "zoom"), [1, math.nan]),
        (("shots", 0, "offset_start"), [101, 0]),
        (("shots", 0, "screen"), [350, 500]),
        (("shots", 0, "safe_margin"), 0),
        (("shots", 0, "framing"), "auto"),
        (("shots", 0, "foreground"), "hide"),
        (("shots", 0, "continuity"), "dissolve"),
        (("shots", 0, "track"), 1),
        (("shots", 0, "track"), True),
        (("shots", 1, "track"), False),
        (("shots", 1, "look_ahead_seconds"), 0.36),
        (("shots", 0, "hold_in_frames"), 23),
        (("shots", 0, "hold_out_frames"), True),
        (("shots", 2, "target", "id"), "missing"),
        (("shots", 2, "target", "id"), "root"),
        (("shots", 1, "target", "id"), "receiver"),
        (("shots", 0, "target", "depth"), 0),
        (("shots", 0, "target", "position"), [180, math.inf]),
        (("shots", 2, "target"), {"kind": "actor", "id": "rowan"}),
    ],
)
def test_reject_invalid_and_unsupported(data, path, value):
    d = data
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value
    with pytest.raises(InputError):
        compile_direction(data)


@pytest.mark.parametrize("where", ["root", "shot", "target"])
@pytest.mark.parametrize("field", ["code", "include", "budget_mib", "expression", "gpu"])
def test_unknown_fields_reject(data, where, field):
    target = data if where == "root" else data["shots"][0]
    if where == "target":
        target = target["target"]
    target[field] = "anything"
    with pytest.raises(InputError):
        compile_direction(data)


@pytest.mark.parametrize("name", NAMES)
def test_schema_and_compiled_budget(name, plans):
    import jsonschema

    from reelforge.direction.schema import direction_schema

    schema = direction_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(
        json.loads((ROOT / f"examples/direction/{name}.json").read_text())
    )
    p = plans[name]
    assert p.compiled.path_allowance <= 4096 and p.compiled.operation_allowance <= 80000
    assert len(p.compiled.painter_ids) <= 32 and len(p.compiled.hierarchy) <= 64


@pytest.mark.parametrize("name", NAMES)
def test_tracking_matches_actual_world_with_predeclared_tolerance(name, plans):
    p = plans[name]
    for f in range(90):
        d = inspect_frame(p, f)
        assert d["source_frame"] == f and d["seconds"] == f / 30
        assert d["tracking_error_logical"] <= TRACKING_TOLERANCE
        assert d["actor_world"] == tuple(inspect_motion(p.blocking, f)["position"])
        shot = shot_at(p, f)
        if shot.track:
            motion = inspect_motion(p.blocking, f)
            assert target_at(p, shot, f)[0] == tuple(motion["position"])
            assert d["focal_world"][0] == pytest.approx(
                motion["position"][0] + motion["velocity"] * shot.look_ahead, abs=1e-9
            )


@pytest.mark.parametrize("name", NAMES)
def test_cut_selection_motion_pose_and_environment_global_time(name, plans):
    p = plans[name]
    for s in p.shots[1:]:
        assert shot_at(p, s.start - 1).id != s.id
        assert shot_at(p, s.start).id == s.id
        assert inspect_frame(p, s.start)["cut"]
        # Camera-independent character samples are exactly the accepted global-frame sample.
        from reelforge.blocking.sampling import commands

        x, local = commands(p.blocking, s.start / 30)
        override = actor_override(p, s.start)
        assert override.commands == local and override.world.x == x
        assert override.commands != commands(p.blocking, 0)[1]
        # Same frame and identical explicit camera path gives the same breeze/paint output.
        assert direction_layers(p, s.start) == evaluate_layers(
            p.compiled, s.start, character_override=override, camera_override=camera_at(p, s.start)
        )


def test_parallax_registration_and_no_double_projection(plans):
    p = plans["woodland_suspense"]
    f = 42
    c = camera_at(p, f)
    identity_layers = evaluate_layers(
        p.compiled, f, character_override=actor_override(p, f), camera_override=type(c)(0, 0, 1)
    )
    projected = direction_layers(p, f)
    for old, new in zip(identity_layers, projected, strict=True):
        t = c.transform(old.depth)
        assert old.instance_ids == new.instance_ids
        for a, b in zip(old.commands, new.commands, strict=True):
            assert b.transform.tx == pytest.approx(t.tx + t.sx * a.transform.tx, abs=1e-9)
            assert b.transform.ty == pytest.approx(t.ty + t.sy * a.transform.ty, abs=1e-9)
            assert b.transform.sx == pytest.approx(t.sx * a.transform.sx, abs=1e-12)
    actor = next(r for r in p.compiled.hierarchy if r.id == p.actor_id)
    ground = next(r for r in p.compiled.hierarchy if r.id == p.blocking.support_id)
    assert actor.depth == ground.depth
    assert c.transform(0).tx == c.transform(0).ty == 0
    assert c.transform(0.18).tx != c.transform(1.4).tx


def test_easing_holds_and_zoom(plans):
    p = plans["shelter_discovery"]
    s = p.shots[1]
    assert camera_state(p, s, s.start)[0] == camera_state(p, s, s.start + s.hold_in)[0]
    assert camera_state(p, s, s.end - 1)[0] == camera_state(p, s, s.end - 1 - s.hold_out)[0]
    values = [camera_state(p, s, f)[0].zoom for f in range(s.start, s.end)]
    assert values == sorted(values) and values[0] == s.zoom[0] and values[-1] == s.zoom[1]
    hold = p.shots[2]
    assert camera_state(p, hold, hold.start)[0] == camera_state(p, hold, hold.end - 1)[0]


def test_out_of_order_geometry_and_frame_guards(plans):
    p = plans["woodland_suspense"]
    seen = {}
    for f in [89, 0, 23, 24, 59, 60, 45, 0, 89, 24]:
        commands = direction_frame(p, f)
        assert f not in seen or commands == seen[f]
        seen[f] = commands
    for f in [-1, 90, True, 1.5]:
        with pytest.raises(InputError):
            direction_frame(p, f)


def test_reject_framing_pan_speed_continuity_and_occlusion(data):
    cases = [
        ({"screen": [16, 520]}, "DIRECTION_FRAMING"),
        ({"offset_start": [-100, 0], "offset_end": [100, 0]}, "DIRECTION_SPEED"),
    ]
    for change, code in cases:
        d = copy.deepcopy(data)
        d["shots"][1].update(change)
        with pytest.raises(InputError) as e:
            compile_direction(d)
        assert e.value.issue.code == code
    d = copy.deepcopy(data)
    d["shots"][1].update(continuity="matched", screen=[240, 550])
    with pytest.raises(InputError) as e:
        compile_direction(d)
    assert e.value.issue.code == "DIRECTION_CONTINUITY"
    d = copy.deepcopy(data)
    d["shots"][0]["target"]["depth"] = 0.18
    d["shots"][0]["screen"] = [340, 520]
    with pytest.raises(InputError) as e:
        compile_direction(d)
    assert e.value.issue.code == "DIRECTION_CAMERA"


def test_declared_crop_and_unreadable_object(data, plans):
    d = copy.deepcopy(data)
    d["shots"][0].update(screen=[180, 624], framing="full")
    with pytest.raises(InputError):
        compile_direction(d)
    d["shots"][0]["framing"] = "feet_crop"
    # Width/head remain protected; foot crop is an explicit narrow exception.
    assert compile_direction(d)
    d = copy.deepcopy(data)
    d["shots"][2].update(
        offset_start=[100, 100], offset_end=[100, 100], screen=[16, 520], framing="offscreen"
    )
    with pytest.raises(InputError) as e:
        compile_direction(d)
    assert e.value.issue.code in ("DIRECTION_FRAMING", "DIRECTION_CAMERA")
    assert plans["settlement_escape"].shots[-1].framing == "offscreen"


@pytest.mark.parametrize("kind", ["scene", "environment", "composition"])
def test_other_accepted_bases_and_original_documents_unchanged(data, kind):
    d = copy.deepcopy(data)
    if kind == "scene":
        d["base"] = json.loads((ROOT / "examples/scenes/rural_outpost.json").read_text())
    else:
        d["base"] = data["base"]["base"] if kind == "composition" else data["base"]["base"]["base"]
    d["shots"] = [dict(d["shots"][0], end_frame=90, framing="offscreen")]
    before = copy.deepcopy(d)
    assert compile_direction(d)
    assert d == before


def test_native_free_schema_inspection_and_strict_loader(tmp_path, data):
    script = """import json,sys
from reelforge.direction.contract import compile_direction
from reelforge.direction.sampling import inspect_frame
from reelforge.direction.schema import direction_schema
p=compile_direction(json.loads(sys.stdin.read()));print(json.dumps(inspect_frame(p,45)))
assert 'cairo' not in sys.modules and 'subprocess' not in sys.modules
assert direction_schema()['$id']=='urn:reelforge:direction-0.1'
"""
    r = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps(data), capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    f = tmp_path / "bad.json"
    f.write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(InputError):
        load_direction(f)


def test_invalid_render_has_no_artifacts(tmp_path, monkeypatch, data):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import direction

    d = copy.deepcopy(data)
    d["shots"][0]["zoom"] = [1, 8]
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(d))
    with pytest.raises(InputError):
        direction.render(f, tmp_path / "never")
    assert not (tmp_path / "never").exists()


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg")
def test_direction_output_protection_cancel_reaping_and_cleanup(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import direction

    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.rendering.backends.cairo import CairoRenderer

    f = tmp_path / "d.json"
    f.write_text(json.dumps(data))
    out = tmp_path / "existing"
    out.mkdir()
    (out / "keep").write_bytes(b"keep")
    with pytest.raises(OperationError) as e:
        direction.render(f, out)
    assert e.value.code == "OUTPUT_EXISTS" and (out / "keep").read_bytes() == b"keep"
    children, renderer = [], CairoRenderer()

    def capture(*a, **kw):
        c = FFmpegEncoder(*a, **kw)
        children.append(c)
        return c

    def interrupt(*a, **kw):
        raise KeyboardInterrupt("controlled direction interruption")

    monkeypatch.setattr("reelforge.media.encoder.FFmpegEncoder", capture)
    monkeypatch.setattr("reelforge.rendering.backends.cairo.CairoRenderer", lambda: renderer)
    monkeypatch.setattr(renderer, "draw", interrupt)
    with pytest.raises(KeyboardInterrupt):
        direction.render(f, tmp_path / "cancelled")
    assert children and children[0].proc.poll() is not None
    assert not list((tmp_path / "cancelled").glob(".reelforge-*"))
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_foreground_rejection_and_geometry_envelope(plans, monkeypatch):
    from reelforge.direction.sampling import validate_safety

    p = plans["woodland_suspense"]
    strict = replace(p, shots=tuple(replace(s, foreground="clear") for s in p.shots))
    import reelforge.direction.sampling as sampling

    original = sampling.inspect_frame

    def occluded(*args):
        return dict(original(*args), foreground_bbox_overlap_upper=1.0)

    with monkeypatch.context() as m:
        m.setattr(sampling, "inspect_frame", occluded)
        with pytest.raises(InputError) as e:
            validate_safety(strict)
        assert e.value.issue.code == "DIRECTION_OCCLUSION"
    from reelforge.scenes.assets import cost

    for f in (0, 24, 60, 89):
        paths, ops = cost(direction_frame(p, f))
        assert paths <= p.compiled.path_allowance and ops <= p.compiled.operation_allowance


@pytest.mark.skipif(not NATIVE, reason="optional Cairo/FFmpeg")
def test_failed_encoder_does_not_publish(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import direction

    import reelforge.media.encoder as media

    original = media.encoder_command

    def failed(*a, **kw):
        command = original(*a, **kw)
        return [command[0], "-invalid-direction-test-option", *command[1:]]

    monkeypatch.setattr(media, "encoder_command", failed)
    f = tmp_path / "d.json"
    f.write_text(json.dumps(data))
    out = tmp_path / "failed"
    with pytest.raises(OperationError):
        direction.render(f, out)
    assert not (out / "scene.mp4").exists() and not list(out.glob(".reelforge-*"))


def test_resource_preflight_leaves_no_artifacts(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import direction

    class Refused:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            raise OperationError("MEMORY_ADMISSION", "controlled direction preflight refusal")

        def __exit__(self, *a):
            pass

    monkeypatch.setattr("reelforge.resources.monitor.JobMonitor", Refused)
    f = tmp_path / "d.json"
    f.write_text(json.dumps(data))
    with pytest.raises(OperationError) as e:
        direction.render(f, tmp_path / "refused")
    assert e.value.code == "MEMORY_ADMISSION" and not (tmp_path / "refused").exists()


def test_oversized_shots_and_behavior_constraints(data):
    d = copy.deepcopy(data)
    d["shots"] *= 3
    with pytest.raises(InputError):
        compile_direction(d)
    for changes in [
        dict(behavior="push_in"),
        dict(behavior="reaction"),
        dict(behavior="suspense_hold", offset_end=[1, 0]),
    ]:
        d = copy.deepcopy(data)
        d["shots"][0].update(changes)
        with pytest.raises(InputError):
            compile_direction(d)
