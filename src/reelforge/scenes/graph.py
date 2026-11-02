"""Bounded graph compilation and absolute-time evaluation; no native objects or frame cache."""

import math
from dataclasses import dataclass

from reelforge.characters.presets import smooth
from reelforge.environments.scene import Camera
from reelforge.rendering.model import DrawPath

from .assets import asset_by_id, cost, recipe
from .contract import (
    MAX_DEPTH,
    MAX_INSTANCES,
    MAX_LAYERS,
    MAX_NODES,
    MAX_OPS,
    MAX_PATHS,
    Scene,
    fail,
)
from .geometry import GeneratedGeometry
from .transforms import Placement


@dataclass(frozen=True)
class ResolvedNode:
    id: str
    parent: str | None
    kind: str
    world: Placement
    visible: bool
    layer: str | None
    depth: float | None


@dataclass(frozen=True)
class CompiledScene:
    scene: Scene
    hierarchy: tuple[ResolvedNode, ...]
    painter_ids: tuple[str, ...]
    path_allowance: int
    operation_allowance: int
    generated: tuple[GeneratedGeometry, ...] = ()


@dataclass(frozen=True)
class CharacterFrame:
    """Trusted per-frame character sample; JSON never supplies commands or world transforms."""

    node_id: str
    world: Placement
    commands: tuple[DrawPath, ...]


@dataclass(frozen=True)
class EvaluatedLayer:
    id: str
    depth: float
    commands: tuple[DrawPath, ...]
    instance_ids: tuple[str, ...]


def compile_scene(scene: Scene, *, generated: tuple[GeneratedGeometry, ...] = ()) -> CompiledScene:
    # Only trusted native-free planners can provide sealed geometry. scene-0.1 JSON
    # continues to resolve exclusively through its original registered catalog.
    if not isinstance(generated, tuple) or len(generated) > MAX_INSTANCES:
        fail("/nodes", "Generated geometry catalog exceeds instance budget", "SCENE_BUDGET")
    if any(not isinstance(g, GeneratedGeometry) for g in generated):
        fail("/nodes", "Only sealed trusted geometry is supported")
    if len({g.asset.id for g in generated}) != len(generated):
        fail("/nodes", "Duplicate generated asset IDs")

    def resolve(asset_id):
        return next((g.asset for g in generated if g.asset.id == asset_id), None) or asset_by_id(
            asset_id
        )

    for i, node in enumerate(scene.nodes):
        if node.asset_id:
            asset = resolve(node.asset_id)
            if asset is None or asset.kind != node.kind or node.variant not in asset.variants:
                fail(f"/nodes/{i}/asset_id", "Unknown or incompatible trusted asset", "SCENE_ASSET")
    if not 1 <= len(scene.nodes) <= MAX_NODES:
        fail("/nodes", "Node count exceeds the graph budget", "SCENE_BUDGET")
    lookup, indices = {}, {}
    for i, n in enumerate(scene.nodes):
        if n.id in lookup:
            fail(f"/nodes/{i}/id", f"Duplicate node ID: {n.id}")
        lookup[n.id], indices[n.id] = n, i
    roots = [n for n in scene.nodes if n.kind == "root"]
    if len(roots) != 1:
        fail("/nodes", "Exactly one scene root is required")
    layers = [n for n in scene.nodes if n.kind == "layer"]
    if not 1 <= len(layers) <= MAX_LAYERS:
        fail("/nodes", f"Require 1..{MAX_LAYERS} depth layers", "SCENE_BUDGET")
    for n in scene.nodes:
        seen = set()
        current = n
        while current.parent is not None:
            if current.id in seen:
                fail(f"/nodes/{indices[n.id]}/parent", "Parent cycle detected")
            seen.add(current.id)
            if len(seen) > MAX_DEPTH:
                fail(
                    f"/nodes/{indices[n.id]}/parent",
                    f"Graph depth exceeds {MAX_DEPTH}",
                    "SCENE_BUDGET",
                )
            if current.parent not in lookup:
                fail(f"/nodes/{indices[current.id]}/parent", f"Missing parent: {current.parent}")
            current = lookup[current.parent]
        if current.id != roots[0].id:
            fail(f"/nodes/{indices[n.id]}/parent", "Every node must reach the single root")
    children = {n.id: [] for n in scene.nodes}
    for n in scene.nodes:
        if n.parent is not None:
            children[n.parent].append(n)
    for group in children.values():
        group.sort(key=lambda n: (n.order, n.id))
    resolved = []

    def visit(n, parent_world, inherited_visible, layer, depth):
        world = parent_world.compose(n.transform)
        p = f"/nodes/{indices[n.id]}"
        if (
            not 0.1 <= world.scale <= 3
            or max(abs(world.x), abs(world.y)) > 2048
            or abs(world.angle) > math.pi / 2 + 1e-12
        ):
            fail(
                p + "/transform",
                "Composed scale .1..3, position +/-2048, rotation +/-90 degrees required",
                "SCENE_BUDGET",
            )
        if n.kind == "layer":
            if layer is not None:
                fail(
                    p + "/parent",
                    "Layers cannot nest; each instance has exactly one parallax depth",
                )
            layer, depth = n.id, n.depth
        if n.asset_id:
            if layer is None:
                fail(p + "/parent", "Visual instances must descend from a layer")
            asset = resolve(n.asset_id)
            if asset.upright and abs(world.angle) > 1e-12:
                fail(p + "/transform", f"{asset.id} requires zero composed rotation")
        visible = inherited_visible and n.visible
        resolved.append(ResolvedNode(n.id, n.parent, n.kind, world, visible, layer, depth))
        for child in children[n.id]:
            visit(child, world, visible, layer, depth)

    visit(roots[0], Placement(), True, None, None)
    worlds = {r.id: r for r in resolved}
    for n in scene.nodes:
        if n.kind != "character":
            continue
        p = f"/nodes/{indices[n.id]}/ground_id"
        ground = lookup.get(n.ground_id)
        support = resolve(ground.asset_id) if ground is not None else None
        if support is None or support.support_envelope is None:
            fail(p, "Reference a registered supporting-ground instance")
        actor, floor = worlds[n.id], worlds[ground.id]
        if actor.depth != floor.depth or (actor.visible and not floor.visible):
            fail(p, "Character and visible supporting ground must share parallax depth")
        x = (actor.world.x - floor.world.x) / floor.world.scale
        y = (actor.world.y - floor.world.y) / floor.world.scale
        left, top, right, bottom = support.support_envelope
        if not left <= x <= right or not top <= y <= bottom:
            fail(p, "Character origin lies outside the ground's local support envelope")
    instances = [n for n in scene.nodes if n.asset_id]
    if len(instances) > MAX_INSTANCES:
        fail("/nodes", f"At most {MAX_INSTANCES} visual instances", "SCENE_BUDGET")
    paths = sum(resolve(n.asset_id).max_paths for n in instances)
    ops = sum(resolve(n.asset_id).max_ops for n in instances)
    if paths > MAX_PATHS or ops > MAX_OPS:
        fail(
            "/nodes",
            f"Trusted envelopes require {paths} paths/{ops} operations; caps {MAX_PATHS}/{MAX_OPS}",
            "SCENE_BUDGET",
        )
    painter = tuple(
        r.id
        for layer in sorted(layers, key=lambda n: (n.order, n.id))
        for r in resolved
        if r.layer == layer.id and lookup[r.id].asset_id
    )
    return CompiledScene(scene, tuple(resolved), painter, paths, ops, generated)


