"""Art-direction invariants and native failure checks beyond the 301 baseline cases."""

import importlib.util
import json
import math
import os
import subprocess
import sys
from dataclasses import asdict, replace

import pytest

from reelforge.characters.presets import CharacterPreset, sample_pose, smooth
from reelforge.characters.rowan import draw_character
from reelforge.environments import polish
from reelforge.environments.artwork import placed
from reelforge.environments.presets import EnvironmentPreset, load_preset
from reelforge.environments.scene import camera_at, environment_frame, layers_at
from reelforge.rendering.diagnostic import color
from reelforge.rendering.model import RenderError

NATIVE = importlib.util.find_spec("cairo") is not None


def test_variation_independent_of_order_and_python_hash_seed():
    values = [polish.variation(47, i) for i in range(40)]
    assert len(set(values)) == 40
    assert all(0 <= v < 1 for v in values)
    assert [polish.variation(47, i) for i in reversed(range(40))] == list(reversed(values))
    script = (
        "from reelforge.environments.polish import variation; "
        "print([variation(47,i) for i in range(40)])"
    )
    results = [
        subprocess.check_output(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            text=True,
        )
        for seed in (1, 99)
    ]
    assert results[0] == results[1]
    assert json.loads(results[0]) == values


def test_tree_identity_and_bounded_breeze():
    trees = [polish.tree(i, 0.7, 0.45, 1) for i in (43, 98, 360)]
    assert len(set(trees)) == 3
    assert trees[0] == polish.tree(43, 0.7, 0.45, 1)
    assert polish.tree(43, 0.7, 0, 0) == polish.tree(43, 0.7, 0, 6)
    assert polish.tree(43, 0.7, 1, 0) != polish.tree(43, 0.7, 1, 6)
    assert len({tuple(c.path for c in t) for t in trees}) == 3


@pytest.mark.parametrize("shot", ["locked", "orchard_pan", "orchard_push"])
def test_accepted_camera_is_numerically_unchanged(shot):
    preset = EnvironmentPreset(shot=shot, framing=0.3)
    for f in (0, 29, 90, 179):
        c = camera_at(preset, f)
        u = smooth(f / 179)
        expected = (
            (2.4, 0, 1)
            if shot == "locked"
            else (-10 + 20 * u + 2.4, 0, 1.025)
            if shot == "orchard_pan"
            else (-4 + 10 * u + 2.4, -2 * u, 1 + 0.085 * u)
        )
        assert (c.x, c.y, c.zoom) == pytest.approx(expected)
    assert EnvironmentPreset.from_data(asdict(preset)) == preset


@pytest.mark.parametrize("shot", ["locked", "orchard_pan", "orchard_push", "orchard_suspense"])
def test_geometry_and_extreme_presets_remain_bounded(shot):
    for value in (0, 1):
        p = EnvironmentPreset(
            shot=shot, atmosphere=value, warmth=value, breeze=value, framing=value * 2 - 1
        )
        for f in (0, 90, 179):
            commands = environment_frame(f, p)
            assert len(commands) < 1500
            assert sum(len(c.path) + len(c.clip or ()) for c in commands) < 12000
            assert commands == environment_frame(f, p)


@pytest.mark.parametrize(
    "key,value",
    [
        ("warmth", -1),
        ("warmth", 1.001),
        ("atmosphere", math.inf),
        ("atmosphere", True),
        ("warmth", "0.7"),
        ("breeze", math.nan),
    ],
)
def test_lighting_and_motion_inputs_stay_validated(key, value):
    with pytest.raises(RenderError):
        replace(EnvironmentPreset(), **{key: value})


def test_suspense_drives_threshold_toward_center_and_holds():
    p = load_preset("examples/environments/orchard_suspense.json")

    def distance(f):
        t = camera_at(p, f).transform(0.85)
        x, y = t.tx + 231 * t.sx, t.ty + 365 * t.sy
        return math.hypot(x - 180, y - 320)

    assert distance(179) < distance(0) * 0.5
    assert camera_at(p, 0) == camera_at(p, 25)
    assert camera_at(p, 162) == camera_at(p, 179)
    assert camera_at(p, 179).zoom == 1.23
    assert camera_at(p, 90).transform(1.4).sx > camera_at(p, 90).transform(0.18).sx


@pytest.mark.parametrize("shot", ["orchard_push", "orchard_suspense"])
def test_projected_light_remains_attached_to_barn_threshold(shot):
    p = EnvironmentPreset(shot=shot)
    for f in (0, 90, 179):
        layers = {x.id: x for x in layers_at(p, f)}
        camera = camera_at(p, f)
        gt = camera.transform(layers["door_light"].depth)
        bt = camera.transform(layers["barn"].depth)
        light = layers["door_light"].commands[0].path[0].points
        assert (gt.tx + light[0] * gt.sx, gt.ty + light[1] * gt.sy) == pytest.approx(
            (bt.tx + (257 - 56 * 0.91) * bt.sx, bt.ty + 405 * bt.sy)
        )
        assert layers["ground"].depth == layers["rowan"].depth == 1


