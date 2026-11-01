"""Hostile inputs, conservative admission and integration for the geometry trust boundary."""

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from reelforge.core.errors import InputError, OperationError
from reelforge.geometry.compiler import compile_geometry, inspect_geometry, preview_scene
from reelforge.geometry.composition import compile_composition, validate_composition
from reelforge.geometry.contract import load_geometry, validate_geometry
from reelforge.geometry.schema import composition_schema, geometry_schema
from reelforge.scenes.assets import cost
from reelforge.scenes.contract import validate_scene
from reelforge.scenes.graph import compile_scene, evaluate_layers, scene_frame

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data():
    return {
        "schema_version": "geometry-0.1",
        "palette": {"metal": "#899b9e", "dark": "#1b3038", "shine": "#b8ad8480"},
        "assets": [
            {
                "id": "novel",
                "size": [100, 100],
                "anchors": {"origin": [50, 95]},
                "shapes": [{"type": "rect", "rect": [10, 10, 80, 80], "fill": "metal"}],
            }
        ],
    }


@pytest.fixture
def composition():
    return json.loads((ROOT / "examples/compositions/woodland_relay.json").read_text())


def shape(data):
    return data["assets"][0]["shapes"][0]


def rejected(data, code=None):
    with pytest.raises(InputError) as caught:
        validate_geometry(data)
    if code:
        assert caught.value.issue.code == code
    assert caught.value.issue.path.startswith("/") or caught.value.issue.path == ""
    return caught.value.issue


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "geometry-99"),
        (("palette",), []),
        (("assets",), []),
        (("assets", 0, "id"), "rowan_01"),
        (("assets", 0, "id"), "generated_sky"),
        (("assets", 0, "id"), "agent_ground"),
        (("assets", 0, "id"), "../../file"),
        (("assets", 0, "size"), [0, 100]),
        (("assets", 0, "size"), [100, 513]),
        (("assets", 0, "size"), [True, 100]),
        (("assets", 0, "anchors"), {}),
        (("assets", 0, "anchors"), {"origin": [101, 0]}),
        (("assets", 0, "shapes"), []),
        (("assets", 0, "shapes", 0, "type"), "svg"),
        (("assets", 0, "shapes", 0, "rect"), [0, 0, 0, 20]),
        (("assets", 0, "shapes", 0, "rect"), [0, 0, -1, 20]),
        (("assets", 0, "shapes", 0, "rect"), [0, 0, float("nan"), 20]),
        (("assets", 0, "shapes", 0, "rect"), [0, 0, float("inf"), 20]),
        (("assets", 0, "shapes", 0, "rect"), [0, 0, 10**1000, 20]),
        (("assets", 0, "shapes", 0, "fill"), "https://host/x"),
        (("palette", "metal"), "url(file:///secret)"),
        (("palette", "metal"), "#fff"),
        (("assets", 0, "shapes", 0, "stroke"), {"paint": "metal", "width": 0}),
        (("assets", 0, "shapes", 0, "stroke"), {"paint": "metal", "width": 13}),
        (("assets", 0, "shapes", 0, "stroke"), {"paint": "metal", "width": True}),
        (
            ("assets", 0, "shapes", 0, "fill"),
            {"linear": [0, 0, 0, 0], "stops": [[0, "metal"], [1, "dark"]]},
        ),
        (
            ("assets", 0, "shapes", 0, "fill"),
            {"linear": [0, 0, 0, 80], "stops": [[1, "metal"], [0, "dark"]]},
        ),
        (
            ("assets", 0, "shapes", 0, "fill"),
            {"linear": [0, 0, 0, 80], "stops": [[0, "metal"], [1, "missing"]]},
        ),
        (
            ("assets", 0, "shapes", 0, "fill"),
            {"linear": [0, 0, 0, 80], "stops": [[0.2, "metal"], [1, "dark"]]},
        ),
    ],
)
def test_invalid_numbers_materials_and_names(data, path, value):
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    issue = rejected(data)
    assert issue.path.startswith("/" + "/".join(str(k) for k in path[:-1]))


