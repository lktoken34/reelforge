"""Reusable poses and deterministic jump motion curves for Yellow Mellow.

Defines isolated pose constructors (rest, hands_up, crouch, jump_apex, land)
and the 30-frame deterministic animation timeline sampler.
"""

import math
from dataclasses import dataclass

from reelforge.characters.rig import Pose, Rigid

from .rig import UPPER_ARM, UPPER_LEG, solve_vertical_leg_ik

GROUND_Y = 530.0
CHAR_SCALE = 1.30
HIP_LOCAL_Y = 4.0
REST_LEG_LENGTH = 48.0   # 24 upper + 24 lower
# Standing root Y so foot (hip 4 + leg 48 = 52) lands exactly at GROUND_Y:
REST_ROOT_Y = GROUND_Y - (HIP_LOCAL_Y + REST_LEG_LENGTH) * CHAR_SCALE  # 530 - 52 * 1.3 = 462.4


def smooth_step(t: float) -> float:
    """Hermite smoothstep interpolation on [0, 1]."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def pose_rest() -> Pose:
    """Standard neutral standing pose with arms relaxed symmetrically at sides."""
    return Pose(
        root=Rigid(0.0, 0.0, 0.0),
        angles=(
            ("torso", 0.0),
            ("neck", 0.0),
            ("head", 0.0),
            ("beanie", 0.0),
            ("far_shoulder", -0.08),
            ("far_elbow", -0.05),
            ("far_hand", 0.0),
            ("near_shoulder", 0.08),
            ("near_elbow", 0.05),
            ("near_hand", 0.0),
            ("far_hip", 0.0),
            ("far_knee", 0.0),
            ("far_foot", 0.0),
            ("near_hip", 0.0),
            ("near_knee", 0.0),
            ("near_foot", 0.0),
        ),
    )


def pose_hands_up(raise_amount: float = 1.0) -> Pose:
    """Expressive hands-raised pose with both shoulders rotated upward symmetrically."""
    u = smooth_step(raise_amount)
    near_sh = 0.08 - 2.08 * u      # Rotates up-right to -2.00 rad
    far_sh = -0.08 + 2.08 * u      # Rotates up-left to +2.00 rad
    near_el = 0.05 - 0.45 * u      # Curves inward
    far_el = -0.05 + 0.45 * u      # Curves inward
    neck_angle = -0.12 * u         # Tilts back/up
    head_angle = -0.10 * u
    
    return Pose(
        root=Rigid(0.0, 0.0, 0.0),
        angles=(
            ("torso", 0.0),
            ("neck", neck_angle),
            ("head", head_angle),
            ("beanie", 0.0),
            ("far_shoulder", far_sh),
            ("far_elbow", far_el),
            ("far_hand", 0.15 * u),
            ("near_shoulder", near_sh),
            ("near_elbow", near_el),
            ("near_hand", -0.15 * u),
            ("far_hip", 0.0),
            ("far_knee", 0.0),
            ("far_foot", 0.0),
            ("near_hip", 0.0),
            ("near_knee", 0.0),
            ("near_foot", 0.0),
        ),
    )


def pose_crouch(compression_ratio: float = 0.65, torso_lean: float = 0.12, arm_back: float = 0.80) -> Pose:
    """Pre-jump anticipation crouch with deeply bent knees and feet pinned flat."""
    target_dy = REST_LEG_LENGTH * compression_ratio
    hip_angle, knee_angle, ankle_angle = solve_vertical_leg_ik(target_dy)
    
    return Pose(
        root=Rigid(0.0, 0.0, 0.0),
        angles=(
            ("torso", torso_lean),
            ("neck", -0.06),
            ("head", 0.08),
            ("beanie", 0.0),
            ("far_shoulder", -arm_back),
            ("far_elbow", -0.85),
            ("far_hand", 0.0),
            ("near_shoulder", arm_back),
            ("near_elbow", 0.85),
            ("near_hand", 0.0),
            ("far_hip", hip_angle),
            ("far_knee", knee_angle),
            ("far_foot", ankle_angle),
            ("near_hip", hip_angle),
            ("near_knee", knee_angle),
            ("near_foot", ankle_angle),
        ),
    )


def pose_jump_apex() -> Pose:
    """Peak airborne jump pose with tucked legs and triumphant raised arms."""
    return Pose(
        root=Rigid(0.0, 0.0, 0.0),
        angles=(
            ("torso", -0.05),
            ("neck", -0.08),
            ("head", -0.08),
            ("beanie", -0.04),
            # Symmetrical celebratory raised arms
            ("far_shoulder", 2.15),
            ("far_elbow", 0.35),
            ("far_hand", 0.15),
            ("near_shoulder", -2.15),
            ("near_elbow", -0.35),
            ("near_hand", -0.15),
            # Symmetrical athletic mid-air leg tuck
            ("far_hip", 0.35),
            ("far_knee", -0.70),
            ("far_foot", 0.35),
            ("near_hip", 0.35),
            ("near_knee", -0.70),
            ("near_foot", 0.35),
        ),
    )


def pose_land(compression_ratio: float = 0.75) -> Pose:
    """Landing pose absorbing impact through knee flexion with level feet."""
    target_dy = REST_LEG_LENGTH * compression_ratio
    hip_angle, knee_angle, ankle_angle = solve_vertical_leg_ik(target_dy)
    comp_norm = 1.0 - compression_ratio
    
    return Pose(
        root=Rigid(0.0, 0.0, 0.0),
        angles=(
            ("torso", 0.08 * comp_norm),
            ("neck", 0.0),
            ("head", 0.0),
            ("beanie", 0.0),
            # Symmetrical arm balance
            ("far_shoulder", 0.45 * comp_norm),
            ("far_elbow", -0.60 * comp_norm),
            ("far_hand", 0.0),
            ("near_shoulder", -0.45 * comp_norm),
            ("near_elbow", 0.60 * comp_norm),
            ("near_hand", 0.0),
            ("far_hip", hip_angle),
            ("far_knee", knee_angle),
            ("far_foot", ankle_angle),
            ("near_hip", hip_angle),
            ("near_knee", knee_angle),
            ("near_foot", ankle_angle),
        ),
    )


@dataclass(frozen=True)
class FrameAnimationState:
    frame: int
    char_pos: tuple[float, float]
    pose: Pose
    expression: str
    eye_scale: float
    brow_lift: float
    mouth_open: float
    shadow_scale: float
    shadow_alpha: float


def sample_jump_animation(frame: int) -> FrameAnimationState:
    """Evaluates the exact 30-frame animation state for frame 0..29."""
    if not 0 <= frame <= 29:
        raise ValueError(f"Frame must be 0..29, got {frame}")
    
    x_center = 180.0
    
    # --- PHASE 1: Frames 0..5 (Standing & Raising Hands) ---
    if frame <= 5:
        u = frame / 5.0
        e = smooth_step(u)
        pose = pose_hands_up(raise_amount=e)
        return FrameAnimationState(
            frame=frame,
            char_pos=(x_center, REST_ROOT_Y),
            pose=pose,
            expression="excited" if u > 0.4 else "smile",
            eye_scale=1.0 + 0.35 * e,
            brow_lift=3.5 * e,
            mouth_open=0.2 * e,
            shadow_scale=1.0,
            shadow_alpha=0.45,
        )
    
    # --- PHASE 2: Frames 6..11 (Anticipation Crouch) ---
    elif frame <= 11:
        u = (frame - 5) / 6.0
        e = smooth_step(u)
        crouch_drop = 22.0 * e  # Drops root by up to 22 units
        root_y = REST_ROOT_Y + crouch_drop
        
        # Calculate exact target_dy in local character units so feet stay at GROUND_Y
        world_hip_y = root_y + HIP_LOCAL_Y * CHAR_SCALE
        local_dy = (GROUND_Y - world_hip_y) / CHAR_SCALE
        hip_angle, knee_angle, ankle_angle = solve_vertical_leg_ik(local_dy)
        
        arm_back = 0.80 * e
        near_sh = (0.08 - 2.08) * (1.0 - e) + arm_back * e
        far_sh = (-0.08 + 2.08) * (1.0 - e) - arm_back * e
        near_el = 0.05 * (1.0 - e) + 0.85 * e
        far_el = -0.05 * (1.0 - e) - 0.85 * e
        
        pose = Pose(
            root=Rigid(0.0, 0.0, 0.0),
            angles=(
                ("torso", 0.12 * e),
                ("neck", -0.06 * e),
                ("head", 0.08 * e),
                ("beanie", 0.0),
                ("far_shoulder", far_sh),
                ("far_elbow", far_el),
                ("far_hand", 0.0),
                ("near_shoulder", near_sh),
                ("near_elbow", near_el),
                ("near_hand", 0.0),
                ("far_hip", hip_angle),
                ("far_knee", knee_angle),
                ("far_foot", ankle_angle),
                ("near_hip", hip_angle),
                ("near_knee", knee_angle),
                ("near_foot", ankle_angle),
            ),
        )
        
        return FrameAnimationState(
            frame=frame,
            char_pos=(x_center, root_y),
            pose=pose,
            expression="smile",
            eye_scale=1.35 - 0.25 * e,
            brow_lift=3.5 * (1.0 - e),
            mouth_open=0.0,
            shadow_scale=1.0 + 0.15 * e,
            shadow_alpha=0.45 + 0.08 * e,
        )
    
    # --- PHASE 3: Frames 12..20 (The Jump / Airborne Phase) ---
    elif frame <= 20:
        # Parabolic jump trajectory: apex at F=16
        tau = (frame - 16.0) / 4.0
        tau = max(-1.0, min(1.0, tau))
        jump_height = 56.0 * (1.0 - tau * tau)  # Peaks at 56 units
        root_y = REST_ROOT_Y - jump_height
        
        air_factor = smooth_step(jump_height / 56.0)
        
        tuck_hip = 0.35 * air_factor
        tuck_knee = -0.70 * air_factor
        tuck_ankle = 0.35 * air_factor
        
        near_sh = -2.15 * air_factor + 0.40 * (1.0 - air_factor)
        far_sh = 2.15 * air_factor - 0.40 * (1.0 - air_factor)
        near_el = -0.35 * air_factor + 0.50 * (1.0 - air_factor)
        far_el = 0.35 * air_factor - 0.50 * (1.0 - air_factor)
        
        pose = Pose(
            root=Rigid(0.0, 0.0, 0.0),
            angles=(
                ("torso", -0.06 * air_factor),
                ("neck", -0.08 * air_factor),
                ("head", -0.08 * air_factor),
                ("beanie", -0.04 * air_factor),
                ("far_shoulder", far_sh),
                ("far_elbow", far_el),
                ("far_hand", 0.15 * air_factor),
                ("near_shoulder", near_sh),
                ("near_elbow", near_el),
                ("near_hand", -0.15 * air_factor),
                ("far_hip", tuck_hip),
                ("far_knee", tuck_knee),
                ("far_foot", tuck_ankle),
                ("near_hip", tuck_hip),
                ("near_knee", tuck_knee),
                ("near_foot", tuck_ankle),
            ),
        )
        
        shadow_s = 1.0 - 0.35 * air_factor
        shadow_a = 0.45 - 0.28 * air_factor
        
        return FrameAnimationState(
            frame=frame,
            char_pos=(x_center, root_y),
            pose=pose,
            expression="excited",
            eye_scale=1.1 + 0.30 * air_factor,
            brow_lift=3.0 * air_factor,
            mouth_open=0.45 * air_factor,
            shadow_scale=shadow_s,
            shadow_alpha=shadow_a,
        )
    
    # --- PHASE 4: Frames 21..26 (Landing & Impact Cushioning) ---
    elif frame <= 26:
        if frame <= 23:
            u = (frame - 20) / 3.0
            e = smooth_step(u)
            comp_drop = 16.0 * e  # Drops root to cushion impact
        else:
            u = (frame - 23) / 3.0
            e = smooth_step(u)
            comp_drop = 16.0 * (1.0 - e)
        
        root_y = REST_ROOT_Y + comp_drop
        world_hip_y = root_y + HIP_LOCAL_Y * CHAR_SCALE
        local_dy = (GROUND_Y - world_hip_y) / CHAR_SCALE
        hip_angle, knee_angle, ankle_angle = solve_vertical_leg_ik(local_dy)
        
        comp_norm = comp_drop / 16.0
        
        near_sh = -0.45 * comp_norm
        far_sh = 0.45 * comp_norm
        near_el = 0.60 * comp_norm
        far_el = -0.60 * comp_norm
        
        pose = Pose(
            root=Rigid(0.0, 0.0, 0.0),
            angles=(
                ("torso", 0.08 * comp_norm),
                ("neck", 0.0),
                ("head", 0.0),
                ("beanie", 0.0),
                ("far_shoulder", far_sh),
                ("far_elbow", far_el),
                ("far_hand", 0.0),
                ("near_shoulder", near_sh),
                ("near_elbow", near_el),
                ("near_hand", 0.0),
                ("far_hip", hip_angle),
                ("far_knee", knee_angle),
                ("far_foot", ankle_angle),
                ("near_hip", hip_angle),
                ("near_knee", knee_angle),
                ("near_foot", ankle_angle),
            ),
        )
        
        return FrameAnimationState(
            frame=frame,
            char_pos=(x_center, root_y),
            pose=pose,
            expression="smile",
            eye_scale=1.1,
            brow_lift=1.0 * comp_norm,
            mouth_open=0.0,
            shadow_scale=1.0 + 0.12 * comp_norm,
            shadow_alpha=0.45 + 0.05 * comp_norm,
        )
    
    # --- PHASE 5: Frames 27..29 (Recovery & Rest Settle) ---
    else:
        pose = pose_rest()
        return FrameAnimationState(
            frame=frame,
            char_pos=(x_center, REST_ROOT_Y),
            pose=pose,
            expression="satisfied",
            eye_scale=1.0,
            brow_lift=0.0,
            mouth_open=0.0,
            shadow_scale=1.0,
            shadow_alpha=0.45,
        )
