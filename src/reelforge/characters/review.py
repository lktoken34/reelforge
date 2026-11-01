"""Fixed vector-only review diagrams; no episode text, catalog or quality classifier."""

from reelforge.rendering.diagnostic import color, ellipse
from reelforge.rendering.model import DrawPath, Stroke, Transform

from .presets import EXPRESSIONS, SKELETON, CharacterPreset, sample_pose
from .rowan import BAG_PIVOT, HAT_PIVOT, PARTS, draw_character
from .secondary import around, preset_secondary
from .study import character_frame, demo_pose, label
from .transition import transition_secondary


def transition_sheet():
    commands = []
    for index, frame in enumerate((24, 30, 35, 84, 90, 95)):
        x = (index % 3) * 360
        y = (index // 3) * 640
        for command in character_frame(frame):
            t = command.transform
            commands.append(
                DrawPath(
                    command.path,
                    command.fill,
                    command.stroke,
                    Transform(t.tx + x, t.ty + y, t.rotation, t.sx, t.sy),
                    command.clip,
                )
            )
        commands.extend(label(f"FRAME {frame:03}", x + 28, y + 106, 1.3, color("ecc88c")))
    return tuple(commands)


def expression_sheet():
    commands = list(label("ROWAN / EXPRESSION STUDY", 45, 38, 2.7, color("405651")))
    head_art = tuple(p for p in PARTS if p.joint == "head")
    for index, emotion in enumerate(EXPRESSIONS):
        x = 210 + index % 3 * 400
        y = 370 + index // 3 * 430
        preset = CharacterPreset(expression=emotion)
        pose = sample_pose(preset, 0, travel=False)
        w = SKELETON.evaluate(pose)["head"]
        scale = 3.2
        commands.extend(
            draw_character(
                pose,
                position=(x - scale * w.x, y - scale * w.y),
                scale=scale,
                expression=emotion,
                artwork=head_art,
            )
        )
        commands.extend(label(emotion.upper(), x - 150, y + 42, 2, color("405651")))
    return tuple(commands)


def review_sheet():
    commands = list(label("ROWAN / MOTION CORRECTIONS", 48, 36, 3.1, color("405651")))
    cases = (
        ("GROUNDED IDLE", 0, "HIP OVER SUPPORT"),
        ("WEIGHT / WALK", 60, "PLANTED FOOT TARGETS"),
        ("RUN RECOVERY", 120, "ELBOW FOLLOW THROUGH"),
        ("CONTINUOUS PHASE", 90, "NO GAIT PHASE RESET"),
        ("BAG AND HAT LAG", 108, "STRAP FOLLOWS ANCHOR"),
        ("DANGER REACTION", None, "BOUNDED ACTING PRESET"),
    )
    for index, (title, frame, note) in enumerate(cases):
        x = 240 + (index % 3) * 480
        y = 598 + (index // 3) * 560
        if frame is None:
            preset = CharacterPreset(action="react", expression="frightened")
            pose = sample_pose(preset, 0.3, travel=False)
            state = preset_secondary(preset, 0.3)
            expression = "frightened"
        else:
            pose, _ = demo_pose(frame)
            state = transition_secondary(frame / 30)
            expression = "concerned"
        scale = 1.6
        commands.extend(
            draw_character(
                pose, position=(x, y), scale=scale, expression=expression, secondary=state
            )
        )
        worlds = SKELETON.evaluate(pose)
        if index == 4:
            points = [
                worlds["torso"]
                .compose(around(BAG_PIVOT, state.bag_angle, state.bag_y))
                .point((-23, -22)),
                worlds["head"]
                .compose(around(HAT_PIVOT, state.hat_angle, state.hat_y))
                .point((0, -80)),
            ]
        elif index == 5:
            points = []
        else:
            points = [
                worlds[name].point((0, 10) if name.endswith("foot") else (0, 0))
                for name in ("root", "near_foot", "far_foot")
            ]
        for point in points:
            px = x + scale * point[0]
            py = y + scale * point[1]
            commands.append(DrawPath(ellipse(px, py, 6, 6), stroke=Stroke(color("a95e35"), 1)))
        commands.extend(label(title, x - 178, y - 452, 1.9, color("405651")))
        commands.extend(label(note, x - 185, y + 35, 1.4, color("7b6343")))
    return tuple(commands)
