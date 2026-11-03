"""Native-free episode-0.1 compiler; cuts are editorial, never seamless acting promises."""

from dataclasses import dataclass
from pathlib import Path

from reelforge.audio.registry import AudioRegistry
from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue
from reelforge.reels.contract import cue_schedule, metadata_plan
from reelforge.scenes.contract import identifier
from reelforge.stories.audio_contract import AudioPlan, audio_from_data
from reelforge.storyboards.compiler import (
    Storyboard,
    bounded_copy,
    compile_storyboard,
    inspect_beats,
    inspect_frame,
)


@dataclass(frozen=True)
class Segment:
    id: str
    storyboard: Storyboard


@dataclass(frozen=True)
class Episode:
    title: str
    segments: tuple[Segment, ...]
    audio: AudioPlan | None

    @property
    def frames(self) -> int:
        return len(self.segments) * 90

    @property
    def silent(self) -> bool:
        return self.audio is None


def fail(path, message):
    raise InputError(Issue("EPISODE_INVALID", path, message))


def compile_episode(data: object) -> Episode:
    d = bounded_copy(data)
    if not isinstance(d, dict) or set(d) != {"schema_version", "title", "segments", "audio"}:
        fail("", "Use exactly schema_version, title, segments, audio")
    if d["schema_version"] not in ("episode-0.1", "episode-0.2"):
        fail("/schema_version", "Use episode-0.1 or episode-0.2")
    version = d["schema_version"]
    if not isinstance(d["title"], str) or not d["title"].strip() or len(d["title"]) > 120:
        fail("/title", "Use nonblank text <=120 characters")
    if not isinstance(d["segments"], list) or not 1 <= len(d["segments"]) <= 10:
        fail("/segments", "Use 1..10 ordered 90-frame storyboard segments")
    segments = []
    seen = set()
    for i, item in enumerate(d["segments"]):
        path = f"/segments/{i}"
        if not isinstance(item, dict) or set(item) != {"id", "storyboard"}:
            fail(path, "Use exactly id and storyboard; embed the complete accepted document")
        identifier(item["id"], path + "/id")
        if item["id"] in seen:
            fail(path + "/id", "Segment IDs must be unique")
        seen.add(item["id"])
        try:
            storyboard = compile_storyboard(item["storyboard"])
        except InputError as error:
            raise InputError(
                Issue(
                    error.issue.code, path + "/storyboard" + error.issue.path, error.issue.message
                )
            ) from error
        segments.append(Segment(item["id"], storyboard))
    audio = audio_from_data(d["audio"], 90 * len(segments))
    if audio is None and version == "episode-0.1":
        fail("/audio", "Choose at least one registered narration or SFX track")
    # episode-0.2 permits audio: null to request a genuinely silent (zero-audio-stream) MP4.
    return Episode(d["title"], tuple(segments), audio)


def load_episode(path: Path) -> Episode:
    return compile_episode(load_project(path))


def frame_origin(plan: Episode, frame: int) -> tuple[Segment, int]:
    if type(frame) is not int or not 0 <= frame < plan.frames:
        fail("/frame", f"Use integer frame 0..{plan.frames - 1}")
    index, local = divmod(frame, 90)
    return plan.segments[index], local


def inspect_episode(plan: Episode, registry: AudioRegistry, frame: int | None = None) -> dict:
    cues = [] if plan.silent else cue_schedule(metadata_plan(plan, registry, plan.frames))
    result = {
        "contract": "episode-0.2" if plan.silent else "episode-0.1",
        "title": plan.title,
        "frames": plan.frames,
        "fps": 30,
        "seconds": plan.frames / 30,
        "output": [720, 1280],
        "silent": plan.silent,
        "audio_streams": 0 if plan.silent else 1,
        "effective_samples_per_channel": 0 if plan.silent else plan.frames * 1600,
        "registry_validation": "not-applicable" if plan.silent else "metadata-only",
        "media_bytes_validated": False,
        "audio_cues": cues,
        "editorial_cuts": [i * 90 for i in range(1, len(plan.segments))],
        "acting_continuity_across_segments": False,
        "segments": [
            {
                "id": s.id,
                "start_frame": i * 90,
                "end_frame": (i + 1) * 90,
                "storyboard": inspect_beats(s.storyboard),
            }
            for i, s in enumerate(plan.segments)
        ],
    }
    if frame is not None:
        segment, local = frame_origin(plan, frame)
        result.update(
            global_frame=frame,
            global_sample=frame * 1600,
            segment_id=segment.id,
            local_frame=local,
            visual=inspect_frame(segment.storyboard, local),
            active_cues=[c for c in cues if c["start_sample"] <= frame * 1600 < c["end_sample"]],
        )
    return result
