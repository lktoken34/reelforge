"""Scene graph contracts, bounded topology, transform/material math and pipeline integration."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from reelforge.core.errors import InputError, OperationError
from reelforge.rendering.model import DrawPath, Transform
from reelforge.scenes import assets, graph
from reelforge.scenes.contract import load_scene, validate_scene
from reelforge.scenes.schema import scene_schema
from reelforge.scenes.transforms import Placement

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data():
    return json.loads((ROOT / "examples/scenes/rural_outpost.json").read_text())


def change(data, path, value):
    obj = data
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "story-0.2"),
        (("title",), ""),
        (("title",), " " * 120 + "x"),
        (("output", "frames"), True),
        (("output", "frames"), 29),
        (("output", "frames"), 181),
        (("output", "fps"), 30.0),
        (("output", "width"), 360),
        (("output", "codec"), "h265"),
        (("output", "pixel_format"), "rgba"),
        (("camera",), "eval(1)"),
        (("camera",), []),
        (("art_direction", "breeze"), float("nan")),
        (("art_direction", "warmth"), float("inf")),
        (("art_direction", "atmosphere"), True),
        (("nodes", 0, "id"), "../root"),
        (("nodes", 0, "kind"), "python"),
        (("nodes", 0, "visible"), 1),
        (("nodes", 0, "order"), 1.0),
        (("nodes", 0, "order"), -1),
        (("nodes", 0, "transform", "x"), True),
        (("nodes", 1, "transform", "x"), float("nan")),
        (("nodes", 1, "transform", "y"), 1281),
        (("nodes", 1, "transform", "x"), -721),
        (("nodes", 1, "transform", "scale"), 0),
        (("nodes", 1, "transform", "scale"), -1),
        (("nodes", 1, "transform", "scale"), [1, 2]),
        (("nodes", 1, "transform", "rotation_degrees"), 46),
        (("nodes", 1, "depth"), 1.51),
        (("nodes", 1, "depth"), True),
        (("nodes", 2, "asset_id"), "../image.png"),
        (("nodes", 2, "asset_id"), "no_asset"),
        (("nodes", 2, "asset_id"), "barn_01"),
        (("nodes", 2, "variant"), "new_texture"),
        (("nodes", 0, "parent"), "sky"),
        (("nodes", 1, "parent"), None),
        (("nodes", 9, "character", "action"), "walk"),
        (("nodes", 9, "character", "action"), "run"),
    ],
)
def test_strict_fields(data, path, value):
    change(data, path, value)
    with pytest.raises(InputError) as caught:
        validate_scene(data)
    assert caught.value.issue.path.startswith("/" + str(path[0]))


@pytest.mark.parametrize(
    "path", [(), ("output",), ("art_direction",), ("nodes", 0), ("nodes", 1, "transform")]
)
def test_unknown_fields_are_rejected(data, path):
    obj = data
    for key in path:
        obj = obj[key]
    obj["executable"] = "ffmpeg -i private"
    with pytest.raises(InputError):
        validate_scene(data)


def test_huge_integer_is_actionable_not_overflow(data):
    data["nodes"][1]["transform"]["x"] = 10**1000
    with pytest.raises(InputError):
        validate_scene(data)


@pytest.mark.parametrize("which", ["rural_outpost", "tree_path", "barn_approach"])
def test_examples_compile_and_match_published_schema(which):
    import jsonschema

    data = json.loads((ROOT / f"examples/scenes/{which}.json").read_text())
    jsonschema.Draft202012Validator(scene_schema()).validate(data)
    c = graph.compile_scene(validate_scene(data))
    for frame in (0, c.scene.frames // 2, c.scene.frames - 1):
        paths, ops = assets.cost(graph.scene_frame(c, frame))
        assert 0 < paths <= c.path_allowance <= 4096
        assert 0 < ops <= c.operation_allowance <= 80000


@pytest.mark.parametrize(
    "kind", ["cycle", "duplicate", "missing_parent", "second_root", "nested_layer", "unlayered"]
)
def test_topology_rejection(data, kind):
    if kind == "cycle":
        data["nodes"][-1]["parent"] = data["nodes"][-1]["id"]
    elif kind == "duplicate":
        data["nodes"][-1]["id"] = data["nodes"][2]["id"]
    elif kind == "missing_parent":
        data["nodes"][-1]["parent"] = "missing"
    elif kind == "second_root":
        data["nodes"].append(dict(data["nodes"][0], id="second"))
    elif kind == "nested_layer":
        data["nodes"][3]["parent"] = "sky_layer"
    else:
        data["nodes"][2]["parent"] = "root"
    with pytest.raises(InputError) as caught:
        validate_scene(data)
    assert caught.value.issue.path.startswith("/nodes")


def test_depth_limit(data):
    for i in range(9):
        n = copy.deepcopy(data["nodes"][0])
        n.update(id=f"group_{i}", kind="group", parent="root" if i == 0 else f"group_{i - 1}")
        data["nodes"].append(n)
    with pytest.raises(InputError, match="depth"):
        validate_scene(data)


@pytest.mark.parametrize(
    "kind",
    ["nodes", "instances", "layers", "paths", "world_scale", "world_position", "world_rotation"],
)
def test_expansion_budgets(data, kind):
    if kind in ("nodes", "instances", "paths"):
        prototype = next(n for n in data["nodes"] if n["id"] == "building")
        for i in range({"nodes": 65, "instances": 33, "paths": 17}[kind]):
            data["nodes"].append(dict(prototype, id=f"copy_{i}", visible=False))
    elif kind == "layers":
        prototype = data["nodes"][1]
        for i in range(9):
            data["nodes"].append(dict(prototype, id=f"layer_{i}"))
    else:
        group = next(n for n in data["nodes"] if n["id"] == "outpost")
        child = next(n for n in data["nodes"] if n["id"] == "building")
        if kind == "world_scale":
            group["transform"]["scale"] = child["transform"]["scale"] = 2
        elif kind == "world_position":
            group["transform"].update(x=720, scale=2)
            child["transform"]["x"] = 720
        else:
            # Three nested +45 degree groups exceed the composed +/-90 degree budget.
            for i in range(3):
                n = copy.deepcopy(data["nodes"][0])
                n.update(id=f"g{i}", kind="group", parent="structures" if i == 0 else f"g{i - 1}")
                n["transform"]["rotation_degrees"] = 45
                data["nodes"].append(n)
            child["parent"] = "g2"
    with pytest.raises(InputError) as caught:
        validate_scene(data)
    assert caught.value.issue.code == "SCENE_BUDGET"


def test_upright_ground_and_character_reject_effective_rotation(data):
    for name in ("rowan", "ground", "sky"):
        d = copy.deepcopy(data)
        next(n for n in d["nodes"] if n["id"] == name)["transform"]["rotation_degrees"] = 1
        with pytest.raises(InputError, match="zero composed rotation"):
            validate_scene(d)


def test_same_asset_has_independent_instances_and_static_attachments(data):
    original = next(n for n in data["nodes"] if n["id"] == "building")
    data["nodes"].append(dict(original, id="attached_barn", parent="building"))
    c = graph.compile_scene(validate_scene(data))
    assert c.painter_ids.index("attached_barn") == c.painter_ids.index("building") + 1
    a, b = (next(n for n in c.hierarchy if n.id == x) for x in ("building", "attached_barn"))
    assert a.world == b.world


def test_reordered_json_preserves_traversal_and_geometry(data):
    first = graph.compile_scene(validate_scene(data))
    data["nodes"].reverse()
    second = graph.compile_scene(validate_scene(data))
    assert first.hierarchy == second.hierarchy and first.painter_ids == second.painter_ids
    assert graph.scene_frame(first, 45) == graph.scene_frame(second, 45)


def test_visibility_is_inherited_without_bypassing_budget(data):
    next(n for n in data["nodes"] if n["id"] == "outpost")["visible"] = False
    c = graph.compile_scene(validate_scene(data))
    emitted = [id for layer in graph.evaluate_layers(c, 0) for id in layer.instance_ids]
    assert "building" not in emitted and "gate" not in emitted and "rowan" in emitted
    assert c.path_allowance > sum(len(layer.commands) for layer in graph.evaluate_layers(c, 0))


def test_camera_parallax_and_character_ground_origin(data):
    c = graph.compile_scene(validate_scene(data))
    before = graph.inspect_scene(c, 0)
    after = graph.inspect_scene(c, 89)
    world = next(n.world for n in c.hierarchy if n.id == "rowan")
    assert before["character_ground_contacts"]["rowan"]["world"] == [world.x, world.y]
    camera = graph.camera_at(c, 89)
    sky = camera.transform(0)
    near = camera.transform(1.4)
    assert (sky.tx, sky.ty, sky.sx) == (0, 0, 1)
    assert near.tx != 0 and near.sx > 1
    assert before["character_ground_contacts"] != after["character_ground_contacts"]
    commands = graph.scene_frame(c, 89)
    assert commands


@pytest.mark.parametrize("frame", [-1, 90, 1.0, True])
def test_frame_bounds(data, frame):
    with pytest.raises(InputError):
        graph.scene_frame(graph.compile_scene(validate_scene(data)), frame)


def test_validation_compilation_never_constructs_cairo(data):
    script = """import sys,json
