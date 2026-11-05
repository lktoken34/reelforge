"""Declarative narrative grammars; no object IDs, artwork, positions or camera equations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pattern:
    id: str
    stages: tuple[str, ...]
    required: frozenset[str]


PATTERNS = (
    Pattern(
        "discovery_reaction",
        ("establish", "approach", "discover", "react", "hold"),
        frozenset(("establish", "discover", "react")),
    ),
    Pattern(
        "approach_suspense",
        ("establish", "approach", "hold", "react"),
        frozenset(("establish", "approach", "hold", "react")),
    ),
    Pattern(
        "threat_escape",
        ("establish", "approach", "discover", "react", "escape", "hold"),
        frozenset(("establish", "react", "escape")),
    ),
)

# These describe observable supported performances, not inferred emotions or audio.
BEAT_ACTIONS = {
    "establish": ("idle", "look_around", "walk_to"),
    "discover": ("idle", "look_around", "stop_at"),
    "approach": ("walk_to", "stop_at"),
    "react": ("react", "look_around", "activate"),
    "escape": ("run_to",),
    "hold": ("idle", "look_around", "react", "activate"),
}
ACTIONS = ("idle", "look_around", "react", "activate", "walk_to", "stop_at", "run_to")


def pattern_capabilities() -> list[dict]:
    return [
        {
            "id": p.id,
            "ordered_stages": p.stages,
            "required": sorted(p.required),
            "repeatable_stages": ["approach", "hold"],
        }
        for p in PATTERNS
    ]
