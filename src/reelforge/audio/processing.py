"""Sample-grid mixing and AAC muxing using supervised, fixed FFmpeg commands."""

import array
import hashlib
import json
import math
import sys
from pathlib import Path
from threading import Event

from reelforge.core.errors import OperationError
from reelforge.media.process import run_bounded

from .registry import ResolvedCue


def command(
    args: list[str], *, cancelled: Event | None = None, timeout: float = 60, max_bytes: int = 262144
) -> bytes:
    rc, raw, errors = run_bounded(args, timeout=timeout, max_bytes=max_bytes, cancelled=cancelled)
    if rc or errors.strip():
        raise OperationError(
            "AUDIO_PROCESS", errors.decode(errors="replace")[-2048:] or "Audio child failed"
        )
    return raw


def ffmpeg() -> list[str]:
    return [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-xerror",
        "-max_alloc",
        "67108864",
        "-threads",
        "1",
        "-filter_threads",
        "1",
        "-filter_complex_threads",
        "1",
    ]


def mix_pcm(
    resolved: tuple[ResolvedCue, ...],
    frames: int,
    snapshots: dict[str, Path],
    output: Path,
    *,
    cancelled: Event | None = None,
) -> dict:
    args = ffmpeg()
    filters = []
    for i, r in enumerate(resolved):
        args += ["-protocol_whitelist", "file", "-f", "wav", "-i", str(snapshots[r.asset.id])]
        channel = (
            "pan=stereo|c0=c0|c1=c0,"
            if r.asset.channels == 1
            else "aformat=channel_layouts=stereo,"
        )
        filters.append(
            f"[{i}:a:0]{channel}aresample=48000:async=0:first_pts=0,"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=start_sample={r.cue.trim_start_frame * 1600}:"
            f"end_sample={r.trim_end_frame * 1600},"
            f"asetpts=PTS-STARTPTS,volume={r.cue.gain:.12g},"
            f"adelay={r.cue.start_frame * 1600}S:all=1[a{i}]"
        )
    labels = "".join(f"[a{i}]" for i in range(len(resolved)))
    samples = frames * 1600
    filters.append(
        labels + f"amix=inputs={len(resolved)}:duration=longest:dropout_transition=0:normalize=0,"
        f"apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB[mix]"
    )
    args += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[mix]",
        "-vn",
        "-sn",
        "-dn",
        "-threads:a",
        "1",
        "-c:a",
        "pcm_f32le",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-f",
        "f32le",
        "-n",
        str(output),
    ]
    command(args, cancelled=cancelled)
    if output.stat().st_size != samples * 8:
        raise OperationError(
            "AUDIO_LENGTH", "Mixed PCM did not produce exactly frames*1600 stereo samples"
        )
    stats = pcm_stats(output)
    if stats["peak"] > 0.90:
        raise OperationError(
            "AUDIO_CLIPPING", "Mix exceeds 0.90 full-scale headroom; reduce cue gains"
        )
    if stats["peak"] < 0.00001:
        raise OperationError(
            "AUDIO_SILENCE", "Selected audio produced a silent mix; no silent fallback"
        )
    return {
        "samples": samples,
        "statistics": stats,
        "command": args,
        "timing_grid": "1600 samples per integer 30-FPS frame at 48 kHz",
    }


def mux_audio(
    video: Path, pcm: Path, output: Path, frames: int, *, cancelled: Event | None = None
) -> list[str]:
    args = ffmpeg() + [
        "-protocol_whitelist",
        "file",
        "-i",
        str(video),
        "-f",
        "f32le",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-protocol_whitelist",
        "file",
        "-i",
        str(pcm),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-profile:a",
        "aac_low",
        "-b:a",
        "128000",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-threads:a",
        "1",
        "-frames:v",
        str(frames),
        "-t",
        f"{frames / 30:.9f}",
        "-map_metadata",
        "-1",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        "-n",
        str(output),
    ]
    command(args, cancelled=cancelled)
    return args


def blocks(path: Path, *, start: int = 0, end: int | None = None):
    """At most 64 KiB of interleaved stereo float32 PCM per iteration."""
    with path.open("rb") as f:
        f.seek(start * 8)
        remaining = None if end is None else max(0, end - start) * 8
        while remaining is None or remaining:
            raw = f.read(65536 if remaining is None else min(65536, remaining))
            if not raw:
                break
            if len(raw) % 8:
                raise OperationError("AUDIO_PCM", "Incomplete stereo float sample")
            if remaining is not None:
                remaining -= len(raw)
            values = array.array("f")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            yield values


