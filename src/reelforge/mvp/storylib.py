"""Reusable story-shot library: compact parameters -> validated storyboard-0.1 dicts.

Every helper emits data for the existing contracts only; nothing here draws or encodes. Two
registered environments are supported (Frost Peak snowy mountain and the Last Light orchard),
both placing the registered ``yellow_mellow_v2`` actor on an existing walkable ground. A small set
of named, parameterised shot presets (establish / reaction / investigate-activate / threat /
travel / arrive / resolve) produce 90-frame storyboard segments. The 60-second reel and the
prompt planner both build reels purely from these presets, so the same machinery serves both.

All numeric staging (actor scale band 0.35..0.75, calibrated walk/stop gait, close-up zoom, the
beacon activation socket alignment) matches the visually-reviewed Phase 9C shots.
"""

from __future__ import annotations

from reelforge.characters.yellow_mellow_v2.episode import DEFAULT_DRAW_SCALE
from reelforge.characters.yellow_mellow_v2.motions import ACTIVATE_HEIGHT, ACTIVATE_REACH
from reelforge.environments.snowy import BEACON_SOCKET

GROUND_Y = 470.0
OUT = {
    "width": 720,
    "height": 1280,
    "fps": 30,
    "codec": "h264",
    "pixel_format": "yuv420p",
    "frames": 90,
}

# Actor scales within the blocking support band (0.35..0.75); camera zoom carries closeness.
WIDE_SCALE = 0.5
NEAR_SCALE = 0.75
CHAR_K = NEAR_SCALE * DEFAULT_DRAW_SCALE

# Beacon staging so its activation socket lands on the activate fingertip target.
STOP_X = 180.0
BEACON_SCALE = (ACTIVATE_HEIGHT * CHAR_K) / -BEACON_SOCKET[1]
BEACON_X = STOP_X + ACTIVATE_REACH * CHAR_K - BEACON_SOCKET[0] * BEACON_SCALE


# ---------------------------------------------------------------- node + scene helpers
def _t(x, y, scale=1.0):
    return {"x": x, "y": y, "scale": scale, "rotation_degrees": 0.0}


def _node(nid, kind, parent, order, transform, **extra):
    node = {
        "id": nid,
        "kind": kind,
        "parent": parent,
        "order": order,
        "visible": True,
        "transform": transform,
    }
    node.update(extra)
    return node


def frost_peak_scene(
    title,
    *,
    art,
    actor_x,
    actor_scale,
    beacon,
    props=(),
    fg="default",
    answer=None,
    peaks=("far", "mid"),
):
    """Frost Peak snowy-mountain scene-0.1. ``beacon`` = (variant, layer, x, y, scale)."""
    nodes = [
        _node("root", "root", None, 0, _t(0, 0)),
        _node("sky_layer", "layer", "root", 0, _t(0, 0), depth=0.0),
        _node(
            "sky",
            "background",
            "sky_layer",
            0,
            _t(0, 0),
            asset_id="frost_sky_01",
            variant="default",
        ),
        _node("distance", "layer", "root", 1, _t(0, 0), depth=0.18),
        _node("terrain", "layer", "root", 2, _t(0, 0), depth=1.0),
        _node(
            "ridge",
            "environment",
            "terrain",
            0,
            _t(180, GROUND_Y),
            asset_id="frost_ridge_01",
            variant="default",
        ),
        _node("structures", "layer", "root", 3, _t(0, 0), depth=0.85),
        _node("people", "layer", "root", 5, _t(0, 0), depth=1.0),
        _node(
            "mellow",
            "character",
            "people",
            0,
            _t(actor_x, GROUND_Y, actor_scale),
            asset_id="yellow_mellow_v2",
            variant="default",
            character={
                "character": "yellow_mellow_v2",
                "action": "idle",
                "expression": art["expression"],
            },
            ground_id="ridge",
        ),
        _node("foreground", "layer", "root", 6, _t(0, 0), depth=1.4),
        _node(
            "fg_drifts",
            "environment",
            "foreground",
            0,
            _t(180, 640),
            asset_id="frost_foreground_01",
            variant=fg,
        ),
    ]
    for i, variant in enumerate(peaks):
        nodes.append(
            _node(
                f"peaks_{variant}",
                "background",
                "distance",
                i,
                _t(180, 300),
                asset_id="frost_peaks_01",
                variant=variant,
            )
        )
    if answer is not None:
        nodes.append(
            _node(
                "answer",
                "asset",
                "distance",
                5,
                _t(*answer),
                asset_id="answer_light_01",
                variant="default",
            )
        )
    for i, (pid, asset, variant, x, y, s) in enumerate(props):
        nodes.append(
            _node(pid, "asset", "structures", i, _t(x, y, s), asset_id=asset, variant=variant)
        )
    if beacon is not None:
        variant, layer, bx, by, bs = beacon
        nodes.append(
            _node(
                "beacon", "asset", layer, 9, _t(bx, by, bs), asset_id="beacon_01", variant=variant
            )
        )
    return _scene(title, "gentle_drift", art, nodes)


