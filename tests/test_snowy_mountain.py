"""Focused tests for the Phase 9C snowy-mountain environment and its production integration.

These cover only the new, additive behavior: the registered Frost Peak assets, their complexity
budgets, and that a scene placing Yellow Mellow on the new walkable ``frost_ridge_01`` ground
compiles through the real scene/blocking/direction pipeline and renders a frame. Existing orchard
behavior is exercised by the unchanged suites.
"""

from __future__ import annotations

import pytest

from reelforge.rendering.model import DrawPath
from reelforge.scenes.assets import asset_by_id, cost, recipe

SNOWY_ASSET_IDS = (
    "frost_sky_01",
    "frost_peaks_01",
    "frost_ridge_01",
    "pine_snow_01",
    "frost_rocks_01",
    "beacon_01",
    "frost_foreground_01",
)


@pytest.mark.parametrize("asset_id", SNOWY_ASSET_IDS)
def test_snowy_asset_registered(asset_id):
    asset = asset_by_id(asset_id)
    assert asset is not None
    assert asset.variants  # at least one variant


@pytest.mark.parametrize("asset_id", SNOWY_ASSET_IDS)
def test_snowy_recipe_within_budget(asset_id):
    asset = asset_by_id(asset_id)
    for variant in asset.variants:
        commands = recipe(asset, variant, 0.2, 0.6, 0.5, 1.5, None)
        assert all(isinstance(c, DrawPath) for c in commands)
        paths, ops = cost(commands)
        assert paths <= asset.max_paths, (asset_id, variant, paths, asset.max_paths)
        assert ops <= asset.max_ops, (asset_id, variant, ops, asset.max_ops)


def test_beacon_variants_differ():
    asset = asset_by_id("beacon_01")
    buried = recipe(asset, "buried", 0.2, 0.5, 0.4, 1.5, None)
    active = recipe(asset, "active", 0.8, 0.5, 0.4, 1.5, None)
    # The active beacon adds glow/beam geometry, so it draws strictly more commands.
    assert len(active) > len(buried)


def test_frost_ridge_is_walkable_support():
    ridge = asset_by_id("frost_ridge_01")
    assert ridge.kind == "environment"
    assert ridge.support_envelope is not None


def _snowy_storyboard():
    """Minimal snowy storyboard: Mellow walks the ridge past the beacon and reacts."""
    out = {
        "width": 720,
        "height": 1280,
        "fps": 30,
        "frames": 90,
        "codec": "h264",
        "pixel_format": "yuv420p",
    }

    def t(x, y, s=1.0):
        return {"x": x, "y": y, "scale": s, "rotation_degrees": 0.0}

    nodes = [
        {
            "id": "root",
            "kind": "root",
            "parent": None,
            "order": 0,
            "visible": True,
            "transform": t(0, 0),
        },
        {
            "id": "sky_layer",
            "kind": "layer",
            "parent": "root",
            "order": 0,
            "visible": True,
            "transform": t(0, 0),
            "depth": 0.0,
        },
        {
            "id": "sky",
            "kind": "background",
            "parent": "sky_layer",
            "order": 0,
            "visible": True,
            "transform": t(0, 0),
            "asset_id": "frost_sky_01",
            "variant": "default",
        },
        {
            "id": "distance",
            "kind": "layer",
            "parent": "root",
            "order": 1,
            "visible": True,
            "transform": t(0, 0),
            "depth": 0.18,
        },
        {
            "id": "peaks",
            "kind": "background",
            "parent": "distance",
            "order": 0,
            "visible": True,
            "transform": t(180, 300),
            "asset_id": "frost_peaks_01",
            "variant": "mid",
        },
        {
            "id": "terrain",
            "kind": "layer",
            "parent": "root",
            "order": 2,
            "visible": True,
            "transform": t(0, 0),
            "depth": 1.0,
        },
        {
            "id": "ridge",
            "kind": "environment",
            "parent": "terrain",
            "order": 0,
            "visible": True,
            "transform": t(180, 470),
            "asset_id": "frost_ridge_01",
            "variant": "default",
        },
        {
            "id": "structures",
            "kind": "layer",
            "parent": "root",
            "order": 3,
            "visible": True,
            "transform": t(0, 0),
            "depth": 0.85,
        },
        {
            "id": "beacon",
            "kind": "asset",
            "parent": "structures",
            "order": 0,
            "visible": True,
            "transform": t(230, 460, 1.0),
            "asset_id": "beacon_01",
            "variant": "buried",
        },
        {
            "id": "people",
            "kind": "layer",
            "parent": "root",
            "order": 5,
            "visible": True,
            "transform": t(0, 0),
            "depth": 1.0,
        },
        {
            "id": "mellow",
            "kind": "character",
            "parent": "people",
            "order": 0,
            "visible": True,
            "transform": t(150, 470, 0.5),
            "asset_id": "yellow_mellow_v2",
            "variant": "default",
            "character": {
                "character": "yellow_mellow_v2",
                "action": "idle",
                "expression": "curious",
            },
            "ground_id": "ridge",
        },
    ]
    world = {
        "schema_version": "scene-0.1",
        "title": "snowy ridge test",
        "output": out,
        "camera": "locked",
        "art_direction": {"warmth": 0.1, "atmosphere": 0.6, "breeze": 0.4},
        "nodes": nodes,
    }
    return {
        "schema_version": "storyboard-0.1",
        "title": "Frost ridge test",
        "world": world,
        "rowan": {
            "actor_id": "mellow",
            "support_id": "ridge",
            "character": "yellow_mellow_v2",
            "start": {"position": [120, 470], "facing": "right"},
        },
        "subjects": [
            {"id": "mellow", "target": {"kind": "actor", "id": "mellow"}},
            {"id": "device", "target": {"kind": "node", "id": "beacon"}},
        ],
        "views": [
            {
                "id": "wide",
                "kind": "establishing",
                "subject": "device",
                "zoom": [1.0, 1.1],
                "screen": [230, 452],
                "offset_start": [0, 0],
                "offset_end": [10, 0],
                "lead_seconds": 0.0,
                "hold": [6, 10],
                "crop": "full",
                "foreground": "clear",
                "cut": "matched",
            }
        ],
        "pattern": "discovery_reaction",
        "beats": [
            {
                "id": "establish",
                "type": "establish",
                "frames": 12,
                "subject": "device",
                "view": "wide",
                "action": {"kind": "idle", "expression": "neutral"},
            },
            {
                "id": "cross",
                "type": "approach",
                "frames": 42,
                "subject": "device",
                "view": "wide",
                "action": {
                    "kind": "walk_to",
                    "expression": "curious",
                    "end_x": 150,
                    "end_speed": 30,
                },
            },
            {
                "id": "spot",
                "type": "discover",
                "frames": 18,
                "subject": "device",
                "view": "wide",
                "action": {"kind": "stop_at", "expression": "curious", "end_x": 159},
            },
            {
                "id": "look",
                "type": "react",
                "frames": 18,
                "subject": "device",
                "view": "wide",
                "action": {"kind": "look_around", "expression": "curious"},
            },
        ],
    }