from reelforge.scenes.contract import validate_scene
from reelforge.scenes.graph import compile_scene
compile_scene(validate_scene(json.loads(sys.stdin.read())))
assert 'cairo' not in sys.modules
assert 'reelforge.rendering.backends.cairo' not in sys.modules
print('native-free')"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(data),
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "native-free"


def test_all_examples_avoid_complete_orchard_composition(monkeypatch):
    from reelforge.environments import scene

    def forbidden(*args, **kwargs):
        raise AssertionError("whole orchard composition called")

    monkeypatch.setattr(scene, "compose_layers", forbidden)
    for file in (ROOT / "examples/scenes").glob("*.json"):
        assert graph.scene_frame(graph.compile_scene(load_scene(file)), 0)


@pytest.mark.parametrize("angle", [0, 0.2, -0.6])
def test_parent_child_matrix_and_material_preservation(angle):
    from reelforge.environments.artwork import gradient
    from reelforge.rendering.diagnostic import color
    from reelforge.rendering.model import Stroke, rectangle

    parent = Placement(21, 37, 1.4, angle)
    child = Placement(13, -8, 0.6, 0.1)
    p = parent.compose(child)
    x, y = child.point(9, 17)
    assert p.point(9, 17) == pytest.approx(parent.point(x, y))
    clip = rectangle(0, 0, 9, 10)
    paint = gradient(color("ddaa88", 0.5), color("222233", 0.2), 0, 10)
    command = DrawPath(
        rectangle(0, 0, 10, 10),
        paint,
        Stroke(color("eeeeee", 0.4), 1.2),
        Transform(3, 4, 0.2, -0.8, 1.3),
        clip,
    )
    result = parent.command(command)
    assert result.path is command.path and result.clip is command.clip
    assert result.fill is paint and result.stroke is command.stroke
    assert (result.transform.tx, result.transform.ty) == pytest.approx(parent.point(3, 4))
    assert result.transform.sx == pytest.approx(-1.12) and result.transform.sy == pytest.approx(
        1.82
    )
    assert result.transform.rotation == pytest.approx(angle + 0.2)