def orchard_scene(title, *, art, actor_x, actor_scale, props=(), fg=True):
    """Last Light orchard scene-0.1 (reuses the registered orchard assets)."""
    nodes = [
        _node("root", "root", None, 0, _t(0, 0)),
        _node("sky_layer", "layer", "root", 0, _t(0, 0), depth=0.0),
        _node(
            "sky", "background", "sky_layer", 0, _t(0, 0), asset_id="dusk_sky_01", variant="default"
        ),
        _node("distance", "layer", "root", 1, _t(0, 0), depth=0.18),
        _node(
            "hills",
            "background",
            "distance",
            0,
            _t(180, 360),
            asset_id="distant_hills_01",
            variant="default",
        ),
        _node("terrain", "layer", "root", 2, _t(0, 0), depth=1.0),
        _node(
            "ground",
            "environment",
            "terrain",
            0,
            _t(155, 515, 1.15),
            asset_id="orchard_ground_01",
            variant="default",
        ),
        _node("structures", "layer", "root", 3, _t(0, 0), depth=0.85),
        _node("people", "layer", "root", 5, _t(0, 0), depth=1.0),
        _node(
            "mellow",
            "character",
            "people",
            0,
            _t(actor_x, 535, actor_scale),
            asset_id="yellow_mellow_v2",
            variant="default",
            character={
                "character": "yellow_mellow_v2",
                "action": "idle",
                "expression": art["expression"],
            },
            ground_id="ground",
        ),
        _node("foreground", "layer", "root", 6, _t(0, 0), depth=1.4),
    ]
    for i, (pid, asset, variant, x, y, s) in enumerate(props):
        nodes.append(
            _node(pid, "asset", "structures", i, _t(x, y, s), asset_id=asset, variant=variant)
        )
    if fg:
        nodes.append(
            _node(
                "fg_tree",
                "asset",
                "foreground",
                0,
                _t(-6, 624, 1.8),
                asset_id="orchard_tree_01",
                variant="broad",
            )
        )
        nodes.append(
            _node(
                "fg_tree_r",
                "asset",
                "foreground",
                1,
                _t(385, 610, 1.7),
                asset_id="orchard_tree_01",
                variant="windswept",
            )
        )
    return _scene(title, "gentle_drift", art, nodes)


def _scene(title, camera, art, nodes):
    return {
        "schema_version": "scene-0.1",
        "title": title,
        "output": OUT,
        "camera": camera,
        "art_direction": {k: art[k] for k in ("warmth", "atmosphere", "breeze")},
        "nodes": nodes,
    }


# ---------------------------------------------------------------- storyboard helpers
def view(
    vid,
    kind,
    subject,
    zoom,
    screen,
    *,
    offset=(0, 0),
    hold=(6, 8),
    crop="feet_crop",
    foreground="clear",
    lead=0.0,
):
    return {
        "id": vid,
        "kind": kind,
        "subject": subject,
        "zoom": list(zoom),
        "screen": list(screen),
        "offset_start": list(offset),
        "offset_end": list(offset),
        "lead_seconds": lead,
        "hold": list(hold),
        "crop": crop,
        "foreground": foreground,
        "cut": "intentional_reframe",
    }


def beat(bid, kind, frames, subject, vid, action, expression, **extra):
    return {
        "id": bid,
        "type": kind,
        "frames": frames,
        "subject": subject,
        "view": vid,
        "action": {"kind": action, "expression": expression, **extra},
    }


def storyboard(
    title,
    description,
    world,
    support_id,
    start_x,
    start_y,
    subjects,
    views,
    pattern,
    beats,
    facing="right",
):
    return {
        "schema_version": "storyboard-0.1",
        "title": title,
        "description": description,
        "world": world,
        "rowan": {
            "actor_id": "mellow",
            "support_id": support_id,
            "character": "yellow_mellow_v2",
            "start": {"position": [start_x, start_y], "facing": facing},
        },
        "subjects": [{"id": "mellow", "target": {"kind": "actor", "id": "mellow"}}] + subjects,
        "views": views,
        "pattern": pattern,
        "beats": beats,
    }