def test_character_grading_keeps_every_path_and_attachment():
    original = draw_character(
        sample_pose(CharacterPreset(action="look_around"), 3), position=(165, 498), scale=0.69
    )
    graded = polish.grade_character(original, 0.7, 0.65)
    assert [(c.path, c.transform, c.clip) for c in graded] == [
        (c.path, c.transform, c.clip) for c in original
    ]
    assert [c.stroke.width if c.stroke else None for c in graded] == [
        c.stroke.width if c.stroke else None for c in original
    ]
    assert graded != original


def test_light_does_not_drift_into_front_of_rowan():
    ids = [layer.id for layer in layers_at(EnvironmentPreset(), 90)]
    assert (
        ids.index("ground") < ids.index("door_light") < ids.index("rowan") < ids.index("foreground")
    )
    off = polish.ground_light((206, 405), (255, 407), 0)
    assert all(all(p.a == 0 for _, p in c.fill.stops) for c in off)


@pytest.mark.skipif(not NATIVE, reason="optional Cairo")
def test_wall_light_excludes_open_door_pixels(tmp_path):
    import cairo

    from reelforge.rendering.backends.cairo import CairoRenderer

    renderer = CairoRenderer()
    output = tmp_path / "wall.png"
    with renderer.surface(200, 220) as surface:
        renderer.draw(
            surface,
            placed(polish.barn_light(1), 100, 200),
            background=color("000000", 0),
            logical_size=(200, 220),
        )
        surface.write_png(output)
    image = cairo.ImageSurface.create_from_png(str(output))
    view = image.get_data()
    try:
        # Deep inside the doorway must stay transparent; nearby lit wall must receive light.
        assert view[160 * image.get_stride() + 80 * 4 + 3] == 0
        assert view[105 * image.get_stride() + 120 * 4 + 3] > 0
    finally:
        view.release()
        image.finish()
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


@pytest.mark.skipif(not NATIVE, reason="optional Cairo")
def test_polished_out_of_order_pixels_and_failure_cleanup():
    from reelforge.rendering.backends.cairo import CairoRenderer

    renderer = CairoRenderer()
    p = EnvironmentPreset(shot="orchard_suspense")
    hashes = {}
    with renderer.surface(360, 640) as surface:
        for f in (179, 0, 90, 0, 179, 90):
            renderer.draw(
                surface,
                environment_frame(f, p),
                background=color("243e49"),
                logical_size=(360, 640),
            )
            assert hashes.setdefault(f, surface.pixel_sha256()) == surface.pixel_sha256()
    with pytest.raises(RenderError), renderer.surface(360, 640):
        environment_frame(-1, p)
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


@pytest.mark.skipif(not NATIVE, reason="optional Cairo")
def test_polished_encoder_failure_reaps_child_and_surface(tmp_path):
    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.rendering.backends.cairo import CairoRenderer

    renderer = CairoRenderer()
    output = tmp_path / "interrupted.mp4"
    with pytest.raises(RuntimeError, match="injected"):
        with FFmpegEncoder(output, width=360, height=640, frames=180) as encoder:
            with renderer.surface(360, 640) as surface:
                renderer.draw(
                    surface,
                    environment_frame(90),
                    background=color("243e49"),
                    logical_size=(360, 640),
                )
                encoder.write_surface(surface)
                raise RuntimeError("injected proof failure")
    assert encoder.proc.poll() is not None
    assert not output.exists()
    assert not list(tmp_path.glob(".reelforge-encode-*"))
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


@pytest.mark.skipif(not NATIVE, reason="optional Cairo")
def test_proof_panel_material_clip_cannot_bleed_into_neighbor(tmp_path, monkeypatch):
    from pathlib import Path

    import cairo

    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.model import DrawPath, rectangle

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from review_environment_polish import render_panels

    renderer = CairoRenderer()
    overscan = DrawPath(
        rectangle(350, 0, 100, 640), color("ff0000"), clip=rectangle(350, 0, 100, 640)
    )
    neighbor = DrawPath(rectangle(0, 0, 360, 640), color("0000ff"))
    render_panels(
        renderer, tmp_path, "panels.png", (("", (overscan,)), ("", (neighbor,))), 2, labels=False
    )
    image = cairo.ImageSurface.create_from_png(str(tmp_path / "panels.png"))
    view = image.get_data()
    try:
        offset = 10 * image.get_stride() + 370 * 4
        assert bytes(view[offset : offset + 4]) == bytes((255, 0, 0, 255))
    finally:
        view.release()
        image.finish()
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
