"""Yellow Mellow: original code-authored cartoon character artwork and rendering.

Pure vector geometry rendering via ReelForge DrawPath, PathOp, LinearGradient,
Color and Stroke primitives. Implements parent-child skeletal transformation mapping.
"""

from dataclasses import dataclass, replace

from reelforge.characters.rig import Pose, Skeleton
from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import (
    DrawPath,
    LinearGradient,
    PathOp,
    RenderError,
    Stroke,
    Transform,
    finite,
)

from .rig import UPPER_ARM, UPPER_LEG, YELLOW_MELLOW_SKELETON

# Core Palette
BLACK_INK = color("101214")
BLACK_SHOE = color("16191d")
WHITE = color("ffffff")
WHITE_GLOW = color("ffffff", 0.95)
WHITE_AURA = color("d8eaff", 0.28)

GOLD_LIGHT = color("ffc83b")
GOLD_MAIN = color("f5b823")
GOLD_SHADOW = color("d49811")
GOLD_DARK = color("a87405")

BEANIE_RED = color("db2828")
BEANIE_DARK = color("b51c1c")
BEANIE_FOLD = color("8f1313")
BEANIE_RIB = color("f25e5e")
BEANIE_SHADOW = color("6b0d0d")

SHORTS_CHARCOAL = color("282a30")
SHORTS_DARK = color("1b1c20")


def path(*ops) -> tuple[PathOp, ...]:
    return tuple(PathOp(op[0], tuple(op[1:])) for op in ops)


def shape(outline, fill, *, stroke_color=BLACK_INK, stroke_width=1.0):
    return DrawPath(outline, fill, Stroke(stroke_color, stroke_width))


def line(outline, paint=BLACK_INK, width=1.0, cap="round", join="round"):
    return DrawPath(outline, stroke=Stroke(paint, width, cap=cap, join=join))


def grad(c1, c2, start=(-20, -40), end=(20, 10)):
    return LinearGradient(start, end, ((0, c1), (1, c2)))


@dataclass(frozen=True)
class Part:
    joint: str
    order: int
    commands: tuple[DrawPath, ...]


# --- VECTOR GEOMETRY DEFINITIONS ---

# 1. Beanie (Attached to beanie joint on head)
BEANIE_COMMANDS = (
    # Main red knit dome
    shape(
        path(
            ("M", -19, -4),
            ("C", -21, -16, -16, -26, 0, -28),
            ("C", 16, -26, 21, -16, 19, -4),
            ("Z",),
        ),
        grad(BEANIE_RED, BEANIE_DARK, start=(0, -28), end=(0, -4)),
        stroke_color=BEANIE_SHADOW,
        stroke_width=1.0,
    ),
    # Subtle ribbed knitted texture lines
    line(path(("M", -14, -6), ("C", -15, -16, -11, -22, -2, -26)), paint=BEANIE_RIB, width=0.7),
    line(path(("M", -7, -6), ("C", -8, -17, -5, -23, 0, -27)), paint=BEANIE_RIB, width=0.7),
    line(path(("M", 0, -6), ("L", 0, -27)), paint=BEANIE_RIB, width=0.7),
    line(path(("M", 7, -6), ("C", 8, -17, 5, -23, 0, -27)), paint=BEANIE_RIB, width=0.7),
    line(path(("M", 14, -6), ("C", 15, -16, 11, -22, 2, -26)), paint=BEANIE_RIB, width=0.7),
    # Small top pom-pom / knit tip
    shape(ellipse(0, -29, 3.5, 3.5), BEANIE_RED, stroke_color=BEANIE_SHADOW, stroke_width=0.8),
    # Thick folded brim
    shape(
        path(
            ("M", -21, -7),
            ("C", -22, -1, -20, 2, -18, 2),
            ("L", 18, 2),
            ("C", 20, 2, 22, -1, 21, -7),
            ("C", 19, -8, -19, -8, -21, -7),
            ("Z",),
        ),
        grad(BEANIE_RED, BEANIE_FOLD, start=(0, -8), end=(0, 2)),
        stroke_color=BEANIE_SHADOW,
        stroke_width=1.1,
    ),
    # Brim fold ribbing lines
    line(path(("M", -15, -6), ("L", -15, 1)), paint=BEANIE_RIB, width=0.6),
    line(path(("M", -9, -6), ("L", -9, 1)), paint=BEANIE_RIB, width=0.6),
    line(path(("M", -3, -6), ("L", -3, 1)), paint=BEANIE_RIB, width=0.6),
    line(path(("M", 3, -6), ("L", 3, 1)), paint=BEANIE_RIB, width=0.6),
    line(path(("M", 9, -6), ("L", 9, 1)), paint=BEANIE_RIB, width=0.6),
    line(path(("M", 15, -6), ("L", 15, 1)), paint=BEANIE_RIB, width=0.6),
)