def camera_at(compiled: CompiledScene, frame: int) -> Camera:
    if type(frame) is not int or not 0 <= frame < compiled.scene.frames:
        fail("/frame", f"Use integer frame 0..{compiled.scene.frames - 1}")
    u = smooth(frame / (compiled.scene.frames - 1))
    if compiled.scene.camera == "locked":
        return Camera(0, 0, 1)
    if compiled.scene.camera == "gentle_drift":
        return Camera(-6 + 12 * u, -2 * u, 1.015 + 0.025 * u)
    return Camera(5 + 15 * u, 3 + 5 * u, 1.015 + 0.07 * u)


def evaluate_layers(
    compiled: CompiledScene,
    frame: int,
    *,
    character_override: CharacterFrame | None = None,
    camera_override: Camera | None = None,
) -> tuple[EvaluatedLayer, ...]:
    camera = camera_at(compiled, frame) if camera_override is None else camera_override
    scene = compiled.scene
    lookup = {n.id: n for n in scene.nodes}
    resolved = {n.id: n for n in compiled.hierarchy}
    layers = []
    for layer in sorted(
        (n for n in scene.nodes if n.kind == "layer"), key=lambda n: (n.order, n.id)
    ):
        commands = []
        emitted = []
        projection = camera.transform(layer.depth)
        camera_world = Placement(projection.tx, projection.ty, projection.sx)
        for name in compiled.painter_ids:
            r = resolved[name]
            if r.layer != layer.id or not r.visible:
                continue
            n = lookup[name]
            sealed = next((g for g in compiled.generated if g.asset.id == n.asset_id), None)
            asset = sealed.asset if sealed else asset_by_id(n.asset_id)
            override = (
                character_override
                if character_override and character_override.node_id == name
                else None
            )
            if override and n.kind != "character":
                fail("/override", "Only a trusted character frame override is supported")
            world = camera_world.compose(override.world if override else r.world)
            emitted.append(name)
            local = (
                override.commands
                if override
                else sealed.commands
                if sealed
                else recipe(
                    asset,
                    n.variant,
                    scene.warmth,
                    scene.atmosphere,
                    scene.breeze,
                    frame / 30,
                    n.character,
                )
            )
            commands.extend(world.command(c) for c in local)
        layers.append(EvaluatedLayer(layer.id, layer.depth, tuple(commands), tuple(emitted)))
    count, operations = cost(tuple(c for layer in layers for c in layer.commands))
    if count > compiled.path_allowance or operations > compiled.operation_allowance:
        fail("/nodes", "Evaluated geometry exceeded its compiled envelope", "SCENE_BUDGET")
    return tuple(layers)


def scene_frame(compiled: CompiledScene, frame: int) -> tuple[DrawPath, ...]:
    return tuple(c for layer in evaluate_layers(compiled, frame) for c in layer.commands)


def inspect_scene(compiled: CompiledScene, frame: int = 0) -> dict:
    from dataclasses import asdict

    camera = camera_at(compiled, frame)
    contacts = {}
    for r in compiled.hierarchy:
        if r.kind == "character":
            t = camera.transform(r.depth)
            contacts[r.id] = {
                "ground_id": next(n.ground_id for n in compiled.scene.nodes if n.id == r.id),
                "world": [r.world.x, r.world.y],
                "screen": [t.tx + t.sx * r.world.x, t.ty + t.sy * r.world.y],
            }
    return {
        "schema_version": "scene-0.1",
        "title": compiled.scene.title,
        "frame": frame,
        "hierarchy": [asdict(r) for r in compiled.hierarchy],
        "painter_ids": compiled.painter_ids,
        "path_allowance": compiled.path_allowance,
        "operation_allowance": compiled.operation_allowance,
        "character_ground_contacts": contacts,
        "camera": asdict(camera),
    }
