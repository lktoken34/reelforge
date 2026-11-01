"""Environment request validation, independent streams, sealed geometry and supervised rendering."""

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Event

import pytest

from reelforge.core.errors import InputError, OperationError
from reelforge.procedural import compiler, planning
from reelforge.procedural.contract import FAMILIES, load_environment, validate_environment
from reelforge.procedural.schema import environment_schema
from reelforge.rendering.model import DrawPath, RenderError, rectangle
from reelforge.scenes.assets import Asset, cost
from reelforge.scenes.contract import load_scene, validate_scene
from reelforge.scenes.geometry import GeneratedGeometry
from reelforge.scenes.graph import compile_scene, evaluate_layers, inspect_scene, scene_frame

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def data():
    return json.loads((ROOT / "examples/procedural/woodland_trail_417.json").read_text())


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "scene-0.1"),
        (("family",), "orchard"),
        (("family",), None),
        (("seed",), -1),
        (("seed",), 2**32),
        (("seed",), 1.0),
        (("seed",), True),
        (("seed",), "exec(1)"),
        (("title",), " " * 121),
        (("title",), ""),
        (("composition", "density"), 0),
        (("composition", "density"), 4),
        (("composition", "density"), True),
        (("composition", "path_alignment"), -1.01),
        (("composition", "path_alignment"), float("inf")),
        (("composition", "structure"), float("nan")),
        (("composition", "framing"), False),
        (("composition", "framing"), 1.1),
        (("composition", "detail"), "unbounded"),
        (("art_direction", "lighting"), "shader.py"),
        (("art_direction", "atmosphere"), 2),
        (("rowan", "enabled"), 1),
        (("rowan", "action"), "run"),
        (("rowan", "action"), "invented"),
        (("rowan", "side"), "../asset"),
    ],
)
def test_invalid_parameters_are_actionable(data, path, value):
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InputError) as caught:
        validate_environment(data)
    assert caught.value.issue.path == "/" + "/".join(path)
    assert caught.value.issue.code == "ENVIRONMENT_INVALID"


@pytest.mark.parametrize("path", [(), ("composition",), ("art_direction",), ("rowan",)])
def test_unknown_fields_and_executable_payloads(data, path):
    target = data
    for key in path:
        target = target[key]
    target["python"] = '__import__("os").system("anything")'
    with pytest.raises(InputError):
        validate_environment(data)


def test_strict_loader_rejects_duplicate_nan_nesting_and_oversize(tmp_path, data):
    for payload in (
        '{"seed":1,"seed":2}',
        json.dumps(data).replace("0.7", "NaN"),
        "[" * 40 + "0" + "]" * 40,
        " " * 1048577,
    ):
        file = tmp_path / "invalid.json"
        file.write_text(payload)
        with pytest.raises(InputError):
            load_environment(file)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("density", [1, 2, 3])
@pytest.mark.parametrize("detail", ["standard", "rich"])
@pytest.mark.parametrize("lighting", ["dusk", "overcast"])
def test_geometry_envelopes_all_family_extremes(data, family, density, detail, lighting):
    data["family"] = family
    data["composition"].update(density=density, detail=detail)
    data["art_direction"]["lighting"] = lighting
    r = validate_environment(data)
    for seed in (0, 417, 2**32 - 1):
        plan, c = compiler.compile_environment(replace(r, seed=seed))
        assert len(c.scene.nodes) == plan.node_allowance <= 64
        assert len(c.generated) + 1 == plan.instance_allowance <= 32
        assert c.path_allowance == plan.path_allowance <= 4096
        assert c.operation_allowance == plan.operation_allowance <= 80000
        for g in c.generated:
            paths, ops = cost(g.commands)
            assert paths <= g.asset.max_paths and ops <= g.asset.max_ops
        assert cost(scene_frame(c, 89))[0] <= c.path_allowance