@pytest.mark.parametrize(
    "field", ["python", "exec", "import", "include", "url", "shader", "image", "support_envelope"]
)
@pytest.mark.parametrize("location", ["document", "asset", "shape"])
def test_unknown_fields_and_executable_payloads(data, field, location):
    target = (
        data
        if location == "document"
        else data["assets"][0]
        if location == "asset"
        else shape(data)
    )
    target[field] = '__import__("os").system("payload")'
    rejected(data)


@pytest.mark.parametrize(
    "path",
    [
        [["L", 1, 2], ["L", 3, 4]],
        [["M", 1, 1], ["Z"]],
        [["M", 1, 1], ["L", 1, 1]],
        [["M", 1, 1], ["C", 2, 2]],
        [["M", 1, 1], ["Q", 4, 4, 8, 8]],
        [["M", 1, 1], ["L", 5, 5], ["Z"], ["L", 6, 6]],
        [["M", 1, 1], ["L", 5, 5], ["M", 7, 7], ["L", 8, 8]],
        [["M", 1, 1], ["L", 3, 3], ["L", 6, 6], ["Z"]],
        [["M", 1, 1], ["L", 9, 1], ["L", 9, 9]],
    ],
)
def test_malformed_and_degenerate_filled_paths(data, path):
    data["assets"][0]["shapes"] = [{"type": "path", "path": path, "fill": "metal"}]
    rejected(data)


def test_bezier_open_stroke_and_multiple_closed_subpaths(data):
    data["assets"][0]["shapes"] = [
        {
            "type": "path",
            "path": [["M", 10, 10], ["C", 10, 30, 80, 30, 80, 10]],
            "stroke": {"paint": "metal", "width": 2},
        },
        {
            "type": "path",
            "path": [
                ["M", 10, 40],
                ["L", 40, 40],
                ["L", 40, 80],
                ["Z"],
                ["M", 60, 40],
                ["L", 90, 40],
                ["L", 90, 80],
                ["Z"],
            ],
            "fill": "dark",
        },
    ]
    g = compile_geometry(validate_geometry(data))[0]
    assert g.commands[0].path[1].kind == "C" and g.commands[0].fill is None
    assert [op.kind for op in g.commands[1].path].count("M") == 2


@pytest.mark.parametrize(
    "primitive,values,ops",
    [
        ("rect", [10, 10, 50, 50], 5),
        ("ellipse", [50, 50, 20, 30], 6),
        ("polygon", [[10, 10], [80, 20], [50, 80]], 4),
    ],
)
def test_primitive_expansion_is_exact(data, primitive, values, ops):
    data["assets"][0]["shapes"] = [
        {
            "type": primitive,
            "points" if primitive == "polygon" else primitive: values,
            "fill": "metal",
        }
    ]
    d = validate_geometry(data)
    g = compile_geometry(d)[0]
    assert cost(g.commands) == (1, ops) == (len(d.assets[0].shapes), d.assets[0].operations)


def test_gradient_clip_and_group_transform(data):
    child = {
        "type": "rect",
        "rect": [0, 0, 20, 20],
        "fill": {"linear": [0, 0, 0, 20], "stops": [[0, "metal"], [1, "dark"]]},
        "clip": [["M", 0, 0], ["L", 20, 0], ["L", 0, 20], ["Z"]],
    }
    data["assets"][0]["shapes"] = [
        {
            "type": "group",
            "transform": {"x": 30, "y": 20, "scale": 2, "rotation_degrees": 0},
            "shapes": [child],
        }
    ]
    d = validate_geometry(data)
    g = compile_geometry(d)[0]
    c = g.commands[0]
    assert c.transform.tx == 30 and c.transform.sx == 2
    assert c.clip is not None and c.fill.stops[1][0] == 1 and cost(g.commands) == (1, 9)
    data["assets"][0]["shapes"][0]["transform"]["rotation_degrees"] = 45
    d = validate_geometry(data)
    assert compile_geometry(d)[0].commands[0].transform.rotation > 0


