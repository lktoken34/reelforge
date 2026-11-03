"""Focused tests for the Yellow Mellow V2 rig, expressions, motion presets and timeline."""

import math

import pytest

from reelforge.characters.yellow_mellow_v2 import (
    EXPRESSIONS,
    PRESETS,
    ActionRequest,
    Stage,
    YellowMellowV2,
    evaluate,
)
from reelforge.characters.yellow_mellow_v2.catalog import CATALOG, command_source, scale_for_height
from reelforge.characters.yellow_mellow_v2.environment import observatory_background
from reelforge.characters.yellow_mellow_v2.expressions import blend_faces, blink_starts
from reelforge.characters.yellow_mellow_v2.motions import ClipStart, LocomotionClip, LocoSegment
from reelforge.characters.yellow_mellow_v2.quality import analyse
from reelforge.characters.yellow_mellow_v2.rig import (
    ANKLE_HEIGHT,
    HEAD_HEIGHT,
    LEG_MAX,
    STANDING_HEIGHT,
    ArmPose,
    FootState,
    MellowPose,
    ankle_from_foot,
    pivot_local,
    solve_two_bone,
    standing_pose,
)
from reelforge.characters.yellow_mellow_v2.transitions import pose_vector
from reelforge.rendering.model import DrawPath, RenderError

SHOWCASE = [
    ActionRequest("idle", 10, "neutral"),
    ActionRequest("wave", 35, "happy", {"hand": "far"}),
    ActionRequest("hands_up", 22, "excited"),
    ActionRequest("hands_down", 23, "happy"),
    ActionRequest("look", 12, "curious", {"direction": "right"}),
    ActionRequest("point", 33, "curious", {"elevation": 1.15, "lower": True}),
    ActionRequest("jump", 60, "excited"),
    ActionRequest("walk", 60, "happy", {"direction": "left"}),
    ActionRequest("run", 60, "determined", {"direction": "left", "stop": True}),
    ActionRequest("jumping_jack", 45, "determined", {"reps": 3}),
    ActionRequest("squat", 22, "determined"),
    ActionRequest("stretch", 23, "tired"),
    ActionRequest("dance", 45, "happy"),
]


@pytest.fixture(scope="module")
def showcase():
    return YellowMellowV2().animate(SHOWCASE)


def world_joints(state):
    pts = {k: state.world((j.x, j.y)) for k, j in state.joints.items()}
    for side in ("near", "far"):
        leg = state.legs[side]
        pts[side + "_knee"] = state.world(leg.knee)
        pts[side + "_ankle"] = state.world(leg.ankle)
    return pts


# ---------------------------------------------------------------- rig
def test_proportions_are_three_and_a_half_heads():
    assert 3.3 <= STANDING_HEIGHT / HEAD_HEIGHT <= 3.7


def test_standing_feet_are_flat_on_the_ground():
    state = evaluate(standing_pose(0.0, 0.25))
    for side in ("near", "far"):
        heel, toe = state.sole_points(side)
        assert heel[1] == pytest.approx(0, abs=1e-6)
        assert toe[1] == pytest.approx(0, abs=1e-6)
        assert state.legs[side].reach_error == 0


def test_ik_reaches_targets_and_bends_in_requested_direction():
    knee, ankle, err = solve_two_bone((0, 0), (5, 38), bend=1.0)
    assert err == 0 and math.dist(ankle, (5, 38)) < 1e-9
    assert math.dist((0, 0), knee) == pytest.approx(22.0)
    assert math.dist(knee, ankle) == pytest.approx(21.0)
    knee_neg, _, _ = solve_two_bone((0, 0), (5, 38), bend=-1.0)
    assert knee[0] > 2.5 > knee_neg[0]
    _, ankle, err = solve_two_bone((0, 0), (0, 90))
    assert err > 0 and math.dist((0, 0), ankle) == pytest.approx(LEG_MAX)


def test_front_view_knees_splay_and_three_quarter_knees_point_forward():
    def crouch(f):
        pose = standing_pose(0.0, f)
        return evaluate(pose.with_(pelvis_height=36.0))

    front = crouch(0.05)
    assert front.legs["near"].knee[0] < front.legs["near"].hip[0] - 3
    assert front.legs["far"].knee[0] > front.legs["far"].hip[0] + 3
    side = crouch(0.95)
    for leg in side.legs.values():
        assert leg.knee[0] > leg.hip[0] + 3


