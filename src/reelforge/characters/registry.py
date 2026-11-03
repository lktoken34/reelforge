"""Trusted character registry: the single place episode-side code resolves a character id.

This decouples the blocking/scene/storyboard contracts from the hardwired Rowan drawer. Only
two characters are registered: the legacy ``rowan_01`` and ``yellow_mellow_v2``. Each entry
advertises its accepted scene-asset id, drawing conventions (ground origin, +X facing, uniform
scale), its supported scene-node actions, its expression vocabulary and the character-unit
standing height used to match physical size across rigs. No executable data, paths or code are
ever accepted from manifests; selection is by registered id only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from reelforge.rendering.model import DrawPath, RenderError

ROWAN_ID = "rowan_01"
YELLOW_MELLOW_ID = "yellow_mellow_v2"
DEFAULT_CHARACTER = ROWAN_ID


@dataclass(frozen=True)
class CharacterInfo:
    character_id: str
    asset_id: str
    display_name: str
    standing_height_units: float
    scene_actions: tuple[str, ...]
    expressions: tuple[str, ...]
    default_expression: str


def _rowan_info() -> CharacterInfo:
    from reelforge.characters.presets import ACTIONS, EXPRESSIONS

    return CharacterInfo(
        ROWAN_ID,
        ROWAN_ID,
        "Rowan Vale",
        # Rowan's skeleton: root->neck 58, +head 10 => ~94.5 standing root height in presets.
        94.5,
        ACTIONS,
        EXPRESSIONS,
        "concerned",
    )


def _yellow_mellow_info() -> CharacterInfo:
    from reelforge.characters.yellow_mellow_v2.catalog import CATALOG

    entry = CATALOG[YELLOW_MELLOW_ID]
    return CharacterInfo(
        YELLOW_MELLOW_ID,
        YELLOW_MELLOW_ID,
        entry.display_name,
        entry.standing_height_units,
        entry.actions,
        entry.expressions,
        "neutral",
    )


# Built lazily so importing this module never forces the renderer-heavy character packages.
_BUILDERS: dict[str, Callable[[], CharacterInfo]] = {
    ROWAN_ID: _rowan_info,
    YELLOW_MELLOW_ID: _yellow_mellow_info,
}


def is_registered(character_id: str) -> bool:
    return character_id in _BUILDERS


def character_ids() -> tuple[str, ...]:
    return tuple(_BUILDERS)


def character_info(character_id: str) -> CharacterInfo:
    if character_id not in _BUILDERS:
        raise RenderError(f"Unknown character {character_id!r}; registered: {sorted(_BUILDERS)}")
    return _BUILDERS[character_id]()


def asset_id_for(character_id: str) -> str:
    return character_info(character_id).asset_id


# Drawer protocol: a callable (pose_or_sample_time -> DrawPath tuple) is character-specific and
# produced by the blocking layer. The registry only needs to know *which* builder to call. The
# concrete Rowan drawer stays in blocking.sampling; the Yellow Mellow drawer lives in
# characters.yellow_mellow_v2.episode. This indirection avoids a hard import cycle.
def draw_commands_builder(character_id: str) -> str:
    """Return the module path whose ``build_drawer`` yields this character's per-frame drawer."""
    return {
        ROWAN_ID: "reelforge.characters.rowan",
        YELLOW_MELLOW_ID: "reelforge.characters.yellow_mellow_v2.episode",
    }[character_id]


def _ensure_commands(value: object) -> tuple[DrawPath, ...]:
    if not isinstance(value, tuple) or any(not isinstance(c, DrawPath) for c in value):
        raise RenderError("Character drawer must return a tuple of DrawPath commands")
    return value
