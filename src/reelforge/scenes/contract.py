"""Strict native-free scene-0.1 data contract; every executable recipe is registered code."""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from reelforge.characters.presets import CharacterPreset
from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue

from .assets import asset_by_id
from .transforms import Placement

MAX_NODES, MAX_INSTANCES, MAX_DEPTH, MAX_LAYERS = 64, 32, 8, 8
MAX_PATHS, MAX_OPS = 4096, 80000
CAMERAS = ("locked", "gentle_drift", "approach")
KINDS = ("root", "group", "layer", "asset", "background", "environment", "character")
VISUAL = ("asset", "background", "environment", "character")


def fail(path: str, message: str, code: str = "SCENE_INVALID") -> None:
    raise InputError(Issue(code, path, message))


def fields(data, expected: set[str], path: str) -> None:
    if not isinstance(data, dict):
        fail(path, "Expected an object")
    missing, unknown = expected - data.keys(), data.keys() - expected
    if missing or unknown:
        fail(path, f"Missing fields: {sorted(missing)}; unsupported fields: {sorted(unknown)}")


def number(value, low: float, high: float, path: str) -> None:
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        fail(path, f"Use a finite number in [{low}, {high}]")


def integer(value, low: int, high: int, path: str) -> None:
    if type(value) is not int or not low <= value <= high:
        fail(path, f"Use an integer in [{low}, {high}]")


def identifier(value, path: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,47}", value) is None:
        fail(path, "Use a snake_case identifier, 1..48 characters; paths/URLs are forbidden")


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    parent: str | None
    order: int
    visible: bool
    transform: Placement
    depth: float | None = None
    asset_id: str | None = None
    variant: str | None = None
    character: CharacterPreset | None = None
    ground_id: str | None = None


@dataclass(frozen=True)
class Scene:
    title: str
    frames: int
    camera: str
    warmth: float
    atmosphere: float
    breeze: float
    nodes: tuple[Node, ...]


def validate_scene(data) -> Scene:
    fields(data, {"schema_version", "title", "output", "camera", "art_direction", "nodes"}, "")
    if data["schema_version"] != "scene-0.1":
        fail("/schema_version", "Supported experimental version: scene-0.1")
    title = data["title"]
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        fail("/title", "Supply a nonempty title of at most 120 characters")
    out = data["output"]
    fields(out, {"width", "height", "fps", "frames", "codec", "pixel_format"}, "/output")
    for key, value in (("width", 720), ("height", 1280), ("fps", 30)):
        if type(out[key]) is not int or out[key] != value:
            fail("/output/" + key, f"Use the trusted output value {value}")
    integer(out["frames"], 30, 180, "/output/frames")
    if out["codec"] != "h264" or out["pixel_format"] != "yuv420p":
        fail("/output", "Only H.264/yuv420p is supported")
    if data["camera"] not in CAMERAS:
        fail("/camera", f"Choose a trusted camera: {CAMERAS}")
    direction = data["art_direction"]
    fields(direction, {"warmth", "atmosphere", "breeze"}, "/art_direction")
    for key in direction:
        number(direction[key], 0, 1, "/art_direction/" + key)
    records = data["nodes"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_NODES:
        fail("/nodes", f"Supply 1..{MAX_NODES} nodes", "SCENE_BUDGET")
    nodes = []
    for i, record in enumerate(records):
        p = f"/nodes/{i}"
        if not isinstance(record, dict) or record.get("kind") not in KINDS:
            fail(p + "/kind", f"Choose a node kind: {KINDS}")
        kind = record["kind"]
        expected = {"id", "kind", "parent", "order", "visible", "transform"}
        if kind == "layer":
            expected |= {"depth"}
        if kind in VISUAL:
            expected |= {"asset_id", "variant"}
        if kind == "character":
            expected |= {"character", "ground_id"}
        fields(record, expected, p)
        identifier(record["id"], p + "/id")
        if record["parent"] is not None:
            identifier(record["parent"], p + "/parent")
        if (kind == "root") != (record["parent"] is None):
            fail(p + "/parent", "Only root has null parent; all other nodes require a parent ID")
        integer(record["order"], 0, 127, p + "/order")
        if type(record["visible"]) is not bool:
            fail(p + "/visible", "Visibility must be a boolean")
        t = record["transform"]
        fields(t, {"x", "y", "scale", "rotation_degrees"}, p + "/transform")
        number(t["x"], -720, 720, p + "/transform/x")
        number(t["y"], -720, 1280, p + "/transform/y")
        number(t["scale"], 0.25, 2, p + "/transform/scale")
        number(t["rotation_degrees"], -45, 45, p + "/transform/rotation_degrees")
        placement = Placement(t["x"], t["y"], t["scale"], math.radians(t["rotation_degrees"]))
        if kind == "root" and placement != Placement():
            fail(p + "/transform", "Root must have the identity transform; use a child group")
        if kind == "layer":
            number(record["depth"], 0, 1.5, p + "/depth")
        character = None
        if kind in VISUAL:
            asset = asset_by_id(record["asset_id"]) if isinstance(record["asset_id"], str) else None
            if asset is None or asset.kind != kind:
                fail(p + "/asset_id", "Select a registered asset of this node kind", "SCENE_ASSET")
            if record["variant"] not in asset.variants:
                fail(p + "/variant", f"Trusted variants: {asset.variants}")
        if kind == "character":
            identifier(record["ground_id"], p + "/ground_id")
            try:
                character = CharacterPreset.from_data(record["character"])
            except (TypeError, ValueError) as error:
                fail(p + "/character", str(error))
            if character.action not in ("idle", "look_around", "react"):
                fail(
                    p + "/character/action", "Scene-0.1 supports stationary idle/look_around/react"
                )
        nodes.append(
            Node(
                record["id"],
                kind,
                record["parent"],
                record["order"],
                record["visible"],
                placement,
                record.get("depth"),
                record.get("asset_id"),
                record.get("variant"),
                character,
                record.get("ground_id"),
            )
        )
    scene = Scene(
        title,
        out["frames"],
        data["camera"],
        direction["warmth"],
        direction["atmosphere"],
        direction["breeze"],
        tuple(nodes),
    )
    from .graph import compile_scene

    compile_scene(scene)
    return scene


def load_scene(path: Path) -> Scene:
    return validate_scene(load_project(Path(path)))
