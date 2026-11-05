"""Focused tests for the MVP prompt-to-reel layer: storylib presets and the planner.

These validate only the new, additive orchestration: every shot preset compiles through the real
storyboard/direction validation for its environment; the planner turns prompts into validated
production-0.1 manifests; two different prompts produce materially different plans; and
unsupported prompts/durations are reported rather than silently defaulted. No rendering here.
"""

from __future__ import annotations

import pytest

from reelforge.mvp.planner import (
    PlanError,
    build_production_manifest,
    plan_story,
    plan_summary,
    supported,
)
from reelforge.mvp.storylib import ENVIRONMENTS, SHOT_PRESETS, build_shot
from reelforge.productions.contract import compile_production
from reelforge.storyboards.compiler import compile_storyboard

# preset -> environments it must support (investigate/threat need the Frost Peak beacon)
_PRESET_ENVS = {
    "establish": ("frost_peak", "orchard"),
    "reaction": ("frost_peak", "orchard"),
    "travel": ("frost_peak", "orchard"),
    "travel_run": ("frost_peak", "orchard"),
    "resolve": ("frost_peak", "orchard"),
    "investigate": ("frost_peak",),
    "threat": ("frost_peak",),
}


@pytest.mark.parametrize("preset,envs", _PRESET_ENVS.items())
def test_shot_presets_compile(preset, envs):
    for env in envs:
        sb = build_shot(preset, env, title=f"{preset} {env}", description="t", mood="calm")
        plan = compile_storyboard(sb)
        assert plan.direction.blocking is not None  # a real moving actor on a walkable ground


def test_beacon_presets_reject_orchard():
    for preset in ("investigate", "threat"):
        with pytest.raises(ValueError):
            build_shot(preset, "orchard", title="x", description="y", mood="calm")


def test_supported_vocabulary():
    s = supported()
    assert 15 in s["durations_seconds"] and 60 in s["durations_seconds"]
    assert set(s["environments"]) == set(ENVIRONMENTS)
    assert set(s["shot_presets"]) == set(SHOT_PRESETS)


@pytest.mark.parametrize("duration,segments", [(15, 5), (60, 20)])
def test_plan_and_manifest_compile(duration, segments):
    prompt = (
        "Yellow Mellow crosses the snowy mountains, finds an emergency beacon, activates "
        "it in a storm, then travels to the valley orchard where rescue answers"
    )
    plan = plan_story(prompt, duration)
    manifest = build_production_manifest(plan)
    compiled = compile_production(manifest)
    assert compiled.frames == segments * 90
    assert len(compiled.segments) == segments
    # Establish first, resolve last (coherent arc), and a beacon activation present.
    beats = plan_summary(plan)["beats"]
    assert beats[0]["preset"] == "establish"
    assert beats[-1]["preset"] == "resolve"
    assert any(b["preset"] == "investigate" for b in beats)


def test_two_prompts_differ_materially():
    a = plan_story("Yellow Mellow finds an emergency signal in the snowy mountains.", 15)
    b = plan_story(
        "Yellow Mellow explores an orchard, discovers something unusual, and runs to safety.", 15
    )
    # Different environments.
    assert a.environments == ["frost_peak"]
    assert b.environments == ["orchard"]
    pa = [bt.preset for bt in a.beats]
    pb = [bt.preset for bt in b.beats]
    assert pa != pb
    # A activates the beacon; B escapes, no beacon.
    assert "investigate" in pa and "investigate" not in pb
    assert "travel_run" in pb and "travel_run" not in pa
    # Manifests reference different scene assets.
    ma, mb = build_production_manifest(a), build_production_manifest(b)

    def assets(m):
        return {
            n["asset_id"]
            for s in m["segments"]
            for n in s["storyboard"]["world"]["nodes"]
            if n.get("asset_id")
        }

    assert "beacon_01" in assets(ma) and "beacon_01" not in assets(mb)
    assert "orchard_ground_01" in assets(mb) and "orchard_ground_01" not in assets(ma)


def test_unsupported_prompt_and_duration_report_errors():
    with pytest.raises(PlanError):
        plan_story("Yellow Mellow pilots a spaceship through a nebula", 15)
    with pytest.raises(PlanError):
        plan_story("snowy mountain beacon", 30)
    with pytest.raises(PlanError):
        plan_story("", 15)


