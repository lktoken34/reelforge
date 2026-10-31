"""Rig/agent/locomotion contracts independent of the optional native Cairo backend."""

import json
import math
from dataclasses import asdict, replace
from importlib.resources import files

import pytest
from jsonschema import Draft202012Validator

from reelforge.characters.presets import (
    SKELETON,
    CharacterPreset,
    blend,
    foot_target,
    load_preset,
    sample_pose,
)
from reelforge.characters.rig import Joint, Pose, Rigid, Skeleton, two_bone
from reelforge.characters.rowan import PARTS, draw_character
from reelforge.characters.study import character_frame, demo_pose
from reelforge.core.errors import InputError
from reelforge.rendering.model import RenderError


def test_configurable_pivots_and_parent_transforms():
    skeleton = Skeleton(
        (Joint("root", None, pivot=(3, 2)), Joint("child", "root", (10, 5), (2, -3)))
    )
    pose = Pose(Rigid(40, 30, 0.4), (("root", 0.6), ("child", -0.9)))
    worlds = skeleton.evaluate(pose)
    assert worlds["root"].point((3, 2)) == pytest.approx((40, 30))
    assert worlds["child"].point((2, -3)) == pytest.approx(worlds["root"].point((10, 5)))
    assert worlds["child"].angle == pytest.approx(0.1)
    assert blend(Pose(Rigid(angle=0.2)), Pose(Rigid(angle=1.2)), 0.5).root.angle == pytest.approx(
        0.7
    )


@pytest.mark.parametrize(
    "joints",
    [
        (Joint("a", None), Joint("a", "a")),
        (Joint("a", None), Joint("b", "missing")),
        (Joint("a", None), Joint("b", None)),
        (Joint("a", "b"), Joint("b", "a")),
    ],
)
def test_invalid_hierarchy_rejected(joints):
    with pytest.raises(RenderError):
        Skeleton(joints)


@pytest.mark.parametrize("action", ("idle", "walk", "run"))
@pytest.mark.parametrize("speed", (0.5, 1, 1.5))
def test_every_joint_stays_attached_and_evaluation_is_order_independent(action, speed):
    preset = CharacterPreset(action=action, speed=speed)
    for frame in (60, 1, 130, 29, 0, 149):
        pose = sample_pose(preset, frame / 30)
        assert pose == sample_pose(preset, frame / 30)
        worlds = SKELETON.evaluate(pose)
        for joint in SKELETON.joints[1:]:
            assert worlds[joint.name].point(joint.pivot) == pytest.approx(
                worlds[joint.parent].point(joint.attachment)
            )


@pytest.mark.parametrize(
    "action,cycle,stride,duty", [("walk", 0.95, 64, 0.62), ("run", 0.6, 164, 0.38)]
)
@pytest.mark.parametrize("speed,intensity", [(0.5, 0.5), (1, 1), (1.5, 1)])
def test_grounded_stance_has_no_world_foot_sliding(action, cycle, stride, duty, speed, intensity):
    preset = CharacterPreset(action=action, speed=speed, intensity=intensity)
    points = []
    for phase in (0.08, 0.18, 0.28):
        pose = sample_pose(preset, phase * cycle / speed)
        foot = SKELETON.evaluate(pose)["near_foot"]
        sole = foot.point((0, 10))
        assert sole[1] == pytest.approx(0, abs=1e-10)
        points.append(sole[0])
    assert max(points) - min(points) < 1e-10
    assert points[0] == pytest.approx(7 + stride * intensity * duty / 2)


@pytest.mark.parametrize("action,duty", [("walk", 0.62), ("run", 0.38)])
def test_contact_wrap_and_toe_off_are_continuous(action, duty):
    for boundary in (duty, 1):
        a = foot_target(action, (boundary - 1e-7) % 1)
        b = foot_target(action, (boundary + 1e-7) % 1)
        assert abs(a[0] - b[0]) < 0.001 and abs(a[1] - b[1]) < 0.001
    preset = CharacterPreset(action=action)
    cycle = 0.95 if action == "walk" else 0.6
    a = dict(sample_pose(preset, (duty - 1e-7) * cycle).angles)
    b = dict(sample_pose(preset, (duty + 1e-7) * cycle).angles)
    assert max(abs(a[k] - b[k]) for k in a) < 0.001


def test_motion_envelopes_and_reach_over_full_parameter_range():
    for action in ("idle", "walk", "run"):
        for intensity in (0.5, 1):
            for index in range(240):
                pose = sample_pose(CharacterPreset(action=action, intensity=intensity), index / 120)
                worlds = SKELETON.evaluate(pose)
                assert all(math.isfinite(w.x + w.y + w.angle) for w in worlds.values())
    run = dict(sample_pose(CharacterPreset(action="run"), 0.1).angles)
    walk = dict(sample_pose(CharacterPreset(action="walk"), 0.1).angles)
    assert abs(run["torso"]) > abs(walk["torso"])
    assert abs(run["near_forearm"]) > abs(walk["near_forearm"])
    idle1 = sample_pose(CharacterPreset(), 0)
    idle2 = sample_pose(CharacterPreset(), 0.7)
    assert 0 < abs(idle1.root.y - idle2.root.y) < 1


