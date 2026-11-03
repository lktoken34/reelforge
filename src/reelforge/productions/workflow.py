"""Render a production-0.1 as sequential silent episode chunks joined by stream-copy concat.

Each chunk is rendered by the existing audited ``render_episode`` into its own owned output
directory (so every chunk keeps the engine's memory admission, owned temp workspace, no-clobber
publish, full decode verification and cleanup). Chunks run strictly one at a time: no uncompressed
frames are accumulated across chunks. The chunk MP4s are then concatenated with the FFmpeg concat
demuxer using ``-c copy`` (no re-encode), guarded by a codec-parameter compatibility check, and the
assembled reel is verified independently for exactly ``frames`` decoded frames and continuous PTS.
"""

from __future__ import annotations

import json
import time
from fractions import Fraction
from pathlib import Path
from threading import Event

from reelforge.core.errors import OperationError
from reelforge.episodes.workflow import render_episode
from reelforge.media.process import run_bounded
from reelforge.media.verify import faststart_boxes
from reelforge.resources.deployment import check_workspace
from reelforge.resources.monitor import memory_snapshot

from .contract import Production

FFPROBE = "ffprobe"
FFMPEG = "ffmpeg"
VIDEO_ALLOWANCE = 64 * 1024**2  # a 60 s silent reel is larger than one 30 s chunk
# Full rgb24 framehash decode is CPU-bound; allow ~1 s per 12 frames plus headroom.
DECODE_TIMEOUT_PER_FRAME = 0.12


def _cancelled(cancelled: Event) -> None:
    if cancelled.is_set():
        raise OperationError("PRODUCTION_CANCELLED", "Production job cancelled")


def _probe_stream(path: Path, cancelled: Event) -> dict:
    rc, raw, err = run_bounded(
        [
            FFPROBE,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_streams",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt,avg_frame_rate,"
            "time_base,nb_frames,start_time,profile,level,color_range,color_space",
            "-of",
            "json",
            str(path),
        ],
        timeout=60,
        cancelled=cancelled,
    )
    if rc or err.strip():
        raise OperationError("PRODUCTION_PROBE", err.decode(errors="replace")[-512:])
    streams = json.loads(raw).get("streams", [])
    if len(streams) != 1:
        raise OperationError("PRODUCTION_STREAMS", f"Chunk {path.name} must have one video stream")
    return streams[0]


def _assert_compatible(streams: list[dict]) -> None:
    """Every chunk must share the codec parameters that make stream-copy concat valid."""
    keys = ("codec_name", "width", "height", "pix_fmt", "avg_frame_rate", "time_base", "profile")
    first = {k: streams[0].get(k) for k in keys}
    if first["codec_name"] != "h264" or first["pix_fmt"] != "yuv420p":
        raise OperationError("PRODUCTION_CODEC", "Chunks must be H.264/yuv420p")
    if first["avg_frame_rate"] != "30/1":
        raise OperationError("PRODUCTION_FPS", "Chunks must be 30/1 fps")
    for i, s in enumerate(streams[1:], 1):
        current = {k: s.get(k) for k in keys}
        if current != first:
            raise OperationError(
                "PRODUCTION_INCOMPATIBLE",
                f"Chunk {i} codec parameters differ from chunk 0; refusing unsafe concat",
            )


def _concat_copy(chunk_videos: list[Path], output: Path, cancelled: Event) -> list[str]:
    """Join chunk MP4s with the concat demuxer and stream copy (no re-encode)."""
    listing = output.parent / "concat_list.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in chunk_videos), encoding="ascii")
    args = [
        FFMPEG,
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-xerror",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-map",
        "0:v:0",
        "-c",
        "copy",
        "-an",
        "-sn",
        "-dn",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        "-n",
        str(output),
    ]
    rc, _out, err = run_bounded(args, timeout=180, cancelled=cancelled)
    if rc or err.strip():
        raise OperationError("PRODUCTION_CONCAT", err.decode(errors="replace")[-1024:])
    return args


