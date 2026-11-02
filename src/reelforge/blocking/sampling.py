"""Reuse accepted poses, contact solve, secondary motion and graph projection."""

import math
from dataclasses import asdict, replace

from reelforge.characters.contact import ease, plant_feet
from reelforge.characters.presets import SKELETON, CharacterPreset, blend, sample_pose
from reelforge.characters.rig import Pose, Rigid
from reelforge.characters.rowan import contact_shadows, draw_character
from reelforge.characters.secondary import SecondaryMotion, preset_secondary
from reelforge.characters.transition import contact_targets, transition_pose, transition_secondary
from reelforge.environments.polish import grade_character
from reelforge.rendering.model import Color, LinearGradient, Transform
from reelforge.scenes.graph import CharacterFrame, camera_at, evaluate_layers
from reelforge.scenes.transforms import Placement

from .timeline import route_step


def segment_at(plan, t):
    return next((s for s in plan.segments if t < s.end / 30), plan.segments[-1])


def clock_at(plan, t):
    for c in plan.clocks:
        if c.start - 0.1 <= t <= c.end:
            return c
    previous = [c for c in plan.clocks if c.end < t]
    return previous[-1] if previous else plan.clocks[0]


def sample(plan, t):
    s = segment_at(plan, t)
    clock = clock_at(plan, t)
    feet = contact_targets(t, clock, stepper=route_step)
    pose, distance = transition_pose(t, clock, feet=feet)
    weight = 0.0
    if s.mode in ("idle", "turn") and s.acting in ("look_around", "react"):
        weight = ease((t - s.start / 30) / 0.2)
        if s.end < 90:
            weight *= ease((s.end / 30 - t) / 0.2)
        preset = CharacterPreset(action=s.acting, expression=s.expression)
        acting = sample_pose(preset, t - s.start / 30, travel=False)
        body = blend(pose, acting, weight)
        body = Pose(Rigid(body.root.x + distance, body.root.y), body.angles)
        solved = plant_feet(body, feet, SKELETON)
        pose = Pose(Rigid(solved.root.x - distance, solved.root.y), solved.angles)
    secondary = transition_secondary(t, clock)
    if weight:
        target = preset_secondary(CharacterPreset(action=s.acting), t - s.start / 30)
        secondary = SecondaryMotion(
            *(
                getattr(secondary, k) * (1 - weight) + getattr(target, k) * weight
                for k in SecondaryMotion.__dataclass_fields__
            )
        )
    x = s.position(t)
    previous = (
        plan.start_facing
        if plan.segments.index(s) == 0
        else plan.segments[plan.segments.index(s) - 1].facing
    )
    facing = previous if s.mode == "turn" else s.facing
    fade = ease((s.u(t) - 0.35) / 0.30) if s.mode == "turn" else 0.0
    return s, clock, pose, feet, secondary, x, facing, fade


def opacity(commands, alpha):
    def paint(p):
        if isinstance(p, Color):
            return replace(p, a=p.a * alpha)
        if isinstance(p, LinearGradient):
            return replace(p, stops=tuple((u, paint(c)) for u, c in p.stops))
        return None

    return tuple(
        replace(
            c,
            fill=paint(c.fill),
            stroke=replace(c.stroke, paint=paint(c.stroke.paint)) if c.stroke else None,
        )
        for c in commands
    )


def crop(plan):
    return Placement(73.6, -44, 1.08) if plan.camera == "exit_right" else Placement()


def commands(plan, t):
    s, clock, pose, feet, secondary, x, facing, fade = sample(plan, t)

    def draw(direction):
        sign = 1 if direction == "right" else -1
        shadows = tuple(
            replace(c, transform=Transform(sx=sign))
            for c in contact_shadows(pose, position=(0, 0), scale=1)
        )
        return shadows + draw_character(
            pose, position=(0, 0), direction=direction, expression=s.expression, secondary=secondary
        )

    local = draw(facing)
    if s.mode == "turn" and fade > 0:
        other = draw(s.facing)
        local = other if fade >= 1 else opacity(local, 1 - fade) + opacity(other, fade)
    return x, grade_character(local, plan.compiled.scene.warmth, plan.compiled.scene.atmosphere)


def blocking_layers(plan, frame):
    x, local = commands(plan, frame / 30)
    override = CharacterFrame(plan.actor_id, Placement(x, plan.y, plan.scale), local)
    layers = evaluate_layers(plan.compiled, frame, character_override=override)
    p = crop(plan)
    return tuple(
        replace(layer, commands=tuple(p.command(c) for c in layer.commands)) for layer in layers
    )


def blocking_frame(plan, frame):
    return tuple(c for layer in blocking_layers(plan, frame) for c in layer.commands)


