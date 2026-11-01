"""Small operator-owned registry. Only hashed, bounded PCM16 RIFF/WAVE files are admitted."""

import hashlib
import os
import re
import shutil
import struct
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event

from reelforge.contracts.project import load_project
from reelforge.core.errors import OperationError
from reelforge.stories.audio_contract import AudioPlan, Cue

from .transaction import private_directory

MAX_ASSETS, MAX_FILE_BYTES = 16, 8 * 1024**2
RATES = (16000, 24000, 44100, 48000)


def error(message: str) -> None:
    raise OperationError("AUDIO_ASSET", message)


def valid_id(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,47}", value) is not None


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(65536):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class Asset:
    id: str
    role: str
    file: str
    sha256: str
    size_bytes: int
    sample_rate: int
    channels: int
    samples: int

    @property
    def usable_frames(self) -> int:
        return self.samples * 30 // self.sample_rate


@dataclass(frozen=True)
class ResolvedCue:
    cue: Cue
    asset: Asset
    path: Path
    trim_end_frame: int
    output_samples: int


def inspect_wav(
    path: Path, role: str, *, cancelled: Event | None = None, workspace: Path | None = None
) -> dict:
    from reelforge.media.process import run_bounded

    if role not in ("narration", "sfx") or path.suffix.lower() != ".wav" or path.is_symlink():
        error("Use a regular .wav file and role narration or sfx; symlinks are forbidden")
    try:
        size = path.stat().st_size
        if not 44 <= size <= MAX_FILE_BYTES:
            error("WAV file must contain 44 bytes..8 MiB")
        with path.open("rb") as f:
            header = f.read(12)
        if (
            header[:4] != b"RIFF"
            or header[8:] != b"WAVE"
            or struct.unpack("<I", header[4:8])[0] + 8 != size
        ):
            error("Expected complete RIFF/WAVE; malformed/truncated/trailing bytes are forbidden")
        with wave.open(str(path), "rb") as w:
            rate, channels, samples = w.getframerate(), w.getnchannels(), w.getnframes()
            if w.getcomptype() != "NONE" or w.getsampwidth() != 2:
                error("Only uncompressed signed PCM16 WAV is supported")
            if rate not in RATES or channels not in (1, 2):
                error("Use mono/stereo PCM at 16000, 24000, 44100 or 48000 Hz")
            maximum = 30 if role == "narration" else 8
            if not (rate + 29) // 30 <= samples <= rate * maximum:
                error(f"{role} duration must be at least one video frame and at most {maximum}s")
            count = 0
            while block := w.readframes(4096):
                count += len(block)
            if count != samples * channels * 2:
                error("Truncated WAV sample payload")
    except (OSError, wave.Error, EOFError, struct.error) as exc:
        error(f"Invalid or missing WAV: {exc}")
    path = path.resolve()
    source_hash = digest(path)
    # Native decoders only see an immutable private copy, not a shared registry pathname.
    # Per-validation paths also isolate native filesystem snapshots between successive jobs.
    with private_directory(workspace or Path.cwd(), ".register-") as staging:
        decoder_path = staging / "input.wav"
        shutil.copyfile(path, decoder_path)
        if digest(decoder_path) != source_hash:
            error("Audio changed while preparing its validation snapshot")
        command = [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file",
            "-f",
            "wav",
            "-show_entries",
            "stream=codec_type,codec_name,sample_rate,channels:format=format_name",
            "-of",
            "json",
            str(decoder_path),
        ]
        rc, raw, err = run_bounded(command, timeout=15, max_bytes=65536, cancelled=cancelled)
        import json

        if rc or err.strip():
            error("WAV probing failed")
        try:
            probe = json.loads(raw)
            streams = probe["streams"]
            valid = (
                probe["format"]["format_name"] == "wav"
                and len(streams) == 1
                and streams[0]["codec_type"] == "audio"
                and streams[0]["codec_name"] == "pcm_s16le"
                and int(streams[0]["sample_rate"]) == rate
                and streams[0]["channels"] == channels
            )
        except (KeyError, ValueError, TypeError):
            valid = False
        if not valid:
            error(
                "Unsupported audio codec or inconsistent media metadata; only PCM16 WAV is accepted"
            )
        # Full bounded decode to the null sink, never collect the PCM in Python.
        rc, _, err = run_bounded(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-xerror",
                "-err_detect",
                "explode",
                "-threads",
                "1",
                "-protocol_whitelist",
                "file",
                "-f",
                "wav",
                "-i",
                str(decoder_path),
                "-map",
                "0:a:0",
                "-vn",
                "-sn",
                "-dn",
                "-threads:a",
                "1",
                "-f",
                "null",
                "-",
            ],
            timeout=30,
            max_bytes=65536,
            cancelled=cancelled,
        )
        if rc or err.strip():
            error("Registered WAV failed complete safe decoding")
    return {
        "sha256": source_hash,
        "size_bytes": size,
        "sample_rate": rate,
        "channels": channels,
        "samples": samples,
    }