@pytest.mark.parametrize(
    "bad",
    [
        {"x": 0, "y": 0, "scale": 1, "rotation_degrees": 0, "shear": 1},
        {"x": 0, "y": 0, "sx": 1, "sy": 2, "rotation_degrees": 0},
        {"x": 0, "y": 0, "scale": -1, "rotation_degrees": 0},
    ],
)
def test_unsupported_transforms_are_not_approximated(data, bad):
    shape(data)["transform"] = bad
    rejected(data)


def test_group_depth_counts_and_bounds(data):
    original = copy.deepcopy(shape(data))
    for _ in range(5):
        original = {"type": "group", "shapes": [original]}
    data["assets"][0]["shapes"] = [original]
    rejected(data, "GEOMETRY_BUDGET")
    data["assets"][0]["shapes"] = [
        {
            "type": "rect",
            "rect": [0, 0, 50, 50],
            "fill": "metal",
            "transform": {"x": 90, "y": 0, "scale": 1, "rotation_degrees": 0},
        }
    ]
    rejected(data, "GEOMETRY_BOUNDS")


def test_clip_must_be_closed_and_nondegenerate(data):
    shape(data)["clip"] = [["M", 0, 0], ["L", 20, 20]]
    rejected(data, "GEOMETRY_PATH")
    shape(data)["clip"] = [["M", 0, 0], ["L", 20, 20], ["L", 30, 30], ["Z"]]
    rejected(data, "GEOMETRY_DEGENERATE")


def test_asset_and_document_complexity_before_drawpath_allocation(data, monkeypatch):
    import reelforge.geometry.compiler as compiler

    def forbidden(*a, **k):
        raise AssertionError("DrawPath allocated during admission")

    monkeypatch.setattr(compiler, "DrawPath", forbidden)
    data["assets"][0]["shapes"] = [copy.deepcopy(shape(data)) for _ in range(129)]
    rejected(data, "GEOMETRY_BUDGET")
    data["assets"][0]["shapes"] = data["assets"][0]["shapes"][:128]
    template = copy.deepcopy(data["assets"][0])
    data["assets"] = [dict(template, id=f"asset_{i}") for i in range(5)]
    rejected(data, "GEOMETRY_BUDGET")


def test_operation_budget_and_clips_included(data):
    contour = (
        [["M", 10, 10]]
        + [["L", 90 if i % 2 else 10, 20 + i] for i in range(61)]
        + [["L", 90, 90], ["Z"]]
    )
    data["assets"][0]["shapes"] = [
        {"type": "path", "path": contour, "fill": "metal", "clip": contour} for _ in range(33)
    ]
    rejected(data, "GEOMETRY_BUDGET")


def test_strict_loader_rejects_duplicate_keys_overflow_nesting_size(tmp_path):
    for content in [
        '{"x":0,"x":1}',
        '{"x":NaN}',
        '{"x":1e999}',
        "[" * 40 + "0" + "]" * 40,
        " " * 1048577,
    ]:
        p = tmp_path / "bad.json"
        p.write_text(content)
        with pytest.raises(InputError):
            load_geometry(p)


def test_native_free_compiler_and_schema_in_fresh_interpreter(data):
    script = """import sys,json
from reelforge.geometry.contract import validate_geometry
from reelforge.geometry.compiler import inspect_geometry
from reelforge.geometry.schema import geometry_schema
print(json.dumps(inspect_geometry(validate_geometry(json.loads(sys.stdin.read())))))
assert 'cairo' not in sys.modules
assert 'subprocess' not in sys.modules
"""
    r = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps(data), capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["assets"][0]["private_id"] == "generated_agent_novel"