# 2. Head Base (Black rounded circle/oval)
HEAD_BASE = (
    shape(
        ellipse(0, 0, 19.5, 18.5),
        BLACK_INK,
        stroke_color=BLACK_INK,
        stroke_width=1.0,
    ),
)

# 3. Torso & Hoodie
TORSO_COMMANDS = (
    # Oversized Golden Hoodie Body
    shape(
        path(
            ("M", -14, -36),
            ("C", -20, -32, -22, -18, -20, -2),
            ("C", -19, 4, 19, 4, 20, -2),
            ("C", 22, -18, 20, -32, 14, -36),
            ("Z",),
        ),
        grad(GOLD_LIGHT, GOLD_SHADOW, start=(0, -36), end=(0, 4)),
        stroke_color=GOLD_DARK,
        stroke_width=1.2,
    ),
    # Ribbed bottom hem
    shape(
        path(
            ("M", -19, -2),
            ("L", -18, 4),
            ("C", -8, 6, 8, 6, 18, 4),
            ("L", 19, -2),
            ("Z",),
        ),
        GOLD_SHADOW,
        stroke_color=GOLD_DARK,
        stroke_width=0.9,
    ),
    # Front Kangaroo Pocket
    shape(
        path(
            ("M", -11, -14),
            ("L", 11, -14),
            ("L", 14, -2),
            ("L", -14, -2),
            ("Z",),
        ),
        grad(GOLD_MAIN, GOLD_DARK, start=(0, -14), end=(0, -2)),
        stroke_color=GOLD_DARK,
        stroke_width=1.0,
    ),
    # Kangaroo pocket side openings
    line(path(("M", -11, -14), ("L", -14, -2)), paint=GOLD_DARK, width=1.1),
    line(path(("M", 11, -14), ("L", 14, -2)), paint=GOLD_DARK, width=1.1),
    # Two White Drawstrings
    line(path(("M", -4, -32), ("C", -5, -24, -3, -18, -4, -13)), paint=WHITE, width=1.4),
    shape(ellipse(-4, -12, 1.2, 1.2), WHITE, stroke_color=BLACK_INK, stroke_width=0.5),
    line(path(("M", 4, -32), ("C", 3, -24, 5, -18, 4, -13)), paint=WHITE, width=1.4),
    shape(ellipse(4, -12, 1.2, 1.2), WHITE, stroke_color=BLACK_INK, stroke_width=0.5),
    # Hoodie neckline / hood collar behind chin
    shape(
        path(
            ("M", -12, -36),
            ("C", -6, -32, 6, -32, 12, -36),
            ("C", 14, -39, -14, -39, -12, -36),
            ("Z",),
        ),
        GOLD_SHADOW,
        stroke_color=GOLD_DARK,
        stroke_width=0.9,
    ),
)

