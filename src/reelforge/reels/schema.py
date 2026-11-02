"""Discoverable JSON structure. Accepted semantic compilers remain authoritative."""

from reelforge.geometry.schema import array, obj
from reelforge.storyboards.schema import storyboard_schema


def reel_schema() -> dict:
    storyboard = storyboard_schema()
    definitions = storyboard.pop("$defs")
    storyboard.pop("$id")
    storyboard.pop("$schema")
    cue = obj(
        {
            "asset_id": {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,47}$"},
            "start_frame": {"type": "integer", "minimum": 0, "maximum": 89},
            "trim_start_frame": {"type": "integer", "minimum": 0, "maximum": 899},
            "trim_end_frame": {
                "anyOf": [{"type": "null"}, {"type": "integer", "minimum": 1, "maximum": 900}]
            },
            "gain": {"type": "number", "minimum": 0.05, "maximum": 0.8},
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:reelforge:reel-0.1",
        "$defs": definitions,
        **obj(
            {
                "schema_version": {"const": "reel-0.1"},
                "title": {"type": "string", "minLength": 1, "maxLength": 120},
                "storyboard": storyboard,
                "audio": obj(
                    {
                        "sample_rate": {"const": 48000},
                        "channels": {"const": 2},
                        "codec": {"const": "aac"},
                        "bitrate": {"const": 128000},
                        "narration": {"anyOf": [{"type": "null"}, cue]},
                        "cues": array(cue, 0, 4),
                    }
                ),
            }
        ),
    }