def test_all_examples_and_schema_roundtrip():
    import jsonschema

    for f in (ROOT / "examples/geometry").glob("*.json"):
        data = json.loads(f.read_text())
        jsonschema.Draft202012Validator(geometry_schema()).validate(data)
        d = validate_geometry(data)
        assert inspect_geometry(d) == inspect_geometry(validate_geometry(copy.deepcopy(data)))
    for f in (ROOT / "examples/compositions").glob("*.json"):
        data = json.loads(f.read_text())
        jsonschema.Draft202012Validator(composition_schema()).validate(data)
        c = compile_composition(validate_composition(data))
        assert len(c.scene.nodes) <= 64 and c.path_allowance <= 4096


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("asset", "missing", "GEOMETRY_REFERENCE"),
        ("anchor", "missing", "GEOMETRY_REFERENCE"),
        ("parent", "missing", "GEOMETRY_REFERENCE"),
        ("id", "rowan", "GEOMETRY_NAMESPACE"),
        ("visible", 1, "GEOMETRY_INVALID"),
        ("order", True, "GEOMETRY_INVALID"),
        ("order", 128, "GEOMETRY_INVALID"),
    ],
)
def test_bad_composition_references(composition, field, value, code):
    composition["instances"][0][field] = value
    with pytest.raises(InputError) as e:
        validate_composition(composition)
    assert e.value.issue.code == code and e.value.issue.path == f"/instances/0/{field}"


def test_repeated_instances_charge_cost_and_preserve_ids(composition):
    composition["instances"] = [
        composition["instances"][0],
        dict(composition["instances"][0], id="second"),
    ]
    c = validate_composition(composition)
    g = compile_composition(c)
    a = c.document.assets[0]
    assert g.path_allowance == c.base.path_allowance + len(a.shapes) * 2
    assert g.operation_allowance == c.base.operation_allowance + a.operations * 2
    assert sum(x.asset.id == "generated_agent_damaged_mast" for x in g.generated) == 1
    for f in (89, 0, 45, 0, 89):
        assert scene_frame(g, f) == scene_frame(compile_composition(c), f)


def test_aggregate_budget_rejects_before_generated_geometry(composition, monkeypatch):
    import reelforge.geometry.composition as module

    def forbidden(*a, **k):
        raise AssertionError("procedural geometry before admission")

    monkeypatch.setattr(module, "compile_plan", forbidden)
    composition["instances"] = [
        dict(composition["instances"][0], id=f"placed_{i}") for i in range(16)
    ]
    with pytest.raises(InputError) as e:
        validate_composition(composition)
    assert e.value.issue.code == "GEOMETRY_BUDGET"


def test_authored_ground_cannot_be_character_support(composition):
    composition["geometry"]["assets"][0]["support_envelope"] = [0, 0, 100, 100]
    with pytest.raises(InputError):
        validate_composition(composition)
    del composition["geometry"]["assets"][0]["support_envelope"]
    g = compile_composition(validate_composition(composition))
    assert all(
        a.asset.support_envelope is None
        for a in g.generated
        if a.asset.id.startswith("generated_agent_")
    )
    nodes = list(g.scene.nodes)
    index = next(i for i, n in enumerate(nodes) if n.id == "rowan")
    nodes[index] = replace(nodes[index], ground_id="relay")
    with pytest.raises(InputError):
        compile_scene(replace(g.scene, nodes=tuple(nodes)), generated=g.generated)


def test_scene_01_cannot_resolve_authored_namespace():
    d = json.loads((ROOT / "examples/scenes/rural_outpost.json").read_text())
    n = next(n for n in d["nodes"] if n["kind"] == "asset")
    n["asset_id"] = "generated_agent_novel"
    with pytest.raises(InputError):
        validate_scene(d)


def test_visibility_inheritance_and_layer_parallax(composition):
    c = compile_composition(validate_composition(composition))
    layers = evaluate_layers(c, 0)
    assert next(layer for layer in layers if "relay" in layer.instance_ids).depth == 1
    composition["instances"][0]["visible"] = False
    hidden = compile_composition(validate_composition(composition))
    assert "relay" not in tuple(
        i for layer in evaluate_layers(hidden, 45) for i in layer.instance_ids
    )
    assert scene_frame(c, 0) != scene_frame(c, 89)


