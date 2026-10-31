"""Bounded metadata + full decode verification of diagnostic MP4s; no artistic scoring."""

import json
import shutil
from fractions import Fraction
from pathlib import Path
from threading import Event

from .process import VideoError, run_bounded


def faststart_boxes(path: Path) -> list[str]:
    """Inspect bounded top-level headers by seeking; never load the MP4 into memory."""
    boxes = []
    length = path.stat().st_size
    with path.open("rb") as handle:
        offset = 0
        while offset < length and len(boxes) < 64:
            handle.seek(offset)
            header = handle.read(8)
            if len(header) != 8:
                raise VideoError("MP4_LAYOUT", "Truncated MP4 box")
            size = int.from_bytes(header[:4], "big")
            header_size = 8
            if size == 1:
                extended = handle.read(8)
                if len(extended) != 8:
                    raise VideoError("MP4_LAYOUT", "Truncated extended MP4 box")
                size = int.from_bytes(extended, "big")
                header_size = 16
            if size == 0:
                size = length - offset
            if size < header_size or offset + size > length:
                raise VideoError("MP4_LAYOUT", "Invalid MP4 box size")
            boxes.append(header[4:].decode("ascii", errors="replace"))
            offset += size
    if (
        offset != length
        or not boxes
        or boxes[0] != "ftyp"
        or "moov" not in boxes
        or "mdat" not in boxes
        or boxes.index("moov") > boxes.index("mdat")
    ):
        raise VideoError("MP4_FASTSTART", "Expected MP4 ftyp and moov before media data")
    return boxes


def verify_video(
    path: Path,
    *,
    width: int,
    height: int,
    frames: int = 150,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    cancelled: Event | None = None,
) -> dict:
    executable, probe = shutil.which(ffmpeg), shutil.which(ffprobe)
    if executable is None or probe is None:
        raise VideoError("VERIFY_TOOL_MISSING", "FFmpeg and ffprobe are required for verification")
    rc, raw, errors = run_bounded(
        [
            probe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name,codec_tag_string,pix_fmt,avg_frame_rate,nb_read_frames:format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        timeout=30,
        cancelled=cancelled,
    )
    if rc or errors.strip():
        raise VideoError("PROBE_FAILED", errors.decode("utf-8", errors="replace")[-2048:])
    try:
        metadata = json.loads(raw)
        stream = metadata["streams"][0]
        matches = (
            (stream["width"], stream["height"]) == (width, height)
            and stream["codec_name"] == "h264"
            and stream["pix_fmt"] == "yuv420p"
            and stream["codec_tag_string"] == "avc1"
            and Fraction(stream["avg_frame_rate"]) == 30
            and int(stream["nb_read_frames"]) == frames
            and abs(float(metadata["format"]["duration"]) - frames / 30) <= 1 / 30
        )
    except (ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as error:
        raise VideoError("PROBE_INVALID", "Malformed ffprobe response") from error
    if not matches:
        raise VideoError("VIDEO_METADATA", "Output metadata differs from requested diagnostic")
    # Every decoded RGB24 frame is checksummed in FFmpeg; raw frame pixels never enter Python.
    decode_command = [
        executable,
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
    rc, raw_hashes, errors = run_bounded(decode_command, timeout=60, cancelled=cancelled)
    if rc or errors.strip():
        raise VideoError("DECODE_FAILED", errors.decode("utf-8", errors="replace")[-2048:])
    hashes = [
        line.rsplit(",", 1)[-1].strip()
        for line in raw_hashes.decode("ascii").splitlines()
        if line and not line.startswith("#")
    ]
    if len(hashes) != frames or any(
        len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in hashes
    ):
        raise VideoError("DECODE_FRAME_COUNT", "Full decode did not produce every expected frame")
    if len(set(hashes)) < 3:
        raise VideoError("MOTION_MISSING", "Decoded diagnostic does not contain changing frames")
    return {
        "passed": True,
        "mp4_top_level_boxes": faststart_boxes(path),
        "metadata": metadata,
        "decoded_frames": len(hashes),
        "unique_decoded_frames": len(set(hashes)),
        "decoded_rgb_sha256": hashes,
        "decode_exit_status": rc,
        "decode_command": decode_command,
        "comparison_scope": "Exact decoded RGB24 hashes on the same native FFmpeg build",
    }
