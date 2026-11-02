"""Native-free IR -> accepted immutable DrawPath -> sealed generated assets."""

import hashlib

from reelforge.rendering.diagnostic import ellipse
from reelforge.rendering.model import DrawPath, PathOp, rectangle
from reelforge.scenes.assets import Asset, cost
from reelforge.scenes.contract import Node, Scene
from reelforge.scenes.geometry import GeneratedGeometry
from reelforge.scenes.graph import compile_scene
from reelforge.scenes.transforms import Placement

from .contract import Document


def compile_geometry(document: Document) -> tuple[GeneratedGeometry, ...]:
    result = []
    for a in document.assets:
        commands = []
        for s in a.shapes:
            if s.kind == "rect":
                path = rectangle(*s.values)
            elif s.kind == "ellipse":
                path = ellipse(*s.values)
            elif s.kind == "polygon":
                path = (
                    (PathOp("M", s.values[0]),)
                    + tuple(PathOp("L", v) for v in s.values[1:])
                    + (PathOp("Z"),)
                )
            else:
                path = tuple(PathOp(k, pts) for k, pts in s.values)
            clip = tuple(PathOp(k, pts) for k, pts in s.clip) if s.clip else None
            commands.append(s.transform.command(DrawPath(path, s.fill, s.stroke, clip=clip)))
        commands = tuple(commands)
        paths, ops = cost(commands)
        if paths != len(a.shapes) or ops != a.operations:
            raise ValueError("Geometry IR expansion accounting mismatch")
        result.append(
            GeneratedGeometry(
                Asset("generated_agent_" + a.id, "asset", ("default",), paths, ops), commands
            )
        )
    return tuple(result)


def inspect_geometry(document: Document) -> dict:
    assets = compile_geometry(document)
    return {
        "contract": "geometry-0.1",
        "assets": [
            {
                "id": a.id,
                "private_id": g.asset.id,
                "size": a.size,
                "anchors": dict(a.anchors),
                "paths": len(g.commands),
                "operations": a.operations,
                "geometry_sha256": hashlib.sha256(repr(g.commands).encode()).hexdigest(),
                "character_support": False,
            }
            for a, g in zip(document.assets, assets, strict=True)
        ],
    }


def preview_scene(document: Document, identity: str):
    from .contract import fail

    a = next((a for a in document.assets if a.id == identity), None)
    if a is None:
        fail("/asset", "Unknown showcase asset", "GEOMETRY_REFERENCE")
    scale = min(240 / a.size[0], 360 / a.size[1], 2)
    nodes = (
        Node("root", "root", None, 0, True, Placement()),
        Node("objects", "layer", "root", 0, True, Placement(), 1),
        Node(
            "showcase",
            "asset",
            "objects",
            0,
            True,
            Placement((360 - a.size[0] * scale) / 2, (640 - a.size[1] * scale) / 2, scale),
            asset_id="generated_agent_" + a.id,
            variant="default",
        ),
    )
    return compile_scene(
        Scene("Geometry showcase", 90, "locked", 0.7, 0.5, 0, nodes),
        generated=compile_geometry(document),
    )
