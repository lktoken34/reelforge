"""Fixed character-review composition, not a story timeline or environment catalog."""

from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import DrawPath, LinearGradient, RenderError, Stroke, Transform

from .presets import (
    RUN_CYCLE,
    RUN_STRIDE,
    WALK_CYCLE,
    WALK_STRIDE,
    CharacterPreset,
    blend,
    sample_pose,
    smooth,
)
from .rowan import draw_character, path

BACKGROUND = color("173235")
# Hand-authored monoline proof labels only; no fonts, subtitles, shaping or agent-supplied text.
GLYPHS = {
    "A": ((0, 7, 2, 0, 4, 7), (1, 4, 3, 4)),
    "B": ((0, 7, 0, 0, 3, 0, 4, 1, 4, 2, 3, 3, 0, 3), (3, 3, 4, 4, 4, 6, 3, 7, 0, 7)),
    "C": ((4, 0, 1, 0, 0, 1, 0, 6, 1, 7, 4, 7),),
    "D": ((0, 7, 0, 0, 2, 0, 4, 2, 4, 5, 2, 7, 0, 7),),
    "E": ((4, 0, 0, 0, 0, 7, 4, 7), (0, 3, 3, 3)),
    "F": ((4, 0, 0, 0, 0, 7), (0, 3, 3, 3)),
    "G": ((4, 0, 1, 0, 0, 1, 0, 6, 1, 7, 4, 7, 4, 4, 2, 4),),
    "H": ((0, 0, 0, 7), (4, 0, 4, 7), (0, 3, 4, 3)),
    "I": ((0, 0, 4, 0), (2, 0, 2, 7), (0, 7, 4, 7)),
    "J": ((4, 0, 4, 6, 3, 7, 1, 7, 0, 6),),
    "K": ((0, 0, 0, 7), (4, 0, 0, 4, 4, 7)),
    "L": ((0, 0, 0, 7, 4, 7),),
    "M": ((0, 7, 0, 0, 2, 3, 4, 0, 4, 7),),
    "N": ((0, 7, 0, 0, 4, 7, 4, 0),),
    "O": ((1, 0, 3, 0, 4, 1, 4, 6, 3, 7, 1, 7, 0, 6, 0, 1, 1, 0),),
    "P": ((0, 7, 0, 0, 3, 0, 4, 1, 4, 3, 3, 4, 0, 4),),
    "Q": ((1, 0, 3, 0, 4, 1, 4, 6, 3, 7, 1, 7, 0, 6, 0, 1, 1, 0), (2, 5, 5, 8)),
    "R": ((0, 7, 0, 0, 3, 0, 4, 1, 4, 3, 3, 4, 0, 4), (2, 4, 4, 7)),
    "S": ((4, 0, 1, 0, 0, 1, 0, 2, 1, 3, 3, 4, 4, 5, 4, 6, 3, 7, 0, 7),),
    "T": ((0, 0, 4, 0), (2, 0, 2, 7)),
    "U": ((0, 0, 0, 6, 1, 7, 3, 7, 4, 6, 4, 0),),
    "V": ((0, 0, 2, 7, 4, 0),),
    "W": ((0, 0, 1, 7, 2, 4, 3, 7, 4, 0),),
    "X": ((0, 0, 4, 7), (4, 0, 0, 7)),
    "Y": ((0, 0, 2, 3, 4, 0), (2, 3, 2, 7)),
    "Z": ((0, 0, 4, 0, 0, 7, 4, 7),),
    "0": ((1, 0, 3, 0, 4, 1, 4, 6, 3, 7, 1, 7, 0, 6, 0, 1, 1, 0), (1, 5, 3, 2)),
    "1": ((0, 1, 2, 0, 2, 7), (0, 7, 4, 7)),
    "2": ((0, 1, 1, 0, 3, 0, 4, 1, 4, 2, 0, 7, 4, 7),),
    "3": ((0, 0, 4, 0, 2, 3, 4, 4, 4, 6, 3, 7, 0, 7),),
    "4": ((3, 7, 3, 0, 0, 5, 4, 5),),
    "5": ((4, 0, 0, 0, 0, 3, 3, 3, 4, 4, 4, 6, 3, 7, 0, 7),),
    "6": ((4, 0, 1, 0, 0, 2, 0, 6, 1, 7, 3, 7, 4, 6, 4, 4, 3, 3, 0, 3),),
    "/": ((0, 7, 4, 0),),
    "-": ((0, 3, 4, 3),),
    ".": ((2, 7, 2, 6.9),),
}


def label(text, x, y, size=1, paint=None):
    commands = []
    for index, char in enumerate(text):
        if char == " ":
            continue
        for points in GLYPHS[char]:
            ops = [("M", points[0], points[1])] + [
                ("L", points[i], points[i + 1]) for i in range(2, len(points), 2)
            ]
            commands.append(
                DrawPath(
                    path(*ops),
                    stroke=Stroke(paint or color("d9d3b7"), 0.65),
                    transform=Transform(x + index * 6 * size, y, sx=size, sy=size),
                )
            )
    return tuple(commands)


