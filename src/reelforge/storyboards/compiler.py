"""Strict, deterministic storyboard scheduling and accepted-plan generation; no native imports."""

import json
import math
from dataclasses import dataclass
from pathlib import Path

from reelforge.characters.presets import EXPRESSIONS
from reelforge.contracts.project import load_project, project_digest
from reelforge.core.errors import InputError, Issue
from reelforge.direction.contract import BEHAVIORS, Direction, compile_direction
from reelforge.direction.sampling import camera_at
from reelforge.direction.sampling import inspect_frame as inspect_camera
from reelforge.scenes.contract import identifier

from .patterns import BEAT_ACTIONS, PATTERNS

MAX_BEATS, MAX_SUBJECTS, MAX_VIEWS = 10, 16, 6
EDITORIAL_CUT_PAN = 60.0  # Logical units, stricter additive storyboard admission.


def fail(path: str, message: str, code: str = "STORYBOARD_INVALID") -> None:
    raise InputError(Issue(code, path, message[:240]))


def fields(value, required, path, optional=()):
    if (
        not isinstance(value, dict)
        or not set(required) <= set(value)
        or not set(value) <= set(required) | set(optional)
    ):
        fail(
            path,
            "Required fields: "
            + ", ".join(sorted(required))
            + ("; optional: " + ", ".join(sorted(optional)) if optional else ""),
        )


def number(value, low, high, path):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        fail(path, f"Use finite number {low}..{high}")
    return value


def name(value, path):
    try:
        identifier(value, path)
    except InputError as e:
        fail(path, e.issue.message)
    return value


def choice(value, values, path):
    if not isinstance(value, str) or value not in values:
        fail(path, "Select " + ", ".join(values))
    return value


def pair(value, low, high, path):
    if not isinstance(value, list) or len(value) != 2:
        fail(path, "Supply two explicit coordinates")
    return [number(v, low, high, path + f"/{i}") for i, v in enumerate(value)]


def text(value, limit, path):
    if not isinstance(value, str) or len(value) > limit:
        fail(path, f"Use text <= {limit} characters; text is metadata only")
    return value


def bounded_copy(data):
    # Check direct Python callers as well as the original strict JSON file loader.
    stack = [(data, 0)]
    count = 0
    while stack:
        value, depth = stack.pop()
        count += 1
        if depth > 32 or count > 100_000:
            fail("", "Input exceeds 32 nesting levels or 100000 values", "STORYBOARD_BUDGET")
        if isinstance(value, dict):
            if any(not isinstance(k, str) for k in value):
                fail("", "Object keys must be strings")
            stack.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            stack.extend((v, depth + 1) for v in value)
        elif value is not None and type(value) not in (str, int, float, bool):
            fail("", "Use JSON values only")
    try:
        raw = json.dumps(data, allow_nan=False, ensure_ascii=True, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError):
        fail("", "Only finite bounded JSON values are permitted")
    if len(raw) > 1_048_576:
        fail("", "Input exceeds 1048576 bytes", "STORYBOARD_BUDGET")
    return json.loads(raw)


@dataclass(frozen=True)
class Beat:
    id: str
    kind: str
    start: int
    end: int
    subject: str
    view: str
    action: str
    description: str


@dataclass(frozen=True)
class Storyboard:
    title: str
    pattern: str
    description: str
    beats: tuple[Beat, ...]
    direction: Direction
    blocking_json: str
    direction_json: str
    subjects_json: str
    shot_beat_indices: tuple[tuple[int, ...], ...]
    plan_digest: str


def remap_error(error, groups, views):
    """Translate accepted intermediate paths back to actionable storyboard source pointers."""
    path = error.issue.path
    code = error.issue.code
    if path.startswith("/base/base"):
        path = "/world" + path[len("/base/base") :]
    elif path.startswith("/base/segments/"):
        parts = path.split("/")
        suffix = "/".join(parts[4:])
        mapping = {"destination": "end_x", "end_speed": "end_speed", "expression": "expression"}
        field = mapping.get(suffix, "")
        path = "/beats/" + parts[3] + "/action" + ("/" + field if field else "")
    elif path.startswith("/base/start"):
        path = "/rowan/start" + path[len("/base/start") :]
    elif path.startswith("/base/"):
        key = path.split("/")[2]
        path = "/rowan/" + key if key in ("actor_id", "support_id", "corridor") else "/beats"
    elif path.startswith("/shots/"):
        parts = path.split("/")
        index = int(parts[2])
        view_index = views[groups[index][0]]
        suffix = "/".join(parts[3:])
        mapping = {
            "behavior": "kind",
            "look_ahead_seconds": "lead_seconds",
            "framing": "crop",
            "continuity": "cut",
            "target": "subject",
            "hold_in_frames": "hold/0",
            "hold_out_frames": "hold/1",
        }
        if suffix.startswith("target"):
            suffix = "subject"
        else:
            suffix = mapping.get(suffix, suffix)
        path = f"/views/{view_index}" + ("/" + suffix if suffix else "")
    fail(path, f"{code}: {error.issue.message}", "STORYBOARD_" + code)