def walk_then_stop(start_x, view_id, subject, expression, *, run=False):
    """Calibrated NEAR_SCALE travel bout: accelerate, then plant. ~1.25 gait cycles."""
    if run:
        return [
            beat(
                "go",
                "approach",
                34,
                subject,
                view_id,
                "run_to",
                expression,
                end_x=start_x + 70,
                end_speed=60,
            ),
            beat(
                "halt", "discover", 20, subject, view_id, "stop_at", expression, end_x=start_x + 92
            ),
        ]
    return [
        beat(
            "go",
            "approach",
            34,
            subject,
            view_id,
            "walk_to",
            expression,
            end_x=start_x + 38,
            end_speed=36,
        ),
        beat("halt", "discover", 20, subject, view_id, "stop_at", expression, end_x=start_x + 60),
    ]


# ---------------------------------------------------------------- environment registry
FROST_PINES = (
    ("pine_a", "pine_snow_01", "tall", 60, 430, 0.9),
    ("pine_b", "pine_snow_01", "short", 300, 436, 0.7),
    ("pine_c", "pine_snow_01", "cluster", 330, 432, 0.6),
    ("rock_a", "frost_rocks_01", "cliff", 40, 448, 0.9),
)
ORCHARD_TREES = (
    ("tree_a", "orchard_tree_01", "broad", 40, 425, 0.95),
    ("tree_b", "orchard_tree_01", "compact", 96, 398, 0.6),
    ("tree_c", "orchard_tree_01", "lean", 322, 452, 1.0),
    ("fence", "fence_01", "default", 119, 439, 0.6),
)

ENVIRONMENTS = {
    "frost_peak": {
        "display": "Frost Peak (snowy mountain)",
        "support_id": "ridge",
        "ground_y": GROUND_Y,
        "has_beacon": True,
    },
    "orchard": {
        "display": "Last Light orchard",
        "support_id": "ground",
        "ground_y": 535.0,
        "has_beacon": False,
    },
}


def _frost(title, **kw):
    return frost_peak_scene(title, **kw)


def _orchard(title, **kw):
    return orchard_scene(title, **kw)


# ---------------------------------------------------------------- shot presets
# Each preset returns a complete storyboard-0.1 dict. ``env`` selects the environment; presets
# raise ValueError if the environment cannot stage them (e.g. activate without a beacon).
def shot_establish(env, *, title, description, mood, variant=0):
    """Wide establishing: actor walks in, stops, looks. Beacon/landmark visible ahead.

    ``variant`` picks a distinct validated staging (start position, how far the actor crosses,
    the focal landmark it ends on and the camera screen X), so repeated establish beats are
    genuinely different compositions, not identical frames.
    """
    art, extra = _mood(env, mood, "curious")
    # (start_x, cross_end, stop_end, focal_dx, screen_x) within the blocking corridor / 16..344.
    vs = [(120, 150, 159, 0, 230), (96, 134, 142, 20, 210), (140, 176, 184, -24, 252)]
    sxi, cross, stopx, fdx, scrx = vs[variant % len(vs)]
    if env == "frost_peak":
        world = _frost(
            title,
            art=art,
            actor_x=150,
            actor_scale=WIDE_SCALE,
            beacon=("buried", "structures", 250 + fdx, 452, 0.62),
            props=FROST_PINES,
            **extra,
        )
        sy, support = GROUND_Y, "ridge"
        focal = [248 + fdx, 452]
    else:
        world = _orchard(
            title, art=art, actor_x=150, actor_scale=WIDE_SCALE, props=ORCHARD_TREES, **extra
        )
        sy, support = 535, "ground"
        focal = [250 + fdx, 500]
    return storyboard(
        title,
        description,
        world,
        support,
        sxi,
        sy,
        [{"id": "trail", "target": {"kind": "point", "position": focal, "depth": 1.0}}],
        [
            view(
                "wide",
                "establishing",
                "trail",
                (1.0, 1.1),
                (scrx, focal[1]),
                hold=(6, 10),
                crop="full",
            )
        ],
        "discovery_reaction",
        [
            beat("establish", "establish", 12, "trail", "wide", "idle", "neutral"),
            beat(
                "cross",
                "approach",
                42,
                "trail",
                "wide",
                "walk_to",
                mood_expr(mood),
                end_x=cross,
                end_speed=30,
            ),
            beat("spot", "discover", 18, "trail", "wide", "stop_at", mood_expr(mood), end_x=stopx),
            beat("look", "react", 18, "trail", "wide", "look_around", mood_expr(mood)),
        ],
    )


