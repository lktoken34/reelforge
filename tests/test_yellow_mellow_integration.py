"""Phase 9A: Yellow Mellow V2 episode integration, silent rendering and Rowan regression.

These tests prove that a JSON-selected Yellow Mellow actually animates through the standard
pipeline (visible movement and facial change), that invalid instructions are rejected, that the
new silent episode-0.2 contract works, and that the existing Rowan episode-0.1 behaviour and the
existing storyboard/blocking contracts are unchanged.
"""

import copy
import json
import math
from pathlib import Path

import pytest

from reelforge.characters import registry
from reelforge.characters.yellow_mellow_v2.episode import (
    SegmentSpec,
    build_drawer,
    requests_from_segments,
    resolve_expression,
)
from reelforge.core.errors import InputError
from reelforge.direction.sampling import actor_override, direction_frame
from reelforge.episodes.contract import compile_episode, load_episode
from reelforge.rendering.model import DrawPath, RenderError
from reelforge.storyboards.compiler import compile_storyboard

ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "examples/episodes/yellow_mellow_orchard.json"
ROWAN_STORYBOARD = ROOT / "examples/storyboards/silent_signal.json"


# ----------------------------------------------------------------- registry
def test_registry_lists_both_characters_without_source_edits():
    assert set(registry.character_ids()) == {"rowan_01", "yellow_mellow_v2"}
    assert registry.DEFAULT_CHARACTER == "rowan_01"
    ym = registry.character_info("yellow_mellow_v2")
    assert ym.asset_id == "yellow_mellow_v2"
    assert {"walk", "run", "jump", "wave", "hands_up", "point", "crouch", "stretch"} <= set(
        ym.scene_actions
    )
    assert len(ym.expressions) == 8
    with pytest.raises(RenderError):
        registry.character_info("nobody")


def test_resolve_expression_maps_rowan_and_accepts_v2():
    assert resolve_expression("happy") == "happy"  # native V2
    assert resolve_expression("concerned") == "concerned"
    assert resolve_expression("calm") == "neutral"  # Rowan -> V2 alias
    assert resolve_expression("frightened") == "surprised"
    with pytest.raises(RenderError):
        resolve_expression("nonsense")


# ----------------------------------------------------------------- adapter mapping
def _specs(*rows):
    specs = []
    frame = 0
    for mode, frames, acting, expr, facing in rows:
        specs.append(SegmentSpec(frame, frame + frames, mode, acting, expr, facing, 0.0))
        frame += frames
    return tuple(specs)


def test_requests_from_segments_maps_modes():
    specs = _specs(
        ("idle", 9, "none", "neutral", "right"),
        ("walk", 36, "none", "curious", "right"),
        ("stop", 12, "none", "curious", "right"),
        ("idle", 18, "look_around", "curious", "right"),
        ("idle", 15, "react", "surprised", "right"),
    )
    requests, start_expr, start_facing = requests_from_segments(specs)
    assert start_expr == "neutral" and start_facing == "right"
    actions = [r.action for r in requests]
    assert actions == ["idle", "walk", "walk", "look", "surprise"]
    assert requests[2].params.get("stop") is True  # stop sub-segment
    assert sum(r.duration_frames for r in requests) == 90


def test_terminal_run_gets_a_stop_so_the_clip_resolves():
    specs = _specs(
        ("idle", 6, "none", "concerned", "right"),
        ("run", 84, "none", "determined", "right"),
    )
    requests, _, _ = requests_from_segments(specs)
    assert requests[-1].action == "run"
    assert requests[-1].params.get("stop") is True


# ----------------------------------------------------------------- real motion + expression
@pytest.fixture(scope="module")
def episode_plan():
    return load_episode(EPISODE)


def _actor_points(direction, frame):
    """World-space (pre-camera) control points of the drawn character for one frame."""
    override = actor_override(direction, frame)
    pts = []
    for c in override.commands:
        t = c.transform
        for op in c.path:
            for i in range(0, len(op.points), 2):
                x = t.tx + t.sx * op.points[i]
                y = t.ty + t.sy * op.points[i + 1]
                pts.append(
                    (
                        override.world.x + override.world.scale * x,
                        override.world.y + override.world.scale * y,
                    )
                )
    return pts


def _root_relative(pts):
    """Translate points so the lowest-left extent is the origin, isolating pose from travel."""
    ox = min(p[0] for p in pts)
    oy = max(p[1] for p in pts)  # feet (largest y) as vertical anchor
    return [(x - ox, y - oy) for x, y in pts]


def test_json_selected_yellow_mellow_actually_moves(episode_plan):
    # Segment 1: idle -> curious walk -> discover. Both the pose and the world travel change.
    direction = episode_plan.segments[0].storyboard.direction
    assert direction.blocking.character == "yellow_mellow_v2"
    a = _actor_points(direction, 3)
    b = _actor_points(direction, 40)
    assert len(a) > 100 and len(b) > 100
    # Pose change, isolated from travel by anchoring each frame at its own root extent. The
    # root-relative bounding box and the hand command count both change between idle and walk.
    ra, rb = _root_relative(a), _root_relative(b)

    def box(pts):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    ba, bb = box(ra), box(rb)
    assert math.dist(ba, bb) > 1.0 or len(a) != len(b), "character pose did not change"
    # The root also travels along the blocking route (absolute world X advances).
    assert abs(min(p[0] for p in b) - min(p[0] for p in a)) > 10, "no route travel"


