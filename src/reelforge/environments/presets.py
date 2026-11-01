"""Native-free weak-agent contract for the orchard quality gate."""

from dataclasses import dataclass
from pathlib import Path

from reelforge.rendering.model import RenderError, finite


@dataclass(frozen=True)
class EnvironmentPreset:
    environment: str = "last_light_orchard_01"
    shot: str = "orchard_push"
    atmosphere: float = 0.65
    warmth: float = 0.7
    breeze: float = 0.45
    framing: float = 0.0

    def __post_init__(self):
        if self.environment != "last_light_orchard_01":
            raise RenderError("/environment: choose last_light_orchard_01")
        if self.shot not in ("orchard_push", "orchard_pan", "locked", "orchard_suspense"):
            raise RenderError("/shot: choose orchard_push, orchard_pan, locked or orchard_suspense")
        for key in ("atmosphere", "warmth", "breeze", "framing"):
            value = getattr(self, key)
            finite(value)
            low, high = (-1, 1) if key == "framing" else (0, 1)
            if not low <= value <= high:
                raise RenderError(f"/{key}: use a finite number in [{low}, {high}]")

    @classmethod
    def from_data(cls, data: dict) -> "EnvironmentPreset":
        fields = {"environment", "shot", "atmosphere", "warmth", "breeze", "framing"}
        if not isinstance(data, dict) or set(data) != fields:
            raise RenderError("Environment preset requires exactly: " + ", ".join(sorted(fields)))
        if not isinstance(data["environment"], str) or not isinstance(data["shot"], str):
            raise RenderError("/environment and /shot must be published string IDs")
        return cls(**data)


def load_preset(path) -> EnvironmentPreset:
    from reelforge.contracts.project import load_project

    return EnvironmentPreset.from_data(load_project(Path(path)))
