"""Phase 3B: contract, independent geometry/camera invariants and native lifecycle."""

import importlib.util
import math
from dataclasses import replace

import pytest

from reelforge.environments.presets import EnvironmentPreset, load_preset
from reelforge.environments.scene import (
    Camera,
    camera_at,
    environment_frame,
    layers_at,
    transform_command,
)
from reelforge.rendering.diagnostic import color
from reelforge.rendering.model import DrawPath, RenderError, Transform, rectangle


def test_example():
    assert load_preset("examples/environments/orchard_push.json") == EnvironmentPreset()


@pytest.mark.parametrize(
    "key,value",
    [
        ("environment", "barn"),
        ("shot", "fly"),
        ("warmth", True),
        ("breeze", math.nan),
        ("atmosphere", -0.01),
        ("framing", 1.01),
        ("warmth", 1.1),
        ("breeze", "slow"),
    ],
)
def test_bounds(key, value):
    with pytest.raises(RenderError):
        replace(EnvironmentPreset(), **{key: value})


@pytest.mark.parametrize("data", [{}, {"extra": 1}, [], None])
def test_unknown_missing(data):
    with pytest.raises(RenderError):
        EnvironmentPreset.from_data(data)


@pytest.mark.parametrize("frame", [-1, 180, True, 0.5])
def test_frame_bounds(frame):
    with pytest.raises(RenderError):
        environment_frame(frame)


def test_painter_order_and_occlusion():
    layers = layers_at(EnvironmentPreset(), 90)
    assert [x.id for x in layers] == [
        "sky",
        "hills",
        "ground",
        "orchard",
        "barn",
        "fence_props",
        "door_light",
        "rowan",
        "foreground",
        "edge_grade",
    ]
    assert len(environment_frame(90)) < 1800
    assert next(x.depth for x in layers if x.id == "foreground") > 1


def test_transform_composition_numeric():
    cmd = DrawPath(rectangle(0, 0, 5, 5), color("ffffff"), transform=Transform(10, 20, 0.3, 2, 3))
    out = transform_command(cmd, Transform(4, 5, sx=1.2, sy=1.2))
    assert (
        out.transform.tx,
        out.transform.ty,
        out.transform.rotation,
        out.transform.sx,
        out.transform.sy,
    ) == pytest.approx((16, 29, 0.3, 2.4, 3.6))
    with pytest.raises(RenderError):
        transform_command(cmd, Transform(rotation=0.1))


def test_camera_parallax_ground_anchor():
    camera = Camera(10, 0, 1.1)
    for d in (0, 0.18, 0.72, 1, 1.4):
        t = camera.transform(d)
        assert t.tx + 180 * t.sx == pytest.approx(180 - 10 * d)
        assert t.ty + 400 * t.sy == pytest.approx(400)
    assert camera.transform(0) == Transform()
    assert camera.transform(1).sx == camera.transform(1).sy
    # Character, contact plane and props use the identical camera transform.
    layers = layers_at(EnvironmentPreset(), 60)
    assert {x.depth for x in layers if x.id in ("rowan", "ground", "fence_props")} == {1}


@pytest.mark.parametrize("shot", ["locked", "orchard_pan", "orchard_push"])
def test_camera_determinism(shot):
    preset = EnvironmentPreset(shot=shot)
    a = camera_at(preset, 90)
    camera_at(preset, 179)
    assert a == camera_at(preset, 90)
    assert environment_frame(17, preset) == environment_frame(17, preset)
    assert camera_at(preset, 0).zoom <= camera_at(preset, 179).zoom


def test_layer_selection_and_parameter_effects():
    a = EnvironmentPreset()
    for key in ("atmosphere", "warmth", "breeze", "framing"):
        assert environment_frame(90, a) != environment_frame(90, replace(a, **{key: 1}))
    assert environment_frame(0, a, only_layer="sky") == environment_frame(179, a, only_layer="sky")
    with pytest.raises(RenderError):
        environment_frame(0, a, only_layer="unknown")


@pytest.mark.skipif(importlib.util.find_spec("cairo") is None, reason="optional Cairo")
def test_repeated_render_and_exception_cleanup():
    from reelforge.rendering.backends.cairo import CairoRenderer

    renderer = CairoRenderer()
    hashes = {}
    with renderer.surface(360, 640) as surface:
        for index in (0, 90, 179, 90, 0) * 3:
            renderer.draw(
                surface,
                environment_frame(index),
                background=color("243e49"),
                logical_size=(360, 640),
            )
            digest = surface.pixel_sha256()
            assert hashes.setdefault(index, digest) == digest
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    with pytest.raises(RenderError), renderer.surface(360, 640) as surface:
        environment_frame(180)
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