def test_trusted_recipe_overrun_is_detected(monkeypatch, data):
    original = assets.art.fence

    def expanded():
        return original() * 40

    monkeypatch.setattr(assets.art, "fence", expanded)
    with pytest.raises(ValueError, match="envelope"):
        graph.scene_frame(graph.compile_scene(validate_scene(data)), 0)


def test_pixel_consistency_out_of_order_and_flattened_rotation(data):
    cairo = pytest.importorskip("cairo")
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    renderer = CairoRenderer()
    c = graph.compile_scene(validate_scene(data))
    hashes = {}
    for frame in (45, 0, 89, 45, 0):
        with renderer.surface(720, 1280) as surface:
            renderer.draw(
                surface,
                graph.scene_frame(c, frame),
                background=color("243e49"),
                logical_size=(360, 640),
            )
            digest = surface.pixel_sha256()
            assert frame not in hashes or hashes[frame] == digest
            hashes[frame] = digest
    # Independent native CTM oracle for transformed clips, alpha, gradients and strokes.
    from reelforge.environments.artwork import gradient
    from reelforge.rendering.model import Stroke, rectangle

    cmd = DrawPath(
        rectangle(0, 0, 40, 50),
        gradient(color("ddaa88", 0.7), color("442222", 0.3), 0, 50),
        Stroke(color("ffffff", 0.8), 2),
        Transform(4, 2, 0.13, 1.1, 0.8),
        rectangle(1, 2, 30, 40),
    )
    parent = Placement(90, 100, 1.5, 0.32)
    native = cairo.ImageSurface(cairo.FORMAT_ARGB32, 360, 640)
    context = cairo.Context(native)
    context.set_antialias(cairo.ANTIALIAS_GRAY)
    context.set_tolerance(0.1)
    context.translate(parent.x, parent.y)
    context.rotate(parent.angle)
    context.scale(parent.scale, parent.scale)
    renderer._draw_path(context, cmd)
    with renderer.surface(360, 640) as surface:
        renderer.draw(
            surface, (parent.command(cmd),), background=color("000000", 0), logical_size=(360, 640)
        )
        actual = bytes(surface._open().get_data())
        expected = bytes(native.get_data())
        assert max(abs(a - b) for a, b in zip(actual, expected, strict=True)) <= 1
    context = None
    native.finish()
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_scene_render_failure_reaps_encoder_and_surfaces(tmp_path, monkeypatch, data):
    pytest.importorskip("cairo")
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import scene as tool

    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.rendering.backends.cairo import CairoRenderer

    output = tmp_path / "failed"
    renderer = CairoRenderer()
    encoders = []

    def capture(*args, **kwargs):
        e = FFmpegEncoder(*args, **kwargs)
        encoders.append(e)
        return e

    original = tool.scene_frame

    def fail(compiled, frame):
        if frame == 1:
            raise OperationError("INJECTED", "controlled scene failure")
        return original(compiled, frame)

    monkeypatch.setattr("reelforge.rendering.backends.cairo.CairoRenderer", lambda: renderer)
    monkeypatch.setattr("reelforge.media.encoder.FFmpegEncoder", capture)
    monkeypatch.setattr(tool, "scene_frame", fail)
    with pytest.raises(OperationError, match="controlled scene failure"):
        tool.render_scene(graph.compile_scene(validate_scene(data)), output)
    assert encoders and encoders[0].proc.poll() is not None
    assert not (output / "scene.mp4").exists()
    assert not list(output.glob(".reelforge-encode-*"))
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


