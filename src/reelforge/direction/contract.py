"""Strict native-free direction-0.1 compilation and finite shot safety admission."""

from dataclasses import dataclass, replace
from pathlib import Path

from reelforge.blocking.contract import Plan as BlockingPlan
from reelforge.blocking.contract import compile_blocking
from reelforge.contracts.project import load_project
from reelforge.core.errors import InputError, Issue
from reelforge.geometry.composition import compile_composition, validate_composition
from reelforge.procedural.compiler import compile_environment
from reelforge.procedural.contract import validate_environment
from reelforge.scenes.contract import identifier, validate_scene
from reelforge.scenes.graph import CompiledScene, compile_scene

BEHAVIORS = ("establishing", "follow", "push_in", "reaction", "object_reveal", "suspense_hold")
FRAMINGS = ("full", "feet_crop", "offscreen")
MAX_SHOTS = 6
# Predeclared tolerances in logical units (output pixels = 2 * logical).
TRACKING_TOLERANCE = 1e-7
MAX_PAN_SPEED = 240.0
MAX_ZOOM_SPEED = 1.5
MAX_SCALE_CUT_RATIO = 1.8


def fail(path, message, code="DIRECTION_INVALID"):
    raise InputError(Issue(code, path, message[:240]))


def fields(value, keys, path):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail(path, "Supply exactly " + ", ".join(sorted(keys)))


def number(v, low, high, path):
    import math

    if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
        fail(path, f"Use finite number {low}..{high}")
    return float(v)


def point(v, low, high, path):
    if not isinstance(v, list) or len(v) != 2:
        fail(path, "Use two explicit coordinates")
    return tuple(number(n, low, high, path + f"/{i}") for i, n in enumerate(v))


def choice(v, choices, path):
    if not isinstance(v, str) or v not in choices:
        fail(path, "Select " + ", ".join(choices))
    return v


def identity(v, path):
    try:
        identifier(v, path)
        return v
    except InputError as e:
        fail(path, e.issue.message)


@dataclass(frozen=True)
class Target:
    kind: str
    node_id: str | None
    position: tuple[float, float] | None
    depth: float


@dataclass(frozen=True)
class Shot:
    id: str
    start: int
    end: int
    behavior: str
    target: Target
    track: bool
    look_ahead: float
    zoom: tuple[float, float]
    offset_start: tuple[float, float]
    offset_end: tuple[float, float]
    screen: tuple[float, float]
    hold_in: int
    hold_out: int
    framing: str
    margin: float
    foreground: str
    continuity: str


@dataclass(frozen=True)
class Direction:
    title: str
    compiled: CompiledScene
    blocking: BlockingPlan | None
    actor_id: str | None
    shots: tuple[Shot, ...]


