"""Strict native-free reel planning; media validation is deferred explicitly to rendering."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from reelforge.audio.registry import AudioRegistry, ResolvedCue
from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue, OperationError
from reelforge.stories.audio_contract import AudioPlan, audio_from_data
from reelforge.storyboards.compiler import (
    Storyboard,
    bounded_copy,
    compile_storyboard,
    inspect_beats,
    inspect_frame,
    inspect_plans,
)


class AudioRequest(Protocol):
    title: str
    audio: AudioPlan


@dataclass(frozen=True)
class Reel:
    title: str
    storyboard: Storyboard
    audio: AudioPlan


def compile_reel(data: object) -> Reel:
    d = bounded_copy(data)
    if not isinstance(d, dict) or set(d) != {"schema_version", "title", "storyboard", "audio"}:
        raise InputError(
            Issue("REEL_INVALID", "", "Use exactly schema_version, title, storyboard, audio")
        )
    if d["schema_version"] != "reel-0.1":
        raise InputError(Issue("REEL_VERSION", "/schema_version", "Use reel-0.1"))
    title = d["title"]
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        raise InputError(Issue("REEL_INVALID", "/title", "Use nonblank text <=120 characters"))
    audio = audio_from_data(d["audio"], 90)
    if audio is None:
        raise InputError(
            Issue("REEL_AUDIO", "/audio", "Select at least one registered audio track")
        )
    try:
        storyboard = compile_storyboard(d["storyboard"])
    except InputError as error:
        raise InputError(
            Issue(error.issue.code, "/storyboard" + error.issue.path, error.issue.message)
        ) from error
    return Reel(title, storyboard, audio)


def load_reel(path: Path) -> Reel:
    return compile_reel(load_project(path))


def metadata_plan(
    plan: AudioRequest, registry: AudioRegistry, frames: int = 90
) -> tuple[ResolvedCue, ...]:
    try:
        return registry.resolve(plan.audio, frames, validate_media=False)
    except OperationError as error:
        raise InputError(Issue(error.code, "/audio", str(error))) from error


def cue_schedule(resolved: tuple[ResolvedCue, ...]) -> list[dict]:
    return [
        {
            **asdict(r.cue),
            "role": r.asset.role,
            "source_sha256": r.asset.sha256,
            "trim_end_frame": r.trim_end_frame,
            "start_sample": r.cue.start_frame * 1600,
            "end_sample": r.cue.start_frame * 1600 + r.output_samples,
            "effective_samples": r.output_samples,
        }
        for r in resolved
    ]


def inspect_reel(plan: Reel, resolved: tuple[ResolvedCue, ...], frame: int | None = None) -> dict:
    cues = cue_schedule(resolved)
    result = {
        "contract": "reel-0.1",
        "title": plan.title,
        "frames": 90,
        "fps": 30,
        "sample_rate": 48000,
        "samples_per_frame": 1600,
        "effective_samples_per_channel": 144000,
        "registry_validation": "metadata-only",
        "media_bytes_validated": False,
        "audio_cues": cues,
        "storyboard": inspect_beats(plan.storyboard),
    }
    if frame is None:
        result["compiled"] = inspect_plans(plan.storyboard)
    else:
        result["visual"] = inspect_frame(plan.storyboard, frame)
        result["sample"] = frame * 1600
        result["active_cues"] = [
            c for c in cues if c["start_sample"] <= frame * 1600 < c["end_sample"]
        ]
        result["starting_cues"] = [c for c in cues if c["start_frame"] == frame]
    return result
