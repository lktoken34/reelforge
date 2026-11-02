"""Structural blocking schema. Continuous motion/support admission remains mandatory."""

from reelforge.characters.presets import EXPRESSIONS
from reelforge.geometry.schema import array, composition_schema, number, obj
from reelforge.procedural.schema import environment_schema
from reelforge.scenes.schema import scene_schema


def blocking_schema():
    identity = {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,47}$"}
    point = array(number(0, 640), 2, 2)
    facing = {"enum": ["left", "right"]}
    composition = composition_schema()

    # Its geometry refs are rooted in this embedding, not external files or resources.
    def rewrite(value):
        if isinstance(value, dict):
            return {
                k: (
                    "#/$defs/composition/$defs/geometry/$defs/shape"
                    if k == "$ref" and v == "#/$defs/geometry/$defs/shape"
                    else "#/$defs/composition/$defs/geometry"
                    if k == "$ref" and v == "#/$defs/geometry"
                    else rewrite(v)
                )
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        return value

    composition = rewrite(composition)
    composition.pop("$id", None)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:reelforge:blocking-0.1",
        "$defs": {"composition": composition},
        **obj(
            {
                "schema_version": {"const": "blocking-0.1"},
                "title": {"type": "string", "minLength": 1, "maxLength": 120},
                "base": {
                    "oneOf": [scene_schema(), environment_schema(), {"$ref": "#/$defs/composition"}]
                },
                "actor_id": identity,
                "support_id": identity,
                "corridor": {"const": "level_field"},
                "start": obj({"position": point, "facing": facing}),
                "camera": {"enum": ["base", "locked", "exit_right"]},
                "segments": array(
                    obj(
                        {
                            "id": identity,
                            "start_frame": {"type": "integer", "minimum": 0, "maximum": 90},
                            "end_frame": {"type": "integer", "minimum": 0, "maximum": 90},
                            "mode": {"enum": ["idle", "walk", "run", "stop", "turn"]},
                            "destination": point,
                            "end_speed": number(0, 90),
                            "facing": facing,
                            "acting": {"enum": ["idle", "look_around", "react", "none"]},
                            "expression": {"enum": list(EXPRESSIONS)},
                        }
                    ),
                    1,
                    12,
                ),
            }
        ),
    }