def inspect_frame(plan, frame):
    if type(frame) is not int or not 0 <= frame < 90:
        from .contract import fail

        fail("/frame", "Use integer frame 0..89")
    t = frame / 30
    s, clock, pose, feet, secondary, x, facing, fade = sample(plan, t)
    sign = 1 if facing == "right" else -1
    worlds = SKELETON.evaluate(pose)
    contacts = []
    depth = next(r.depth for r in plan.compiled.hierarchy if r.id == plan.actor_id)
    c = camera_at(plan.compiled, frame).transform(depth)
    projection = crop(plan).compose(Placement(c.tx, c.ty, c.sx))
    for side, foot in zip(("near", "far"), feet, strict=True):
        point = worlds[side + "_foot"].point((foot.pivot_x, 10))
        actual = (x + sign * plan.scale * point[0], plan.y + plan.scale * point[1])
        expected = (clock.origin + sign * plan.scale * (foot.x + foot.pivot_x), plan.y)
        # A completed left-facing bout uses its own signed distance; a stationary turn
        # exchanges near/far depth labels, while preserving the unordered footprint.
        if facing != ("right" if clock.sign > 0 else "left"):
            expected = (x + sign * plan.scale * (foot.x - clock.distance(t) + foot.pivot_x), plan.y)
        contacts.append(
            {
                "side": side,
                "state": foot.state,
                "lift": foot.lift,
                "cycle_start": math.floor(clock.cycles(t) + (0 if side == "near" else 0.5))
                - (0 if side == "near" else 0.5),
                "world": actual,
                "expected": expected,
                "screen": projection.point(*actual),
                "expected_screen": projection.point(*expected),
                "error": math.dist(actual, expected) if foot.state != "swing" else None,
            }
        )
    turn_set_error = turn_label_exchange = 0.0
    if s.mode == "turn":
        sole = [worlds[side + "_foot"].point((0, 10)) for side in ("near", "far")]
        old = [(x + sign * plan.scale * p[0], plan.y + plan.scale * p[1]) for p in sole]
        new = [(x - sign * plan.scale * p[0], plan.y + plan.scale * p[1]) for p in sole]
        turn_set_error = max(min(math.dist(a, b) for b in new) for a in old)
        turn_label_exchange = max(math.dist(a, b) for a, b in zip(old, new, strict=True))
    return {
        "turn_contact_set_error_world": turn_set_error,
        "turn_side_label_exchange_world": turn_label_exchange,
        "frame": frame,
        "segment": s.id,
        "mode": s.mode,
        "position": [x, plan.y],
        "velocity": s.velocity(t),
        "phase": clock.cycles(t),
        "distance_rig": clock.distance(t),
        "stride_factor": clock.factor,
        "run_weight": clock.running(t),
        "facing": facing,
        "target_facing": s.facing,
        "dominant_facing": s.facing if s.mode == "turn" and fade > 0.5 else facing,
        "turn_blend": fade,
        "pose": asdict(pose),
        "secondary": asdict(secondary),
        "contacts": contacts,
        "screen_origin": projection.point(x, plan.y),
    }


def validate_contacts(plan):
    from .contract import fail

    left, top, right, bottom = plan.support
    for c in plan.clocks:
        times = {c.start, c.end}
        for off, hip in ((0, 7), (0.5, -7)):
            for k in range(math.ceil(c.total_cycles) + 2):
                start = k - off
                _, duty, _ = c.contact_step(start, hip)
                for phase in (start, start + duty, start + 1):
                    if 0 < phase < c.total_cycles:
                        times.add(c.time_at(phase))
        projections = []
        for t in times:
            for foot in contact_targets(t, c, stepper=route_step):
                projections.append(c.origin + c.sign * plan.scale * foot.x)
        # Monotone stance/swing x and a conservative +/-40 rig-unit boot rotation bound
        # prove support over the whole continuous trajectory, not merely frame endpoints.
        if (
            min(projections) - 40 * plan.scale < left
            or max(projections) + 40 * plan.scale > right
            or not top <= plan.y <= bottom
        ):
            fail(
                "/segments",
                "Continuous foot sweep leaves trusted supporting plane",
                "BLOCKING_SUPPORT",
            )
    for frame in range(90):
        try:
            d = inspect_frame(plan, frame)
        except ValueError as e:
            fail("/segments", str(e), "BLOCKING_GAIT")
        if any(c["error"] is not None and c["error"] > 1e-7 for c in d["contacts"]):
            fail("/segments", "Contact solver exceeded 1e-7 world-unit residual", "BLOCKING_GAIT")
        x, y = d["screen_origin"]
        margin = 80 * plan.scale + 4
        if (
            (plan.camera != "exit_right" or frame < 60) and not margin <= x <= 360 - margin
        ) or not 150 <= y <= 610:
            fail("/camera", "Framing crops the supported actor route", "BLOCKING_CAMERA")
    if plan.camera == "exit_right":
        if plan.segments[-1].facing != "right" or inspect_frame(plan, 89)["screen_origin"][0] < 380:
            fail(
                "/camera",
                "exit_right requires a rightward departure beyond x=380",
                "BLOCKING_CAMERA",
            )
