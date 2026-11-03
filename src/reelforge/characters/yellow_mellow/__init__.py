"""Yellow Mellow character package for ReelForge.

Includes skeletal rig, vector artwork, reusable poses, and moonlit rooftop environment.
"""

from .artwork import draw_yellow_mellow
from .environment import draw_observatory_rooftop
from .poses import (
    FrameAnimationState,
    pose_crouch,
    pose_hands_up,
    pose_jump_apex,
    pose_land,
    pose_rest,
    sample_jump_animation,
)
from .rig import YELLOW_MELLOW_SKELETON, solve_vertical_leg_ik

__all__ = [
    "YELLOW_MELLOW_SKELETON",
    "solve_vertical_leg_ik",
    "draw_yellow_mellow",
    "draw_observatory_rooftop",
    "pose_rest",
    "pose_hands_up",
    "pose_crouch",
    "pose_jump_apex",
    "pose_land",
    "sample_jump_animation",
    "FrameAnimationState",
]