class AudioRegistry:
    def __init__(self, root: Path):
        self.root = root.resolve()
        data = load_project(self.root / "registry.json")
        if (
            not isinstance(data, dict)
            or set(data) != {"schema_version", "assets"}
            or data["schema_version"] != "audio-assets-0.1"
        ):
            error("Unsupported trusted audio registry schema")
        if not isinstance(data["assets"], list) or not 0 <= len(data["assets"]) <= MAX_ASSETS:
            error("Registry supports at most sixteen assets")
        self.assets: dict[str, Asset] = {}
        keys = {"id", "role", "file", "sha256", "size_bytes", "sample_rate", "channels", "samples"}
        for record in data["assets"]:
            if not isinstance(record, dict) or set(record) != keys:
                error("Malformed audio registry entry")
            if not valid_id(record["id"]) or record["id"] in self.assets:
                error("Registry IDs must be unique snake_case names")
            if record["file"] != record["id"] + ".wav" or record["role"] not in (
                "narration",
                "sfx",
            ):
                error("Registry filename must be exactly ID.wav with a published role")
            if not isinstance(record["sha256"], str) or not re.fullmatch(
                "[a-f0-9]{64}", record["sha256"]
            ):
                error("Registry asset needs an exact SHA-256")
            for key in ("size_bytes", "sample_rate", "channels", "samples"):
                if type(record[key]) is not int or record[key] <= 0:
                    error("Registry numeric metadata must be positive integers")
            self.assets[record["id"]] = Asset(**record)

    def resolve(
        self,
        plan: AudioPlan,
        frames: int,
        *,
        cancelled: Event | None = None,
        workspace: Path | None = None,
    ) -> tuple[ResolvedCue, ...]:
        result = []
        checked = {}
        for cue in plan.tracks:
            asset = self.assets.get(cue.asset_id)
            if asset is None:
                error(f"Unknown audio ID {cue.asset_id}; register the asset before selecting it")
            role = "narration" if plan.narration is cue else "sfx"
            if asset.role != role:
                error(f"{asset.id}: expected registered role {role}")
            path = self.root / asset.file
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                error(f"{asset.id}: asset path escapes the registry")
            if asset.id not in checked:
                actual = inspect_wav(
                    path, asset.role, cancelled=cancelled, workspace=workspace or self.root
                )
                if any(actual[key] != getattr(asset, key) for key in actual):
                    error(f"{asset.id}: bytes/metadata changed; register a new trusted take")
                checked[asset.id] = actual
            end = asset.usable_frames if cue.trim_end_frame is None else cue.trim_end_frame
            if not 0 <= cue.trim_start_frame < end <= asset.usable_frames:
                error(f"{asset.id}: trim must lie within [0, {asset.usable_frames}] usable frames")
            with wave.open(str(path), "rb") as w:
                first = cue.trim_start_frame * asset.sample_rate // 30
                remaining = end * asset.sample_rate // 30 - first
                w.setpos(first)
                audible = False
                while remaining:
                    block = w.readframes(min(4096, remaining))
                    remaining -= len(block) // (asset.channels * 2)
                    if not block:
                        error(f"{asset.id}: truncated trim range")
                    audible = audible or any(block)
                if not audible:
                    error(f"{asset.id}: selected trim is entirely silent")
            samples = min(end - cue.trim_start_frame, frames - cue.start_frame) * 1600
            result.append(ResolvedCue(cue, asset, path, end, samples))
        # Conservative peak headroom at each overlap, without normalizing quiet cues upward.
        events = []
        for r in result:
            events.extend(
                (
                    (r.cue.start_frame * 1600, r.cue.gain),
                    (r.cue.start_frame * 1600 + r.output_samples, -r.cue.gain),
                )
            )
        gain = 0.0
        for _, delta in sorted(events):
            gain += delta
            if gain > 0.800000001:
                error("Overlapping cue gains exceed 0.8; reduce gain for explicit headroom")
        return tuple(result)


def register_asset(root: Path, source: Path, asset_id: str, role: str) -> Asset:
    """Operator-only import. Agent story data cannot choose source/registry paths."""
    if not valid_id(asset_id):
        error("Use a snake_case asset ID")
    root.mkdir(parents=True, exist_ok=True)
    if (root / "registry.json").exists():
        registry = AudioRegistry(root)
        records = [asdict(a) for a in registry.assets.values()]
    else:
        records = []
    if len(records) >= MAX_ASSETS or any(r["id"] == asset_id for r in records):
        error("Registry full or ID already registered; use a new take ID")
    metadata = inspect_wav(source, role, workspace=root)
    entry = Asset(asset_id, role, asset_id + ".wav", **metadata)
    destination = root / entry.file
    if destination.exists() or destination.is_symlink():
        error("Registered destination already exists; no overwrite permitted")
    import json

    with private_directory(root, ".register-") as private:
        pending = Path(private) / "asset.wav"
        shutil.copyfile(source, pending)
        if digest(pending) != entry.sha256:
            error("Source audio changed during registration")
        os.link(pending, destination)
        try:
            data = {"schema_version": "audio-assets-0.1", "assets": records + [asdict(entry)]}
            index = Path(private) / "registry.json"
            index.write_text(json.dumps(data, indent=2) + "\n")
            with index.open("rb") as f:
                os.fsync(f.fileno())
            os.replace(index, root / "registry.json")
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    return entry
