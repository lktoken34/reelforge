"""Discoverable structure; semantic camera/framing admission is additionally mandatory."""

from reelforge.blocking.schema import blocking_schema
from reelforge.geometry.schema import array, number, obj
from reelforge.procedural.schema import environment_schema
from reelforge.scenes.schema import scene_schema

from .contract import BEHAVIORS, CLOSE_UP_ZOOM_RANGE, FRAMINGS


def direction_schema() -> dict:
    # Relocate all internal pointers when embedding independently versioned contracts.
    def embed(value, name):
        if isinstance(value, dict):
            return {
                k: (
                    f"#/$defs/{name}/" + v[2:]
                    if k == "$ref" and v.startswith("#/")
                    else embed(v, name)
                )
                for k, v in value.items()
                if k != "$id"
            }
        if isinstance(value, list):
            return [embed(v, name) for v in value]
        return value

    b = blocking_schema()
    # The extracted composition refs already include its old parent; use original schema.
    from reelforge.geometry.schema import composition_schema

    composition = composition_schema()
    identity = {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,47}$"}
    frame = {"type": "integer", "minimum": 0, "maximum": 90}
    offset = array(number(-100, 100), 2, 2)
    defs = {
        name: embed(schema, name)
        for name, schema in (
            ("blocking", b),
            ("composition", composition),
            ("environment", environment_schema()),
            ("scene", scene_schema()),
        )
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:reelforge:direction-0.1",
        "$defs": defs,
        **obj(
            {
                "schema_version": {"const": "direction-0.1"},
                "title": {"type": "string", "minLength": 1, "maxLength": 120},
                "base": {"oneOf": [{"$ref": f"#/$defs/{name}"} for name in defs]},
                "shots": array(
                    obj(
                        {
                            "id": identity,
                            "start_frame": frame,
                            "end_frame": frame,
                            "behavior": {"enum": list(BEHAVIORS)},
                            "target": {
                                "oneOf": [
                                    obj({"kind": {"const": kind}, "id": identity})
                                    for kind in ("actor", "node")
                                ]
                                + [
                                    obj(
                                        {
                                            "kind": {"const": "point"},
                                            "position": array(number(0, 640), 2, 2),
                                            "depth": number(0.18, 1.4),
                                        }
                                    )
                                ]
                            },
                            "track": {"type": "boolean"},
                            "look_ahead_seconds": number(0, 0.35),
                            # 0.9..1.7 for every behavior except close_up (contract-enforced).
                            "zoom": array(number(*CLOSE_UP_ZOOM_RANGE), 2, 2),
                            "offset_start": offset,
                            "offset_end": offset,
                            "screen": {
                                "type": "array",
                                "prefixItems": [number(16, 344), number(16, 624)],
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "hold_in_frames": frame,
                            "hold_out_frames": frame,
                            "framing": {"enum": list(FRAMINGS)},
                            "safe_margin": number(4, 32),
                            "foreground": {"enum": ["clear", "declared_overlap"]},
                            "continuity": {"enum": ["matched", "intentional_reframe"]},
                        }
                    ),
                    1,
                    6,
                ),
            }
        ),
    }