@pytest.mark.parametrize("filename", ["scene.mp4", "frame_000.png", "render_report.json", None])
def test_scene_render_refuses_existing_output(tmp_path, data, monkeypatch, filename):
    pytest.importorskip("cairo")
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import scene as tool

    output = tmp_path / "existing"
    output.mkdir()
    prior = output / filename if filename else None
    if prior is not None:
        prior.write_bytes(b"prior success")
    with pytest.raises(OperationError) as caught:
        tool.render_scene(graph.compile_scene(validate_scene(data)), output)
    assert caught.value.code == "OUTPUT_EXISTS"
    if prior is not None:
        assert prior.read_bytes() == b"prior success"
    else:
        assert not list(output.iterdir())


def test_cli_invalid_data_creates_no_render_directory(tmp_path):
    output = tmp_path / "never"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/scene.py"),
            "render",
            str(ROOT / "examples/stories/last_farm.json"),
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and not output.exists()
    issue = json.loads(result.stdout)["issue"]
    assert issue["path"] == "" and issue["code"] == "SCENE_INVALID"
    assert "Missing fields" in issue["message"]


@pytest.mark.parametrize("asset", assets.ASSETS, ids=lambda a: a.id)
def test_every_registered_variant_stays_inside_its_envelope(asset):
    from reelforge.characters.presets import CharacterPreset

    for variant in asset.variants:
        for t in (0, 2.5, 5.966666666666667):
            commands = assets.recipe(asset, variant, 1, 1, 1, t, CharacterPreset(action="react"))
            paths, ops = assets.cost(commands)
            assert paths <= asset.max_paths and ops <= asset.max_ops