def test_plan_is_deterministic():
    prompt = "Yellow Mellow finds an emergency signal in the snowy mountains."
    a = plan_summary(plan_story(prompt, 60))
    b = plan_summary(plan_story(prompt, 60))
    assert a == b


# ---------------------------------------------------------------- staging variety (Task 1)
def _staging_key(seg):
    import hashlib
    import json

    sb = json.loads(json.dumps(seg["storyboard"]))
    sb.pop("title", None)
    sb.pop("description", None)
    return hashlib.sha256(json.dumps(sb, sort_keys=True).encode()).hexdigest()


def test_repeated_presets_get_distinct_staging():
    """Variants make the same (preset, env) stage differently, so no two segments are identical."""
    a = build_shot("reaction", "frost_peak", title="t", description="d", mood="tense", variant=0)
    b = build_shot("reaction", "frost_peak", title="t", description="d", mood="tense", variant=1)
    assert _staging_key({"storyboard": a}) != _staging_key({"storyboard": b})


def test_sixty_second_plan_has_no_identical_segments():
    prompt = (
        "Yellow Mellow travels across the snowy mountains, discovers a buried emergency "
        "beacon, activates it as a storm hits, then follows the signal down to the valley "
        "orchard where rescue answers"
    )
    manifest = build_production_manifest(plan_story(prompt, 60))
    compile_production(manifest)  # all 20 segments validate
    keys = [_staging_key(s) for s in manifest["segments"]]
    assert len(set(keys)) == len(keys) == 20, "every 60s segment must have distinct staging"


def test_variant_out_of_range_wraps_not_errors():
    # The planner may request any occurrence index; presets wrap within their variant table.
    for v in (0, 1, 2, 5, 99):
        sb = build_shot(
            "establish", "frost_peak", title="t", description="d", mood="calm", variant=v
        )
        compile_storyboard(sb)


# ---------------------------------------------------------------- output no-clobber (Task 2)
def _load_cli():
    import importlib.util
    from pathlib import Path

    tool = Path(__file__).resolve().parent.parent / "tools" / "make_reel.py"
    spec = importlib.util.spec_from_file_location("make_reel", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_refuses_to_overwrite_existing_output(tmp_path, monkeypatch):
    """The render path must refuse an existing --output by default and never start a render."""
    cli = _load_cli()
    existing = tmp_path / "already.mp4"
    existing.write_bytes(b"keep me")

    def _boom(*a, **k):  # render must not be reached
        raise AssertionError("render_production must not run when the output already exists")

    import reelforge.productions.workflow as wf

    monkeypatch.setattr(wf, "render_production", _boom)
    monkeypatch.setattr(
        "sys.argv",
        [
            "make_reel.py",
            "--prompt",
            "snowy mountain emergency beacon",
            "--duration",
            "15",
            "--output",
            str(existing),
        ],
    )
    rc = cli.main()
    assert rc == 6
    assert existing.read_bytes() == b"keep me"  # untouched


def test_cli_overwrite_flag_allows_replacing(tmp_path, monkeypatch):
    """With --overwrite the guard is lifted (the render itself is stubbed here)."""
    cli = _load_cli()
    existing = tmp_path / "already.mp4"
    existing.write_bytes(b"old")
    work = tmp_path / "work"  # must not exist yet (the CLI owns/creates it)

    import reelforge.productions.workflow as wf

    def _fake_render(compiled, work_dir, *, registry_root, cancelled):
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "reel.mp4").write_bytes(b"new reel bytes")
        return {
            "success": True,
            "frames": 450,
            "seconds": 15.0,
            "editorial_cuts": [],
            "chunk_boundaries": [],
        }

    monkeypatch.setattr(wf, "render_production", _fake_render)
    monkeypatch.setattr(
        "sys.argv",
        [
            "make_reel.py",
            "--prompt",
            "snowy mountain emergency beacon",
            "--duration",
            "15",
            "--output",
            str(existing),
            "--work-dir",
            str(work),
            "--overwrite",
        ],
    )
    rc = cli.main()
    assert rc == 0
    assert existing.read_bytes() == b"new reel bytes"  # replaced atomically