def test_foot_roll_keeps_pivot_fixed():
    f = 0.9
    for pitch in (0.3, -0.25):
        foot = FootState(10.0, 0.0, pitch)
        ax, ay = ankle_from_foot(foot, 10.0, f)
        px, py = pivot_local(pitch, f)
        c, s = math.cos(pitch), math.sin(pitch)
        world_pivot = (ax + c * px - s * py, ay + s * px + c * py)
        assert world_pivot[0] == pytest.approx(10.0 + px)
        assert world_pivot[1] == pytest.approx(0.0, abs=1e-9)


def test_joint_limits_clamp_and_report():
    pose = standing_pose().with_(near_arm=ArmPose(5.0, -4.0, 0.0), spine=2.0)
    state = evaluate(pose)
    assert {"near_shoulder", "near_elbow", "spine"} <= set(state.clamped)
    assert state.pose.near_arm.shoulder == pytest.approx(3.25)


def test_mirroring_matches_world_positions():
    right = evaluate(standing_pose(0.0, 0.6).with_(spine=0.1))
    left = evaluate(standing_pose(0.0, -0.6).with_(spine=0.1))
    r, lf = world_joints(right), world_joints(left)
    for name in ("head", "chest", "near_wrist", "far_knee"):
        assert r[name][0] == pytest.approx(-lf[name][0], abs=1e-9)
        assert r[name][1] == pytest.approx(lf[name][1], abs=1e-9)


def test_pelvis_soft_limit_keeps_planted_feet_reachable():
    state = evaluate(standing_pose().with_(pelvis_height=70.0))
    assert state.pelvis_limited > 15
    for leg in state.legs.values():
        assert leg.reach_error < 0.01


# ---------------------------------------------------------------- expressions
def test_all_required_expressions_exist_and_blend():
    required = {
        "neutral",
        "happy",
        "excited",
        "curious",
        "surprised",
        "concerned",
        "determined",
        "tired",
    }
    assert required <= set(EXPRESSIONS)
    mid = blend_faces(EXPRESSIONS["happy"], EXPRESSIONS["surprised"], 0.5)
    assert EXPRESSIONS["happy"].eye_scale < mid.eye_scale < EXPRESSIONS["surprised"].eye_scale


def test_blinks_are_deterministic():
    assert blink_starts("a", 450) == blink_starts("a", 450)
    assert blink_starts("a", 450) != blink_starts("b", 450)


# ---------------------------------------------------------------- presets
@pytest.mark.parametrize("action", sorted(PRESETS))
def test_every_preset_contains_real_joint_motion(action):
    durations = {"jump": 60, "dance": 45, "jumping_jack": 45}
    duration = durations.get(action, 30)
    start = ClipStart(standing_pose(0.0, 0.25), EXPRESSIONS["neutral"])
    clip = PRESETS[action](start, duration)
    vectors = [pose_vector(clip.pose(t)) for t in range(0, duration + 1)]
    # Ignore the facing channel: every action must move actual joints.
    moved = max(abs(a - b) for v in vectors for a, b in zip(v, vectors[0], strict=True))
    assert moved > 0.1, action
    first = world_joints(evaluate(clip.pose(0)))
    ref = world_joints(evaluate(start.pose))
    assert max(math.dist(first[k], ref[k]) for k in ref) < 2.5, (
        "clip must start from the start pose"
    )


def test_presets_validate_parameters():
    start = ClipStart(standing_pose(), EXPRESSIONS["neutral"])
    with pytest.raises(RenderError):
        PRESETS["wave"](start, 30, hand="left")
    with pytest.raises(RenderError):
        PRESETS["jump"](start, 20)  # too short for anticipation + flight + landing
    with pytest.raises(RenderError):
        YellowMellowV2().animate([ActionRequest("moonwalk", 30)])
    with pytest.raises(RenderError):
        YellowMellowV2().animate([ActionRequest("wave", 30, params={"speed": 2})])
    with pytest.raises(RenderError):
        ActionRequest("wave", 30, expression="angry")
    with pytest.raises(RenderError):
        YellowMellowV2().animate([ActionRequest("walk", 40)])  # must end with a stop


