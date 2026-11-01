"""Discoverable structural schema; semantic expansion admission remains mandatory."""

from .contract import FAMILIES


def environment_schema():
    def obj(fields):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": list(fields),
            "properties": fields,
        }

    def num(low, high):
        return {"type": "number", "minimum": low, "maximum": high}

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:reelforge:environment-0.1",
        **obj(
            {
                "schema_version": {"const": "environment-0.1"},
                "title": {"type": "string", "minLength": 1, "maxLength": 120},
                "family": {"enum": list(FAMILIES)},
                "seed": {"type": "integer", "minimum": 0, "maximum": 2**32 - 1},
                "composition": obj(
                    {
                        "density": {"type": "integer", "minimum": 1, "maximum": 3},
                        "path_alignment": num(-1, 1),
                        "structure": num(0, 1),
                        "framing": num(0, 1),
                        "detail": {"enum": ["standard", "rich"]},
                    }
                ),
                "art_direction": obj(
                    {"lighting": {"enum": ["dusk", "overcast"]}, "atmosphere": num(0, 1)}
                ),
                "rowan": obj(
                    {
                        "enabled": {"type": "boolean"},
                        "action": {"enum": ["idle", "look_around", "react"]},
                        "side": {"enum": ["left", "right"]},
                    }
                ),
            }
        ),
    }
