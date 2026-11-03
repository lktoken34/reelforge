"""Advisory production-0.1 schema; semantic validation lives in the compiler as elsewhere."""

from reelforge.episodes.schema import episode_schema
from reelforge.geometry.schema import array, obj


def production_schema() -> dict:
    episode = episode_schema()
    storyboard = episode["properties"]["segments"]["items"]["properties"]["storyboard"]
    return {
        "$schema": episode["$schema"],
        "$id": "urn:reelforge:production-0.1",
        "$defs": episode["$defs"],
        **obj(
            {
                "schema_version": {"const": "production-0.1"},
                "title": {"type": "string", "minLength": 1, "maxLength": 120},
                "segments": array(
                    obj(
                        {
                            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,47}$"},
                            "storyboard": storyboard,
                        }
                    ),
                    2,
                    20,
                ),
                "audio": {"type": "null"},
            }
        ),
    }
