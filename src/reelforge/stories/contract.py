"""Versioned, native-free timeline validation. JSON selects trusted IDs, never code."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reelforge.characters.presets import CharacterPreset
from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue
from reelforge.environments.presets import EnvironmentPreset

VERSION = "story-0.1"
CAMERAS = ("establishing_wide", "character_reaction", "suspense_reveal")
MAX_SHOTS, MAX_FRAMES = 8, 900


def fail(path: str, message: str, code: str = "STORY_INVALID") -> None:
    raise InputError(Issue(code, path, message))


def fields(data: Any, expected: set[str], path: str) -> None:
    if not isinstance(data, dict):
        fail(path, "Expected an object")
    missing, unknown = expected - data.keys(), data.keys() - expected
    if missing or unknown:
        fail(path, f"Missing fields: {sorted(missing)}; unsupported fields: {sorted(unknown)}")


def integer(value: Any, low: int, high: int, path: str) -> None:
    if type(value) is not int or not low <= value <= high:
        fail(path, f"Use an integer in [{low}, {high}]; booleans/floats are not frames")


@dataclass(frozen=True)
class Output:
    width: int
    height: int
    fps: int
    frames: int
    codec: str
    pixel_format: str


@dataclass(frozen=True)
class Shot:
    id: str
    start_frame: int
    end_frame: int
    camera: str
    environment: EnvironmentPreset
    character: CharacterPreset

    @property
    def frames(self) -> int:
        return self.end_frame - self.start_frame


@dataclass(frozen=True)
class Story:
    schema_version: str
    title: str
    output: Output
    shots: tuple[Shot, ...]

    def to_data(self) -> dict:
        from dataclasses import asdict

        return {
            "schema_version": self.schema_version,
            "title": self.title,
            "output": asdict(self.output),
            "shots": [
                {
                    "id": s.id,
                    "start_frame": s.start_frame,
                    "end_frame": s.end_frame,
                    "environment": s.environment.environment,
                    "camera": s.camera,
                    "character": asdict(s.character),
                    "transition": "cut",
                    "art_direction": {
                        key: getattr(s.environment, key)
                        for key in ("atmosphere", "warmth", "breeze", "framing")
                    },
                }
                for s in self.shots
            ],
        }


def validate_story(data: Any) -> Story:
    fields(data, {"schema_version", "title", "output", "shots"}, "")
    if data["schema_version"] != VERSION:
        fail("/schema_version", f"Use {VERSION}", "STORY_VERSION")
    if not isinstance(data["title"], str) or (
        not data["title"].strip() or len(data["title"]) > 120
    ):
        fail("/title", "Use a nonempty title of at most 120 characters; title is metadata only")
    out = data["output"]
    fields(out, {"width", "height", "fps", "frames", "codec", "pixel_format"}, "/output")
    for key, value in (("width", 720), ("height", 1280), ("fps", 30)):
        if type(out[key]) is not int or out[key] != value:
            fail("/output/" + key, f"This milestone supports only {value}")
    integer(out["frames"], 30, MAX_FRAMES, "/output/frames")
    if out["codec"] != "h264" or out["pixel_format"] != "yuv420p":
        fail("/output", "Use codec h264 and pixel_format yuv420p")
    records = data["shots"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_SHOTS:
        fail("/shots", f"Use 1..{MAX_SHOTS} consecutive shots")
    expected_start, ids, shots = 0, set(), []
    for i, record in enumerate(records):
        p = f"/shots/{i}"
        fields(
            record,
            {
                "id",
                "start_frame",
                "end_frame",
                "environment",
                "camera",
                "character",
                "art_direction",
                "transition",
            },
            p,
        )
        name = record["id"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", name):
            fail(p + "/id", "Use a snake_case ID beginning with a letter, at most 48 characters")
        if name in ids:
            fail(p + "/id", "Shot IDs must be unique")
        ids.add(name)
        start, end = record["start_frame"], record["end_frame"]
        integer(start, 0, MAX_FRAMES - 1, p + "/start_frame")
        integer(end, 1, MAX_FRAMES, p + "/end_frame")
        if start != expected_start:
            problem = "gap" if start > expected_start else "overlap/out-of-order shot"
            fail(
                p + "/start_frame",
                f"Expected {expected_start}; got {start} ({problem})",
                "STORY_CONTIGUITY",
            )
        if not 30 <= end - start <= 300:
            fail(p + "/end_frame", "Each end-exclusive shot must last 30..300 frames (1..10 s)")
        expected_start = end
        if record["transition"] != "cut":
            fail(p + "/transition", "Only hard-cut transition 'cut' is supported")
        if not isinstance(record["camera"], str) or record["camera"] not in CAMERAS:
            fail(p + "/camera", "Choose " + ", ".join(CAMERAS))
        if record["environment"] != "last_light_orchard_01":
            fail(p + "/environment", "Choose last_light_orchard_01")
        fields(
            record["art_direction"],
            {"atmosphere", "warmth", "breeze", "framing"},
            p + "/art_direction",
        )
        try:
            environment = EnvironmentPreset(
                environment=record["environment"], shot="locked", **record["art_direction"]
            )
        except (TypeError, ValueError) as exc:
            fail(p + "/art_direction", str(exc))
        try:
            character = CharacterPreset.from_data(record["character"])
        except (TypeError, ValueError) as exc:
            fail(p + "/character", str(exc))
        if character.action not in ("idle", "look_around", "react"):
            fail(
                p + "/character/action",
                "Stationary shots support idle, look_around or react; "
                "walk/run require a future blocking/travel contract",
            )
        shots.append(Shot(name, start, end, record["camera"], environment, character))
    if expected_start != out["frames"]:
        fail(
            "/output/frames", f"Must equal the final end_frame ({expected_start})", "STORY_DURATION"
        )
    return Story(VERSION, data["title"], Output(**out), tuple(shots))


def load_story(path: Path) -> Story:
    # Reuses strict UTF-8, 1 MiB bounded read, duplicate/nonfinite and depth-32 rejection.
    return validate_story(load_project(Path(path)))