def compile_storyboard(data: object) -> Storyboard:
    d = bounded_copy(data)
    fields(
        d,
        {"schema_version", "title", "world", "rowan", "subjects", "views", "pattern", "beats"},
        "",
        optional=("description",),
    )
    if d["schema_version"] != "storyboard-0.1":
        fail("/schema_version", "Use storyboard-0.1")
    title = text(d["title"], 120, "/title")
    if not title.strip():
        fail("/title", "Use a nonblank title")
    description = text(d.get("description", ""), 800, "/description")
    if not isinstance(d["world"], dict) or d["world"].get("schema_version") not in (
        "scene-0.1",
        "environment-0.1",
        "composition-0.1",
    ):
        fail("/world", "Embed one accepted scene/environment/composition; no includes")
    rowan = d["rowan"]
    fields(rowan, {"actor_id", "support_id", "start"}, "/rowan")
    name(rowan["actor_id"], "/rowan/actor_id")
    name(rowan["support_id"], "/rowan/support_id")
    fields(rowan["start"], {"position", "facing"}, "/rowan/start")
    x, y = pair(rowan["start"]["position"], 0, 640, "/rowan/start/position")
    facing = choice(rowan["start"]["facing"], ("left", "right"), "/rowan/start/facing")
    subjects = d["subjects"]
    if not isinstance(subjects, list) or not 1 <= len(subjects) <= MAX_SUBJECTS:
        fail("/subjects", "Define 1..16 local focal subjects", "STORYBOARD_BUDGET")
    subject_defs = {}
    for i, s in enumerate(subjects):
        p = f"/subjects/{i}"
        fields(s, {"id", "target"}, p)
        alias = name(s["id"], p + "/id")
        if alias in subject_defs:
            fail(p + "/id", "Duplicate local subject ID", "STORYBOARD_REFERENCE")
        t = s["target"]
        if not isinstance(t, dict):
            fail(p + "/target", "Use actor, node or world point")
        kind = choice(t.get("kind"), ("actor", "node", "point"), p + "/target/kind")
        if kind == "point":
            fields(t, {"kind", "position", "depth"}, p + "/target")
            pair(t["position"], 0, 640, p + "/target/position")
            number(t["depth"], 0.18, 1.4, p + "/target/depth")
        else:
            fields(t, {"kind", "id"}, p + "/target")
            name(t["id"], p + "/target/id")
            if kind == "actor" and t["id"] != rowan["actor_id"]:
                fail(
                    p + "/target/id",
                    "Actor alias must reference this Rowan",
                    "STORYBOARD_REFERENCE",
                )
        subject_defs[alias] = t
    records = d["views"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_VIEWS:
        fail("/views", "Define 1..6 reusable local camera views", "STORYBOARD_BUDGET")
    view_defs, view_indices = {}, {}
    for i, v in enumerate(records):
        p = f"/views/{i}"
        fields(
            v,
            {
                "id",
                "kind",
                "subject",
                "zoom",
                "screen",
                "offset_start",
                "offset_end",
                "lead_seconds",
                "hold",
                "crop",
                "foreground",
                "cut",
            },
            p,
        )
        alias = name(v["id"], p + "/id")
        if alias in view_defs:
            fail(p + "/id", "Duplicate view ID", "STORYBOARD_REFERENCE")
        choice(v["kind"], BEHAVIORS, p + "/kind")
        ref = name(v["subject"], p + "/subject")
        if ref not in subject_defs:
            fail(p + "/subject", "Select a local subject ID", "STORYBOARD_REFERENCE")
        pair(v["zoom"], 0.9, 1.7, p + "/zoom")
        pair(v["screen"], 16, 624, p + "/screen")
        if v["screen"][0] > 344:
            fail(p + "/screen/0", "Screen X must be 16..344")
        pair(v["offset_start"], -100, 100, p + "/offset_start")
        pair(v["offset_end"], -100, 100, p + "/offset_end")
        number(v["lead_seconds"], 0, 0.35, p + "/lead_seconds")
        if (
            not isinstance(v["hold"], list)
            or len(v["hold"]) != 2
            or any(type(n) is not int or not 0 <= n <= 88 for n in v["hold"])
        ):
            fail(p + "/hold", "Use [opening,closing] nonnegative integer frame counts <=88")
        choice(v["crop"], ("full", "feet_crop", "offscreen"), p + "/crop")
        choice(v["foreground"], ("clear", "declared_overlap"), p + "/foreground")
        choice(v["cut"], ("matched", "intentional_reframe"), p + "/cut")
        view_defs[alias], view_indices[alias] = v, i
    pattern_id = choice(d["pattern"], tuple(p.id for p in PATTERNS), "/pattern")
    pattern = next(p for p in PATTERNS if p.id == pattern_id)
    raw = d["beats"]
    if not isinstance(raw, list) or not 2 <= len(raw) <= MAX_BEATS:
        fail("/beats", "Supply 2..10 beats", "STORYBOARD_BUDGET")
    beats, segments, seen, cursor, stage, stages_seen = [], [], set(), 0, -1, set()
    groups, beat_view_indices = [], []
    for i, b in enumerate(raw):
        p = f"/beats/{i}"
        fields(
            b, {"id", "type", "frames", "subject", "action", "view"}, p, optional=("description",)
        )
        beat_id = name(b["id"], p + "/id")
        if beat_id in seen:
            fail(p + "/id", "Duplicate beat ID", "STORYBOARD_TIMELINE")
        seen.add(beat_id)
        kind = choice(b["type"], tuple(BEAT_ACTIONS), p + "/type")
        if kind not in pattern.stages or pattern.stages.index(kind) < stage:
            fail(p + "/type", "Beat violates selected pattern stage order", "STORYBOARD_PATTERN")
        if kind in stages_seen and kind not in ("approach", "hold"):
            fail(p + "/type", "Only approach and hold stages may repeat", "STORYBOARD_PATTERN")
        stage = pattern.stages.index(kind)
        stages_seen.add(kind)
        if type(b["frames"]) is not int or not 6 <= b["frames"] <= 90:
            fail(p + "/frames", "Use integer duration 6..90 frames", "STORYBOARD_TIMELINE")
        end = cursor + b["frames"]
        if end > 90:
            fail(p + "/frames", "Cumulative timeline exceeds 90 frames", "STORYBOARD_TIMELINE")
        subject, view = name(b["subject"], p + "/subject"), name(b["view"], p + "/view")
        if subject not in subject_defs or view not in view_defs:
            fail(
                p + ("/subject" if subject not in subject_defs else "/view"),
                "Select a declared local ID",
                "STORYBOARD_REFERENCE",
            )
        if kind in ("discover", "approach") and subject_defs[subject]["kind"] == "actor":
            fail(
                p + "/subject",
                "Discover/approach identify a non-actor subject",
                "STORYBOARD_REFERENCE",
            )
        a = b["action"]
        if not isinstance(a, dict):
            fail(p + "/action", "Supply supported action data")
        action = choice(a.get("kind"), BEAT_ACTIONS[kind], p + "/action/kind")
        required = {"kind", "expression"}
        if action in ("walk_to", "run_to", "stop_at"):
            required.add("end_x")
        if action in ("walk_to", "run_to"):
            required.add("end_speed")
        fields(a, required, p + "/action")
        choice(a["expression"], EXPRESSIONS, p + "/action/expression")
        if (kind in ("react", "escape") or action == "react") and b["frames"] < 12:
            fail(p + "/frames", "Reaction/escape requires >=12 frames", "STORYBOARD_TIMELINE")
        xx = number(a["end_x"], 0, 640, p + "/action/end_x") if "end_x" in a else x
        speed = (
            number(
                a["end_speed"],
                10 if action == "walk_to" else 40,
                45 if action == "walk_to" else 90,
                p + "/action/end_speed",
            )
            if "end_speed" in a
            else 0
        )
        mode = {"walk_to": "walk", "run_to": "run", "stop_at": "stop"}.get(action, "idle")
        acting = "none" if mode != "idle" else action
        segments.append(
            dict(
                id=beat_id,
                start_frame=cursor,
                end_frame=end,
                mode=mode,
                destination=[xx, y],
                end_speed=speed,
                facing=facing,
                acting=acting,
                expression=a["expression"],
            )
        )
        beats.append(
            Beat(
                beat_id,
                kind,
                cursor,
                end,
                subject,
                view,
                action,
                text(b.get("description", ""), 400, p + "/description"),
            )
        )
        beat_view_indices.append(view_indices[view])
        if i and beats[-2].view == view:
            groups[-1].append(i)
        else:
            groups.append([i])
        cursor, x = end, xx
    if cursor != 90:
        fail("/beats", "Durations must sum to exactly 90 frames", "STORYBOARD_TIMELINE")
    if not pattern.required <= stages_seen:
        fail(
            "/beats",
            "Pattern requires " + ", ".join(sorted(pattern.required)),
            "STORYBOARD_PATTERN",
        )
    if not any(s["mode"] in ("walk", "run") for s in segments):
        fail(
            "/beats",
            "This milestone requires a travel bout admitted by blocking-0.1",
            "STORYBOARD_UNSUPPORTED",
        )
    used_views = {b.view for b in beats}
    if used_views != set(view_defs):
        fail("/views", "Every view must be allocated to at least one beat", "STORYBOARD_REFERENCE")
    blocking = dict(
        schema_version="blocking-0.1",
        title=title,
        base=d["world"],
        actor_id=rowan["actor_id"],
        support_id=rowan["support_id"],
        corridor="level_field",
        start=rowan["start"],
        camera="locked",
        segments=segments,
    )
    shots = []
    for group in groups:
        start, end = beats[group[0]].start, beats[group[-1]].end
        v = view_defs[beats[group[0]].view]
        shots.append(
            dict(
                id="shot_" + beats[group[0]].id,
                start_frame=start,
                end_frame=end,
                behavior=v["kind"],
                target=subject_defs[v["subject"]],
                track=v["kind"] == "follow",
                look_ahead_seconds=v["lead_seconds"],
                zoom=v["zoom"],
                offset_start=v["offset_start"],
                offset_end=v["offset_end"],
                screen=v["screen"],
                hold_in_frames=v["hold"][0],
                hold_out_frames=v["hold"][1],
                framing=v["crop"],
                safe_margin=8,
                foreground=v["foreground"],
                continuity=v["cut"],
            )
        )
    # Prefix length can exceed the earlier 48-char ID bound; derive stable bounded IDs.
    for i, s in enumerate(shots):
        s["id"] = f"shot_{i:02d}"
    direction = dict(schema_version="direction-0.1", title=title, base=blocking, shots=shots)
    try:
        compiled = compile_direction(direction)
    except InputError as e:
        remap_error(e, groups, beat_view_indices)
    nodes = {r.id: r for r in compiled.compiled.hierarchy}
    for i, s in enumerate(subjects):
        t = s["target"]
        if t["kind"] == "point":
            continue
        n = nodes.get(t["id"])
        if (
            n is None
            or not n.visible
            or n.id not in compiled.compiled.painter_ids
            or n.depth is None
            or n.depth < 0.18
            or (t["kind"] == "node" and n.kind == "character")
        ):
            fail(
                f"/subjects/{i}/target/id",
                "Select a visible compatible world instance",
                "STORYBOARD_REFERENCE",
            )
    for i, shot in enumerate(compiled.shots[1:], 1):
        before, after = camera_at(compiled, shot.start - 1), camera_at(compiled, shot.start)
        if math.hypot(after.x - before.x, after.y - before.y) > EDITORIAL_CUT_PAN:
            fail(
                f"/beats/{groups[i][0]}/view",
                "Storyboard cut pan jump exceeds 60 logical units; "
                "match the views or reuse one view across beats",
                "STORYBOARD_EDITORIAL",
            )

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    return Storyboard(
        title,
        pattern_id,
        description,
        tuple(beats),
        compiled,
        canonical(blocking),
        canonical(direction),
        canonical(subjects),
        tuple(tuple(g) for g in groups),
        project_digest(direction),
    )


def load_storyboard(path: Path) -> Storyboard:
    return compile_storyboard(load_project(path))


def inspect_beats(plan: Storyboard) -> dict:
    from dataclasses import asdict

    return {
        "contract": "storyboard-0.1",
        "title": plan.title,
        "pattern": plan.pattern,
        "description_metadata": plan.description,
        "frames": 90,
        "fps": 30,
        "beats": [asdict(b) for b in plan.beats],
        "shots": [
            {
                "id": shot.id,
                "start": shot.start,
                "end": shot.end,
                "beats": [plan.beats[i].id for i in group],
            }
            for shot, group in zip(plan.direction.shots, plan.shot_beat_indices, strict=True)
        ],
        "plan_sha256": plan.plan_digest,
        "audio_present": False,
    }


def inspect_plans(plan: Storyboard) -> dict:
    from reelforge.scenes.graph import inspect_scene

    return {
        **inspect_beats(plan),
        "scene": inspect_scene(plan.direction.compiled),
        "scene_is_static_reference": True,
        "blocking_document": json.loads(plan.blocking_json),
        "direction_document": json.loads(plan.direction_json),
        "subjects": json.loads(plan.subjects_json),
    }


def inspect_frame(plan: Storyboard, frame: int) -> dict:
    camera = inspect_camera(plan.direction, frame)  # Validate frame before motion sampling.
    beat = next(b for b in plan.beats if b.start <= frame < b.end)
    from reelforge.blocking.sampling import inspect_frame as inspect_motion

    return {
        "beat": beat.id,
        "beat_type": beat.kind,
        "subject": beat.subject,
        "source_frame": frame,
        "camera": camera,
        "motion": inspect_motion(plan.direction.blocking, frame),
    }