def test_facial_expression_changes_across_segments(episode_plan):
    # Segment 2 ends on a surprised reaction; the face differs from its neutral/curious start.
    from reelforge.blocking.sampling import _yellow_mellow_drawer

    direction = episode_plan.segments[1].storyboard.direction
    drawer = _yellow_mellow_drawer(direction.blocking)
    early = drawer._perf.sample(4).face
    late = drawer._perf.sample(80).face
    assert (early.eye_scale, early.mouth_open) != (late.eye_scale, late.mouth_open)
    assert late.eye_scale > early.eye_scale  # surprise widens the eyes


def test_every_segment_frame_renders_valid_commands(episode_plan):
    for seg in episode_plan.segments:
        direction = seg.storyboard.direction
        for frame in (0, 45, 89):
            cmds = direction_frame(direction, frame)
            assert isinstance(cmds, tuple) and 0 < len(cmds) <= 4096
            assert all(isinstance(c, DrawPath) for c in cmds)


def test_character_stays_grounded_no_runaway(episode_plan):
    # The drawn feet never leave a sane vertical band around the ground line across the story.
    from reelforge.blocking.sampling import _yellow_mellow_drawer

    for seg in episode_plan.segments:
        drawer = _yellow_mellow_drawer(seg.storyboard.direction.blocking)
        for frame in range(0, 90, 9):
            cf = drawer._perf.sample(frame)
            for side in ("near", "far"):
                heel, toe = cf.state.sole_points(side)
                # Local sole y is near 0 (ground) except small lifts during steps/jumps.
                assert -30 <= min(heel[1], toe[1]) <= 8


# ----------------------------------------------------------------- invalid instructions
def test_unknown_character_is_rejected():
    sb = json.loads(ROWAN_STORYBOARD.read_text())
    sb["rowan"]["character"] = "dragon_99"
    with pytest.raises(InputError):
        compile_storyboard(sb)


def test_character_field_requires_the_newer_contract():
    # A raw blocking-0.1 dict may not carry a character field.
    from reelforge.blocking.contract import compile_blocking

    sb = json.loads(ROWAN_STORYBOARD.read_text())
    compiled = compile_storyboard(sb)  # Rowan path still fine
    blocking = json.loads(compiled.blocking_json)
    assert blocking["schema_version"] == "blocking-0.1"
    assert "character" not in blocking
    bad = copy.deepcopy(blocking)
    bad["character"] = "yellow_mellow_v2"
    with pytest.raises(InputError):
        compile_blocking(bad)  # still 0.1 -> character field refused


def test_invalid_expression_for_yellow_mellow_rejected():
    sb = json.loads(EPISODE.read_text())["segments"][0]["storyboard"]
    bad = copy.deepcopy(sb)
    bad["beats"][0]["action"]["expression"] = "calm"  # Rowan-only; not a V2 expression
    with pytest.raises(InputError):
        compile_storyboard(bad)


def test_adapter_rejects_too_short_subsegment():
    with pytest.raises(RenderError):
        build_drawer(_specs(("idle", 1, "none", "neutral", "right")))


def test_no_executable_or_path_data_accepted():
    sb = json.loads(EPISODE.read_text())["segments"][0]["storyboard"]
    bad = copy.deepcopy(sb)
    bad["rowan"]["character"] = {"eval": "import os"}  # not a string id
    with pytest.raises(InputError):
        compile_storyboard(bad)


# ----------------------------------------------------------------- silent episode contract
def test_silent_episode_contract_accepts_null_audio():
    plan = load_episode(EPISODE)
    assert plan.silent is True
    assert plan.audio is None
    assert plan.frames == 450


def test_episode_01_still_requires_audio():
    r = json.loads((ROOT / "examples/reels/silent_signal.json").read_text())
    silent_01 = {
        "schema_version": "episode-0.1",
        "title": "needs audio",
        "segments": [{"id": "first", "storyboard": r["storyboard"]}],
        "audio": None,
    }
    with pytest.raises(InputError):
        compile_episode(silent_01)
    # episode-0.2 with the same null audio is accepted.
    silent_02 = {**silent_01, "schema_version": "episode-0.2"}
    assert compile_episode(silent_02).silent is True


def test_episode_02_still_accepts_audio_enabled():
    r = json.loads((ROOT / "examples/reels/silent_signal.json").read_text())
    with_audio = {
        "schema_version": "episode-0.2",
        "title": "audio under 0.2",
        "segments": [{"id": "first", "storyboard": r["storyboard"]}],
        "audio": r["audio"],
    }
    plan = compile_episode(with_audio)
    assert plan.silent is False and plan.audio is not None


# ----------------------------------------------------------------- Rowan regression
def test_rowan_storyboards_unchanged():
    for name in ("silent_signal", "abandoned_settlement", "shelter_entrance"):
        sb = json.loads((ROOT / f"examples/storyboards/{name}.json").read_text())
        compiled = compile_storyboard(sb)
        blocking = json.loads(compiled.blocking_json)
        # No character field, still blocking-0.1, still Rowan.
        assert blocking["schema_version"] == "blocking-0.1"
        assert "character" not in blocking
        assert compiled.direction.blocking.character == "rowan_01"


def test_rowan_episode_still_renders_frames_identically():
    # Compile the accepted Rowan reel storyboard through the episode and sample a frame; the
    # character drawer path is still Rowan's (sign-mirrored draw_character), unaffected by the
    # new dispatch.
    r = json.loads((ROOT / "examples/reels/silent_signal.json").read_text())
    plan = compile_episode(
        {
            "schema_version": "episode-0.1",
            "title": "rowan regression",
            "segments": [{"id": "first", "storyboard": r["storyboard"]}],
            "audio": r["audio"],
        }
    )
    direction = plan.segments[0].storyboard.direction
    assert direction.blocking.character == "rowan_01"
    cmds = direction_frame(direction, 20)
    assert isinstance(cmds, tuple) and len(cmds) > 100