def test_snowy_storyboard_compiles_and_renders_a_frame():
    from reelforge.direction.sampling import direction_frame
    from reelforge.storyboards.compiler import compile_storyboard

    sb = compile_storyboard(_snowy_storyboard())
    commands = direction_frame(sb.direction, 45)
    assert commands and all(isinstance(c, DrawPath) for c in commands)


def test_orchard_ground_still_walkable():
    # Regression guard: the existing orchard ground remains a registered walkable support.
    orchard = asset_by_id("orchard_ground_01")
    assert orchard is not None and orchard.support_envelope is not None


# ---------------------------------------------------------------- Phase 9C visual correction
def _tool():
    import sys
    from pathlib import Path

    # The preview tool imports the Cairo backend at module load; skip these tool-backed checks
    # when the renderer extra is absent (the non-renderer CI job), where they cannot run.
    pytest.importorskip("cairo", reason="preview tool requires the renderer extra (pycairo)")
    tools = str(Path(__file__).resolve().parent.parent / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import phase9c_snowy_storyboard as tool

    return tool


def test_activate_preset_reaches_its_target():
    from reelforge.characters.yellow_mellow_v2 import ActionRequest, YellowMellowV2
    from reelforge.characters.yellow_mellow_v2.motions import (
        ACTIVATE_HEIGHT,
        ACTIVATE_REACH,
        ACTIVATE_TOLERANCE,
        fingertip,
    )

    perf = YellowMellowV2(facing=0.92).animate(
        [ActionRequest("idle", 10), ActionRequest("activate", 30, "determined")]
    )
    assert perf.entries[1].clip.residual <= ACTIVATE_TOLERANCE
    x, y = fingertip(perf.sample(39).state, "near")
    assert abs(x - ACTIVATE_REACH) < 0.6 and abs(y + ACTIVATE_HEIGHT) < 0.6


def test_activate_rejects_unreachable_target_and_short_duration():
    from reelforge.characters.yellow_mellow_v2 import ActionRequest, YellowMellowV2
    from reelforge.rendering.model import RenderError

    with pytest.raises(RenderError):
        YellowMellowV2().animate([ActionRequest("activate", 30, params={"reach": 60})])
    with pytest.raises(RenderError):
        YellowMellowV2().animate([ActionRequest("activate", 12)])


def test_shot3_fingertip_lands_on_beacon_socket():
    """The interaction is measured: fingertip vs the registered activation socket."""
    tool = _tool()
    from reelforge.storyboards.compiler import compile_storyboard

    report = tool.contact_report(compile_storyboard(tool.shot3()))
    held = [r for r in report["frames"] if r["frame"] >= 78]
    assert held and max(r["distance_world"] for r in held) < 0.25
    approach = [r for r in report["frames"] if r["frame"] == 60]
    assert approach[0]["distance_world"] > 5  # the hand travels to the button, not parked on it


def test_all_corrected_shots_compile_through_production_safety():
    tool = _tool()
    from reelforge.direction.sampling import direction_frame
    from reelforge.storyboards.compiler import compile_storyboard

    for _num, _title, _size, builder, frame, _story, _reads in tool.SHOTS:
        sb = compile_storyboard(builder())
        assert direction_frame(sb.direction, frame)


def test_close_up_zoom_is_scoped_to_close_up_behavior():
    from reelforge.core.errors import InputError
    from reelforge.storyboards.compiler import compile_storyboard

    tool = _tool()
    data = tool.shot2()
    data["views"][0]["kind"] = "reaction"  # same 4.6..4.8 zoom on a normal behavior
    with pytest.raises(InputError):
        compile_storyboard(data)
    data = tool.shot2()
    data["views"][0]["crop"] = "full"  # a close-up may not claim full-figure framing
    with pytest.raises(InputError):
        compile_storyboard(data)


def test_activate_gate_is_per_character():
    """Blocking admits acting=activate only for characters that register the performance."""
    from reelforge.characters.registry import character_info

    assert "activate" in character_info("yellow_mellow_v2").scene_actions
    assert "activate" not in character_info("rowan_01").scene_actions