def compile_direction(data: object) -> Direction:
    fields(data, {"schema_version", "title", "base", "shots"}, "")
    if data["schema_version"] != "direction-0.1":
        fail("/schema_version", "Use direction-0.1")
    title = data["title"]
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        fail("/title", "Use nonblank title <=120 characters")
    base = data["base"]
    if not isinstance(base, dict):
        fail("/base", "Embed one accepted world; paths/includes unsupported")
    blocking = None
    try:
        version = base.get("schema_version")
        if version == "blocking-0.1":
            blocking = compile_blocking(base)
            compiled = blocking.compiled
        elif version == "scene-0.1":
            compiled = compile_scene(validate_scene(base))
        elif version == "environment-0.1":
            _, compiled = compile_environment(validate_environment(base))
        elif version == "composition-0.1":
            compiled = compile_composition(validate_composition(base))
        else:
            fail("/schema_version", "Use accepted scene/environment/composition/blocking")
    except InputError as e:
        fail("/base" + e.issue.path, e.issue.message, e.issue.code)
    # Camera direction replaces base framing, including exit_right crop; base motion is untouched.
    compiled = replace(compiled, scene=replace(compiled.scene, title=title, frames=90))
    actors = [r.id for r in compiled.hierarchy if r.kind == "character" and r.visible]
    if len(actors) > 1:
        fail("/base", "At most one visible character", "DIRECTION_REFERENCE")
    actor_id = actors[0] if actors else None
    nodes = {r.id: r for r in compiled.hierarchy}
    records = data["shots"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_SHOTS:
        fail("/shots", "Use 1..6 shots", "DIRECTION_TIMELINE")
    shots, seen, cursor = [], set(), 0
    for i, r in enumerate(records):
        p = f"/shots/{i}"
        fields(
            r,
            {
                "id",
                "start_frame",
                "end_frame",
                "behavior",
                "target",
                "track",
                "look_ahead_seconds",
                "zoom",
                "offset_start",
                "offset_end",
                "screen",
                "hold_in_frames",
                "hold_out_frames",
                "framing",
                "safe_margin",
                "foreground",
                "continuity",
            },
            p,
        )
        name = identity(r["id"], p + "/id")
        if name in seen:
            fail(p + "/id", "Duplicate shot ID")
        seen.add(name)
        start, end = r["start_frame"], r["end_frame"]
        if (
            type(start) is not int
            or type(end) is not int
            or start != cursor
            or not start + 8 <= end <= 90
        ):
            fail(p, "Contiguous [0,90); each shot >=8 frames", "DIRECTION_TIMELINE")
        cursor = end
        behavior = choice(r["behavior"], BEHAVIORS, p + "/behavior")
        target = r["target"]
        if not isinstance(target, dict):
            fail(p + "/target", "Supply target object")
        kind = choice(target.get("kind"), ("actor", "node", "point"), p + "/target/kind")
        if kind == "point":
            fields(target, {"kind", "position", "depth"}, p + "/target")
            pos = point(target["position"], 0, 640, p + "/target/position")
            depth = number(target["depth"], 0.18, 1.4, p + "/target/depth")
            t = Target(kind, None, pos, depth)
        else:
            fields(target, {"kind", "id"}, p + "/target")
            node_id = identity(target["id"], p + "/target/id")
            node = nodes.get(node_id)
            if (
                node is None
                or not node.visible
                or node.depth is None
                or node.depth < 0.18
                or node_id not in compiled.painter_ids
                or (kind == "actor" and node_id != actor_id)
                or (kind == "node" and node.kind == "character")
            ):
                fail(
                    p + "/target/id",
                    "Select a visible compatible visual instance",
                    "DIRECTION_REFERENCE",
                )
            t = Target(kind, node_id, None, node.depth)
        if type(r["track"]) is not bool:
            fail(p + "/track", "Use boolean")
        track = r["track"]
        lead = number(r["look_ahead_seconds"], 0, 0.35, p + "/look_ahead_seconds")
        if (track or lead) and (kind != "actor" or blocking is None):
            fail(p, "Tracking/look-ahead requires a Phase 6A moving actor")
        if lead and not track:
            fail(p, "Look-ahead requires tracking")
        zoom = point(r["zoom"], 0.9, 1.7, p + "/zoom")
        a = point(r["offset_start"], -100, 100, p + "/offset_start")
        b = point(r["offset_end"], -100, 100, p + "/offset_end")
        screen = point(r["screen"], 16, 624, p + "/screen")
        if screen[0] > 344:
            fail(p + "/screen/0", "Screen x 16..344 logical units")
        holds = (r["hold_in_frames"], r["hold_out_frames"])
        if any(type(v) is not int or v < 0 for v in holds) or sum(holds) > end - start - 2:
            fail(p, "Nonnegative integer holds leave >=2 movement samples")
        framing = choice(r["framing"], FRAMINGS, p + "/framing")
        margin = number(r["safe_margin"], 4, 32, p + "/safe_margin")
        foreground = choice(r["foreground"], ("clear", "declared_overlap"), p + "/foreground")
        continuity = choice(r["continuity"], ("matched", "intentional_reframe"), p + "/continuity")
        if behavior == "follow" and not track:
            fail(p, "Follow requires actual actor tracking")
        if behavior == "reaction" and kind != "actor":
            fail(p, "Reaction requires actor target")
        if behavior == "object_reveal" and kind == "actor":
            fail(p, "Object reveal requires a node or bounded point")
        if behavior == "push_in" and zoom[1] <= zoom[0]:
            fail(p + "/zoom", "Push-in requires increasing zoom")
        if behavior == "establishing" and max(zoom) > 1.15:
            fail(p + "/zoom", "Establishing zoom <=1.15")
        if behavior == "suspense_hold" and (track or a != b or zoom[0] != zoom[1]):
            fail(p, "Suspense hold requires stationary camera endpoints")
        shots.append(
            Shot(
                name,
                start,
                end,
                behavior,
                t,
                track,
                lead,
                zoom,
                a,
                b,
                screen,
                *holds,
                framing,
                margin,
                foreground,
                continuity,
            )
        )
    if cursor != 90:
        fail("/shots", "Cover [0,90) exactly", "DIRECTION_TIMELINE")
    result = Direction(title, compiled, blocking, actor_id, tuple(shots))
    from .sampling import validate_safety

    validate_safety(result)
    return result


def load_direction(path: Path) -> Direction:
    return compile_direction(load_project(path))
