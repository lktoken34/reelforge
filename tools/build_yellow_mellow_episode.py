"""Author the Phase 9A Yellow Mellow silent episode manifest from the documented interface.

This emits a valid episode-0.2 JSON manifest: five 90-frame storyboard segments, each selecting
the registered ``yellow_mellow_v2`` character through the optional ``rowan.character`` field, an
embedded accepted ``scene-0.1`` world whose single character node is Yellow Mellow bound to the
orchard ground, distinct V2 expressions and camera views, and ``audio: null`` for a genuinely
silent video. No engine source is edited and no executable data is placed in the manifest.

Usage:  python3 tools/build_yellow_mellow_episode.py examples/episodes/yellow_mellow_orchard.json
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCENE = json.loads((REPO / "examples/scenes/tree_path.json").read_text())
GROUND_Y = 535  # Yellow Mellow node world Y; blocking start Y must equal this.


def _transform(x, y, scale=1.0, rot=0.0):
    return {"x": x, "y": y, "scale": scale, "rotation_degrees": rot}


def world(expression: str, action: str = "idle", direction: str = "right") -> dict:
    """Clone the accepted tree_path scene and swap the character node to Yellow Mellow.

    Only the character node changes; every environment/asset node and the ground binding are the
    accepted originals, so the embedded scene keeps validating under scene-0.1.
    """
    scene = copy.deepcopy(SCENE)
    scene["title"] = "Orchard trail at dusk"
    scene["camera"] = "gentle_drift"
    for node in scene["nodes"]:
        if node["id"] == "rowan":
            node["id"] = "mellow"
            node["asset_id"] = "yellow_mellow_v2"
            node["variant"] = "default"
            # Use actor world scale 0.47 (the value the accepted example worlds resolve to) so the
            # proven walk/run trajectory magnitudes settle in the calibrated stride phase. This is
            # inside the blocking 0.35..0.75 band.
            node["transform"] = _transform(243, GROUND_Y, 0.47)
            node["character"] = {
                "character": "yellow_mellow_v2",
                "action": action,
                "expression": expression,
            }
    return scene


def start(position, facing="right"):
    return {"position": list(position), "facing": facing}


def subject(alias, kind, **kw):
    if kind == "actor":
        return {"id": alias, "target": {"kind": "actor", "id": kw["id"]}}
    if kind == "node":
        return {"id": alias, "target": {"kind": "node", "id": kw["id"]}}
    return {
        "id": alias,
        "target": {"kind": "point", "position": list(kw["position"]), "depth": kw["depth"]},
    }


def view(
    alias,
    kind,
    subj,
    zoom,
    screen,
    *,
    offset_end=(0, 0),
    lead=0.0,
    hold=(0, 0),
    crop="full",
    cut="matched",
    foreground="clear",
):
    return {
        "id": alias,
        "kind": kind,
        "subject": subj,
        "zoom": list(zoom),
        "screen": list(screen),
        "offset_start": [0, 0],
        "offset_end": list(offset_end),
        "lead_seconds": lead,
        "hold": list(hold),
        "crop": crop,
        "foreground": foreground,
        "cut": cut,
    }


def beat(
    bid,
    btype,
    frames,
    subj,
    view_id,
    action_kind,
    expression,
    *,
    end_x=None,
    end_speed=None,
    description="",
):
    action = {"kind": action_kind, "expression": expression}
    if end_x is not None:
        action["end_x"] = end_x
    if end_speed is not None:
        action["end_speed"] = end_speed
    return {
        "id": bid,
        "type": btype,
        "frames": frames,
        "subject": subj,
        "view": view_id,
        "action": action,
        "description": description,
    }


def storyboard(title, description, start_block, subjects, views, pattern, beats, expr0, action0):
    return {
        "schema_version": "storyboard-0.1",
        "title": title,
        "description": description,
        "world": world(expr0, action0),
        "rowan": {
            "actor_id": "mellow",
            "support_id": "ground",
            "character": "yellow_mellow_v2",
            "start": start_block,
        },
        "subjects": subjects,
        "views": views,
        "pattern": pattern,
        "beats": beats,
    }


def segment_one():
    # Discovery + reaction. Mirrors silent_signal's proven trajectory magnitudes.
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("trail", "point", position=(210, 500), depth=1.0),
        subject("glimmer", "node", id="right_tree"),
    ]
    views = [
        view(
            "trail_push",
            "push_in",
            "trail",
            (1.08, 1.22),
            (250, 500),
            offset_end=(70, 0),
            hold=(6, 12),
        ),
    ]
    beats = [
        beat(
            "enter",
            "establish",
            9,
            "trail",
            "trail_push",
            "idle",
            "neutral",
            description="Mellow arrives on the orchard trail.",
        ),
        beat(
            "walk_in",
            "approach",
            36,
            "glimmer",
            "trail_push",
            "walk_to",
            "curious",
            end_x=180,
            end_speed=35,
            description="A curious walk up the trail.",
        ),
        beat(
            "spot",
            "discover",
            12,
            "glimmer",
            "trail_push",
            "stop_at",
            "curious",
            end_x=187,
            description="Something catches the eye by the right tree.",
        ),
        beat(
            "wonder",
            "react",
            18,
            "glimmer",
            "trail_push",
            "look_around",
            "curious",
            description="A visible curious look around.",
        ),
        beat(
            "hold_wonder",
            "hold",
            15,
            "glimmer",
            "trail_push",
            "look_around",
            "curious",
            description="Holds on the discovery.",
        ),
    ]
    return storyboard(
        "Something in the orchard",
        "Mellow walks the dusk trail and notices something by the far tree.",
        start((140, GROUND_Y)),
        subjects,
        views,
        "discovery_reaction",
        beats,
        "neutral",
        "idle",
    )


def segment_two():
    # Approach + suspense. Mirrors shelter_entrance magnitudes; ends on a surprised react.
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("glimmer", "point", position=(240, 470), depth=1.0),
        subject("beyond", "point", position=(245, 430), depth=0.85),
    ]
    views = [
        view("approach_push", "push_in", "glimmer", (1.05, 1.24), (250, 470), hold=(6, 16)),
    ]
    beats = [
        beat("ready", "establish", 6, "glimmer", "approach_push", "idle", "curious"),
        beat(
            "creep",
            "approach",
            36,
            "glimmer",
            "approach_push",
            "walk_to",
            "curious",
            end_x=201,
            end_speed=30,
            description="A careful approach.",
        ),
        beat(
            "arrive",
            "approach",
            18,
            "glimmer",
            "approach_push",
            "stop_at",
            "excited",
            end_x=210,
            description="Stops right at the spot.",
        ),
        beat(
            "pause",
            "hold",
            12,
            "beyond",
            "approach_push",
            "idle",
            "excited",
            description="A held, eager pause.",
        ),
        beat(
            "startle",
            "react",
            18,
            "beyond",
            "approach_push",
            "react",
            "surprised",
            description="Something startles Mellow.",
        ),
    ]
    return storyboard(
        "Closer to the glimmer",
        "Mellow creeps up to the spot and is startled by what is there.",
        start((165, GROUND_Y)),
        subjects,
        views,
        "approach_suspense",
        beats,
        "curious",
        "idle",
    )


def segment_three():
    # Threat + escape. Mirrors abandoned_settlement magnitudes; a run clears the area.
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("clearing", "point", position=(180, 500), depth=1.0),
        subject("shadow", "point", position=(265, 420), depth=0.85),
    ]
    views = [
        view("hold_wide", "establishing", "clearing", (1.06, 1.06), (180, 500)),
        view("run_follow", "follow", "mellow", (1.12, 1.12), (175, 560), lead=0.16),
    ]
    beats = [
        beat("brace", "establish", 6, "clearing", "hold_wide", "idle", "concerned"),
        beat(
            "edge_up",
            "approach",
            27,
            "clearing",
            "hold_wide",
            "walk_to",
            "concerned",
            end_x=168.5,
            end_speed=40,
            description="A wary step forward.",
        ),
        beat(
            "decide",
            "discover",
            12,
            "shadow",
            "hold_wide",
            "stop_at",
            "determined",
            end_x=176.5,
            description="Mellow steels up.",
        ),
        beat(
            "scan",
            "react",
            15,
            "shadow",
            "hold_wide",
            "react",
            "concerned",
            description="A worried reaction to a shadow.",
        ),
        beat(
            "bolt",
            "escape",
            30,
            "clearing",
            "run_follow",
            "run_to",
            "determined",
            end_x=216.5,
            end_speed=80,
            description="A decisive run down the trail.",
        ),
    ]
    return storyboard(
        "Down the trail",
        "A worried look, then Mellow runs to clear the area.",
        start((140, GROUND_Y)),
        subjects,
        views,
        "threat_escape",
        beats,
        "concerned",
        "idle",
    )


def segment_four():
    # Approach + suspense (resolution). Relieved, then happy.
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("home", "point", position=(210, 500), depth=1.0),
        subject("calm", "point", position=(215, 450), depth=0.85),
    ]
    views = [
        view("settle_push", "push_in", "home", (1.0, 1.2), (210, 500), hold=(6, 18)),
    ]
    beats = [
        beat("slow", "establish", 6, "home", "settle_push", "idle", "determined"),
        beat(
            "ease_in",
            "approach",
            36,
            "home",
            "settle_push",
            "walk_to",
            "happy",
            end_x=201,
            end_speed=30,
            description="A relieved walk to a safe spot.",
        ),
        beat(
            "stand",
            "approach",
            18,
            "home",
            "settle_push",
            "stop_at",
            "happy",
            end_x=210,
            description="Settles, safe again.",
        ),
        beat(
            "breathe",
            "hold",
            12,
            "calm",
            "settle_push",
            "idle",
            "happy",
            description="A calm, happy pause.",
        ),
        beat(
            "relief",
            "react",
            18,
            "calm",
            "settle_push",
            "look_around",
            "happy",
            description="Looks around, relieved.",
        ),
    ]
    return storyboard(
        "Catching breath",
        "Mellow eases to a safe spot and relaxes.",
        start((165, GROUND_Y)),
        subjects,
        views,
        "approach_suspense",
        beats,
        "determined",
        "idle",
    )


def segment_five():
    # Discovery + reaction (upbeat close). Happy realization, confident end.
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("path", "point", position=(210, 500), depth=1.0),
        subject("prize", "node", id="right_tree"),
    ]
    views = [
        view(
            "close_push",
            "push_in",
            "path",
            (1.05, 1.2),
            (250, 500),
            offset_end=(55, 0),
            hold=(6, 14),
        ),
    ]
    beats = [
        beat("glance", "establish", 9, "path", "close_push", "idle", "happy"),
        beat(
            "step_up",
            "approach",
            36,
            "prize",
            "close_push",
            "walk_to",
            "excited",
            end_x=180,
            end_speed=35,
            description="An eager step toward the tree.",
        ),
        beat(
            "realize",
            "discover",
            12,
            "prize",
            "close_push",
            "stop_at",
            "excited",
            end_x=187,
            description="A happy realization.",
        ),
        beat(
            "cheer",
            "react",
            18,
            "prize",
            "close_push",
            "look_around",
            "happy",
            description="A bright look around.",
        ),
        beat(
            "end_pose",
            "hold",
            15,
            "prize",
            "close_push",
            "look_around",
            "determined",
            description="Ends on a confident, settled note.",
        ),
    ]
    return storyboard(
        "A good find",
        "Mellow returns, realizes all is well, and ends on a confident note.",
        start((140, GROUND_Y)),
        subjects,
        views,
        "discovery_reaction",
        beats,
        "happy",
        "idle",
    )


def build() -> dict:
    segments = [
        ("something_in_the_orchard", segment_one()),
        ("closer_to_the_glimmer", segment_two()),
        ("back_down_the_trail", segment_three()),
        ("catching_breath", segment_four()),
        ("a_good_find", segment_five()),
    ]
    return {
        "schema_version": "episode-0.2",
        "title": "Yellow Mellow: The Orchard Trail",
        "segments": [{"id": sid, "storyboard": sb} for sid, sb in segments],
        "audio": None,
    }


def main():
    out = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else REPO / "examples/episodes/yellow_mellow_orchard.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=2) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
