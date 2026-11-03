"""Phase 9B: production-0.1 (60-second chunked reel) contract, ordering and safety tests.

These tests do not render a full 60-second video (that is the separate demonstration); they
cover the production contract, chunking/ordering, frame accounting, silent validation, backward
compatibility with episode-0.1/0.2, and the workflow's compatibility/assembly guards via small
fakes so they stay fast and deterministic.
"""

import copy
import json
from pathlib import Path

import pytest

from reelforge.core.errors import InputError, OperationError
from reelforge.episodes.contract import compile_episode
from reelforge.productions import compile_production, load_production
from reelforge.productions.contract import (
    MAX_SEGMENTS,
    MAX_SEGMENTS_PER_CHUNK,
    MIN_SEGMENTS,
)
from reelforge.productions.workflow import _assert_compatible

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "examples/productions/yellow_mellow_60s.json"


@pytest.fixture(scope="module")
def manifest():
    return json.loads(PRODUCTION.read_text())


# ----------------------------------------------------------------- contract
def test_sixty_second_manifest_compiles(manifest):
    plan = compile_production(manifest)
    assert len(plan.segments) == 20
    assert plan.frames == 1800
    assert plan.seconds == 60.0


def test_twenty_segments_split_into_two_ordered_chunks(manifest):
    plan = compile_production(manifest)
    assert len(plan.chunks) == 2
    assert [c.frames for c in plan.chunks] == [900, 900]
    assert [c.start_frame for c in plan.chunks] == [0, 900]
    assert plan.chunk_boundaries == [900]
    # Segment order is preserved across the chunk split.
    manifest_ids = [s["id"] for s in manifest["segments"]]
    plan_ids = [s.id for s in plan.segments]
    assert plan_ids == manifest_ids
    chunk_ids = [s.id for c in plan.chunks for s in c.episode.segments]
    assert chunk_ids == manifest_ids


def test_editorial_cuts_at_every_segment_boundary(manifest):
    plan = compile_production(manifest)
    assert plan.editorial_cuts == [i * 90 for i in range(1, 20)]
    # The 30-second chunk join coincides with an editorial cut, never mid-segment.
    assert set(plan.chunk_boundaries).issubset(set(plan.editorial_cuts))


def test_frame_total_is_segments_times_ninety(manifest):
    plan = compile_production(manifest)
    assert plan.frames == len(plan.segments) * 90


# ----------------------------------------------------------------- validation / bounds
def test_audio_must_be_null(manifest):
    bad = copy.deepcopy(manifest)
    bad["audio"] = {
        "sample_rate": 48000,
        "channels": 2,
        "codec": "aac",
        "bitrate": 128000,
        "narration": None,
        "cues": [],
    }
    with pytest.raises(InputError) as e:
        compile_production(bad)
    assert e.value.issue.path == "/audio"


def test_too_few_and_too_many_segments_rejected(manifest):
    one = copy.deepcopy(manifest)
    one["segments"] = one["segments"][:1]
    with pytest.raises(InputError):
        compile_production(one)
    too_many = copy.deepcopy(manifest)
    base = too_many["segments"]
    too_many["segments"] = [
        {"id": f"seg_{i}", "storyboard": base[i % len(base)]["storyboard"]}
        for i in range(MAX_SEGMENTS + 1)
    ]
    with pytest.raises(InputError):
        compile_production(too_many)


def test_wrong_schema_version_rejected(manifest):
    bad = copy.deepcopy(manifest)
    bad["schema_version"] = "production-9"
    with pytest.raises(InputError) as e:
        compile_production(bad)
    assert e.value.issue.path == "/schema_version"


def test_duplicate_segment_ids_rejected(manifest):
    bad = copy.deepcopy(manifest)
    bad["segments"][1]["id"] = bad["segments"][0]["id"]
    with pytest.raises(InputError) as e:
        compile_production(bad)
    assert "unique" in e.value.issue.message.lower()


def test_segment_error_pointer_remapped_to_production_index(manifest):
    # Break a storyboard in the second chunk (segment index 12) and confirm the error path
    # reports the production-level index, not the chunk-local one.
    bad = copy.deepcopy(manifest)
    bad["segments"][12]["storyboard"]["schema_version"] = "storyboard-9"
    with pytest.raises(InputError) as e:
        compile_production(bad)
    assert e.value.issue.path.startswith("/segments/12/")


def test_bounds_constants_sane():
    assert MIN_SEGMENTS == 2
    assert MAX_SEGMENTS == 20
    assert MAX_SEGMENTS_PER_CHUNK == 10


# ----------------------------------------------------------------- backward compatibility
def test_episode_contracts_unchanged():
    # episode-0.1 still requires audio; episode-0.2 still allows null. production bounds do not
    # leak into the episode contract (still 1..10 segments).
    r = json.loads((ROOT / "examples/reels/silent_signal.json").read_text())
    with pytest.raises(InputError):
        compile_episode(
            {
                "schema_version": "episode-0.1",
                "title": "x",
                "segments": [{"id": "a", "storyboard": r["storyboard"]}],
                "audio": None,
            }
        )
    plan = compile_episode(
        {
            "schema_version": "episode-0.2",
            "title": "x",
            "segments": [{"id": "a", "storyboard": r["storyboard"]}],
            "audio": None,
        }
    )
    assert plan.silent and plan.frames == 90
    eleven = {
        "schema_version": "episode-0.2",
        "title": "x",
        "segments": [{"id": f"s{i}", "storyboard": r["storyboard"]} for i in range(11)],
        "audio": None,
    }
    with pytest.raises(InputError):
        compile_episode(eleven)  # episodes stay capped at 10 segments


def test_each_chunk_is_a_valid_silent_episode(manifest):
    plan = compile_production(manifest)
    for chunk in plan.chunks:
        assert chunk.episode.silent is True
        assert chunk.episode.audio is None
        assert 1 <= len(chunk.episode.segments) <= MAX_SEGMENTS_PER_CHUNK


# ----------------------------------------------------------------- chunk compatibility gate
def _stream(**over):
    base = {
        "codec_name": "h264",
        "width": 720,
        "height": 1280,
        "pix_fmt": "yuv420p",
        "avg_frame_rate": "30/1",
        "time_base": "1/15360",
        "profile": "Main",
    }
    base.update(over)
    return base


def test_compatible_chunks_pass():
    _assert_compatible([_stream(), _stream()])  # no raise


def test_incompatible_chunks_rejected():
    with pytest.raises(OperationError) as e:
        _assert_compatible([_stream(), _stream(width=1080)])
    assert e.value.code == "PRODUCTION_INCOMPATIBLE"
    with pytest.raises(OperationError):
        _assert_compatible([_stream(codec_name="hevc")])
    with pytest.raises(OperationError):
        _assert_compatible([_stream(avg_frame_rate="25/1")])


def test_loader_roundtrip():
    plan = load_production(PRODUCTION)
    assert plan.frames == 1800 and len(plan.chunks) == 2
