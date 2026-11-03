"""Phase 9B.1: author the 60-second production with VISUALLY DISTINCT scenes per act.

Same validated production-0.1 engine, same 20 segments / 1800 frames, same Yellow Mellow V2 rig.
The only change is artistic: each act (and most segments) composes the registered orchard
catalog differently so the four acts read as different places/moods instead of one repeated
3-second composition.

Levers used (all within the accepted scene-0.1 catalog; the character still binds to the single
supporting ground orchard_ground_01):
- scene camera mode (locked / gentle_drift / approach)
- art_direction warmth/atmosphere/breeze (lighting + haze + motion -> time-of-day / mood)
- hills on/off, barn landmark present/absent and placed, foreground framing trees
  (both / left / right / none, varied scale) -> depth and skyline
- tree count / variant (broad|lean|compact|windswept) / position / scale -> landmarks
- fence position/scale, ground placement/scale -> spatial layout
- shot scale (establishing / medium / closer), screen position, subject, camera offsets

No new assets, no rig/scale change, no engine edits.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_yellow_mellow_episode import beat, start, storyboard, subject, view  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
GROUND_Y = 535

ESTABLISH = (1.12, 1.15)  # `establishing` behaviour caps at 1.15
MEDIUM = (1.30, 1.40)
CLOSER = (1.40, 1.48)
FOLLOW = (1.30, 1.30)


# ----------------------------------------------------------------- scene construction
def _xf(x, y, scale=1.0, rot=0.0):
    return {"x": x, "y": y, "scale": scale, "rotation_degrees": rot}


def _node(
    nid,
    kind,
    parent,
    order,
    transform,
    *,
    visible=True,
    depth=None,
    asset_id=None,
    variant=None,
    character=None,
    ground_id=None,
):
    n = {
        "id": nid,
        "kind": kind,
        "parent": parent,
        "order": order,
        "visible": visible,
        "transform": transform,
    }
    if depth is not None:
        n["depth"] = depth
    if asset_id is not None:
        n["asset_id"] = asset_id
        n["variant"] = variant
    if character is not None:
        n["character"] = character
        n["ground_id"] = ground_id
    return n


def _tree(nid, parent, order, x, y, scale, variant, rot=0.0):
    return _node(
        nid,
        "asset",
        parent,
        order,
        _xf(x, y, scale, rot),
        asset_id="orchard_tree_01",
        variant=variant,
    )


def scene(
    *,
    title,
    camera,
    warmth,
    atmosphere,
    breeze,
    expression,
    action="idle",
    hills=True,
    ground_xf=(155, 515, 1.15),
    structures=(),
    foreground=(),
    barn=None,
    fence=None,
):
    """Build one validated scene-0.1 world binding Yellow Mellow to the orchard ground."""
    nodes = [
        _node("root", "root", None, 0, _xf(0, 0)),
        _node("sky_layer", "layer", "root", 0, _xf(0, 0), depth=0),
        _node(
            "sky",
            "background",
            "sky_layer",
            0,
            _xf(0, 0),
            asset_id="dusk_sky_01",
            variant="default",
        ),
        _node("distance", "layer", "root", 1, _xf(0, 0), depth=0.18),
    ]
    if hills:
        nodes.append(
            _node(
                "hills",
                "background",
                "distance",
                0,
                _xf(180, 360, 1.0),
                asset_id="distant_hills_01",
                variant="default",
            )
        )
    gx, gy, gs = ground_xf
    nodes += [
        _node("terrain", "layer", "root", 2, _xf(0, 0), depth=1),
        _node(
            "ground",
            "environment",
            "terrain",
            0,
            _xf(gx, gy, gs),
            asset_id="orchard_ground_01",
            variant="default",
        ),
        _node("structures", "layer", "root", 3, _xf(0, 0), depth=0.85),
        _node("people", "layer", "root", 5, _xf(0, 0), depth=1),
        _node(
            "mellow",
            "character",
            "people",
            0,
            _xf(243, GROUND_Y, 0.47),
            asset_id="yellow_mellow_v2",
            variant="default",
            character={"character": "yellow_mellow_v2", "action": action, "expression": expression},
            ground_id="ground",
        ),
        _node("foreground", "layer", "root", 6, _xf(0, 0), depth=1.4),
    ]
    order = 0
    if barn is not None:
        bx, by, bs = barn
        nodes.append(
            _node(
                "barn",
                "asset",
                "structures",
                order,
                _xf(bx, by, bs),
                asset_id="barn_01",
                variant="default",
            )
        )
        order += 1
    for i, (x, y, s, variant, rot) in enumerate(structures):
        nodes.append(_tree(f"tree_{i}", "structures", order + i, x, y, s, variant, rot))
    order += len(structures)
    if fence is not None:
        fx, fy, fs = fence
        nodes.append(
            _node(
                "fence",
                "asset",
                "structures",
                order,
                _xf(fx, fy, fs),
                asset_id="fence_01",
                variant="default",
            )
        )
    for i, (x, y, s, variant) in enumerate(foreground):
        nodes.append(_tree(f"fg_{i}", "foreground", i, x, y, s, variant))
    return {
        "schema_version": "scene-0.1",
        "title": title,
        "output": {
            "width": 720,
            "height": 1280,
            "fps": 30,
            "frames": 90,
            "codec": "h264",
            "pixel_format": "yuv420p",
        },
        "camera": camera,
        "art_direction": {"warmth": warmth, "atmosphere": atmosphere, "breeze": breeze},
        "nodes": nodes,
    }


# ----------------------------------------------------------------- per-act scene palettes
# Act 1 — Discovery: open dusk orchard, warm low sun, wide airy space, trees framing left.
def scene_act1(expression, variant_set, camera="gentle_drift"):
    return scene(
        title="Act 1 - open orchard at dusk",
        camera=camera,
        warmth=0.80,
        atmosphere=0.62,
        breeze=0.35,
        expression=expression,
        hills=True,
        ground_xf=(155, 515, 1.15),
        structures=[(40, 425, 0.95, variant_set[0], 0.0), (96, 398, 0.6, variant_set[1], -3.0)],
        foreground=[(-6, 624, 1.8, "broad")],
        fence=(119, 439, 0.6),
    )


# Act 2 — Investigation: barn landmark close on the right, denser trees, cooler/hazier,
# tighter space, foreground on both sides for intimacy. Camera approach.
def scene_act2(expression, variant_set, camera="approach"):
    return scene(
        title="Act 2 - by the old barn",
        camera=camera,
        warmth=0.52,
        atmosphere=0.80,
        breeze=0.25,
        expression=expression,
        hills=False,
        ground_xf=(170, 520, 1.22),
        barn=(300, 300, 0.95),
        structures=[(70, 410, 1.05, variant_set[0], 0.0), (120, 452, 0.7, variant_set[1], 4.0)],
        foreground=[(-10, 628, 1.9, "lean"), (392, 616, 1.7, "windswept")],
        fence=(150, 452, 0.8),
    )


# Act 3 — Escape: bare, high-energy, almost no foreground, hills back for openness, strong
# breeze, cool twilight, trees pushed to far edges, no fence -> a clearing to run across.
def scene_act3(expression, variant_set, camera="gentle_drift"):
    return scene(
        title="Act 3 - the clearing",
        camera=camera,
        warmth=0.40,
        atmosphere=0.55,
        breeze=0.9,
        expression=expression,
        hills=True,
        ground_xf=(150, 512, 1.08),
        structures=[(18, 430, 0.8, variant_set[0], -6.0), (338, 452, 0.85, variant_set[1], 5.0)],
        foreground=[],
        fence=None,
    )


# Act 4 — Resolution: a sheltered corner, barn on the left as "home", warm again but calmer,
# soft haze, framing trees on the right, fence close -> a settled, enclosed destination.
def scene_act4(expression, variant_set, camera="gentle_drift"):
    return scene(
        title="Act 4 - the sheltered corner",
        camera=camera,
        warmth=0.72,
        atmosphere=0.68,
        breeze=0.2,
        expression=expression,
        hills=False,
        ground_xf=(165, 522, 1.18),
        barn=(70, 316, 0.9),
        structures=[(300, 420, 1.0, variant_set[0], 0.0), (250, 392, 0.62, variant_set[1], 3.0)],
        foreground=[(392, 612, 1.75, "broad")],
        fence=(210, 452, 0.7),
    )


# ----------------------------------------------------------------- beat kits (unchanged motion)
def _discovery(zoom_a, exprs):
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("trail", "point", position=(210, 500), depth=1.0),
    ]
    views = [view("push", "push_in", "trail", zoom_a, (236, 500), offset_end=(40, 0), hold=(6, 12))]
    return (
        subjects,
        views,
        [
            beat("establish", "establish", 9, "trail", "push", "idle", exprs[0]),
            beat(
                "approach",
                "approach",
                36,
                "trail",
                "push",
                "walk_to",
                exprs[1],
                end_x=180,
                end_speed=35,
            ),
            beat("discover", "discover", 12, "trail", "push", "stop_at", exprs[2], end_x=187),
            beat("react", "react", 18, "trail", "push", "look_around", exprs[3]),
            beat("hold", "hold", 15, "trail", "push", "look_around", exprs[4]),
        ],
    )


def _approach(zoom, exprs, start_x=165):
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("focus", "point", position=(240, 470), depth=1.0),
        subject("beyond", "point", position=(245, 430), depth=0.85),
    ]
    views = [view("susp", "push_in", "focus", zoom, (220, 470), hold=(6, 16))]
    return (
        subjects,
        views,
        [
            beat("ready", "establish", 6, "focus", "susp", "idle", exprs[0]),
            beat(
                "creep",
                "approach",
                36,
                "focus",
                "susp",
                "walk_to",
                exprs[1],
                end_x=201,
                end_speed=30,
            ),
            beat("arrive", "approach", 18, "focus", "susp", "stop_at", exprs[2], end_x=210),
            beat("pause", "hold", 12, "beyond", "susp", "idle", exprs[3]),
            beat("react", "react", 18, "beyond", "susp", "react", exprs[4]),
        ],
    )


def _escape(exprs):
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("clearing", "point", position=(180, 500), depth=1.0),
        subject("shadow", "point", position=(265, 420), depth=0.85),
    ]
    views = [
        view("wide", "establishing", "clearing", ESTABLISH, (180, 500)),
        view(
            "run_follow",
            "follow",
            "mellow",
            FOLLOW,
            (175, 540),
            lead=0.16,
            cut="intentional_reframe",
        ),
    ]
    return (
        subjects,
        views,
        [
            beat("brace", "establish", 6, "clearing", "wide", "idle", exprs[0]),
            beat(
                "edge_up",
                "approach",
                27,
                "clearing",
                "wide",
                "walk_to",
                exprs[1],
                end_x=168.5,
                end_speed=40,
            ),
            beat("decide", "discover", 12, "shadow", "wide", "stop_at", exprs[2], end_x=176.5),
            beat("scan", "react", 15, "shadow", "wide", "react", exprs[3]),
            beat(
                "bolt",
                "escape",
                30,
                "clearing",
                "run_follow",
                "run_to",
                exprs[4],
                end_x=216.5,
                end_speed=80,
            ),
        ],
    )


def _resolve(zoom, exprs):
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("home", "point", position=(210, 500), depth=1.0),
        subject("calm", "point", position=(215, 450), depth=0.85),
    ]
    views = [view("settle", "push_in", "home", zoom, (205, 495), hold=(6, 18))]
    return (
        subjects,
        views,
        [
            beat("slow", "establish", 6, "home", "settle", "idle", exprs[0]),
            beat(
                "ease_in",
                "approach",
                36,
                "home",
                "settle",
                "walk_to",
                exprs[1],
                end_x=201,
                end_speed=30,
            ),
            beat("stand", "approach", 18, "home", "settle", "stop_at", exprs[2], end_x=210),
            beat("breathe", "hold", 12, "calm", "settle", "idle", exprs[3]),
            beat("relief", "react", 18, "calm", "settle", "look_around", exprs[4]),
        ],
    )


def _story(title, desc, pattern, start_block, scene_world, kit, expr0):
    subjects, views, beats = kit
    sb = storyboard(title, desc, start_block, subjects, views, pattern, beats, expr0, "idle")
    sb["world"] = scene_world
    sb["rowan"]["character"] = "yellow_mellow_v2"
    return sb


# ----------------------------------------------------------------- 20 segments
def build() -> dict:
    S = []
    V = ("broad", "lean", "compact", "windswept")

    # Act 1 — Discovery (open orchard). Vary camera, tree set, zoom, start side per segment.
    S.append(
        (
            "a1_arrival",
            _story(
                "Dusk arrival",
                "Mellow steps onto the open orchard path at dusk.",
                "discovery_reaction",
                start((140, GROUND_Y)),
                scene_act1("neutral", (V[0], V[2]), camera="gentle_drift"),
                _discovery(MEDIUM, ("neutral", "neutral", "curious", "curious", "curious")),
                "neutral",
            ),
        )
    )
    S.append(
        (
            "a1_first_glint",
            _story(
                "A first glint",
                "A faint signal glints far down the trail.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act1("curious", (V[1], V[3]), camera="approach"),
                _approach(MEDIUM, ("curious", "curious", "surprised", "curious", "surprised")),
                "curious",
            ),
        )
    )
    S.append(
        (
            "a1_slowing",
            _story(
                "Slowing down",
                "He slows, studying the horizon.",
                "discovery_reaction",
                start((140, GROUND_Y)),
                scene_act1("curious", (V[3], V[0]), camera="locked"),
                _discovery(ESTABLISH, ("curious", "curious", "concerned", "curious", "curious")),
                "curious",
            ),
        )
    )
    S.append(
        (
            "a1_looking",
            _story(
                "Looking around",
                "A careful look across the quiet orchard.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act1("concerned", (V[2], V[1]), camera="gentle_drift"),
                _approach(CLOSER, ("concerned", "curious", "curious", "surprised", "curious")),
                "concerned",
            ),
        )
    )
    S.append(
        (
            "a1_curiosity",
            _story(
                "Growing curiosity",
                "Curiosity wins; he fixes on the signal.",
                "discovery_reaction",
                start((140, GROUND_Y)),
                scene_act1("curious", (V[0], V[3]), camera="approach"),
                _discovery(CLOSER, ("curious", "curious", "excited", "excited", "curious")),
                "curious",
            ),
        )
    )

    # Act 2 — Investigation (by the barn). Barn landmark, cooler/hazier, tighter, intimate.
    S.append(
        (
            "a2_cautious",
            _story(
                "A cautious step",
                "He edges toward the barn and the signal.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act2("concerned", (V[0], V[2]), camera="approach"),
                _approach(MEDIUM, ("concerned", "curious", "concerned", "concerned", "surprised")),
                "concerned",
            ),
        )
    )
    S.append(
        (
            "a2_closer",
            _story(
                "A closer look",
                "The framing tightens beside the barn.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act2("curious", (V[1], V[3]), camera="approach"),
                _approach(CLOSER, ("curious", "curious", "excited", "excited", "surprised")),
                "curious",
            ),
        )
    )
    S.append(
        (
            "a2_reach",
            _story(
                "Reaching the spot",
                "He arrives right at the source.",
                "discovery_reaction",
                start((140, GROUND_Y)),
                scene_act2("curious", (V[2], V[0]), camera="gentle_drift"),
                _discovery(MEDIUM, ("curious", "curious", "excited", "surprised", "excited")),
                "curious",
            ),
        )
    )
    S.append(
        (
            "a2_unexpected",
            _story(
                "The unexpected",
                "Something unexpected: he recoils.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act2("excited", (V[3], V[1]), camera="approach"),
                _approach(CLOSER, ("excited", "excited", "surprised", "surprised", "surprised")),
                "excited",
            ),
        )
    )
    S.append(
        (
            "a2_taking_in",
            _story(
                "Taking it in",
                "He takes it in, uneasy.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act2("surprised", (V[0], V[2]), camera="gentle_drift"),
                _approach(
                    MEDIUM, ("surprised", "concerned", "concerned", "concerned", "surprised")
                ),
                "surprised",
            ),
        )
    )

    # Act 3 — Escape (the clearing). Bare, windy, cool twilight, trees at edges, run.
    S.append(
        (
            "a3_danger",
            _story(
                "Sensing danger",
                "A shadow moves across the clearing.",
                "threat_escape",
                start((140, GROUND_Y)),
                scene_act3("concerned", (V[1], V[3]), camera="gentle_drift"),
                _escape(("concerned", "concerned", "determined", "concerned", "determined")),
                "concerned",
            ),
        )
    )
    S.append(
        (
            "a3_decision",
            _story(
                "The decision",
                "He steels himself to run.",
                "threat_escape",
                start((140, GROUND_Y)),
                scene_act3("concerned", (V[0], V[2]), camera="locked"),
                _escape(("concerned", "concerned", "determined", "determined", "determined")),
                "concerned",
            ),
        )
    )
    S.append(
        (
            "a3_the_run",
            _story(
                "The run",
                "A full run across the clearing.",
                "threat_escape",
                start((140, GROUND_Y)),
                scene_act3("determined", (V[3], V[1]), camera="gentle_drift"),
                _escape(("determined", "determined", "determined", "concerned", "determined")),
                "determined",
            ),
        )
    )
    S.append(
        (
            "a3_check",
            _story(
                "Pause and check",
                "He pauses to check the open ground.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act3("determined", (V[2], V[0]), camera="gentle_drift"),
                _approach(
                    MEDIUM, ("determined", "concerned", "concerned", "concerned", "determined")
                ),
                "determined",
            ),
        )
    )
    S.append(
        (
            "a3_safe_way",
            _story(
                "A safe way",
                "He spots a sheltered direction.",
                "discovery_reaction",
                start((140, GROUND_Y)),
                scene_act3("determined", (V[0], V[3]), camera="approach"),
                _discovery(
                    MEDIUM, ("determined", "determined", "curious", "excited", "determined")
                ),
                "determined",
            ),
        )
    )

    # Act 4 — Resolution (sheltered corner). Barn as home on the left, calm warm, enclosed.
    S.append(
        (
            "a4_safety",
            _story(
                "Reaching safety",
                "He reaches the sheltered corner.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act4("determined", (V[0], V[2]), camera="gentle_drift"),
                _resolve(MEDIUM, ("determined", "determined", "happy", "happy", "happy")),
                "determined",
            ),
        )
    )
    S.append(
        (
            "a4_breath",
            _story(
                "Catching breath",
                "He catches his breath by the barn.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act4("happy", (V[1], V[3]), camera="locked"),
                _resolve(MEDIUM, ("happy", "happy", "happy", "tired", "happy")),
                "happy",
            ),
        )
    )
    S.append(
        (
            "a4_meaning",
            _story(
                "The meaning",
                "He works out what the signal meant.",
                "discovery_reaction",
                start((140, GROUND_Y)),
                scene_act4("happy", (V[2], V[0]), camera="approach"),
                _discovery(MEDIUM, ("happy", "curious", "curious", "excited", "happy")),
                "happy",
            ),
        )
    )
    S.append(
        (
            "a4_smile",
            _story(
                "A small smile",
                "Understanding dawns; a small smile.",
                "approach_suspense",
                start((165, GROUND_Y)),
                scene_act4("happy", (V[3], V[1]), camera="gentle_drift"),
                _resolve(CLOSER, ("happy", "happy", "happy", "happy", "excited")),
                "happy",
            ),
        )
    )
    S.append(
        (
            "a4_closing",
            _story(
                "Closing pose",
                "An expressive, confident closing pose.",
                "discovery_reaction",
                start((140, GROUND_Y)),
                scene_act4("happy", (V[0], V[3]), camera="gentle_drift"),
                _discovery(CLOSER, ("happy", "excited", "excited", "happy", "determined")),
                "happy",
            ),
        )
    )

    assert len(S) == 20, len(S)
    return {
        "schema_version": "production-0.1",
        "title": "Yellow Mellow - The Last Signal",
        "segments": [{"id": sid, "storyboard": sb} for sid, sb in S],
        "audio": None,
    }


def main():
    out = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else REPO / "examples/productions/yellow_mellow_60s.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=2) + "\n")
    print("wrote", out, f"({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