def test_ik_forward_endpoint():
    a, b = two_bone(17, 68, 42, 45)
    thigh = Rigid(angle=a)
    shin = thigh.compose(Rigid(0, 42, b))
    assert shin.point((0, 45)) == pytest.approx((17, 68))
    with pytest.raises(RenderError):
        two_bone(0, 100, 42, 45)


@pytest.mark.parametrize(
    "field,value",
    [
        ("speed", True),
        ("speed", float("nan")),
        ("speed", float("inf")),
        ("speed", 1e309),
        ("speed", 0.49),
        ("speed", 1.51),
        ("intensity", 1.01),
        ("intensity", 0),
        ("action", "eval"),
        ("character", "../../file"),
        ("direction", "north"),
        ("expression", "evil"),
    ],
)
def test_preset_values_reject_unsupported_data(field, value):
    data = asdict(CharacterPreset())
    data[field] = value
    with pytest.raises(RenderError):
        CharacterPreset.from_data(data)


def test_contract_and_example_match_and_reject_unknown_fields():
    schema = json.loads(files("reelforge.characters").joinpath("preset.schema.json").read_text())
    validator = Draft202012Validator(schema)
    data = asdict(CharacterPreset(action="walk"))
    validator.validate(data)
    from reelforge.characters.rowan import preset_commands

    right = preset_commands(data, 30)
    left = preset_commands({**data, "direction": "left"}, 30)
    assert [c.path for c in right] == [c.path for c in left]
    assert right[0].transform.tx + left[0].transform.tx == pytest.approx(360)
    with pytest.raises(RenderError):
        preset_commands(data, True)
    assert CharacterPreset.from_data(data).action == "walk"
    for bad in ({**data, "joints": {}}, {k: v for k, v in data.items() if k != "speed"}):
        assert list(validator.iter_errors(bad))
        with pytest.raises(RenderError):
            CharacterPreset.from_data(bad)


@pytest.mark.parametrize("raw", ['{"speed":1,"speed":2}', '{"speed":1e309}', '{"speed":NaN}'])
def test_preset_loading_reuses_strict_json_rejection(tmp_path, raw):
    p = tmp_path / "preset.json"
    p.write_text(raw)
    with pytest.raises(InputError):
        load_preset(p)


def test_same_artwork_is_reused_and_mirrors_without_reauthoring():
    pose = sample_pose(CharacterPreset(), 0, travel=False)
    right = draw_character(pose)
    left = draw_character(pose, direction="left")
    assert len(right) == len(left)
    for a, b in zip(right, left, strict=True):
        assert a.path is b.path or a.path == b.path
        assert a.transform.tx + b.transform.tx == pytest.approx(360)
        assert a.transform.rotation == -b.transform.rotation
    assert {p.joint for p in PARTS} <= {j.name for j in SKELETON.joints}
    assert [p.order for p in PARTS] == sorted(p.order for p in PARTS)
    from reelforge.rendering.model import Color

    alternate = (
        replace(
            PARTS[0],
            commands=(replace(PARTS[0].commands[0], fill=Color(1, 0, 0)), *PARTS[0].commands[1:]),
        ),
        *PARTS[1:],
    )
    changed = draw_character(pose, artwork=alternate)
    assert changed[0].fill != right[0].fill
    assert [c.transform for c in changed] == [c.transform for c in right]


def test_demo_bounds_transitions_and_determinism():
    previous = None
    for frame in range(150):
        pose, travel = demo_pose(frame)
        assert (pose, travel) == demo_pose(frame)
        assert len(character_frame(frame)) < 600
        worlds = SKELETON.evaluate(pose)
        # Fixed chapter blends allow <1 logical unit (2.64px) of sole overshoot.
        assert (
            max(
                worlds[s + "_foot"].point(p)[1]
                for s in ("near", "far")
                for p in ((-8, 10), (19, 10))
            )
            < 1
        )
        if previous:
            a, b = dict(previous.angles), dict(pose.angles)
            assert max(abs(a[k] - b[k]) for k in a) < 1.2
        previous = pose
    for invalid in (-1, 150, True):
        with pytest.raises(RenderError):
            demo_pose(invalid)


def test_unknown_and_duplicate_pose_angles_rejected():
    for angles in ((("unknown", 0),), (("head", 0), ("head", 1))):
        with pytest.raises(RenderError):
            SKELETON.evaluate(Pose(angles=angles))


def test_actual_character_pixels_repeat_and_expression_changes():
    pytest.importorskip("cairo")
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    renderer = CairoRenderer()
    hashes = []
    pose = sample_pose(CharacterPreset(), 0.3, travel=False)
    with renderer.surface(360, 640) as surface:
        for expression in ("concerned", "calm", "concerned"):
            renderer.draw(
                surface,
                draw_character(pose, expression=expression),
                background=color("ece6d5"),
                logical_size=(360, 640),
            )
            hashes.append(surface.pixel_sha256())
    assert hashes[0] == hashes[2] and hashes[0] != hashes[1]
    assert renderer.allocated_bytes == renderer.active_surfaces == 0
