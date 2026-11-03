"""Additive episode schema; old storyboard/reel/audio structures remain unchanged."""

from reelforge.geometry.schema import array, obj
from reelforge.reels.schema import reel_schema


def episode_schema():
    reel = reel_schema()
    audio = reel["properties"]["audio"]
    # This schema is a fresh value; only the new global episode start bound expands.
    audio["properties"]["narration"]["anyOf"][1]["properties"]["start_frame"]["maximum"] = 899
    audio["properties"]["cues"]["items"]["properties"]["start_frame"]["maximum"] = 899
    # episode-0.2 additionally accepts audio: null for a genuinely silent video.
    silent_or_audio = {"anyOf": [audio, {"type": "null"}]}
    storyboard = reel["properties"]["storyboard"]
    return {
        "$schema": reel["$schema"],
        "$id": "urn:reelforge:episode-0.2",
        "$defs": reel["$defs"],
        **obj(
            {
                "schema_version": {"enum": ["episode-0.1", "episode-0.2"]},
                "title": {"type": "string", "minLength": 1, "maxLength": 120},
                "segments": array(
                    obj(
                        {
                            "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,47}$"},
                            "storyboard": storyboard,
                        }
                    ),
                    1,
                    10,
                ),
                "audio": silent_or_audio,
            }
        ),
    }
