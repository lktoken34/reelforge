"""Publish JSON Schema from the same capability constants; topology is checked by the compiler."""

from reelforge.characters.presets import EXPRESSIONS

from .assets import ASSETS
from .contract import CAMERAS, MAX_NODES


def scene_schema() -> dict:
    identifier = {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,47}$"}

    def number(low, high):
        return {"type": "number", "minimum": low, "maximum": high}

    def obj(props):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": list(props),
            "properties": props,
        }

    transform = obj(
        {
            "x": number(-720, 720),
            "y": number(-720, 1280),
            "scale": number(0.25, 2),
            "rotation_degrees": number(-45, 45),
        }
    )
    nodes = []
    for kind, asset in [("root", None), ("group", None), ("layer", None)] + [
        (a.kind, a) for a in ASSETS
    ]:
        props = {
            "id": identifier,
            "kind": {"const": kind},
            "parent": {"type": "null"} if kind == "root" else identifier,
            "order": {"type": "integer", "minimum": 0, "maximum": 127},
            "visible": {"type": "boolean"},
            "transform": transform,
        }
        if kind == "root":
            props["transform"] = {"const": {"x": 0, "y": 0, "scale": 1, "rotation_degrees": 0}}
        if kind == "layer":
            props["depth"] = number(0, 1.5)
        if asset:
            props.update(asset_id={"const": asset.id}, variant={"enum": list(asset.variants)})
        if kind == "character":
            props["ground_id"] = identifier
            props["character"] = obj(
                {
                    "character": {"const": "rowan_01"},
                    "action": {"enum": ["idle", "look_around", "react"]},
                    "direction": {"enum": ["left", "right"]},
                    "expression": {"enum": list(EXPRESSIONS)},
                    "speed": number(0.5, 1.5),
                    "intensity": number(0.5, 1),
                }
            )
        nodes.append(obj(props))
    schema = obj(
        {
            "schema_version": {"const": "scene-0.1"},
            "title": {"type": "string", "minLength": 1, "maxLength": 120},
            "output": obj(
                {
                    "width": {"const": 720},
                    "height": {"const": 1280},
                    "fps": {"const": 30},
                    "frames": {"type": "integer", "minimum": 30, "maximum": 180},
                    "codec": {"const": "h264"},
                    "pixel_format": {"const": "yuv420p"},
                }
            ),
            "camera": {"enum": list(CAMERAS)},
            "art_direction": obj({k: number(0, 1) for k in ("warmth", "atmosphere", "breeze")}),
            "nodes": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_NODES,
                "items": {"oneOf": nodes},
            },
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:reelforge:scene-0.1",
        **schema,
    }