@pytest.mark.parametrize("family", FAMILIES)
def test_seed_changes_geometry_and_layout_but_remains_deterministic(data, family):
    data["family"] = family
    r = validate_environment(data)
    a, ca = compiler.compile_environment(r)
    b, cb = compiler.compile_environment(replace(r, seed=123))
    _, repeat = compiler.compile_environment(r)
    assert a.objects != b.objects and scene_frame(ca, 45) != scene_frame(cb, 45)
    assert scene_frame(ca, 45) == scene_frame(repeat, 45)
    assert {g.asset.id for g in ca.generated} == {g.asset.id for g in cb.generated}
    assert ca.painter_ids == repeat.painter_ids
    for f in (89, 0, 45, 0, 89):
        assert scene_frame(ca, f) == scene_frame(repeat, f)


@pytest.mark.parametrize("family", FAMILIES)
def test_density_adds_slots_without_rearranging_existing_components(data, family):
    data["family"] = family
    r = validate_environment(data)
    p, a = compiler.compile_environment(replace(r, density=1))
    q, b = compiler.compile_environment(replace(r, density=3))
    old = {o.id: o for o in p.objects}
    new = {o.id: o for o in q.objects}
    assert old.keys() <= new.keys()
    for key in old:
        assert old[key] == new[key]
    geometry = {g.asset.id: g.commands for g in b.generated}
    for g in a.generated:
        if g.asset.id.startswith(("generated_tree_", "generated_building_", "generated_rock_")):
            assert geometry[g.asset.id] == g.commands


def test_samples_are_bounded_even_at_maximum_digest(data, monkeypatch):
    class Maximum:
        def digest(self):
            return b"\xff" * 32

    monkeypatch.setattr(planning.hashlib, "sha256", lambda *a: Maximum())
    x = planning.sample(validate_environment(data), "object", "channel")
    assert 0 <= x < 1


