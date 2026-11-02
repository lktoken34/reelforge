"""Native-free discoverable storyboard structure; semantic compiler admission remains required."""

from reelforge.characters.presets import EXPRESSIONS
from reelforge.direction.contract import BEHAVIORS
from reelforge.direction.schema import direction_schema
from reelforge.geometry.schema import array, number, obj

from .patterns import ACTIONS, BEAT_ACTIONS, PATTERNS


def storyboard_schema() -> dict:
    identity = {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,47}$"}
    frame_count = {"type": "integer", "minimum": 6, "maximum": 90}
    point = array(number(0, 640), 2, 2)
    offset = array(number(-100, 100), 2, 2)
    target = {
        "oneOf": [obj({"kind": {"const": k}, "id": identity}) for k in ("actor", "node")]
        + [obj({"kind": {"const": "point"}, "position": point, "depth": number(0.18, 1.4)})]
    }
    actions = []
    for kind in ACTIONS:
        props = {"kind": {"const": kind}, "expression": {"enum": list(EXPRESSIONS)}}
        if kind in ("walk_to", "run_to", "stop_at"):
            props["end_x"] = number(0, 640)
        if kind in ("walk_to", "run_to"):
            props["end_speed"] = number(
                10 if kind == "walk_to" else 40, 45 if kind == "walk_to" else 90
            )
        actions.append(obj(props))
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:reelforge:storyboard-0.1",
        "$defs": direction_schema()["$defs"],
        **obj(
            {
                "schema_version": {"const": "storyboard-0.1"},
                "title": {"type": "string", "minLength": 1, "maxLength": 120},
                "description": {"type": "string", "maxLength": 800},
                "world": {
                    "oneOf": [
                        {"$ref": "#/$defs/" + k} for k in ("scene", "environment", "composition")
                    ]
                },
                "rowan": obj(
                    {
                        "actor_id": identity,
                        "support_id": identity,
                        "start": obj({"position": point, "facing": {"enum": ["left", "right"]}}),
                    }
                ),
                "subjects": array(obj({"id": identity, "target": target}), 1, 16),
                "views": array(
                    obj(
                        {
                            "id": identity,
                            "kind": {"enum": list(BEHAVIORS)},
                            "subject": identity,
                            "zoom": array(number(0.9, 1.7), 2, 2),
                            "screen": {
                                "type": "array",
                                "prefixItems": [number(16, 344), number(16, 624)],
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "offset_start": offset,
                            "offset_end": offset,
                            "lead_seconds": number(0, 0.35),
                            "hold": array({"type": "integer", "minimum": 0, "maximum": 88}, 2, 2),
                            "crop": {"enum": ["full", "feet_crop", "offscreen"]},
                            "foreground": {"enum": ["clear", "declared_overlap"]},
                            "cut": {"enum": ["matched", "intentional_reframe"]},
                        }
                    ),
                    1,
                    6,
                ),
                "pattern": {"enum": [p.id for p in PATTERNS]},
                "beats": array(
                    obj(
                        {
                            "id": identity,
                            "type": {"enum": list(BEAT_ACTIONS)},
                            "frames": frame_count,
                            "subject": identity,
                            "action": {"oneOf": actions},
                            "view": identity,
                            "description": {"type": "string", "maxLength": 400},
                        },
                        optional=("description",),
                    ),
                    2,
                    10,
                ),
            },
            optional=("description",),
        ),
    }
