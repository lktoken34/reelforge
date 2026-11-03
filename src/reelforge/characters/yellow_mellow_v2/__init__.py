"""Yellow Mellow V2: reusable 2.5D character rig, artwork, expressions and motion library.

V1 (``reelforge.characters.yellow_mellow``) is preserved unchanged; V2 reuses its Moonlit
Observatory layers through an adapter. See docs/YELLOW_MELLOW_V2.md.
"""

from .character import (
    ActionRequest,
    CharacterFrame,
    FollowCamera,
    Performance,
    Stage,
    YellowMellowV2,
    draw_frame,
)
from .expressions import EXPRESSIONS, FaceState, expression
from .motions import LOCOMOTION_ACTIONS, PRESET_DOCS, PRESETS
from .rig import ArmPose, FootState, MellowPose, evaluate

__all__ = [
    "ActionRequest",
    "ArmPose",
    "CharacterFrame",
    "EXPRESSIONS",
    "FaceState",
    "FollowCamera",
    "FootState",
    "LOCOMOTION_ACTIONS",
    "MellowPose",
    "PRESETS",
    "PRESET_DOCS",
    "Performance",
    "Stage",
    "YellowMellowV2",
    "draw_frame",
    "evaluate",
    "expression",
]
