"""production-0.1 compiler: an ordered silent reel built from accepted episode-0.2 chunks.

The production manifest selects every segment of a long reel in one document. It is compiled into
a sequence of silent ``episode-0.2`` chunks (each 1..10 ninety-frame segments). Compiling each
chunk reuses the full accepted storyboard/blocking/direction/scene validation, so nothing about
segment semantics, character selection or silence is reinterpreted here. This layer only adds the
higher-level ordering and the explicit production-level bounds.

Explicit production bounds (new, do not touch episode-0.1/0.2):
- 2..20 segments total (180..1800 frames; 6..60 seconds at 30 FPS).
- chunked into groups of at most 10 segments (the accepted episode maximum), preserving order.
- silent only: audio must be null (a long reel is a silent visual deliverable).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue
from reelforge.episodes.contract import Episode, compile_episode
from reelforge.scenes.contract import identifier
from reelforge.storyboards.compiler import Storyboard, bounded_copy

FRAMES_PER_SEGMENT = 90
MAX_SEGMENTS_PER_CHUNK = 10
MIN_SEGMENTS = 2
MAX_SEGMENTS = 20


@dataclass(frozen=True)
class Segment:
    id: str
    storyboard: Storyboard


@dataclass(frozen=True)
class ProductionChunk:
    """One renderable silent episode-0.2 covering a contiguous slice of the production."""

    index: int
    start_frame: int
    episode: Episode

    @property
    def frames(self) -> int:
        return self.episode.frames


@dataclass(frozen=True)
class Production:
    title: str
    segments: tuple[Segment, ...]
    chunks: tuple[ProductionChunk, ...]

    @property
    def frames(self) -> int:
        return len(self.segments) * FRAMES_PER_SEGMENT

    @property
    def seconds(self) -> float:
        return self.frames / 30

    @property
    def editorial_cuts(self) -> list[int]:
        return [i * FRAMES_PER_SEGMENT for i in range(1, len(self.segments))]

    @property
    def chunk_boundaries(self) -> list[int]:
        """Global frame indices where one rendered chunk hands off to the next."""
        boundaries = []
        frame = 0
        for chunk in self.chunks[:-1]:
            frame += chunk.frames
            boundaries.append(frame)
        return boundaries


def fail(path: str, message: str) -> None:
    raise InputError(Issue("PRODUCTION_INVALID", path, message))


def _chunk_episode(title: str, items: list[dict], chunk_index: int) -> Episode:
    """Compile a contiguous slice of production segments as a silent episode-0.2."""
    data = {
        "schema_version": "episode-0.2",
        "title": f"{title} [chunk {chunk_index + 1}]"[:120],
        "segments": items,
        "audio": None,
    }
    return compile_episode(data)


def compile_production(data: object) -> Production:
    d = bounded_copy(data)
    if not isinstance(d, dict) or set(d) != {"schema_version", "title", "segments", "audio"}:
        fail("", "Use exactly schema_version, title, segments, audio")
    if d["schema_version"] != "production-0.1":
        fail("/schema_version", "Use production-0.1")
    if not isinstance(d["title"], str) or not d["title"].strip() or len(d["title"]) > 120:
        fail("/title", "Use nonblank text <=120 characters")
    if d["audio"] is not None:
        fail("/audio", "production-0.1 is silent; use audio: null (zero audio streams)")
    raw = d["segments"]
    if not isinstance(raw, list) or not MIN_SEGMENTS <= len(raw) <= MAX_SEGMENTS:
        fail(
            "/segments",
            f"Use {MIN_SEGMENTS}..{MAX_SEGMENTS} ordered 90-frame storyboard segments",
        )
    # Validate IDs and uniqueness across the whole production before chunk compilation.
    seen: set[str] = set()
    for i, item in enumerate(raw):
        path = f"/segments/{i}"
        if not isinstance(item, dict) or set(item) != {"id", "storyboard"}:
            fail(path, "Use exactly id and storyboard; embed the complete accepted document")
        identifier(item["id"], path + "/id")
        if item["id"] in seen:
            fail(path + "/id", "Segment IDs must be unique across the production")
        seen.add(item["id"])

    # Split into contiguous chunks of at most MAX_SEGMENTS_PER_CHUNK, preserving order, and
    # compile each as a silent episode-0.2 (reusing the full accepted validation path).
    chunks: list[ProductionChunk] = []
    segments: list[Segment] = []
    frame = 0
    for chunk_index, begin in enumerate(range(0, len(raw), MAX_SEGMENTS_PER_CHUNK)):
        items = raw[begin : begin + MAX_SEGMENTS_PER_CHUNK]
        try:
            episode = _chunk_episode(d["title"], items, chunk_index)
        except InputError as error:
            # Remap chunk-local segment pointers back to production-level indices.
            remapped = _remap(error.issue.path, begin)
            raise InputError(Issue(error.issue.code, remapped, error.issue.message)) from error
        chunks.append(ProductionChunk(chunk_index, frame, episode))
        for seg in episode.segments:
            segments.append(Segment(seg.id, seg.storyboard))
        frame += episode.frames

    return Production(d["title"], tuple(segments), tuple(chunks))


def _remap(path: str, begin: int) -> str:
    """Translate a chunk-local /segments/<k>/... pointer to the production index."""
    prefix = "/segments/"
    if path.startswith(prefix):
        rest = path[len(prefix) :]
        head, _, tail = rest.partition("/")
        if head.isdigit():
            production_index = begin + int(head)
            return f"/segments/{production_index}" + (f"/{tail}" if tail else "")
    return path


def load_production(path: Path) -> Production:
    return compile_production(load_project(path))
