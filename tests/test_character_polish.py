"""Contact, follow-through and acting regressions; no artwork approval is inferred."""

import json
import math
from dataclasses import asdict
from importlib.resources import files

import pytest
from jsonschema import Draft202012Validator

from reelforge.characters.contact import FootPlacement, foot_roll
from reelforge.characters.presets import (
    ACTIONS,
    EXPRESSIONS,
    SKELETON,
    CharacterPreset,
    sample_pose,
)
from reelforge.characters.rowan import BAG_PIVOT, face, preset_commands, strap
from reelforge.characters.secondary import SecondaryMotion, around, preset_secondary
from reelforge.characters.transition import (
    CLOCK,
    contact_targets,
    transition_pose,
    transition_secondary,
)
from reelforge.rendering.model import RenderError


@pytest.mark.parametrize("action", ("idle", "walk", "run", "look_around", "react"))
@pytest.mark.parametrize("speed", (0.5, 1, 1.5))
def test_hierarchy_and_no_floor_penetration(action, speed):
    for i in range(121):
        preset = CharacterPreset(action=action, speed=speed)
        pose = sample_pose(preset, i / 60)
        worlds = SKELETON.evaluate(pose)
        for joint in SKELETON.joints[1:]:
            assert worlds[joint.name].point(joint.pivot) == pytest.approx(
                worlds[joint.parent].point(joint.attachment)
            )
        for side in ("near", "far"):
            assert max(worlds[side + "_foot"].point(p)[1] for p in ((-8, 10), (19, 10))) < 1e-8


@pytest.mark.parametrize("action,cycle,duty", [("walk", 0.95, 0.62), ("run", 0.60, 0.38)])
def test_heel_and_toe_are_stationary_during_roll(action, cycle, duty):
    for phases, pivot in (((0.01, 0.02, 0.03), -8), ((duty - 0.04, duty - 0.03, duty - 0.02), 19)):
        points = []
        for phase in phases:
            pose = sample_pose(CharacterPreset(action=action), phase * cycle)
            sole = SKELETON.evaluate(pose)["near_foot"].point((pivot, 10))
            assert sole[1] == pytest.approx(0, abs=1e-9)
            points.append(sole[0])
        assert max(points) - min(points) < 1e-8


def test_contact_controller_locks_world_anchors_through_both_transitions():
    max_error = 0
    for i in range(1001):
        t = i / 200
        pose, distance = transition_pose(t)
        worlds = SKELETON.evaluate(pose)
        for side, target in zip(("near", "far"), contact_targets(t), strict=True):
            if target.state != "swing":
                point = worlds[side + "_foot"].point((target.pivot_x, 10))
                max_error = max(
                    max_error, abs(point[0] + distance - target.x - target.pivot_x), abs(point[1])
                )
    assert max_error < 1e-8


def test_transition_has_no_resets_and_dense_continuity():
    last = None
    for i in range(601):
        t = i / 120
        pose, distance = transition_pose(t)
        assert pose == transition_pose(t)[0]
        if last:
            before, d = last
            assert distance >= d
            assert math.hypot(pose.root.x - before.root.x, pose.root.y - before.root.y) < 2
            aa, bb = dict(before.angles), dict(pose.angles)
            assert max(abs(aa[k] - bb[k]) for k in aa) < 0.3
        last = pose, distance
    for t in (0.85, 1.15, 2.85, 3.15):
        left = transition_pose(t - 1e-6)[0]
        right = transition_pose(t + 1e-6)[0]
        assert abs(left.root.y - right.root.y) < 0.001
        assert (
            max(abs(dict(left.angles)[k] - dict(right.angles)[k]) for k in dict(left.angles))
            < 0.001
        )


def test_same_shot_camera_distance_is_preserved():
    from reelforge.characters.study import integral_step

    for i in range(150):
        t = i / 30
        original = 64 / 0.95 * integral_step(t, 0.85, 0.3) + (
            164 / 0.6 - 64 / 0.95
        ) * integral_step(t, 2.85, 0.3)
        assert CLOCK.distance(t) == pytest.approx(original)


def test_phase_inverse_is_consistent():
    for phase in (0.01, 0.12, 0.5, 1, 2, 4, 10):
        assert CLOCK.cycles(CLOCK.time_at(phase)) == pytest.approx(phase, abs=1e-10)


@pytest.mark.parametrize("action", ACTIONS)
def test_secondary_is_deterministic_bounded_and_attached(action):
    preset = CharacterPreset(action=action)
    seen = set()
    for i in (120, 1, 40, 0, 80):
        state = preset_secondary(preset, i / 30)
        assert state == preset_secondary(preset, i / 30)
        seen.add(state)
        assert abs(state.bag_angle) <= 0.14 and abs(state.hat_angle) <= 0.055
        pose = sample_pose(preset, i / 30, travel=False)
        t = SKELETON.evaluate(pose)["torso"]
        bag = t.compose(around(BAG_PIVOT, state.bag_angle, state.bag_y))
        # The ribbon endpoint is generated from the same moving bag anchor as its artwork.
        anchor = around(BAG_PIVOT, state.bag_angle, state.bag_y).point((-23, -22))
        assert t.point(anchor) == pytest.approx(bag.point((-23, -22)))
        commands = strap(state)
        assert commands[0].path[1].points[-2:] == pytest.approx(anchor)
    assert len(seen) > 1


