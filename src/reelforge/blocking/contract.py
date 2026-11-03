"""blocking-0.1: finite horizontal routes on trusted planar support corridors."""

import math
from dataclasses import dataclass, replace
from pathlib import Path

from reelforge.characters.registry import (
    DEFAULT_CHARACTER,
    asset_id_for,
    character_ids,
    character_info,
    is_registered,
)
from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue
from reelforge.geometry.composition import compile_composition, validate_composition
from reelforge.procedural.compiler import compile_environment
from reelforge.procedural.contract import validate_environment
from reelforge.scenes.assets import asset_by_id
from reelforge.scenes.contract import validate_scene
from reelforge.scenes.graph import CompiledScene, compile_scene

from .timeline import RouteClock, Segment, make_clock

FRAMES, MAX_SEGMENTS, MAX_ACCELERATION = 90, 12, 240.0


def fail(path, message, code="BLOCKING_INVALID"):
    raise InputError(Issue(code, path, message[:240]))


def fields(d, keys, path):
    if not isinstance(d, dict) or set(d) != set(keys):
        fail(path, "Supply exactly " + ", ".join(sorted(keys)))


def number(v, low, high, path):
    if type(v) not in (int, float) or not low <= v <= high or not math.isfinite(v):
        fail(path, f"Use finite number {low}..{high}")
    return v


def identifier(v, path):
    from reelforge.scenes.contract import identifier as check

    try:
        check(v, path)
    except InputError as e:
        fail(path, e.issue.message)
    return v


@dataclass(frozen=True)
class Plan:
    compiled: CompiledScene
    actor_id: str
    support_id: str
    y: float
    scale: float
    segments: tuple[Segment, ...]
    clocks: tuple[RouteClock, ...]
    camera: str
    corridor: tuple
    support: tuple
    start_facing: str
    character: str = "rowan_01"