@pytest.mark.skipif(importlib.util.find_spec("cairo") is None, reason="optional Cairo backend")
def test_pixel_determinism_all_assets_and_material_clip(data):
    from reelforge.geometry.contract import load_geometry
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    r = CairoRenderer()
    doc = load_geometry(ROOT / "examples/geometry/survival_objects.json")
    for a in doc.assets:
        c = preview_scene(doc, a.id)
        seen = {}
        for f in (89, 0, 45, 0, 89):
            with r.surface(720, 1280) as surface:
                r.draw(
                    surface, scene_frame(c, f), background=color("243e49"), logical_size=(360, 640)
                )
                sha = surface.pixel_sha256()
                assert f not in seen or seen[f] == sha
                seen[f] = sha
    assert r.active_surfaces == r.allocated_bytes == 0


def test_rejected_input_never_imports_native_or_creates_artifact(
    tmp_path, composition, monkeypatch
):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import geometry as tool

    composition["instances"][0]["parent"] = "missing"
    manifest = tmp_path / "bad.json"
    manifest.write_text(json.dumps(composition))
    output = tmp_path / "never" / "job"
    with pytest.raises(InputError):
        tool.render_file(manifest, output)
    assert not output.parent.exists()


@pytest.mark.skipif(
    importlib.util.find_spec("cairo") is None or shutil.which("ffmpeg") is None,
    reason="optional Cairo/FFmpeg integration",
)
def test_existing_output_protection_and_failed_encoder_cleanup(tmp_path, composition, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import geometry as tool

    import reelforge.media.encoder as media
    from reelforge.rendering.backends.cairo import CairoRenderer

    manifest = tmp_path / "composition.json"
    manifest.write_text(json.dumps(composition))
    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "scene.mp4").write_bytes(b"existing")
    with pytest.raises(OperationError) as e:
        tool.render_file(manifest, keep)
    assert e.value.code == "OUTPUT_EXISTS" and (keep / "scene.mp4").read_bytes() == b"existing"
    original = media.encoder_command
    constructor = media.FFmpegEncoder
    children = []
    renderer = CairoRenderer()

    def capture(*a, **kw):
        child = constructor(*a, **kw)
        children.append(child)
        return child

    def broken(*a, **kw):
        cmd = original(*a, **kw)
        return [cmd[0], "-invalid-geometry-test-option", *cmd[1:]]

    monkeypatch.setattr(media, "encoder_command", broken)
    monkeypatch.setattr(media, "FFmpegEncoder", capture)
    monkeypatch.setattr("reelforge.rendering.backends.cairo.CairoRenderer", lambda: renderer)
    out = tmp_path / "failed"
    with pytest.raises(OperationError):
        tool.render_file(manifest, out)
    assert children[0].proc.poll() is not None and not (out / "scene.mp4").exists()
    assert not list(out.glob(".reelforge-*")) and renderer.active_surfaces == 0