def shot_reaction(env, *, title, description, mood, variant=0):
    """Close-up: readable face, concern/surprise. Uses the corrected close_up behavior.

    ``variant`` shifts the start position, how far the actor steps in, the camera screen X and
    the off-screen subject it reacts to, so repeated reaction beats are framed differently
    (reaction on the left, centred, or on the right) while staying inside the close-up pan limit.
    """
    art, extra = _mood(env, mood, "concerned")
    # (start_x, walk_end, stop_end, screen_x, ahead_x): distinct validated framings. Each keeps a
    # ~60-unit calibrated travel bout (walk 38 + stop 22) so the gait always settles.
    vs = [(150, 188, 210, 176, 300), (130, 168, 190, 150, 280), (168, 206, 228, 200, 320)]
    sxi, walk_end, stop_end, scr_x, ahead_x = vs[variant % len(vs)]
    # Place the head near a fixed screen height regardless of the environment's ground line, so the
    # close-up camera pan stays bounded for both the higher frost ridge and the lower orchard.
    if env == "frost_peak":
        world = _frost(
            title,
            art=art,
            actor_x=150,
            actor_scale=NEAR_SCALE,
            beacon=("buried", "structures", 330, 452, 0.5),
            **extra,
        )
        sy, support, screen_y, off_y, zoom = GROUND_Y, "ridge", 296, -54, (4.6, 4.8)
    else:
        world = _orchard(
            title, art=art, actor_x=150, actor_scale=NEAR_SCALE, props=ORCHARD_TREES, **extra
        )
        sy, support, screen_y, off_y, zoom = 535, "ground", 560, -20, (3.1, 3.3)
    beats = [
        beat("settle", "establish", 6, "ahead", "close", "idle", "neutral"),
        beat(
            "edge",
            "approach",
            34,
            "ahead",
            "close",
            "walk_to",
            mood_expr(mood),
            end_x=walk_end,
            end_speed=36,
        ),
        beat("plant", "approach", 20, "ahead", "close", "stop_at", mood_expr(mood), end_x=stop_end),
        beat("hold", "hold", 6, "mellow", "close", "idle", mood_expr(mood)),
        beat("register", "react", 24, "mellow", "close", "look_around", mood_expr(mood)),
    ]
    return storyboard(
        title,
        description,
        world,
        support,
        sxi,
        sy,
        [{"id": "ahead", "target": {"kind": "point", "position": [ahead_x, 430], "depth": 1.0}}],
        [
            view(
                "close",
                "close_up",
                "mellow",
                zoom,
                (scr_x, screen_y),
                offset=(0, off_y),
                hold=(4, 6),
                foreground="declared_overlap",
            )
        ],
        "approach_suspense",
        beats,
    )


def shot_investigate(env, *, title, description, mood):
    """Object close-up: approach the beacon, crouch, press the button (measured contact)."""
    if env != "frost_peak":
        raise ValueError("investigate/activate requires the Frost Peak beacon")
    art, extra = _mood(env, mood, "curious")
    world = _frost(
        title,
        art=art,
        actor_x=150,
        actor_scale=NEAR_SCALE,
        beacon=("buried", "terrain", BEACON_X, GROUND_Y, BEACON_SCALE),
        **extra,
    )
    beats = [beat("arrive", "establish", 6, "device", "reveal", "idle", "curious")]
    beats += walk_then_stop(STOP_X - 60, "reveal", "device", "curious")
    beats += [beat("press", "react", 30, "device", "reveal", "activate", "determined")]
    return storyboard(
        title,
        description,
        world,
        "ridge",
        STOP_X - 60,
        GROUND_Y,
        [{"id": "device", "target": {"kind": "node", "id": "beacon"}}],
        [
            view(
                "reveal",
                "close_up",
                "device",
                (2.7, 2.8),
                (222, 470),
                offset=(0, -14),
                hold=(4, 6),
                crop="offscreen",
            )
        ],
        "discovery_reaction",
        beats,
    )


