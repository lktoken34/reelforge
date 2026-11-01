"""Trusted request -> semantic plan -> bounded sealed assets -> accepted scene graph."""

import hashlib
from dataclasses import asdict

from reelforge.characters.presets import CharacterPreset
from reelforge.scenes.assets import Asset, cost
from reelforge.scenes.contract import Node, Scene
from reelforge.scenes.geometry import GeneratedGeometry
from reelforge.scenes.graph import compile_scene, inspect_scene
from reelforge.scenes.transforms import Placement

from .contract import Request
from .planning import BOUNDS, plan_environment
from .recipes import geometry

LAYERS = (
    ("sky", 0, 0),
    ("backdrop", 1, 0.18),
    ("ground", 2, 1),
    ("distance", 3, 0.48),
    ("objects", 4, 1),
    ("people", 5, 1),
    ("foreground", 6, 1.4),
)


def compile_environment(request: Request):
    plan = plan_environment(request)  # Reject expansion before any geometry recipe is called.
    return plan, compile_plan(plan)


def compile_plan(plan):
    request = plan.request
    nodes = [Node("root", "root", None, 0, True, Placement())]
    nodes.extend(
        Node("layer_" + name, "layer", "root", order, True, Placement(), depth)
        for name, order, depth in LAYERS
    )
    generated = []
    # Within the main plane, far bases paint before near bases. Stable IDs break ties.
    for order, obj in enumerate(sorted(plan.objects, key=lambda o: (o.y, o.id))):
        kind = (
            "background"
            if obj.recipe in ("sky", "backdrop", "distance")
            else "environment"
            if obj.recipe == "ground"
            else "asset"
        )
        paths, ops = BOUNDS[obj.recipe]
        asset = Asset(
            "generated_" + obj.id,
            kind,
            ("default",),
            paths,
            ops,
            upright=obj.recipe == "ground",
            support_envelope=(-175, -75, 175, 130) if obj.recipe == "ground" else None,
        )
        generated.append(GeneratedGeometry(asset, geometry(plan, obj)))
        nodes.append(
            Node(
                obj.id,
                kind,
                "layer_" + obj.layer,
                order,
                True,
                Placement(obj.x, obj.y, obj.scale),
                asset_id=asset.id,
                variant="default",
            )
        )
    if request.rowan:
        preset = CharacterPreset(
            action=request.action,
            expression="calm" if request.action == "idle" else "concerned",
            direction="right" if plan.actor_x < plan.vanishing_x + 22 else "left",
            intensity=0.8,
        )
        nodes.append(
            Node(
                "rowan",
                "character",
                "layer_people",
                0,
                True,
                Placement(plan.actor_x, plan.actor_y, 0.47),
                asset_id="rowan_01",
                variant="default",
                character=preset,
                ground_id="ground",
            )
        )
    scene = Scene(
        request.title,
        90,
        "approach" if request.family == "rocky_shelter" else "gentle_drift",
        0.75 if request.lighting == "dusk" else 0.35,
        request.atmosphere,
        0,
        tuple(nodes),
    )
    return compile_scene(scene, generated=tuple(generated))


def inspect_environment(plan, compiled):
    result = {
        "contract": "environment-0.1",
        "request": asdict(plan.request),
        "plan": asdict(plan),
        "graph": inspect_scene(compiled, 45),
        "generated_assets": [],
    }
    for g in compiled.generated:
        paths, ops = cost(g.commands)
        result["generated_assets"].append(
            {
                "id": g.asset.id,
                "paths": paths,
                "operations": ops,
                "path_bound": g.asset.max_paths,
                "operation_bound": g.asset.max_ops,
                "geometry_sha256": hashlib.sha256(repr(g.commands).encode()).hexdigest(),
                "support_envelope": g.asset.support_envelope,
            }
        )
    return result
