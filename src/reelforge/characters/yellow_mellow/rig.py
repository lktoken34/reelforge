"""Yellow Mellow character rig and skeletal kinematics.

Provides an immutable 16-joint 2D hierarchy with parent-child transformations,
reusable pose objects, and inverse kinematics for planted foot constraints.
"""

import math

from reelforge.characters.rig import Joint, Pose, Rigid, Skeleton
from reelforge.rendering.model import RenderError, finite

UPPER_LEG = 24.0
LOWER_LEG = 24.0
UPPER_ARM = 22.0
FOREARM = 20.0

# 16-joint skeletal hierarchy with single root and explicit joint offsets
YELLOW_MELLOW_SKELETON = Skeleton(
    (
        Joint("root", None),                          # Hips / Pelvis center (0, 0)
        Joint("torso", "root", (0, -4)),              # Lower torso
        Joint("neck", "torso", (0, -38)),             # Upper hoodie neckline
        Joint("head", "neck", (0, -8)),               # Head center
        Joint("beanie", "head", (0, -6)),             # Hat base on top of head
        Joint("far_shoulder", "torso", (-14, -34)),   # Left shoulder
        Joint("far_elbow", "far_shoulder", (0, UPPER_ARM)), # Left elbow
        Joint("far_hand", "far_elbow", (0, FOREARM)),       # Left mitten
        Joint("near_shoulder", "torso", (14, -34)),   # Right shoulder
        Joint("near_elbow", "near_shoulder", (0, UPPER_ARM)),# Right elbow
        Joint("near_hand", "near_elbow", (0, FOREARM)),      # Right mitten
        Joint("far_hip", "root", (-7, 4)),            # Left hip
        Joint("far_knee", "far_hip", (0, UPPER_LEG)), # Left knee
        Joint("far_foot", "far_knee", (0, LOWER_LEG)),# Left shoe / ankle
        Joint("near_hip", "root", (7, 4)),            # Right hip
        Joint("near_knee", "near_hip", (0, UPPER_LEG)),# Right knee
        Joint("near_foot", "near_knee", (0, LOWER_LEG)),# Right shoe / ankle
    )
)


def solve_vertical_leg_ik(
    target_dy: float,
    upper: float = UPPER_LEG,
    lower: float = LOWER_LEG,
) -> tuple[float, float, float]:
    """Calculates hip, knee, and ankle angles for vertical foot displacement.

    target_dy is the distance from hip to foot along the Y axis.
    Returns (hip_angle, knee_angle, ankle_angle) in radians, ensuring the foot
    remains completely level (0.0 rad global rotation).
    """
    finite(target_dy, upper, lower)
    max_reach = (upper + lower) * 0.999
    min_reach = abs(upper - lower) * 1.001 + 0.5
    d = max(min_reach, min(max_reach, target_dy))
    
    # Law of cosines for knee interior angle
    cos_knee = (upper**2 + lower**2 - d**2) / (2.0 * upper * lower)
    cos_knee = max(-1.0, min(1.0, cos_knee))
    interior_knee = math.acos(cos_knee)
    knee_rel = -(math.pi - interior_knee)  # Bend backward
    
    # Law of cosines for hip angle
    cos_hip = (upper**2 + d**2 - lower**2) / (2.0 * upper * d)
    cos_hip = max(-1.0, min(1.0, cos_hip))
    hip_rel = math.acos(cos_hip)           # Bend forward
    
    # Counter-rotate ankle so foot stays perfectly level
    ankle_rel = -(hip_rel + knee_rel)
    
    return hip_rel, knee_rel, ankle_rel