def test_no_global_random_or_python_hash_dependency(data):
    script = """import json,sys,hashlib
from reelforge.procedural.contract import validate_environment
from reelforge.procedural.compiler import compile_environment
from reelforge.scenes.graph import scene_frame
p,c=compile_environment(validate_environment(json.loads(sys.stdin.read())))
assert 'cairo' not in sys.modules
print(hashlib.sha256(repr(scene_frame(c,45)).encode()).hexdigest())"""
    values = []
    for seed in ("1", "9981"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        result = subprocess.run(
            [sys.executable, "-c", script],
            input=json.dumps(data),
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        values.append(result.stdout)
    assert values[0] == values[1]


def test_expansion_is_rejected_before_geometry(data, monkeypatch):
    monkeypatch.setitem(planning.BOUNDS, "tree", (4096, 80000))

    def forbidden(*args):
        raise AssertionError("geometry invoked before admission")

    monkeypatch.setattr(compiler, "geometry", forbidden)
    with pytest.raises(InputError) as caught:
        compiler.compile_environment(validate_environment(data))
    assert caught.value.issue.code == "ENVIRONMENT_BUDGET"


def test_original_orchard_scenery_is_not_called(data, monkeypatch):
    from reelforge.environments import artwork, polish, scene

    def forbidden(*args):
        raise AssertionError("legacy whole scenery or component used")

    for module, name in [
        (artwork, "barn"),
        (polish, "ground"),
        (polish, "sky"),
        (polish, "tree"),
        (scene, "compose_layers"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    for family in FAMILIES:
        data["family"] = family
        assert scene_frame(compiler.compile_environment(validate_environment(data))[1], 45)


def test_agent_scene_json_cannot_supply_generated_assets(data):
    scene = json.loads((ROOT / "examples/scenes/rural_outpost.json").read_text())
    scene["nodes"][2]["asset_id"] = "generated_sky"
    with pytest.raises(InputError):
        validate_scene(scene)
    data["commands"] = [{"path": "anything"}]
    with pytest.raises(InputError):
        validate_environment(data)


@pytest.mark.parametrize(
    "mode", ["mutable", "oversize", "raw", "budget", "namespace", "kind", "envelope"]
)
def test_sealed_geometry_rejects_unsafe_or_excessive_values(mode):
    from reelforge.rendering.diagnostic import color

    commands = (DrawPath(rectangle(0, 0, 1, 1), color("ffffff")),)
    a = Asset("generated_test", "asset", ("default",), 1, 5)
    if mode == "mutable":
        commands = list(commands)
    elif mode == "oversize":
        commands = commands * 4097
    elif mode == "raw":
        commands = ({"eval": "anything"},)
    elif mode == "budget":
        commands = commands * 2
    elif mode == "namespace":
        a = replace(a, id="rowan_01")
    elif mode == "kind":
        a = replace(a, kind="character")
    else:
        a = replace(a, max_ops=float("nan"))
    with pytest.raises(RenderError):
        GeneratedGeometry(a, commands)


def test_sealed_catalog_is_immutable_and_duplicates_rejected(data):
    _, c = compiler.compile_environment(validate_environment(data))
    g = c.generated[0]
    with pytest.raises(FrozenInstanceError):
        g.commands = ()
    with pytest.raises(InputError):
        compile_scene(c.scene, generated=(*c.generated, g))
    with pytest.raises(InputError):
        compile_scene(c.scene, generated=(object(),))


@pytest.mark.parametrize("family", FAMILIES)
def test_ground_support_painter_order_and_parallax(data, family):
    data["family"] = family
    plan, c = compiler.compile_environment(validate_environment(data))
    ground = next(n for n in c.hierarchy if n.id == "ground")
    actor = next(n for n in c.hierarchy if n.id == "rowan")
    assert actor.depth == ground.depth == 1
    assert actor.world.scale == 0.47
    assert abs(actor.world.x - plan.path_x(525)) == pytest.approx(17)
    assert (
        c.painter_ids.index("ground")
        < c.painter_ids.index("rowan")
        < c.painter_ids.index("foreground")
    )
    before = inspect_scene(c, 0)
    after = inspect_scene(c, 89)
    assert before["character_ground_contacts"]["rowan"]["ground_id"] == "ground"
    assert before["character_ground_contacts"] != after["character_ground_contacts"]
    assert [layer.depth for layer in evaluate_layers(c, 45)] == [0, 0.18, 1, 0.48, 1, 1, 1.4]


def test_parameter_controls_change_structure_and_rowan_can_be_disabled(data):
    r = validate_environment(data)
    _, a = compiler.compile_environment(r)
    for key, value in [
        ("alignment", 1),
        ("structure", 0),
        ("framing", 0),
        ("lighting", "overcast"),
        ("detail", "standard"),
    ]:
        _, b = compiler.compile_environment(replace(r, **{key: value}))
        assert scene_frame(a, 45) != scene_frame(b, 45), key
    _, hidden = compiler.compile_environment(replace(r, rowan=False))
    assert "rowan" not in hidden.painter_ids


def test_examples_match_schema():
    import jsonschema

    for f in (ROOT / "examples/procedural").glob("*.json"):
        d = json.loads(f.read_text())
        jsonschema.Draft202012Validator(environment_schema()).validate(d)
        assert compiler.compile_environment(load_environment(f))


def test_pixel_repeat_and_legacy_scene_checkpoints():
    pytest.importorskip("cairo")
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    renderer = CairoRenderer()
    for f in (ROOT / "examples/procedural").glob("*.json"):
        _, c = compiler.compile_environment(load_environment(f))
        seen = {}
        for frame in (89, 0, 45, 0, 89):
            with renderer.surface(720, 1280) as surface:
                renderer.draw(
                    surface,
                    scene_frame(c, frame),
                    background=color("243e49"),
                    logical_size=(360, 640),
                )
                digest = surface.pixel_sha256()
                assert frame not in seen or seen[frame] == digest
                seen[frame] = digest
    for name in ("rural_outpost", "tree_path", "barn_approach"):
        c = compile_scene(load_scene(ROOT / f"examples/scenes/{name}.json"))
        old = json.loads((ROOT / f"artifacts/phase5a/{name}/stills_report.json").read_text())
        for frame in (0, 45, 89):
            with renderer.surface(720, 1280) as surface:
                renderer.draw(
                    surface,
                    scene_frame(c, frame),
                    background=color("243e49"),
                    logical_size=(360, 640),
                )
                assert surface.pixel_sha256() == old["source_pixel_sha256"][str(frame)]
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_cancelled_generation_never_enters_renderer(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import procedural_environment as tool

    class Cancel:
        def __init__(self, **kwargs):
            self.cancelled = Event()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def sample(self):
            self.cancelled.set()

    monkeypatch.setattr("reelforge.resources.monitor.JobMonitor", Cancel)
    with pytest.raises(OperationError) as caught:
        tool.render_request(validate_environment(data), tmp_path / "cancelled")
    assert caught.value.code == "ENVIRONMENT_RESOURCE"
    assert not (tmp_path / "cancelled").exists()


def test_render_failure_reaps_child_and_preserves_other_output(tmp_path, data, monkeypatch):
    pytest.importorskip("cairo")
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import procedural_environment as tool

    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.rendering.backends.cairo import CairoRenderer

    renderer = CairoRenderer()
    encoders = []

    def capture(*args, **kwargs):
        e = FFmpegEncoder(*args, **kwargs)
        encoders.append(e)
        return e

    def broken(*args, **kwargs):
        raise OperationError("INJECTED", "controlled rasterization failure")

    monkeypatch.setattr("reelforge.media.encoder.FFmpegEncoder", capture)
    monkeypatch.setattr("reelforge.rendering.backends.cairo.CairoRenderer", lambda: renderer)
    monkeypatch.setattr(renderer, "draw", broken)
    other = tmp_path / "keep.mp4"
    other.write_bytes(b"pre-existing")
    with pytest.raises(OperationError):
        tool.render_request(validate_environment(data), tmp_path / "failed")
    assert encoders[0].proc.poll() is not None
    assert not list((tmp_path / "failed").glob(".reelforge-*"))
    assert not (tmp_path / "failed/scene.mp4").exists() and other.read_bytes() == b"pre-existing"
    assert renderer.active_surfaces == renderer.allocated_bytes == 0


def test_invalid_request_and_existing_destination_are_protected(tmp_path, data, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import procedural_environment as tool

    output = tmp_path / "existing"
    output.mkdir()
    f = output / "keep"
    f.write_bytes(b"keep")
    if __import__("importlib").util.find_spec("cairo") is not None:
        with pytest.raises(OperationError) as e:
            tool.render_request(validate_environment(data), output)
        assert e.value.code == "OUTPUT_EXISTS" and f.read_bytes() == b"keep"
    bad = tmp_path / "invalid.json"
    bad.write_text('{"python":"arbitrary"}')
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/procedural_environment.py"),
            "render",
            str(bad),
            "--output-dir",
            str(tmp_path / "never"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and not (tmp_path / "never").exists()


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("alignment", [-1, 1])
def test_extreme_paths_keep_character_inside_generated_support(data, family, alignment):
    data["family"] = family
    data["composition"]["path_alignment"] = alignment
    for seed in (0, 2**32 - 1):
        plan, c = compiler.compile_environment(replace(validate_environment(data), seed=seed))
        assert 5 <= plan.actor_x <= 355
        ground = next(g for g in c.generated if g.asset.id == "generated_ground")
        left, top, right, bottom = ground.asset.support_envelope
        assert left <= plan.actor_x - 180 <= right and top <= plan.actor_y - 510 <= bottom


def test_unexpected_ffmpeg_exit_is_not_published(tmp_path, data, monkeypatch):
    pytest.importorskip("cairo")
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    import procedural_environment as tool

    import reelforge.media.encoder as media

    original = media.encoder_command
    constructor = media.FFmpegEncoder
    encoders = []

    def broken(*args, **kwargs):
        command = original(*args, **kwargs)
        return [command[0], "-invalid-procedural-test-option", *command[1:]]

    def capture(*args, **kwargs):
        encoder = constructor(*args, **kwargs)
        encoders.append(encoder)
        return encoder

    monkeypatch.setattr(media, "encoder_command", broken)
    monkeypatch.setattr(media, "FFmpegEncoder", capture)
    out = tmp_path / "bad-encoder"
    with pytest.raises(OperationError):
        tool.render_request(validate_environment(data), out)
    assert encoders and encoders[0].proc.poll() is not None
    assert not (out / "scene.mp4").exists() and not list(out.glob(".reelforge-*"))


def test_pen_rejects_expansion_before_retaining_excess_geometry():
    from reelforge.procedural.drawing import Pen, ink

    pen = Pen((1, 5))
    pen.rect(0, 0, 1, 1, ink("ffffff"))
    with pytest.raises(ValueError):
        pen.rect(0, 0, 1, 1, ink("ffffff"))
    assert len(pen.result()) == 1