def pcm_stats(path: Path) -> dict:
    count, peak, energy = 0, 0.0, 0.0
    h = hashlib.sha256()
    with path.open("rb") as f:
        while raw := f.read(65536):
            h.update(raw)
    for values in blocks(path):
        for value in values:
            if not math.isfinite(value):
                raise OperationError("AUDIO_PCM", "Nonfinite decoded PCM")
            peak = max(peak, abs(value))
            energy += value * value
        count += len(values)
    return {
        "samples_per_channel": count // 2,
        "peak": peak,
        "rms": math.sqrt(energy / max(1, count)),
        "energy": energy,
        "sha256": h.hexdigest(),
    }


def activity(path: Path, start: int, end: int, threshold: float) -> tuple[int | None, int | None]:
    first, last, index = None, None, start
    for values in blocks(path, start=start, end=end):
        for i in range(0, len(values), 2):
            if max(abs(values[i]), abs(values[i + 1])) >= threshold:
                if first is None:
                    first = index
                last = index
            index += 1
    return first, last


def envelope(path: Path, total: int, bin_samples: int = 2400) -> list[float]:
    """At most 600 peak-envelope bins for the 30-second contract ceiling."""
    peaks = []
    peak = 0.0
    count = 0
    for values in blocks(path, end=total):
        for i in range(0, len(values), 2):
            peak = max(peak, abs(values[i]), abs(values[i + 1]))
            count += 1
            if count == bin_samples:
                peaks.append(peak)
                peak, count = 0.0, 0
    if count:
        peaks.append(peak)
    return peaks


def video_pts(path: Path, *, cancelled: Event | None = None) -> list[str]:
    raw = command(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp_time",
            "-of",
            "json",
            str(path),
        ],
        cancelled=cancelled,
    )
    return [f["best_effort_timestamp_time"] for f in json.loads(raw)["frames"]]


def bitstream_hash(path: Path, *, cancelled: Event | None = None) -> str:
    return (
        command(
            ffmpeg()
            + [
                "-protocol_whitelist",
                "file",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-f",
                "hash",
                "-hash",
                "sha256",
                "pipe:1",
            ],
            cancelled=cancelled,
        )
        .decode()
        .strip()
    )


