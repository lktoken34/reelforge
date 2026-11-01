"""Original diagnostic signals, synthesized in fixed-size blocks; no TTS or external audio."""

import argparse
import math
import struct
import tempfile
import wave
from pathlib import Path

from reelforge.audio.registry import register_asset
from reelforge.resources.monitor import JobMonitor

ROOT = Path(__file__).resolve().parents[1] / "assets/audio"


def synthesize(path: Path, rate: int, channels: int, frames: int, kind: int) -> None:
    count = rate * frames // 30
    with wave.open(str(path), "wb") as w:
        w.setparams((channels, 2, rate, count, "NONE", "not compressed"))
        for start in range(0, count, 2048):
            block = bytearray()
            for n in range(start, min(start + 2048, count)):
                t = n / rate
                duration = count / rate
                fade = min(1, t / 0.008, (duration - t) / 0.025)
                if kind == 0:
                    value = (
                        0.36
                        * fade
                        * (
                            0.8 * math.sin(math.tau * (720 * t + 120 * t * t))
                            + 0.2 * math.sin(math.tau * 1440 * t)
                        )
                    )
                elif kind == 1:
                    noise = ((n * 1103515245 + 12345) & 0x7FFFFFFF) / 1073741824 - 1
                    value = (
                        0.30
                        * fade
                        * math.exp(-t * 9)
                        * (0.8 * math.sin(math.tau * 170 * t) + 0.2 * noise)
                    )
                else:
                    value = (
                        0.36
                        * fade
                        * (
                            0.75 * math.sin(math.tau * (230 * t - 22 * t * t))
                            + 0.25 * math.sin(math.tau * 460 * t)
                        )
                    )
                for channel in range(channels):
                    v = value * (1 if channel == 0 else 0.8)
                    block.extend(struct.pack("<h", round(max(-1, min(1, v)) * 32767)))
            w.writeframesraw(block)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    root = parser.parse_args().output_dir
    root.mkdir(parents=True, exist_ok=True)
    with (
        JobMonitor(workspace=root),
        tempfile.TemporaryDirectory(prefix="audio-fixtures-", dir=root.parent) as temp,
    ):
        for asset_id, role, rate, channels, frames, kind in (
            ("diag_opening", "narration", 24000, 1, 36, 0),
            ("diag_fence", "sfx", 44100, 2, 12, 1),
            ("diag_suspense", "sfx", 48000, 1, 54, 2),
        ):
            source = Path(temp) / (asset_id + ".wav")
            synthesize(source, rate, channels, frames, kind)
            register_asset(root, source, asset_id, role)
    print("Registered three original diagnostic WAV assets.")


if __name__ == "__main__":
    main()