def shot_threat(env, *, title, description, mood):
    """Low foreground beacon flare + storm; actor jolted back and stares."""
    if env != "frost_peak":
        raise ValueError("threat flare requires the Frost Peak beacon")
    art, extra = _mood(env, "storm", "surprised")
    world = _frost(
        title,
        art=art,
        actor_x=160,
        actor_scale=NEAR_SCALE,
        fg="storm",
        beacon=("active", "foreground", 118, 505, 1.05),
        props=(("rock_a", "frost_rocks_01", "cliff", 320, 448, 1.0),),
        **extra,
    )
    beats = [beat("flare", "establish", 6, "mellow", "low", "idle", "surprised")]
    beats += walk_then_stop(160, "low", "glow", "surprised")
    beats += [beat("jolt", "react", 30, "mellow", "low", "react", "surprised")]
    return storyboard(
        title,
        description,
        world,
        "ridge",
        160,
        GROUND_Y,
        [{"id": "glow", "target": {"kind": "point", "position": [140, 430], "depth": 1.0}}],
        [
            view(
                "low",
                "follow",
                "mellow",
                (1.55, 1.6),
                (214, 548),
                hold=(4, 6),
                foreground="declared_overlap",
            )
        ],
        "discovery_reaction",
        beats,
    )


def shot_travel(env, *, title, description, mood, run=False, variant=0):
    """A traversal bout across the environment, tracked by a following camera.

    ``run`` uses the threat_escape pattern (its ``escape`` stage admits run_to); a walk uses
    discovery_reaction. Either way the camera follows the moving actor. ``variant`` shifts the
    start position and the camera screen X so repeated journey beats cover different ground with
    different framing rather than being identical.
    """
    art, extra = _mood(env, mood, "determined")
    # (start_x, screen_x): distinct validated journey framings (walk bout only).
    vs = [(90, 170), (72, 150), (104, 190)]
    sxi, scr_x = vs[variant % len(vs)]
    actor_x0 = sxi + 20
    if env == "frost_peak":
        world = _frost(
            title,
            art=art,
            actor_x=actor_x0,
            actor_scale=NEAR_SCALE,
            beacon=None,
            props=FROST_PINES,
            **extra,
        )
        sy, support = GROUND_Y, "ridge"
    else:
        world = _orchard(
            title, art=art, actor_x=actor_x0, actor_scale=NEAR_SCALE, props=ORCHARD_TREES, **extra
        )
        sy, support = 535, "ground"
    subjects = [{"id": "path", "target": {"kind": "point", "position": [300, 430], "depth": 1.0}}]
    if run:
        # The run is a one-off escape set piece; keep its stable framing.
        rx = 90
        rworld = (_frost if env == "frost_peak" else _orchard)(
            title,
            art=art,
            actor_x=110,
            actor_scale=NEAR_SCALE,
            **(
                {"beacon": None, "props": FROST_PINES}
                if env == "frost_peak"
                else {"props": ORCHARD_TREES}
            ),
            **extra,
        )
        rv = view(
            "track",
            "follow",
            "mellow",
            (1.2, 1.3),
            (170, 400),
            hold=(4, 6),
            lead=0.1,
            foreground="declared_overlap",
        )
        beats = [
            beat("set", "establish", 8, "mellow", "track", "idle", "determined"),
            beat("brace", "react", 18, "mellow", "track", "react", "surprised"),
            beat(
                "bolt",
                "escape",
                64,
                "mellow",
                "track",
                "run_to",
                "determined",
                end_x=rx + 140,
                end_speed=60,
            ),
        ]
        return storyboard(
            title, description, rworld, support, rx, sy, subjects, [rv], "threat_escape", beats
        )
    tv = view(
        "track",
        "follow",
        "mellow",
        (1.2, 1.3),
        (scr_x, 400),
        hold=(4, 6),
        lead=0.1,
        foreground="declared_overlap",
    )
    beats = [beat("set", "establish", 8, "mellow", "track", "idle", "determined")]
    beats += walk_then_stop(sxi, "track", "path", "determined")
    beats += [beat("arrive", "react", 28, "mellow", "track", "look_around", "determined")]
    return storyboard(
        title, description, world, support, sxi, sy, subjects, [tv], "discovery_reaction", beats
    )