def test_resource_cancellation_prevents_native_render(tmp_path, composition, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import geometry as tool

    class Cancel:
        def __init__(self, **kw):
            self.cancelled = Event()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def sample(self):
            self.cancelled.set()

    monkeypatch.setattr("reelforge.resources.monitor.JobMonitor", Cancel)
    f = tmp_path / "c.json"
    f.write_text(json.dumps(composition))
    with pytest.raises(OperationError) as e:
        tool.render_file(f, tmp_path / "cancelled")
    assert e.value.code == "GEOMETRY_RESOURCE" and not (tmp_path / "cancelled").exists()


@pytest.mark.parametrize("mode", ["assets", "palette", "anchors", "duplicate", "gradient_stops"])
def test_additional_document_caps(data, mode):
    if mode == "assets":
        data["assets"] = [dict(data["assets"][0], id=f"part_{i}") for i in range(9)]
    elif mode == "palette":
        data["palette"] = {f"color_{i}": "#112233" for i in range(33)}
    elif mode == "anchors":
        data["assets"][0]["anchors"] = {
            "origin": [0, 0],
            **{f"anchor_{i}": [0, 0] for i in range(8)},
        }
    elif mode == "duplicate":
        data["assets"].append(copy.deepcopy(data["assets"][0]))
    else:
        shape(data)["fill"] = {
            "linear": [0, 0, 0, 80],
            "stops": [[i / 8, "metal"] for i in range(9)],
        }
    rejected(data)


def test_ir_is_immutable_and_independent_of_input(data):
    from dataclasses import FrozenInstanceError

    doc = validate_geometry(data)
    before = inspect_geometry(doc)
    shape(data)["rect"][0] = 75
    assert inspect_geometry(doc) == before
    with pytest.raises(FrozenInstanceError):
        doc.assets = ()


def test_unknown_asset_preview_is_actionable(data):
    with pytest.raises(InputError) as e:
        preview_scene(validate_geometry(data), "missing")
    assert e.value.issue.code == "GEOMETRY_REFERENCE"


@pytest.mark.skipif(
    importlib.util.find_spec("cairo") is None or shutil.which("ffmpeg") is None,
    reason="optional Cairo/FFmpeg integration",
)
def test_interruption_reaps_encoder_and_releases_surface(tmp_path, composition, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import geometry as tool

    import reelforge.media.encoder as media
    from reelforge.rendering.backends.cairo import CairoRenderer

    ctor = media.FFmpegEncoder
    children = []
    renderer = CairoRenderer()

    def capture(*a, **kw):
        e = ctor(*a, **kw)
        children.append(e)
        return e

    def interrupted(*a, **kw):
        raise KeyboardInterrupt("controlled interruption")

    monkeypatch.setattr(media, "FFmpegEncoder", capture)
    monkeypatch.setattr("reelforge.rendering.backends.cairo.CairoRenderer", lambda: renderer)
    monkeypatch.setattr(renderer, "draw", interrupted)
    manifest = tmp_path / "c.json"
    manifest.write_text(json.dumps(composition))
    out = tmp_path / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        tool.render_file(manifest, out)
    assert children[0].proc.poll() is not None and not (out / "scene.mp4").exists()
    assert (
        not list(out.glob(".reelforge-*"))
        and renderer.active_surfaces == renderer.allocated_bytes == 0
    )


@pytest.mark.skipif(importlib.util.find_spec("cairo") is None, reason="optional Cairo backend")
def test_native_clip_gradient_and_order_have_visible_effect(data):
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    shape(data)["fill"] = {"linear": [0, 0, 0, 100], "stops": [[0, "metal"], [1, "dark"]]}
    shape(data)["clip"] = [["M", 10, 10], ["L", 90, 10], ["L", 10, 90], ["Z"]]
    renderer = CairoRenderer()
    hashes = []
    for clipped in (True, False):
        d = copy.deepcopy(data)
        if not clipped:
            del shape(d)["clip"]
        commands = compile_geometry(validate_geometry(d))[0].commands
        with renderer.surface(100, 100) as surface:
            renderer.draw(surface, commands, background=color("243e49"), logical_size=(100, 100))
            hashes.append(surface.pixel_sha256())
    assert hashes[0] != hashes[1]
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_cleanup_failure_is_not_a_successful_render(tmp_path, composition, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import geometry as tool
    import scene

    def rejected(compiled, output, **kw):
        output.mkdir()
        return {
            "success": False,
            "cleanup_error": {"code": "TRANSACTION_CLEANUP", "message": "controlled restoration"},
        }

    monkeypatch.setattr(scene, "render_scene", rejected)
    f = tmp_path / "c.json"
    f.write_text(json.dumps(composition))
    out = tmp_path / "cleanup-failed"
    with pytest.raises(OperationError) as e:
        tool.render_file(f, out)
    assert e.value.code == "TRANSACTION_CLEANUP"
    assert (out / "geometry_job.json").exists()