def _verify_pts(path: Path, frames: int, cancelled: Event) -> dict:
    """Confirm monotonic, gapless PTS at exactly F/30 across the whole assembled reel."""
    rc, raw, err = run_bounded(
        [
            FFPROBE,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=best_effort_timestamp",
            "-of",
            "json",
            str(path),
        ],
        timeout=120,
        max_bytes=8 * 1024**2,
        cancelled=cancelled,
    )
    if rc or err.strip():
        raise OperationError("PRODUCTION_PTS_PROBE", err.decode(errors="replace")[-512:])
    time_base = _probe_stream(path, cancelled)["time_base"]
    base = Fraction(time_base)
    pts = [int(f["best_effort_timestamp"]) for f in json.loads(raw)["frames"]]
    if len(pts) != frames:
        raise OperationError("PRODUCTION_PTS", f"Expected {frames} PTS entries, got {len(pts)}")
    bad = [i for i, v in enumerate(pts) if v * base != Fraction(i, 30)]
    if bad:
        raise OperationError(
            "PRODUCTION_PTS", f"Non-continuous PTS at frames {bad[:8]} (expected exact F/30)"
        )
    return {"frames": len(pts), "time_base": time_base, "exact_video_pts": True}


def render_production(
    plan: Production, output_dir: Path, *, registry_root: Path, cancelled: Event | None = None
) -> dict:
    cancellation = cancelled if cancelled is not None else Event()
    started = time.perf_counter()
    output_dir = output_dir.resolve()
    if output_dir.exists() or output_dir.is_symlink():
        raise OperationError("OUTPUT_EXISTS", "Choose a new output directory")
    check_workspace(output_dir.parent)
    output_dir.mkdir(exist_ok=False)
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir()

    result: dict = {
        "contract": "production-0.1",
        "title": plan.title,
        "success": False,
        "frames": plan.frames,
        "seconds": plan.seconds,
        "fps": 30,
        "output": [720, 1280],
        "audio_streams": 0,
        "segments": len(plan.segments),
        "chunks": len(plan.chunks),
        "chunk_boundaries": plan.chunk_boundaries,
        "editorial_cuts": plan.editorial_cuts,
        "chunk_reports": [],
        "memory": {"initial": memory_snapshot()},
    }

    chunk_videos: list[Path] = []
    # 1. Render each chunk sequentially through the audited episode workflow.
    for chunk in plan.chunks:
        _cancelled(cancellation)
        chunk_out = chunks_dir / f"chunk_{chunk.index:02d}"
        report = render_episode(
            chunk.episode, chunk_out, registry_root=registry_root, cancelled=cancellation
        )
        result["chunk_reports"].append(
            {
                "index": chunk.index,
                "start_frame": chunk.start_frame,
                "frames": chunk.frames,
                "success": report.get("success"),
                "published": report.get("published"),
                "transaction_clean": report.get("transaction_clean"),
                "unique_decoded_frames": report.get("verification", {}).get(
                    "unique_decoded_frames"
                ),
                "peak_rss": (report.get("whole_job_memory") or {}).get(
                    "estimated_simultaneous_tree_peak_rss_bytes"
                ),
            }
        )
        if not report.get("success"):
            result["error"] = {"stage": f"chunk_{chunk.index}", "report": report.get("error")}
            result["memory"]["final"] = memory_snapshot()
            return result
        video = chunk_out / "reel.mp4"
        if not video.is_file():
            raise OperationError("PRODUCTION_CHUNK", f"Chunk {chunk.index} produced no reel.mp4")
        chunk_videos.append(video)

    # 2. Compatibility gate before any concat.
    streams = [_probe_stream(v, cancellation) for v in chunk_videos]
    _assert_compatible(streams)
    result["chunk_stream_params"] = {
        k: streams[0].get(k) for k in ("codec_name", "width", "height", "pix_fmt", "avg_frame_rate")
    }

    # 3. Stream-copy concat (no re-encode).
    final = output_dir / "reel.mp4"
    result["concat_command"] = _concat_copy(chunk_videos, final, cancellation)
    if final.stat().st_size > VIDEO_ALLOWANCE:
        raise OperationError("PRODUCTION_STORAGE", "Assembled reel exceeds the size allowance")

    # 4. Independent verification of the assembled reel: metadata, full decode (per-frame
    # framehash) and continuous PTS. Done with a bounded timeout scaled to the full length rather
    # than the 60 s cap baked into verify_video (which targets single <=900-frame chunks).
    assembled_hashes = _full_decode_hashes(final, plan.frames, cancellation)
    result["verification"] = {
        "decoded_frames": len(assembled_hashes),
        "unique_decoded_frames": len(set(assembled_hashes)),
        "metadata": _probe_metadata(final, cancellation),
        "mp4_top_level_boxes": faststart_boxes(final),
    }
    if len(assembled_hashes) != plan.frames:
        raise OperationError(
            "PRODUCTION_DECODE", f"Decoded {len(assembled_hashes)} frames, expected {plan.frames}"
        )
    result["pts"] = _verify_pts(final, plan.frames, cancellation)

    # 5. Confirm the concat neither dropped nor duplicated frames: the assembled decoded hash
    # sequence must equal the per-chunk source hashes (from each chunk's render report)
    # concatenated in order. This catches assembly-induced duplication or reordering exactly.
    source_hashes: list[str] = []
    for chunk, video in zip(plan.chunks, chunk_videos, strict=True):
        source_hashes.extend(_full_decode_hashes(video, chunk.frames, cancellation))
    if assembled_hashes != source_hashes:
        first = next(
            (
                i
                for i, (a, b) in enumerate(zip(assembled_hashes, source_hashes, strict=False))
                if a != b
            ),
            min(len(assembled_hashes), len(source_hashes)),
        )
        raise OperationError(
            "PRODUCTION_ASSEMBLY",
            f"Assembled frame hashes differ from concatenated chunks at frame {first}",
        )
    result["assembly_frame_hash_match"] = True

    result["file_size_bytes"] = final.stat().st_size
    result["memory"]["final"] = memory_snapshot()
    result["render_seconds"] = round(time.perf_counter() - started, 3)
    result["success"] = True
    (output_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def _probe_metadata(path: Path, cancelled: Event) -> dict:
    rc, raw, err = run_bounded(
        [
            FFPROBE,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name,codec_tag_string,pix_fmt,avg_frame_rate:"
            "format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        timeout=60,
        cancelled=cancelled,
    )
    if rc or err.strip():
        raise OperationError("PRODUCTION_PROBE", err.decode(errors="replace")[-512:])
    meta = json.loads(raw)
    stream = meta["streams"][0]
    if (stream["width"], stream["height"]) != (720, 1280):
        raise OperationError("PRODUCTION_META", "Assembled reel is not 720x1280")
    if stream["codec_name"] != "h264" or stream["pix_fmt"] != "yuv420p":
        raise OperationError("PRODUCTION_META", "Assembled reel is not H.264/yuv420p")
    if stream["codec_tag_string"] != "avc1" or Fraction(stream["avg_frame_rate"]) != 30:
        raise OperationError("PRODUCTION_META", "Assembled reel tag/fps differs")
    return meta


def _full_decode_hashes(path: Path, frames: int, cancelled: Event) -> list[str]:
    """Full per-frame rgb24 framehash decode with a length-scaled bounded timeout.

    Mirrors verify_video's decode (same -xerror/-err_detect explode semantics) but without the
    60 s cap baked in for <=900-frame chunks, so a 1800-frame reel can be fully decoded.
    """
    args = [
        FFMPEG,
        "-hide_banner",
        "-loglevel",
        "error",
        "-xerror",
        "-err_detect",
        "explode",
        "-threads",
        "1",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-threads:v",
        "1",
        "-filter_threads",
        "1",
        "-pix_fmt",
        "rgb24",
        "-fps_mode",
        "passthrough",
        "-f",
        "framehash",
        "-hash",
        "sha256",
        "pipe:1",
    ]
    timeout = max(60.0, frames * DECODE_TIMEOUT_PER_FRAME)
    # Each framehash line is an index plus a 64-hex digest (~100 bytes); allow generous headroom.
    rc, raw, err = run_bounded(
        args, timeout=timeout, max_bytes=frames * 160 + 65536, cancelled=cancelled
    )
    if rc or err.strip():
        raise OperationError("PRODUCTION_DECODE", err.decode(errors="replace")[-1024:])
    hashes = [
        line.rsplit(",", 1)[-1].strip()
        for line in raw.decode("ascii").splitlines()
        if line and not line.startswith("#")
    ]
    if any(len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in hashes):
        raise OperationError("PRODUCTION_DECODE", "Malformed framehash output")
    return hashes