def shot_resolve(env, *, title, description, mood):
    """Medium hero / outcome: actor settles, answering light visible, relief."""
    art, extra = _mood(env, mood, "determined")
    if env == "frost_peak":
        world = _frost(
            title,
            art=art,
            actor_x=150,
            actor_scale=NEAR_SCALE,
            answer=(300, 285, 2.0),
            beacon=("active", "terrain", 132, GROUND_Y, BEACON_SCALE),
            props=(("pine_a", "pine_snow_01", "tall", 330, 436, 0.8),),
            **extra,
        )
        sx, sy, support = 150, GROUND_Y, "ridge"
    else:
        world = _orchard(
            title, art=art, actor_x=150, actor_scale=NEAR_SCALE, props=ORCHARD_TREES, **extra
        )
        sx, sy, support = 150, 535, "ground"
    beats = [
        beat("steady", "establish", 6, "answer", "hope", "idle", "concerned"),
        beat(
            "step",
            "approach",
            34,
            "answer",
            "hope",
            "walk_to",
            "determined",
            end_x=188,
            end_speed=36,
        ),
        beat("plant", "approach", 20, "answer", "hope", "stop_at", "determined", end_x=210),
        beat("hold", "hold", 6, "mellow", "hope", "idle", "determined"),
        beat("relief", "react", 24, "mellow", "hope", "look_around", "happy"),
    ]
    return storyboard(
        title,
        description,
        world,
        support,
        sx,
        sy,
        [{"id": "answer", "target": {"kind": "point", "position": [300, 300], "depth": 0.18}}],
        [
            view(
                "hope",
                "follow",
                "mellow",
                (1.65, 1.7),
                (168, 452),
                hold=(4, 6),
                foreground="declared_overlap",
            )
        ],
        "approach_suspense",
        beats,
    )


SHOT_PRESETS = {
    "establish": shot_establish,
    "reaction": shot_reaction,
    "investigate": shot_investigate,
    "threat": shot_threat,
    "travel": shot_travel,
    "travel_run": lambda env, **kw: shot_travel(env, run=True, **kw),
    "resolve": shot_resolve,
}

# Presets whose staging varies with the ``variant`` index (observation/journey beats that the
# planner may repeat). Set pieces (investigate/threat/resolve) occur once and ignore variant.
_VARIANT_PRESETS = {"establish", "reaction", "travel", "travel_run"}
# Distinct validated stagings available per variable preset (length of its ``vs`` table).
VARIANT_COUNT = {"establish": 3, "reaction": 3, "travel": 3, "travel_run": 1}


# ---------------------------------------------------------------- mood / art direction
_MOODS = {
    "calm": {"warmth": 0.1, "atmosphere": 0.7, "breeze": 0.35},
    "tense": {"warmth": 0.12, "atmosphere": 0.55, "breeze": 0.5},
    "storm": {"warmth": 0.9, "atmosphere": 0.6, "breeze": 1.0},
    "hopeful": {"warmth": 0.55, "atmosphere": 0.5, "breeze": 0.45},
    "warm": {"warmth": 0.8, "atmosphere": 0.62, "breeze": 0.35},
}
_MOOD_EXPR = {
    "calm": "curious",
    "tense": "concerned",
    "storm": "surprised",
    "hopeful": "determined",
    "warm": "happy",
}


def mood_expr(mood: str) -> str:
    return _MOOD_EXPR.get(mood, "neutral")


def _mood(env, mood, default_expr):
    base = dict(_MOODS.get(mood, _MOODS["calm"]))
    base["expression"] = _MOOD_EXPR.get(mood, default_expr)
    # The orchard is a warm dusk location; nudge its palette warmer regardless of story mood.
    if env == "orchard":
        base["warmth"] = max(base["warmth"], 0.7)
    return base, {}


def build_shot(
    preset: str, env: str, *, title: str, description: str, mood: str, variant: int = 0
) -> dict:
    """Build one storyboard-0.1 dict from a named preset and environment.

    ``variant`` selects a distinct validated staging for repeatable observation/journey presets so
    the same preset used more than once produces meaningfully different shots. Set-piece presets
    ignore it.
    """
    if preset not in SHOT_PRESETS:
        raise ValueError(f"Unknown shot preset {preset!r}; use {sorted(SHOT_PRESETS)}")
    if env not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment {env!r}; use {sorted(ENVIRONMENTS)}")
    kwargs = {"title": title, "description": description, "mood": mood}
    if preset in _VARIANT_PRESETS:
        kwargs["variant"] = variant
    return SHOT_PRESETS[preset](env, **kwargs)