def integral_step(t, start, duration):
    u = (t - start) / duration
    if u <= 0:
        return 0
    if u >= 1:
        return t - start - duration / 2
    return duration * (u**3 - 0.5 * u**4)


def demo_pose(frame_index: int):
    if type(frame_index) is not int or not 0 <= frame_index < 150:
        raise RenderError("Character study is exactly frames 0..149 at 30 FPS")
    t = frame_index / 30
    idle = sample_pose(CharacterPreset(action="idle"), t, travel=False)
    walk = sample_pose(CharacterPreset(action="walk"), max(0, t - 0.85), travel=False)
    run = sample_pose(CharacterPreset(action="run"), max(0, t - 2.85), travel=False)
    pose = blend(blend(idle, walk, smooth((t - 0.85) / 0.3)), run, smooth((t - 2.85) / 0.3))
    travel = (WALK_STRIDE / WALK_CYCLE) * integral_step(t, 0.85, 0.3) + (
        RUN_STRIDE / RUN_CYCLE - WALK_STRIDE / WALK_CYCLE
    ) * integral_step(t, 2.85, 0.3)
    return pose, travel


def character_frame(frame_index: int):
    pose, travel = demo_pose(frame_index)
    commands = [
        DrawPath(
            path(("M", 0, 0), ("L", 360, 0), ("L", 360, 640), ("L", 0, 640), ("Z",)),
            LinearGradient(
                (0, 80),
                (300, 600),
                ((0, color("142e32")), (0.65, color("526b60")), (1, color("263e3c"))),
            ),
        ),
        DrawPath(ellipse(235, 297, 148, 207), color("b9b78e", 0.065)),
        DrawPath(
            path(
                ("M", 0, 442),
                ("C", 100, 402, 145, 449, 220, 421),
                ("C", 290, 405, 325, 422, 360, 413),
                ("L", 360, 640),
                ("L", 0, 640),
                ("Z",),
            ),
            color("304b47"),
        ),
        DrawPath(
            path(
                ("M", 0, 490),
                ("C", 109, 459, 203, 494, 360, 474),
                ("L", 360, 640),
                ("L", 0, 640),
                ("Z",),
            ),
            color("203c3b"),
        ),
        DrawPath(ellipse(180, 546, 39, 7), color("071d20", 0.32)),
    ]
    offset = (travel * 1.32) % 72
    for i in range(-1, 7):
        x = i * 72 - offset
        commands.append(
            DrawPath(
                path(("M", x, 558), ("L", x + 16, 558)), stroke=Stroke(color("9aa184", 0.22), 0.65)
            )
        )
    commands.extend(
        draw_character(
            pose,
            position=(180, 538),
            scale=1.32,
            blink=abs(frame_index - 17) < 2 or abs(frame_index - 126) < 2,
        )
    )
    commands.extend(label("ROWAN VALE", 28, 48, 2.1))
    commands.extend(label("ORCHARD KEEPER / FIELD STUDY 01", 29, 75, 0.83, color("b7bc9d")))
    current = 0 if frame_index < 30 else 1 if frame_index < 90 else 2
    for i, word in enumerate(("IDLE", "WALK", "RUN")):
        commands.extend(
            label(
                word, 30 + i * 110, 592, 1.15, color("ecc88c") if i == current else color("738d82")
            )
        )
        commands.append(
            DrawPath(
                path(("M", 30 + i * 110, 611), ("L", 96 + i * 110, 611)),
                stroke=Stroke(color("dab375") if i == current else color("46615a"), 1.2),
            )
        )
    return tuple(commands)


def pose_sheet():
    commands = list(label("ROWAN VALE / POSE STUDY", 55, 42, 3.7, color("384d4b")))
    commands.extend(
        label(
            "ORIGINAL VECTOR CHARACTER / SAME HIERARCHY IN EVERY POSE", 57, 90, 1.5, color("6b786d")
        )
    )
    poses = (
        ("IDLE / CONCERNED", "idle", 0.4, "right"),
        ("WALK / CONTACT", "walk", 0.02, "right"),
        ("WALK / PASSING", "walk", 0.41, "right"),
        ("RUN / DRIVE", "run", 0.06, "right"),
        ("RUN / FLIGHT", "run", 0.27, "right"),
        ("IDLE / LEFT", "idle", 0.9, "left"),
    )
    for index, (name, action, t, direction) in enumerate(poses):
        x = 240 + (index % 3) * 480
        y = 605 + (index // 3) * 565
        commands.append(DrawPath(ellipse(x, y + 4, 72, 10), color("a89f85", 0.18)))
        commands.extend(
            draw_character(
                sample_pose(CharacterPreset(action=action), t, travel=False),
                position=(x, y),
                scale=1.65,
                direction=direction,
            )
        )
        commands.extend(label(name, x - 165, y + 32, 1.8, color("405651")))
    return tuple(commands)