def compile_blocking(data) -> Plan:
    required = {
        "schema_version",
        "title",
        "base",
        "actor_id",
        "support_id",
        "corridor",
        "start",
        "camera",
        "segments",
    }
    # Backward compatible: "character" is optional. blocking-0.1 manifests omit it (Rowan);
    # blocking-0.2 manifests may select a registered character.
    if not isinstance(data, dict) or not required <= set(data) <= required | {"character"}:
        fail("", "Supply exactly " + ", ".join(sorted(required)) + "; optional: character")
    version = data["schema_version"]
    if version not in ("blocking-0.1", "blocking-0.2"):
        fail("/schema_version", "Use blocking-0.1 or blocking-0.2")
    if "character" in data and version == "blocking-0.1":
        fail("/character", "The character field requires blocking-0.2")
    character = data.get("character", DEFAULT_CHARACTER)
    if not isinstance(character, str) or not is_registered(character):
        fail("/character", f"Select a registered character: {sorted(character_ids())}")
    expressions = character_info(character).expressions
    if not isinstance(data["title"], str) or not data["title"].strip() or len(data["title"]) > 120:
        fail("/title", "Use nonblank title <=120 characters")
    base = data["base"]
    if not isinstance(base, dict):
        fail("/base", "Embed an accepted scene/environment/composition")
    try:
        if base.get("schema_version") == "environment-0.1":
            _, compiled = compile_environment(validate_environment(base))
        elif base.get("schema_version") == "scene-0.1":
            compiled = compile_scene(validate_scene(base))
        elif base.get("schema_version") == "composition-0.1":
            compiled = compile_composition(validate_composition(base))
        else:
            fail("/base/schema_version", "Use scene-0.1, environment-0.1 or composition-0.1")
    except InputError as e:
        fail("/base" + e.issue.path, e.issue.message, e.issue.code)
    if data["camera"] not in ("base", "locked", "exit_right"):
        fail("/camera", "Use base, locked or exit_right")
    if data["camera"] != "base":
        compiled = replace(compiled, scene=replace(compiled.scene, camera="locked"))
    compiled = replace(
        compiled,
        scene=replace(compiled.scene, title=data["title"], frames=FRAMES),
        path_allowance=compiled.path_allowance + 256,
        operation_allowance=compiled.operation_allowance + 6000,
    )
    if compiled.path_allowance > 4096 or compiled.operation_allowance > 80000:
        fail("/base", "Two-pass turn reserve exceeds existing caps", "BLOCKING_BUDGET")
    actor_id = identifier(data["actor_id"], "/actor_id")
    support_id = identifier(data["support_id"], "/support_id")
    lookup = {n.id: n for n in compiled.scene.nodes}
    world = {r.id: r for r in compiled.hierarchy}
    actor = lookup.get(actor_id)
    ground = lookup.get(support_id)
    expected_asset = asset_id_for(character)
    if (
        actor is None
        or actor.kind != "character"
        or actor.asset_id != expected_asset
        or sum(n.kind == "character" for n in lookup.values()) != 1
    ):
        fail(
            "/actor_id",
            f"Select the single accepted {character} character asset {expected_asset!r}",
            "BLOCKING_REFERENCE",
        )
    if actor.ground_id != support_id or ground is None:
        fail(
            "/support_id", "Select the actor’s existing trusted ground binding", "BLOCKING_SUPPORT"
        )
    asset = asset_by_id(ground.asset_id) or next(
        (g.asset for g in compiled.generated if g.asset.id == ground.asset_id), None
    )
    if (
        asset is None
        or asset.id not in ("orchard_ground_01", "generated_ground")
        or asset.support_envelope is None
    ):
        fail("/support_id", "Decorative/authored assets do not support motion", "BLOCKING_SUPPORT")
    a, g = world[actor_id], world[support_id]
    if (
        a.depth != g.depth
        or not a.visible
        or not g.visible
        or abs(g.world.angle) > 1e-12
        or abs(a.world.angle) > 1e-12
    ):
        fail(
            "/support_id", "Actor and unrotated visible ground must share depth", "BLOCKING_SUPPORT"
        )
    if not 0.35 <= a.world.scale <= 0.75:
        fail("/actor_id", "Supported motion scale .35.. .75")
    if data["corridor"] != "level_field":
        fail("/corridor", "Only trusted level_field corridor is supported", "BLOCKING_SUPPORT")
    local = (-115, -45, 125, 60) if asset.id == "generated_ground" else (-140, 0, 140, 70)

    def box(bounds):
        left, t, r, b = bounds
        return (*g.world.point(left, t), *g.world.point(r, b))

    corridor = box(local)
    support = box(asset.support_envelope)
    start = data["start"]
    fields(start, {"position", "facing"}, "/start")

    def point(value, path):
        if not isinstance(value, list) or len(value) != 2:
            fail(path, "Use [world_x, world_y]")
        return tuple(number(v, 0, 640, f"{path}/{i}") for i, v in enumerate(value))

    x, y = point(start["position"], "/start/position")
    facing = start["facing"]
    if facing not in ("left", "right"):
        fail("/start/facing", "Use left/right")
    records = data["segments"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_SEGMENTS:
        fail("/segments", "Use 1..12 segments", "BLOCKING_BUDGET")
    segments = []
    seen = set()
    frame = 0
    v = 0.0
    running = 0.0
    for i, r in enumerate(records):
        p = f"/segments/{i}"
        fields(
            r,
            {
                "id",
                "start_frame",
                "end_frame",
                "mode",
                "destination",
                "end_speed",
                "facing",
                "acting",
                "expression",
            },
            p,
        )
        identity = identifier(r["id"], p + "/id")
        if identity in seen:
            fail(p + "/id", "Duplicate segment ID")
        seen.add(identity)
        for key in ("start_frame", "end_frame"):
            if type(r[key]) is not int or not 0 <= r[key] <= FRAMES:
                fail(p + "/" + key, "Use integer frame 0..90")
        if r["start_frame"] != frame or not 6 <= r["end_frame"] - frame <= FRAMES:
            fail(
                p,
                "Contiguous segments of at least 6 frames, no gaps or overlaps",
                "BLOCKING_TIMELINE",
            )
        mode = r["mode"]
        if mode not in ("idle", "walk", "run", "stop", "turn"):
            fail(p + "/mode", "Use idle/walk/run/stop/turn")
        if r["facing"] not in ("left", "right"):
            fail(p + "/facing", "Use left/right")
        if r["expression"] not in expressions:
            fail(p + "/expression", "Select an accepted expression")
        if r["acting"] not in ("idle", "look_around", "react", "none"):
            fail(p + "/acting", "Use idle/look_around/react/none")
        xx, yy = point(r["destination"], p + "/destination")
        end_speed = number(r["end_speed"], 0, 90, p + "/end_speed")
        if yy != y:
            fail(
                p + "/destination",
                "Only horizontal level routes; slopes/depth/stairs unsupported",
                "BLOCKING_SUPPORT",
            )
        moving = mode in ("walk", "run", "stop")
        if moving:
            if r["facing"] != facing or (xx - x) * (1 if facing == "right" else -1) <= 0:
                fail(p + "/destination", "Movement follows facing; stop and turn before reversal")
            if r["acting"] != "none":
                fail(p + "/acting", "Moving segments use none; acting is stationary")
            if mode == "stop" and (v == 0 or end_speed != 0):
                fail(p + "/end_speed", "Stop begins moving and ends at zero")
            if mode in ("walk", "run") and not (10 if mode == "walk" else 40) <= end_speed <= (
                45 if mode == "walk" else 90
            ):
                fail(p + "/end_speed", "Walk end speed 10..45; run 40..90")
        else:
            if xx != x or end_speed != 0 or v != 0:
                fail(p, "Idle/turn must be stationary; use a stop segment first")
            if mode == "turn":
                if r["facing"] == facing or r["end_frame"] - frame < 12:
                    fail(p, "Turn changes facing over at least 12 frames")
            elif r["facing"] != facing:
                fail(p + "/facing", "Only turn may change facing")
        sign = 1 if facing == "right" else -1
        target_run = 1.0 if mode == "run" else 0.0
        s = Segment(
            identity,
            frame,
            r["end_frame"],
            mode,
            x,
            xx,
            y,
            sign * v,
            sign * end_speed,
            r["facing"],
            r["acting"],
            r["expression"],
            running,
            target_run,
        )
        coeff = s.coefficients
        times = [0.0, 1.0]
        if abs(coeff[3]) > 1e-12:
            extremum = -coeff[2] / (3 * coeff[3])
            if 0 < extremum < 1:
                times.append(extremum)
        limit = 45 if mode == "walk" else 90
        for u in times:
            vv = sign * (coeff[1] + 2 * coeff[2] * u + 3 * coeff[3] * u * u) / s.duration
            if vv < -1e-8 or vv > limit + 1e-8:
                fail(
                    p + "/destination",
                    "Hermite route reverses/overspeeds between endpoints",
                    "BLOCKING_TRAJECTORY",
                )
        acceleration = max(abs(2 * coeff[2]), abs(2 * coeff[2] + 6 * coeff[3])) / s.duration**2
        if acceleration > MAX_ACCELERATION + 1e-7:
            fail(p, "Acceleration exceeds 240 world units/s²", "BLOCKING_TRAJECTORY")
        left, t, rr, b = corridor
        if not left <= min(x, xx) <= max(x, xx) <= rr or not t <= y <= b:
            fail(
                p + "/destination",
                "Complete monotone route must fit trusted level_field corridor",
                "BLOCKING_SUPPORT",
            )
        segments.append(s)
        frame = r["end_frame"]
        x = xx
        v = end_speed
        facing = r["facing"]
        running = target_run
    if frame != FRAMES:
        fail("/segments", "Timeline must cover [0,90) exactly", "BLOCKING_TIMELINE")
    bouts = []
    current = []
    for s in segments:
        if s.mode in ("walk", "run", "stop"):
            current.append(s)
        elif current:
            bouts.append(make_clock(tuple(current), a.world.scale))
            current = []
    if current:
        bouts.append(make_clock(tuple(current), a.world.scale))
    if not bouts:
        fail("/segments", "Include at least one supported travel bout")
    if any(not 0.7 <= c.factor <= 1.3 or c.total_cycles > 16 for c in bouts):
        fail(
            "/segments",
            "Route cannot settle in a calibrated stride phase; adjust distance/duration",
            "BLOCKING_GAIT",
        )
    plan = Plan(
        compiled,
        actor_id,
        support_id,
        y,
        a.world.scale,
        tuple(segments),
        tuple(bouts),
        data["camera"],
        corridor,
        support,
        start["facing"],
        character,
    )
    from .sampling import validate_contacts

    validate_contacts(plan)
    return plan


def load_blocking(path: Path) -> Plan:
    return compile_blocking(load_project(path))
