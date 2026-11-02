"""Discoverable structural schemas; semantic validation and expansion admission are mandatory."""

from reelforge.procedural.schema import environment_schema
from reelforge.scenes.schema import scene_schema

from .contract import IDENTIFIER


def obj(props: dict, optional: tuple = ()) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": [p for p in props if p not in optional],
        "additionalProperties": False,
    }


def number(low=-512, high=512) -> dict:
    return {"type": "number", "minimum": low, "maximum": high}


def array(item: dict, low: int, high: int) -> dict:
    return {"type": "array", "items": item, "minItems": low, "maxItems": high}


def geometry_schema() -> dict:
    name = {"type": "string", "pattern": "^" + IDENTIFIER + "$"}
    pair = array(number(), 2, 2)
    transform = obj(
        {
            "x": number(),
            "y": number(),
            "scale": number(0.25, 2),
            "rotation_degrees": number(-45, 45),
        }
    )
    commands = []
    for kind, arity in (("M", 2), ("L", 2), ("C", 6), ("Z", 0)):
        commands.append(
            {
                "type": "array",
                "prefixItems": [{"const": kind}] + [number()] * arity,
                "items": False,
                "minItems": arity + 1,
                "maxItems": arity + 1,
            }
        )
    path = array({"oneOf": commands}, 2, 128)
    stop = {
        "type": "array",
        "prefixItems": [number(0, 1), name],
        "items": False,
        "minItems": 2,
        "maxItems": 2,
    }
    paint = {"oneOf": [name, obj({"linear": array(number(), 4, 4), "stops": array(stop, 2, 8)})]}
    shapes = []
    for kind, parameter in (
        ("rect", "rect"),
        ("ellipse", "ellipse"),
        ("polygon", "points"),
        ("path", "path"),
    ):
        data = (
            path
            if kind == "path"
            else array(pair, 3, 64)
            if kind == "polygon"
            else array(number(), 4, 4)
        )
        shapes.append(
            obj(
                {
                    "type": {"const": kind},
                    parameter: data,
                    "fill": {"anyOf": [paint, {"type": "null"}]},
                    "stroke": {
                        "anyOf": [
                            obj({"paint": paint, "width": number(0.25, 12)}),
                            {"type": "null"},
                        ]
                    },
                    "clip": {"anyOf": [path, {"type": "null"}]},
                    "transform": transform,
                },
                ("fill", "stroke", "clip", "transform"),
            )
        )
    shapes.append(
        obj(
            {
                "type": {"const": "group"},
                "transform": transform,
                "shapes": array({"$ref": "#/$defs/shape"}, 1, 128),
            },
            ("transform",),
        )
    )
    anchors = {
        "type": "object",
        "minProperties": 1,
        "maxProperties": 8,
        "required": ["origin"],
        "propertyNames": name,
        "additionalProperties": array(number(0, 512), 2, 2),
    }
    asset = obj(
        {
            "id": name,
            "size": array(number(1, 512), 2, 2),
            "anchors": anchors,
            "shapes": array({"$ref": "#/$defs/shape"}, 1, 128),
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:reelforge:geometry-0.1",
        "$defs": {"shape": {"oneOf": shapes}},
        **obj(
            {
                "schema_version": {"const": "geometry-0.1"},
                "palette": {
                    "type": "object",
                    "minProperties": 1,
                    "maxProperties": 32,
                    "propertyNames": name,
                    "additionalProperties": {
                        "type": "string",
                        "pattern": "^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$",
                    },
                },
                "assets": array(asset, 1, 8),
            }
        ),
    }


def composition_schema() -> dict:
    name = {"type": "string", "pattern": "^" + IDENTIFIER + "$"}
    geometry = geometry_schema()

    # Geometry's recursive refs must remain rooted in its document in this embedding.
    def rewrite(value):
        if isinstance(value, dict):
            return {
                k: (
                    "#/$defs/geometry/$defs/shape"
                    if k == "$ref" and v == "#/$defs/shape"
                    else rewrite(v)
                )
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        return value

    geometry = rewrite(geometry)
    geometry.pop("$id", None)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:reelforge:composition-0.1",
        "$defs": {"geometry": geometry},
        **obj(
            {
                "schema_version": {"const": "composition-0.1"},
                "title": {"type": "string", "minLength": 1, "maxLength": 120},
                "geometry": {"$ref": "#/$defs/geometry"},
                "base": {"oneOf": [scene_schema(), environment_schema()]},
                "instances": array(
                    obj(
                        {
                            "id": name,
                            "asset": name,
                            "anchor": name,
                            "parent": name,
                            "order": {"type": "integer", "minimum": 0, "maximum": 127},
                            "visible": {"type": "boolean"},
                            "transform": obj(
                                {
                                    "x": number(-720, 720),
                                    "y": number(-1280, 1280),
                                    "scale": number(0.25, 2),
                                    "rotation_degrees": number(-45, 45),
                                }
                            ),
                        }
                    ),
                    1,
                    16,
                ),
            }
        ),
    }