def test_locomotion_plants_feet_alternates_and_stops():
    start = ClipStart(standing_pose(0.0, 0.25), EXPRESSIONS["neutral"])
    clip = LocomotionClip(
        start, [LocoSegment("walk", 60), LocoSegment("run", 60, stop=True)], "right"
    )
    prev = None
    landings = {"A": [], "B": []}
    airborne_run = 0
    for t in range(clip.duration + 1):
        feet = {k: clip._foot(t, k)[0] for k in ("A", "B")}
        if prev:
            for k in feet:
                if feet[k].lift == 0 and prev[k].lift == 0 and feet[k].pitch == prev[k].pitch == 0:
                    assert feet[k].x == pytest.approx(prev[k].x, abs=1e-9)
                if feet[k].lift == 0 and prev[k].lift > 0:
                    landings[k].append(t)
        if t > 75 and all(f.lift > 0.6 for f in feet.values()):
            airborne_run += 1
        prev = feet
    assert len(landings["A"]) >= 3 and len(landings["B"]) >= 3
    assert airborne_run >= 3, "running must have a flight phase"
    end = clip.pose(clip.duration)
    assert end.near_foot.lift == 0 and end.far_foot.lift == 0
    assert end.pelvis_x > 100


def test_walk_has_no_flight_phase():
    start = ClipStart(standing_pose(0.0, 0.9), EXPRESSIONS["neutral"])
    clip = LocomotionClip(start, [LocoSegment("walk", 90, stop=True)], "right")
    for t in range(clip.duration + 1):
        feet = [clip._foot(t, k)[0] for k in ("A", "B")]
        assert min(f.lift for f in feet) == 0


# ---------------------------------------------------------------- timeline
def test_showcase_is_450_frames_and_deterministic(showcase):
    assert showcase.frames == 450
    a = showcase.sample(301)
    showcase.sample(17)
    b = showcase.sample(301)
    assert pose_vector(a.state.pose) == pose_vector(b.state.pose)
    assert a.face == b.face


def test_showcase_motion_quality(showcase):
    sections = (
        (0, 44, "a"),
        (135, 194, "jump"),
        (195, 254, "walk"),
        (255, 314, "run"),
        (315, 359, "jacks"),
    )
    report = analyse(showcase, sections=sections)
    s = report["summary"]
    assert s["all_joint_transforms_finite"]
    assert s["max_ground_penetration_units"] <= 0.05
    assert s["max_planted_contact_slide_units"] < 0.2
    assert not s["knee_flip_events"]
    assert not s["clamped_channel_frames"]
    by = {x["section"]: x for x in report["sections"]}
    assert by["jump"]["airborne_frames"] >= 10
    assert by["jump"]["min_hip_ankle"] < 34  # visible knee compression
    assert by["walk"]["airborne_frames"] == 0
    assert by["run"]["airborne_frames"] >= 3
    assert by["jacks"]["airborne_frames"] >= 6
    assert all(b["ratio"] is None or b["ratio"] < 1.5 for b in report["boundaries"])


def test_drawing_commands_are_valid_and_bounded(showcase):
    stage = Stage(x=180, ground_y=575, scale=2.3)
    for frame in (0, 160, 230, 449):
        cmds = observatory_background(0.0) + showcase.draw(frame, stage)
        assert isinstance(cmds, tuple) and len(cmds) < 4096
        assert all(isinstance(c, DrawPath) for c in cmds)
    left = showcase.draw(230, stage)
    assert any(c.transform.sx < 0 for c in left), "left-facing walk is mirrored"


def test_catalog_adapter_produces_commands():
    assert CATALOG["yellow_mellow_v2"].episode_integrated is False
    frames, source = command_source(
        "yellow_mellow_v2",
        [ActionRequest("wave", 20), ActionRequest("idle", 10)],
        scale=scale_for_height(150),
    )
    assert frames == 30
    assert len(source(12)) > 50
    with pytest.raises(RenderError):
        command_source("rowan_v3", [ActionRequest("idle", 10)])


def test_ankle_height_constant_is_used_by_sole():
    state = evaluate(MellowPose())
    leg = state.legs["near"]
    assert leg.ankle[1] == pytest.approx(-ANKLE_HEIGHT)