# 4. Shorts (Attached to root)
SHORTS_COMMANDS = (
    # Dark charcoal shorts body
    shape(
        path(
            ("M", -13, -2),
            ("L", 13, -2),
            ("L", 14, 12),
            ("L", 2, 12),
            ("L", 0, 4),
            ("L", -2, 12),
            ("L", -14, 12),
            ("Z",),
        ),
        SHORTS_CHARCOAL,
        stroke_color=SHORTS_DARK,
        stroke_width=1.0,
    ),
    # Thin white athletic stripes along both outer sides
    line(path(("M", -13, 0), ("L", -13.5, 11)), paint=WHITE, width=1.0),
    line(path(("M", 13, 0), ("L", 13.5, 11)), paint=WHITE, width=1.0),
)

# 5. Limbs and End Effectors
def make_sleeve(side_sign: float = 1.0) -> tuple[DrawPath, ...]:
    """Baggy yellow hoodie sleeve at upper shoulder."""
    return (
        shape(
            path(
                ("M", -5 * side_sign, 0),
                ("C", -6 * side_sign, 6, -5 * side_sign, 10, -4 * side_sign, 12),
                ("L", 4 * side_sign, 12),
                ("C", 5 * side_sign, 10, 6 * side_sign, 6, 5 * side_sign, 0),
                ("Z",),
            ),
            GOLD_MAIN,
            stroke_color=GOLD_DARK,
            stroke_width=1.0,
        ),
        # Thin stick arm extending below sleeve
        line(path(("M", 0, 10), ("L", 0, UPPER_ARM)), paint=BLACK_INK, width=3.0),
    )


FOREARM_COMMANDS = (
    # Thin black stick forearm
    line(path(("M", 0, 0), ("L", 0, 20)), paint=BLACK_INK, width=2.8),
)

HAND_COMMANDS = (
    # Rounded black mitten hand with thumb
    shape(ellipse(0, 4, 4.2, 4.8), BLACK_INK, stroke_color=BLACK_INK, stroke_width=0.8),
    shape(ellipse(3.2, 2.5, 2.0, 2.2), BLACK_INK, stroke_color=BLACK_INK, stroke_width=0.6),
)

THIGH_COMMANDS = (
    # Thin black stick thigh
    line(path(("M", 0, 0), ("L", 0, UPPER_LEG)), paint=BLACK_INK, width=3.0),
)

SHIN_COMMANDS = (
    # Thin black stick shin
    line(path(("M", 0, 0), ("L", 0, UPPER_LEG)), paint=BLACK_INK, width=2.8),
)

SHOE_COMMANDS = (
    # Oversized rounded black shoe
    shape(
        path(
            ("M", -6, 2),
            ("C", -7, 0, -6, -2, -3, -2),
            ("L", 10, -2),
            ("C", 16, -2, 17, 3, 14, 5),
            ("L", -4, 5),
            ("C", -6, 5, -7, 4, -6, 2),
            ("Z",),
        ),
        BLACK_SHOE,
        stroke_color=BLACK_INK,
        stroke_width=1.0,
    ),
    # White rubber sole accent (ensures clear ground contact visibility)
    line(path(("M", -5, 5), ("L", 14, 5)), paint=WHITE, width=1.0),
)


def make_face_features(
    expression: str = "smile",
    eye_scale: float = 1.0,
    brow_lift: float = 0.0,
    mouth_open: float = 0.0,
) -> tuple[DrawPath, ...]:
    """Generates glowing white oval eyes, expressive eyebrows, and cute mouth."""
    finite(eye_scale, brow_lift, mouth_open)
    
    # 1. Eyes (Bright glowing white ovals)
    ew = 2.4 * eye_scale
    eh = 3.6 * eye_scale
    
    eyes = (
        # Soft outer moonlight aura
        DrawPath(ellipse(-6.5, -2, ew * 1.35, eh * 1.35), WHITE_AURA),
        DrawPath(ellipse(6.5, -2, ew * 1.35, eh * 1.35), WHITE_AURA),
        # Core glowing white ovals
        DrawPath(ellipse(-6.5, -2, ew, eh), WHITE_GLOW),
        DrawPath(ellipse(6.5, -2, ew, eh), WHITE_GLOW),
    )
    
    # 2. White Eyebrows
    by = -9 - brow_lift
    brows = (
        line(path(("M", -10, by + 1), ("L", -3.5, by - 0.5)), paint=WHITE, width=1.5),
        line(path(("M", 3.5, by - 0.5), ("L", 10, by + 1)), paint=WHITE, width=1.5),
    )
    
    # 3. Small cute stylized mouth
    if expression == "excited" or mouth_open > 0.3:
        mouth = (
            shape(
                ellipse(0, 6, 2.5, 1.8 + mouth_open * 1.2),
                color("3b1818"),
                stroke_color=WHITE,
                stroke_width=0.8,
            ),
        )
    elif expression == "satisfied":
        # Warm happy curved smile
        mouth = (
            line(
                path(("M", -3.5, 5.5), ("C", -1.5, 7.5, 1.5, 7.5, 3.5, 5.5)),
                paint=WHITE,
                width=1.2,
            ),
        )
    else:  # Neutral / smile
        mouth = (
            line(
                path(("M", -2.5, 5.5), ("C", -1, 6.8, 1, 6.8, 2.5, 5.5)),
                paint=WHITE,
                width=1.0,
            ),
        )
    
    return eyes + brows + mouth