def verify_audio(
    video: Path,
    final: Path,
    reference: Path,
    decoded: Path,
    resolved: tuple[ResolvedCue, ...],
    frames: int,
    *,
    cancelled: Event | None = None,
) -> dict:
    total = frames * 1600
    raw = command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,sample_rate,channels,start_time,duration,time_base:format=duration",
            "-of",
            "json",
            str(final),
        ],
        cancelled=cancelled,
    )
    metadata = json.loads(raw)
    streams = metadata.get("streams", [])
    if [s.get("codec_type") for s in streams] != ["video", "audio"]:
        raise OperationError(
            "AUDIO_STREAMS", "Final MP4 needs exactly one video and one audio stream"
        )
    audio = streams[1]
    if not (
        audio.get("codec_name") == "aac"
        and audio.get("sample_rate") == "48000"
        and audio.get("channels") == 2
    ):
        raise OperationError("AUDIO_STREAMS", "Expected AAC / 48000 Hz / stereo")
    if (
        abs(float(audio.get("start_time", 999))) > 1 / 48000
        or abs(float(audio.get("duration", 0)) - frames / 30) > 1 / 48000
    ):
        raise OperationError(
            "AUDIO_TIMESTAMP", "AAC declared start/duration differs from the video interval"
        )
    command(
        ffmpeg()
        + [
            "-protocol_whitelist",
            "file",
            "-i",
            str(final),
            "-map",
            "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-c:a",
            "pcm_f32le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-threads:a",
            "1",
            "-f",
            "f32le",
            "-n",
            str(decoded),
        ],
        cancelled=cancelled,
    )
    a, b = pcm_stats(reference), pcm_stats(decoded)
    padding = b["samples_per_channel"] - total
    if not 0 <= padding <= 1024:
        raise OperationError(
            "AUDIO_PADDING", "Decoded AAC length outside one-packet terminal padding allowance"
        )
    if b["peak"] >= 0.9995 or b["energy"] <= 0:
        raise OperationError(
            "AUDIO_CLIPPING", "Decoded AAC clips or is unexpectedly silent; reduce source gain"
        )
    # Container edit-list / priming compensation must leave a gapless decoded audio sample clock.
    raw = command(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp_time,nb_samples",
            "-of",
            "json",
            str(final),
        ],
        cancelled=cancelled,
    )
    clock = json.loads(raw)["frames"]
    position = 0
    for frame in clock:
        if abs(float(frame["best_effort_timestamp_time"]) - position / 48000) > 0.000001:
            raise OperationError(
                "AUDIO_DRIFT", "Decoded audio has an initial offset or nonuniform sample clock"
            )
        position += frame["nb_samples"]
    before, after = video_pts(video, cancelled=cancelled), video_pts(final, cancelled=cancelled)
    if (
        before != after
        or len(after) != frames
        or any(abs(float(t) - i / 30) > 0.000001 for i, t in enumerate(after))
    ):
        raise OperationError("AUDIO_VIDEO_PTS", "Mux changed video presentation timing")
    old_hash, new_hash = (
        bitstream_hash(video, cancelled=cancelled),
        bitstream_hash(final, cancelled=cancelled),
    )
    if old_hash != new_hash:
        raise OperationError("AUDIO_VIDEO_COPY", "H.264 bitstream changed during mux")
    threshold = max(0.0001, a["peak"] * 0.02)
    first, last = activity(reference, 0, total, threshold)
    decoded_first, decoded_last = activity(decoded, 0, total, threshold)
    if (
        first is None
        or decoded_first is None
        or abs(first - decoded_first) > 1024
        or abs(last - decoded_last) > 1024
    ):
        raise OperationError(
            "AUDIO_SYNC", "Decoded audible onset/end differs by more than one AAC frame"
        )
    cues = []
    for r in resolved:
        start = r.cue.start_frame * 1600
        end = start + r.output_samples
        isolated = all(
            other is r
            or end <= other.cue.start_frame * 1600
            or start >= other.cue.start_frame * 1600 + other.output_samples
            for other in resolved
        )
        lo, hi = max(0, start - 1024), min(total, end + 1024)
        expected_onset, _ = activity(reference, lo, hi, threshold)
        observed_onset, _ = activity(decoded, lo, hi, threshold)
        error = (
            None
            if expected_onset is None or observed_onset is None
            else observed_onset - expected_onset
        )
        if isolated and expected_onset is not None and (error is None or abs(error) > 1024):
            raise OperationError(
                "AUDIO_CUE_SYNC", f"{r.asset.id}: decoded cue onset outside AAC tolerance"
            )
        cues.append(
            {
                "asset_id": r.asset.id,
                "start_frame": r.cue.start_frame,
                "scheduled_start_sample": start,
                "trim_start_frame": r.cue.trim_start_frame,
                "trim_end_frame": r.trim_end_frame,
                "effective_samples": r.output_samples,
                "isolated_mixed_window": isolated,
                "reference_audible_start_sample": expected_onset,
                "decoded_audible_start_sample": observed_onset,
                "onset_error_samples": error,
                "onset_error_ms": None if error is None else error / 48,
            }
        )
    difference = 0.0
    for left, right in zip(blocks(reference), blocks(decoded, end=total), strict=True):
        if len(left) != len(right):
            raise OperationError("AUDIO_PCM", "Decoded PCM too short for comparison")
        difference += sum((x - y) ** 2 for x, y in zip(left, right, strict=True))
    snr = None if difference == 0 else 10 * math.log10(a["energy"] / difference)
    return {
        "passed": True,
        "metadata": metadata,
        "effective_samples_per_channel": total,
        "raw_decoded_samples_per_channel": b["samples_per_channel"],
        "terminal_padding_samples": padding,
        "terminal_padding_policy": "Ignore codec tail outside the declared video/audio interval",
        "aac_tolerance_samples": 1024,
        "aac_tolerance_ms": 1024 / 48,
        "reference_pcm": a,
        "decoded_pcm": b,
        "snr_db": snr,
        "cue_timing": cues,
        "first_audible_error_samples": decoded_first - first,
        "last_audible_error_samples": decoded_last - last,
        "audible_drift_samples": (decoded_last - last) - (decoded_first - first),
        "decoded_audio_clock_gapless": True,
        "decoded_audio_first_pts": clock[0]["best_effort_timestamp_time"],
        "video_pts_unchanged": True,
        "video_pts": after,
        "h264_stream_copy_sha256": new_hash,
        "h264_bitstream_unchanged": True,
        "waveform": {
            "bin_samples": 2400,
            "sample_rate": 48000,
            "reference_peak_envelope": envelope(reference, total),
            "decoded_peak_envelope": envelope(decoded, total),
        },
        "scope": "Exact reference PCM frame grid; lossy AAC audible timing uses a tolerance",
    }
