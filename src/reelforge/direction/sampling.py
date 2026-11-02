"""Absolute-time camera solve; one projection shared by actor and supporting ground."""

import math
from dataclasses import asdict

from reelforge.blocking.sampling import commands as actor_commands
from reelforge.blocking.sampling import sample
from reelforge.characters.presets import smooth
from reelforge.environments.scene import Camera
from reelforge.rendering.model import DrawPath
from reelforge.scenes.graph import CharacterFrame, EvaluatedLayer, evaluate_layers
from reelforge.scenes.transforms import Placement

from .contract import (
    MAX_PAN_SPEED,
    MAX_SCALE_CUT_RATIO,
    MAX_ZOOM_SPEED,
    TRACKING_TOLERANCE,
    Direction,
    Shot,
    fail,
)


def shot_at(plan: Direction, frame: int) -> Shot:
    if type(frame) is not int or not 0 <= frame < 90:
        fail("/frame", "Use integer frame 0..89")
    return next(s for s in plan.shots if s.start <= frame < s.end)


def target_at(plan: Direction, shot: Shot, frame: float) -> tuple[tuple[float, float], float]:
    target = shot.target
    if target.kind == "point":
        return target.position, 0.0
    r = next(r for r in plan.compiled.hierarchy if r.id == target.node_id)
    if target.kind == "actor" and plan.blocking:
        s, _, _, _, _, x, _, _ = sample(plan.blocking, frame / 30)
        return (x, plan.blocking.y), s.velocity(frame / 30)
    # This is the validated instance's local registration origin, not a physical socket.
    return (r.world.x, r.world.y), 0.0


def camera_state(plan: Direction, shot: Shot, frame: float) -> tuple[Camera, tuple, tuple, float]:
    u = max(
        0,
        min(
            1,
            (frame - shot.start - shot.hold_in)
            / (shot.end - 1 - shot.hold_out - shot.start - shot.hold_in),
        ),
    )
    e = smooth(u)
    z = shot.zoom[0] + (shot.zoom[1] - shot.zoom[0]) * e
    target, velocity = target_at(plan, shot, frame if shot.track else shot.start)
    offset = tuple(a + (b - a) * e for a, b in zip(shot.offset_start, shot.offset_end, strict=True))
    focal = (target[0] + velocity * shot.look_ahead + offset[0], target[1] + offset[1])
    d = shot.target.depth
    zd = 1 + (z - 1) * d
    x = (180 * (1 - zd) + zd * focal[0] - shot.screen[0]) / d
    y = (400 * (1 - zd) + zd * focal[1] - shot.screen[1]) / d
    return Camera(x, y, z), focal, target, velocity


def camera_at(plan: Direction, frame: int) -> Camera:
    return camera_state(plan, shot_at(plan, frame), frame)[0]


def actor_override(plan: Direction, frame: int) -> CharacterFrame | None:
    if not plan.blocking:
        return None
    p = plan.blocking
    x, commands = actor_commands(p, frame / 30)
    return CharacterFrame(p.actor_id, Placement(x, p.y, p.scale), commands)


def direction_layers(plan: Direction, frame: int) -> tuple[EvaluatedLayer, ...]:
    camera = camera_at(plan, frame)
    return evaluate_layers(
        plan.compiled,
        frame,
        character_override=actor_override(plan, frame),
        camera_override=camera,
    )


def direction_frame(plan: Direction, frame: int) -> tuple[DrawPath, ...]:
    return tuple(c for layer in direction_layers(plan, frame) for c in layer.commands)


def bounds(commands: tuple[DrawPath, ...]) -> tuple[float, float, float, float] | None:
    """Conservative control-hull bounds, including stroke and local transforms; no raster."""
    left = top = math.inf
    right = bottom = -math.inf
    for c in commands:
        t = c.transform
        co, si = math.cos(t.rotation), math.sin(t.rotation)
        pad = (
            (
                c.stroke.width
                / 2
                * max(abs(t.sx), abs(t.sy))
                * (c.stroke.miter_limit if c.stroke.join == "miter" else 1)
            )
            if c.stroke
            else 0
        )
        for op in c.path:
            for i in range(0, len(op.points), 2):
                xx, yy = op.points[i] * t.sx, op.points[i + 1] * t.sy
                x, y = t.tx + co * xx - si * yy, t.ty + si * xx + co * yy
                left, top = min(left, x - pad), min(top, y - pad)
                right, bottom = max(right, x + pad), max(bottom, y + pad)
    return None if left == math.inf else (left, top, right, bottom)


def instance_commands(plan: Direction, node_id: str, frame: int) -> tuple[DrawPath, ...]:
    from reelforge.scenes.assets import asset_by_id, recipe

    r = next(r for r in plan.compiled.hierarchy if r.id == node_id)
    n = next(n for n in plan.compiled.scene.nodes if n.id == node_id)
    override = actor_override(plan, frame) if n.kind == "character" else None
    sealed = next((g for g in plan.compiled.generated if g.asset.id == n.asset_id), None)
    scene = plan.compiled.scene
    local = (
        override.commands
        if override
        else sealed.commands
        if sealed
        else recipe(
            asset_by_id(n.asset_id),
            n.variant,
            scene.warmth,
            scene.atmosphere,
            scene.breeze,
            frame / 30,
            n.character,
        )
    )
    t = camera_at(plan, frame).transform(r.depth)
    world = Placement(t.tx, t.ty, t.sx).compose(override.world if override else r.world)
    return tuple(world.command(c) for c in local)


def intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def inspect_frame(plan: Direction, frame: int) -> dict:
    shot = shot_at(plan, frame)
    cam, focal, target, velocity = camera_state(plan, shot, frame)
    t = cam.transform(shot.target.depth)
    screen = (t.tx + t.sx * focal[0], t.ty + t.sy * focal[1])
    actor = bounds(instance_commands(plan, plan.actor_id, frame)) if plan.actor_id else None
    actor_world = None
    if plan.actor_id:
        r = next(r for r in plan.compiled.hierarchy if r.id == plan.actor_id)
        actor_world = (
            (sample(plan.blocking, frame / 30)[5], plan.blocking.y)
            if plan.blocking
            else (r.world.x, r.world.y)
        )
    # Foreground bounds are conservative warnings, not a claim about pixel alpha or visibility.
    overlap = 0.0
    if actor:
        area = max(1, (actor[2] - actor[0]) * (actor[3] - actor[1]))
        for r in plan.compiled.hierarchy:
            if r.visible and r.id in plan.compiled.painter_ids and r.depth > 1.2:
                for c in instance_commands(plan, r.id, frame):
                    overlap += intersection(actor, bounds((c,))) / area
    node_box = (
        bounds(instance_commands(plan, shot.target.node_id, frame))
        if shot.target.kind == "node"
        else None
    )
    return {
        "frame": frame,
        "source_frame": frame,
        "seconds": frame / 30,
        "shot": shot.id,
        "behavior": shot.behavior,
        "cut": frame == shot.start and frame != 0,
        "camera": asdict(cam),
        "target_world": target,
        "target_depth": shot.target.depth,
        "velocity_world_per_second": velocity,
        "focal_world": focal,
        "focal_screen": screen,
        "desired_screen": shot.screen,
        "tracking_error_logical": math.dist(screen, shot.screen),
        "actor_world": actor_world,
        "actor_bounds_logical": actor,
        "node_bounds_logical": node_box,
        "framing": shot.framing,
        "foreground_bbox_overlap_upper": min(1.0, overlap),
        "intentional_foreground_overlap": shot.foreground == "declared_overlap",
        "projection_by_depth": {
            str(d): asdict(cam.transform(d))
            for d in sorted({r.depth for r in plan.compiled.hierarchy if r.depth is not None})
        },
    }


def validate_safety(plan: Direction) -> None:
    previous = None
    for f in range(90):
        shot = shot_at(plan, f)
        p = f"/shots/{plan.shots.index(shot)}"
        report = inspect_frame(plan, f)
        cam = report["camera"]
        if abs(cam["x"]) > 240 or abs(cam["y"]) > 240:
            fail(p, "Solved camera exceeds +/-240 logical-unit pan", "DIRECTION_CAMERA")
        if report["tracking_error_logical"] > TRACKING_TOLERANCE:
            fail(
                p,
                "Camera solve exceeded predeclared 1e-7 logical-unit tolerance",
                "DIRECTION_CAMERA",
            )
        b, m = report["actor_bounds_logical"], shot.margin
        if b and shot.framing != "offscreen":
            if b[0] < m or b[2] > 360 - m or b[1] < m or b[1] > 640 - m:
                fail(p, f"Actor head/width leaves safe margins at frame {f}", "DIRECTION_FRAMING")
            if shot.framing == "full" and b[3] > 640 - m:
                fail(p, f"Actor feet leave safe margins at frame {f}", "DIRECTION_FRAMING")
        if shot.foreground == "clear" and report["foreground_bbox_overlap_upper"] > 0.15:
            fail(
                p,
                f"Conservative foreground overlap >15% at frame {f}; reframe or declare",
                "DIRECTION_OCCLUSION",
            )
        obj = report["node_bounds_logical"]
        if obj:
            visible = intersection(obj, (m, m, 360 - m, 640 - m))
            area = max(1, (obj[2] - obj[0]) * (obj[3] - obj[1]))
            if visible / area < 0.6 or min(obj[2] - obj[0], obj[3] - obj[1]) < 8:
                fail(
                    p,
                    f"Target object not readable: >=60% bounds and >=8 units at frame {f}",
                    "DIRECTION_FRAMING",
                )
        if previous:
            old = previous["camera"]
            displacement = math.hypot(cam["x"] - old["x"], cam["y"] - old["y"])
            zoom_delta = abs(cam["zoom"] - old["zoom"])
            if not report["cut"]:
                if displacement * 30 > MAX_PAN_SPEED or zoom_delta * 30 > MAX_ZOOM_SPEED:
                    fail(
                        p,
                        f"Camera move exceeds 240 units/s or 1.5 zoom/s at frame {f}",
                        "DIRECTION_SPEED",
                    )
            else:
                ratio = max(cam["zoom"] / old["zoom"], old["zoom"] / cam["zoom"])
                if ratio > MAX_SCALE_CUT_RATIO:
                    fail(p, "Cut scale ratio exceeds 1.8", "DIRECTION_CONTINUITY")
                if shot.continuity == "matched" and (displacement > 24 or zoom_delta > 0.15):
                    fail(
                        p,
                        "Matched cut exceeds 24 units or .15 zoom; declare intentional_reframe",
                        "DIRECTION_CONTINUITY",
                    )
        previous = report
