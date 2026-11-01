"""Additive composition-0.1; legacy manifests remain immutable nested base documents."""

from dataclasses import dataclass, replace
from pathlib import Path

from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError
from reelforge.procedural.compiler import LAYERS, compile_plan
from reelforge.procedural.contract import validate_environment
from reelforge.procedural.planning import plan_environment
from reelforge.scenes.contract import Node, validate_scene
from reelforge.scenes.graph import CompiledScene, compile_scene, inspect_scene
from reelforge.scenes.transforms import Placement

from .compiler import compile_geometry, inspect_geometry
from .contract import Document, fail, fields, identifier, number, placement, validate_geometry


@dataclass(frozen=True)
class Instance:
    id: str
    asset: str
    anchor: str
    parent: str
    order: int
    visible: bool
    transform: Placement


@dataclass(frozen=True)
class Composition:
    title: str
    document: Document
    base: object
    procedural: bool
    instances: tuple[Instance, ...]


def validate_composition(data) -> Composition:
    fields(data, {"schema_version", "title", "geometry", "base", "instances"}, set(), "")
    if data["schema_version"] != "composition-0.1":
        fail("/schema_version", "Use composition-0.1")
    if not isinstance(data["title"], str) or not data["title"].strip() or len(data["title"]) > 120:
        fail("/title", "Supply a nonblank title of at most 120 characters")
    try:
        doc = validate_geometry(data["geometry"])
    except InputError as e:
        fail("/geometry" + e.issue.path, e.issue.message, e.issue.code)
    base = data["base"]
    if not isinstance(base, dict) or base.get("schema_version") not in (
        "scene-0.1",
        "environment-0.1",
    ):
        fail("/base/schema_version", "Embed a scene-0.1 or environment-0.1; no paths/includes")
    procedural = base["schema_version"] == "environment-0.1"
    try:
        if procedural:
            base = plan_environment(validate_environment(base))
            nodes, instances, paths, ops = (
                base.node_allowance,
                base.instance_allowance,
                base.path_allowance,
                base.operation_allowance,
            )
        else:
            base = compile_scene(validate_scene(base))
            nodes, instances = len(base.scene.nodes), len(base.painter_ids)
            paths, ops = base.path_allowance, base.operation_allowance
    except InputError as e:
        fail("/base" + e.issue.path, e.issue.message, e.issue.code)
    records = data["instances"]
    if not isinstance(records, list) or not 1 <= len(records) <= 16:
        fail("/instances", "Place 1..16 instances", "GEOMETRY_BUDGET")
    assets = {a.id: a for a in doc.assets}
    base_kinds = (
        {
            "root": "root",
            **{"layer_" + name: "layer" for name, _, _ in LAYERS},
            **{o.id: "asset" for o in base.objects},
            **({"rowan": "character"} if base.request.rowan else {}),
        }
        if procedural
        else {n.id: n.kind for n in base.scene.nodes}
    )
    result, seen = [], set()
    for i, r in enumerate(records):
        p = f"/instances/{i}"
        fields(r, {"id", "asset", "anchor", "parent", "order", "visible", "transform"}, set(), p)
        identity = identifier(r["id"], p + "/id")
        if (
            identity in seen
            or identity in base_kinds
            or identity.startswith(("generated_", "agent_"))
        ):
            fail(p + "/id", "Duplicate/reserved instance ID", "GEOMETRY_NAMESPACE")
        seen.add(identity)
        name = identifier(r["asset"], p + "/asset")
        a = assets.get(name)
        if a is None:
            fail(p + "/asset", "Select an authored asset", "GEOMETRY_REFERENCE")
        if not isinstance(r["anchor"], str) or r["anchor"] not in dict(a.anchors):
            fail(p + "/anchor", "Select a declared anchor", "GEOMETRY_REFERENCE")
        parent = identifier(r["parent"], p + "/parent")
        if base_kinds.get(parent) not in ("layer", "group"):
            fail(p + "/parent", "Select a base layer/group", "GEOMETRY_REFERENCE")
        order = r["order"]
        if type(order) is not int or not 0 <= order <= 127:
            fail(p + "/order", "Use an integer 0..127")
        if type(r["visible"]) is not bool:
            fail(p + "/visible", "Use a boolean")
        t = placement(r["transform"], p + "/transform", instance=True)
        number(t.x, -720, 720, p + "/transform/x")
        paths += len(a.shapes)
        ops += a.operations
        result.append(Instance(identity, name, r["anchor"], parent, order, r["visible"], t))
    if nodes + len(result) > 64 or instances + len(result) > 32 or paths > 4096 or ops > 80000:
        fail(
            "/instances",
            "Aggregate base + all placements exceeds unchanged scene caps",
            "GEOMETRY_BUDGET",
        )
    return Composition(data["title"], doc, base, procedural, tuple(result))


def compile_composition(c: Composition) -> CompiledScene:
    # Admission above precedes procedural recipe expansion and authored DrawPath allocation.
    base = compile_plan(c.base) if c.procedural else c.base
    nodes = list(base.scene.nodes)
    lookup = {n.id: n for n in nodes}
    assets = {a.id: a for a in c.document.assets}
    for i, r in enumerate(c.instances):
        p = f"/instances/{i}"
        if r.id in lookup:
            fail(p + "/id", "Instance cannot replace a base node", "GEOMETRY_NAMESPACE")
        if r.parent not in lookup or lookup[r.parent].kind not in ("group", "layer"):
            fail(
                p + "/parent",
                "Select a base layer/group, not a visual instance",
                "GEOMETRY_REFERENCE",
            )
        a = assets[r.asset]
        anchor = dict(a.anchors)[r.anchor]
        transform = r.transform.compose(Placement(-anchor[0], -anchor[1]))
        node = Node(
            r.id,
            "asset",
            r.parent,
            r.order,
            r.visible,
            transform,
            asset_id="generated_agent_" + r.asset,
            variant="default",
        )
        lookup[r.id] = node
        nodes.append(node)
    return compile_scene(
        replace(base.scene, title=c.title, nodes=tuple(nodes)),
        generated=(*base.generated, *compile_geometry(c.document)),
    )


def inspect_composition(c: Composition) -> dict:
    compiled = compile_composition(c)
    return {
        "contract": "composition-0.1",
        "geometry": inspect_geometry(c.document),
        "graph": inspect_scene(compiled, 45),
        "character_support_for_authored_assets": False,
    }


def load_composition(path: Path) -> Composition:
    return validate_composition(load_project(path))
