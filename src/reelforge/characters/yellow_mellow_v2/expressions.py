"""Numeric facial expressions for Yellow Mellow V2.

A face is a small vector of bounded numbers (eye size, lids, brows, mouth) so expressions
blend continuously. Blinks are a deterministic schedule derived from a stable seed with
SHA-256, never wall-clock time or Python's randomized ``hash()``.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, fields, replace

from reelforge.rendering.model import RenderError, finite


@dataclass(frozen=True)
class FaceState:
    eye_scale: float = 1.0  # overall eye size
    eye_open: float = 1.0  # 0 closed .. 1 open (blinks multiply this)
    upper_lid: float = 0.0  # 0 none .. 1 heavy (tired/determined)
    lower_lid: float = 0.0  # 0 none .. 1 cheek-raised smile squint
    brow_raise: float = 0.0  # units upward
    brow_tilt: float = 0.0  # + inner ends up (worry), - inner ends down (determination)
    brow_asym: float = 0.0  # + raises the far brow, lowers the near brow (curiosity)
    mouth_curve: float = 0.2  # + smile, - frown
    mouth_open: float = 0.0  # 0 .. 1
    mouth_width: float = 1.0
    mouth_round: float = 0.0  # 0 wide shape .. 1 round "o"

    def __post_init__(self):
        values = [getattr(self, f.name) for f in fields(self)]
        finite(*values)
        if not (
            0.5 <= self.eye_scale <= 1.6
            and 0 <= self.eye_open <= 1
            and 0 <= self.upper_lid <= 1
            and 0 <= self.lower_lid <= 1
            and -2 <= self.brow_raise <= 5
            and abs(self.brow_tilt) <= 0.6
            and abs(self.brow_asym) <= 4
            and abs(self.mouth_curve) <= 1.2
            and 0 <= self.mouth_open <= 1
            and 0.4 <= self.mouth_width <= 1.6
            and 0 <= self.mouth_round <= 1
        ):
            raise RenderError("Face values exceed calibrated bounds")


EXPRESSIONS: dict[str, FaceState] = {
    "neutral": FaceState(),
    "happy": FaceState(
        eye_scale=1.02, lower_lid=0.42, brow_raise=1.2, mouth_curve=0.95, mouth_width=1.15
    ),
    "excited": FaceState(
        eye_scale=1.2,
        lower_lid=0.15,
        brow_raise=3.0,
        mouth_curve=0.75,
        mouth_open=0.75,
        mouth_width=1.15,
    ),
    "curious": FaceState(
        eye_scale=1.1,
        brow_raise=1.0,
        brow_asym=2.4,
        mouth_curve=0.0,
        mouth_open=0.22,
        mouth_width=0.6,
        mouth_round=1.0,
    ),
    "surprised": FaceState(
        eye_scale=1.32,
        brow_raise=3.8,
        mouth_curve=0.0,
        mouth_open=0.85,
        mouth_width=0.75,
        mouth_round=1.0,
    ),
    "concerned": FaceState(
        eye_scale=1.05, brow_raise=0.8, brow_tilt=0.42, mouth_curve=-0.55, mouth_width=0.85
    ),
    "determined": FaceState(
        eye_scale=0.98,
        upper_lid=0.28,
        lower_lid=0.18,
        brow_raise=-1.0,
        brow_tilt=-0.42,
        mouth_curve=0.1,
        mouth_width=0.9,
    ),
    "tired": FaceState(
        eye_scale=0.95,
        upper_lid=0.55,
        brow_raise=-0.6,
        brow_tilt=0.22,
        mouth_curve=-0.2,
        mouth_open=0.12,
        mouth_width=0.8,
        mouth_round=0.6,
    ),
}


def expression(name: str) -> FaceState:
    if name not in EXPRESSIONS:
        raise RenderError(f"Unknown expression {name!r}; use one of {sorted(EXPRESSIONS)}")
    return EXPRESSIONS[name]


def blend_faces(a: FaceState, b: FaceState, u: float) -> FaceState:
    finite(u)
    u = min(1.0, max(0.0, u))
    return FaceState(
        *(getattr(a, f.name) + (getattr(b, f.name) - getattr(a, f.name)) * u for f in fields(a))
    )


def adjust(face: FaceState, **deltas: float) -> FaceState:
    """Add bounded offsets (e.g. eye widening on take-off) to a face."""
    values = {}
    for name, delta in deltas.items():
        values[name] = getattr(face, name) + delta
    clamped = {
        "eye_scale": (0.5, 1.6),
        "eye_open": (0, 1),
        "upper_lid": (0, 1),
        "lower_lid": (0, 1),
        "brow_raise": (-2, 5),
        "brow_tilt": (-0.6, 0.6),
        "brow_asym": (-4, 4),
        "mouth_curve": (-1.2, 1.2),
        "mouth_open": (0, 1),
        "mouth_width": (0.4, 1.6),
        "mouth_round": (0, 1),
    }
    for name, value in values.items():
        lo, hi = clamped[name]
        values[name] = min(hi, max(lo, value))
    return replace(face, **values)


def _unit(seed: str, index: int) -> float:
    digest = hashlib.sha256(f"{seed}:{index}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def blink_starts(seed: str, frames: int, *, min_gap=54, max_gap=110, first=20) -> tuple[int, ...]:
    """Deterministic natural blink onsets (frames) for a timeline of ``frames`` frames."""
    starts, t, i = [], first, 0
    while t < frames:
        starts.append(t)
        t += min_gap + int(_unit(seed, i) * (max_gap - min_gap))
        i += 1
    return tuple(starts)


BLINK_FRAMES = 6


def blink_amount(frame: float, starts: tuple[int, ...]) -> float:
    """1 = eyes fully closed. Fast close (2 frames), slower open (4 frames)."""
    best = 0.0
    for s in starts:
        u = frame - s
        if 0 <= u <= BLINK_FRAMES:
            value = u / 2 if u < 2 else 1 - (u - 2) / (BLINK_FRAMES - 2)
            best = max(best, math.sin(min(1.0, max(0.0, value)) * math.pi / 2))
    return best