def build_yellow_mellow_parts(
    expression: str = "smile",
    eye_scale: float = 1.0,
    brow_lift: float = 0.0,
    mouth_open: float = 0.0,
) -> tuple[Part, ...]:
    """Assembles all character parts mapped to skeletal joints in drawing order."""
    face_cmds = HEAD_BASE + make_face_features(expression, eye_scale, brow_lift, mouth_open)
    
    return (
        # Background limbs (far side)
        Part("far_hip", 10, THIGH_COMMANDS),
        Part("far_knee", 15, SHIN_COMMANDS),
        Part("far_foot", 20, SHOE_COMMANDS),
        Part("far_shoulder", 25, make_sleeve(-1.0)),
        Part("far_elbow", 30, FOREARM_COMMANDS),
        Part("far_hand", 35, HAND_COMMANDS),
        # Central body & shorts
        Part("root", 40, SHORTS_COMMANDS),
        Part("torso", 45, TORSO_COMMANDS),
        # Head and Beanie
        Part("head", 50, face_cmds),
        Part("beanie", 55, BEANIE_COMMANDS),
        # Foreground limbs (near side)
        Part("near_hip", 60, THIGH_COMMANDS),
        Part("near_knee", 65, SHIN_COMMANDS),
        Part("near_foot", 70, SHOE_COMMANDS),
        Part("near_shoulder", 75, make_sleeve(1.0)),
        Part("near_elbow", 80, FOREARM_COMMANDS),
        Part("near_hand", 85, HAND_COMMANDS),
    )


def draw_yellow_mellow(
    pose: Pose,
    *,
    position: tuple[float, float] = (180.0, 462.4),
    scale: float = 1.30,
    expression: str = "smile",
    eye_scale: float = 1.0,
    brow_lift: float = 0.0,
    mouth_open: float = 0.0,
    skeleton: Skeleton = YELLOW_MELLOW_SKELETON,
) -> tuple[DrawPath, ...]:
    """Evaluates skeleton forward kinematics and transforms vector parts to world space."""
    finite(*position, scale, eye_scale, brow_lift, mouth_open)
    if not 0.1 <= scale <= 4.0:
        raise RenderError("Character scale must be within [0.1, 4.0]")
    
    worlds = skeleton.evaluate(pose)
    parts = build_yellow_mellow_parts(expression, eye_scale, brow_lift, mouth_open)
    
    commands = []
    for part in sorted(parts, key=lambda p: p.order):
        if part.joint not in worlds:
            raise RenderError(f"Part refers to unknown joint '{part.joint}'")
        w = worlds[part.joint]
        for cmd in part.commands:
            # Compose joint transformation into world coordinate space
            commands.append(
                replace(
                    cmd,
                    transform=Transform(
                        position[0] + scale * w.x,
                        position[1] + scale * w.y,
                        w.angle,
                        scale,
                        scale,
                    ),
                )
            )
    
    return tuple(commands)