@pytest.mark.parametrize("action", ["idle", "look_around", "react"])
def test_sole_ground_contact_after_parent_and_camera(data, action):
    from reelforge.characters.presets import SKELETON, sample_pose

    actor = next(n for n in data["nodes"] if n["id"] == "rowan")
    actor["character"].update(action=action, direction="left")
    c = graph.compile_scene(validate_scene(data))
    node = next(n for n in c.scene.nodes if n.id == "rowan")
    r = next(n for n in c.hierarchy if n.id == "rowan")
    for frame in (0, 23, 45, 89):
        skeleton = SKELETON.evaluate(sample_pose(node.character, frame / 30, travel=False))
        ys = []
        camera = graph.camera_at(c, frame).transform(r.depth)
        ground = camera.ty + camera.sy * r.world.y
        for side in ("near", "far"):
            for point in ((-8, 10), (19, 10)):
                x, y = skeleton[side + "_foot"].point(point)
                _, world_y = r.world.point(x, y)
                ys.append(camera.ty + camera.sy * world_y)
        assert max(ys) <= ground + 1e-7
        assert max(ys) == pytest.approx(ground, abs=1e-7)


def test_parent_rotation_can_be_explicitly_counter_rotated(data):
    group = copy.deepcopy(data["nodes"][0])
    group.update(id="rotated_parent", kind="group", parent="people")
    group["transform"]["rotation_degrees"] = 20
    data["nodes"].append(group)
    actor = next(n for n in data["nodes"] if n["id"] == "rowan")
    actor["parent"] = "rotated_parent"
    actor["transform"]["rotation_degrees"] = -20
    c = graph.compile_scene(validate_scene(data))
    assert next(n.world.angle for n in c.hierarchy if n.id == "rowan") == pytest.approx(0)


def test_real_scene_stream_decode_and_budget(tmp_path, data, monkeypatch):
    pytest.importorskip("cairo")
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import scene as tool

    data["nodes"] = data["nodes"][:3]  # Explicit static sky-only scene is legal.
    data["output"]["frames"] = 30
    result = tool.render_scene(graph.compile_scene(validate_scene(data)), tmp_path / "encoded")
    assert result["success"] and result["cleanup_error"] is None
    assert result["verification"]["decoded_frames"] == 30
    streams = result["verification"]["metadata"]["streams"]
    assert len(streams) == 1 and streams[0]["codec_name"] == "h264"
    assert streams[0]["width"] == 720 and streams[0]["height"] == 1280
    assert streams[0]["pix_fmt"] == "yuv420p"
    assert result["memory"]["job_budget_bytes"] == 256 * 1024**2
    assert result["memory"]["reserve_bytes"] == 64 * 1024**2
    assert result["memory"]["memory_policy"] == "strict"
    assert result["live_surfaces_after"] == result["surface_bytes_after"] == 0


@pytest.mark.parametrize("case", ["missing", "wrong_asset", "depth", "hidden", "outside"])
def test_explicit_supporting_ground_rejection(data, case):
    actor = next(n for n in data["nodes"] if n["id"] == "rowan")
    floor = next(n for n in data["nodes"] if n["id"] == "ground")
    if case == "missing":
        actor["ground_id"] = "missing"
    elif case == "wrong_asset":
        actor["ground_id"] = "sky"
    elif case == "depth":
        next(n for n in data["nodes"] if n["id"] == "people")["depth"] = 0.7
    elif case == "hidden":
        floor["visible"] = False
    else:
        actor["transform"]["x"] = -700
    with pytest.raises(InputError) as caught:
        validate_scene(data)
    assert caught.value.issue.path.endswith("/ground_id")


def test_ground_binding_uses_registered_support_metadata_not_asset_name(data, monkeypatch):
    from dataclasses import replace

    original = assets.asset_by_id("orchard_ground_01")
    alternate = replace(original, id="other_trusted_floor")
    monkeypatch.setattr(assets, "ASSETS", (*assets.ASSETS, alternate))
    next(n for n in data["nodes"] if n["id"] == "ground")["asset_id"] = alternate.id
    assert graph.compile_scene(validate_scene(data)).painter_ids