def test_secondary_across_transitions_is_continuous():
    for t in (0.85, 1.15, 2.85, 3.15):
        a, b = transition_secondary(t - 1e-6), transition_secondary(t + 1e-6)
        assert max(abs(asdict(a)[k] - asdict(b)[k]) for k in asdict(a)) < 0.001


@pytest.mark.parametrize("expression", EXPRESSIONS)
def test_schema_and_old_fields_accept_closed_expression_menu(expression):
    data = asdict(CharacterPreset(expression=expression))
    schema = json.loads(files("reelforge.characters").joinpath("preset.schema.json").read_text())
    Draft202012Validator(schema).validate(data)
    assert len(data) == 6
    assert CharacterPreset.from_data(data).expression == expression
    assert face(expression, False) == face(expression, False)
    with pytest.raises(RenderError):
        CharacterPreset.from_data({**data, "bag_angle": 0.2})


@pytest.mark.parametrize(
    "params", [{"bag_angle": 0.15}, {"hat_y": 1.01}, {"gaze": True}, {"gaze": float("nan")}]
)
def test_secondary_not_arbitrary_unbounded_controls(params):
    with pytest.raises(RenderError):
        SecondaryMotion(**params)


def test_roll_is_continuous_and_invalid_contacts_rejected():
    for duty in (0.38, 0.62):
        for p in (0.05, duty - 0.05, duty):
            a, b = foot_roll(p - 1e-7, duty), foot_roll(p + 1e-7, duty)
            assert abs(a[0] - b[0]) < 1e-5
    for kw in ({"lift": -1}, {"pitch": 1}, {"pivot_x": 20}, {"state": "script"}):
        with pytest.raises(RenderError):
            FootPlacement(0, **kw)


def test_repeated_pixels_and_each_emotion_remains_distinct_at_phone_scale():
    pytest.importorskip("cairo")
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    renderer = CairoRenderer()
    hashes = []
    with renderer.surface(360, 640) as surface:
        for expression in (*EXPRESSIONS, "frightened"):
            data = asdict(CharacterPreset(action="react", expression=expression))
            for _ in range(2):
                renderer.draw(
                    surface,
                    preset_commands(data, 9),
                    background=color("efe9da"),
                    logical_size=(360, 640),
                )
                hashes.append(surface.pixel_sha256())
    assert all(a == b for a, b in zip(hashes[::2], hashes[1::2], strict=True))
    assert len(set(hashes)) == len(EXPRESSIONS)
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_review_sheets_are_complete_trusted_vector_commands():
    from reelforge.characters.review import expression_sheet, review_sheet, transition_sheet
    from reelforge.rendering.model import DrawPath

    for make in (expression_sheet, review_sheet, transition_sheet):
        commands = make()
        assert 20 < len(commands) < 5000
        assert all(isinstance(c, DrawPath) for c in commands)


@pytest.mark.parametrize("failure", ("encoder", "destination_exists"))
def test_comparison_failure_cleans_private_output_and_preserves_success(monkeypatch, failure):
    pytest.importorskip("cairo")
    import importlib
    import sys
    import tempfile
    from pathlib import Path

    tools = Path(__file__).resolve().parents[1] / "tools"
    sys.path.insert(0, str(tools))
    review = importlib.import_module("review_character_polish")
    parent = Path(__file__).resolve().parents[1] / "outputs"
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as raw:
        directory = Path(raw)
        output = directory / "before_after.mp4"
        output.write_bytes(b"previous success")
        monkeypatch.setattr(review, "verify_video", lambda *a, **kw: {"passed": True})

        def worker(args, **kwargs):
            Path(args[-1]).write_bytes(b"incomplete")
            return (2, b"", b"fixture encode failed") if failure == "encoder" else (0, b"", b"")

        monkeypatch.setattr(review, "run_bounded", worker)
        with pytest.raises((RuntimeError, FileExistsError)):
            review.comparison(review.BASELINE, directory)
        assert output.read_bytes() == b"previous success"
        assert not list(directory.glob(".reelforge-comparison-*"))
        assert not (directory / "comparison_report.json").exists()


def test_recoil_follow_through_settles_without_history():
    from reelforge.characters.secondary import settling_response

    assert settling_response(0.12) == 0
    assert abs(settling_response(0.3)) > 0.3
    assert abs(settling_response(3)) < 0.0001
    for t in (3, 0.3, 0.12, 1, 0.3):
        assert preset_secondary(CharacterPreset(action="react"), t) == preset_secondary(
            CharacterPreset(action="react"), t
        )


def test_long_boundary_is_bounded_and_outside_time_rejected():
    pose, distance = transition_pose(600)
    assert math.isfinite(pose.root.y + pose.root.x + distance)
    assert transition_secondary(600) == transition_secondary(600)
    assert preset_secondary(CharacterPreset(action="react", speed=1.5), 600) == preset_secondary(
        CharacterPreset(action="react", speed=1.5), 600
    )
    for t in (-1, 601, float("nan")):
        for fn in (transition_pose, transition_secondary, contact_targets):
            with pytest.raises(RenderError):
                fn(t)
