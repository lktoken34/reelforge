"""Pure frame-index geometry for one fixed engineering clip; not a timeline engine."""

import math
from dataclasses import replace

from .diagnostic import diagnostic_commands, ellipse, rounded
from .model import Color, DrawPath, RenderError, Stroke, Transform


def diagnostic_frame(frame_index: int, total_frames: int = 150) -> tuple[DrawPath, ...]:
    if (
        type(frame_index) is not int
        or type(total_frames) is not int
        or total_frames < 2
        or not 0 <= frame_index < total_frames
    ):
        raise RenderError("Use an integer frame index within a sequence of at least two frames")
    t = frame_index / (total_frames - 1)
    eased = t * t * (3 - 2 * t)
    commands = list(diagnostic_commands())
    # The new translucent disc travels left to right in front of the fixed upper ribbon.
    commands.append(
        DrawPath(
            ellipse(0, 0, 17, 17),
            Color(0.95, 0.27, 0.35, 0.78),
            Stroke(Color(1, 0.85, 0.73), 1.5),
            Transform(57 + 238 * eased, 95 + 28 * math.sin(math.pi * t)),
        )
    )
    # A separate foreground card rotates/scales over the depth-ordered static middle panel.
    commands.append(
        DrawPath(
            rounded(-25, -14, 50, 28, 5),
            Color(0.4, 0.87, 0.94, 0.8),
            Stroke(Color(0.88, 1, 1), 1.5),
            Transform(
                182,
                319,
                0.9 * t + 0.65 * math.sin(2 * math.pi * t),
                0.85 + 0.18 * math.sin(math.pi * t),
                0.85 + 0.18 * math.sin(math.pi * t),
            ),
        )
    )
    zoom = 1 + 0.025 * eased
    dx, dy = 180 * (1 - zoom) - 5 * eased, 320 * (1 - zoom) - 3 * eased
    # A uniform camera-like scale/translation composes with each object's local transform.
    return tuple(
        replace(
            command,
            transform=Transform(
                dx + zoom * command.transform.tx,
                dy + zoom * command.transform.ty,
                command.transform.rotation,
                zoom * command.transform.sx,
                zoom * command.transform.sy,
            ),
        )
        for command in commands
    )
