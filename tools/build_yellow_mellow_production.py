"""Author the Phase 9B 60-second Yellow Mellow production manifest (production-0.1, 20 segments).

Reuses the proven Phase 9A storyboard/scene/trajectory helpers (same registered orchard scene,
same calibrated walk/run magnitudes at actor scale 0.47) and composes twenty distinct 90-frame
segments into a four-act survival-adventure, "Yellow Mellow — The Last Signal".

Readability improvement over Phase 9A: camera views use higher zoom (medium ~1.45, closer ~1.62,
establishing ~1.2) through the existing validated storyboard zoom bound [0.9, 1.7], plus screen
positions that keep the character centred. No rig or scale change; no new assets.

Usage: python3 tools/build_yellow_mellow_production.py examples/productions/yellow_mellow_60s.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_yellow_mellow_episode import (  # noqa: E402
    GROUND_Y,
    beat,
    start,
    storyboard,
    subject,
    view,
)

# Zoom tiers (within the accepted [0.9, 1.7] storyboard bound) for readable framing.
# `establishing` behavior caps zoom at 1.15; push_in/follow allow the readable [0.9, 1.7] range.
ESTABLISH = (1.12, 1.15)
MEDIUM = (1.30, 1.40)
CLOSER = (1.40, 1.48)
FOLLOW = (1.30, 1.30)


# ----------------------------------------------------------------- reusable beat kits
def _discovery(start_x, walk_end, walk_speed, stop_end, zoom_a, exprs):
    """establish -> approach(walk) -> discover(stop) -> react -> hold on discovery_reaction."""
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("trail", "point", position=(210, 500), depth=1.0),
    ]
    views = [
        view(
            "medium_push", "push_in", "trail", zoom_a, (236, 500), offset_end=(40, 0), hold=(6, 12)
        ),
    ]
    return (
        subjects,
        views,
        [
            beat("establish", "establish", 9, "trail", "medium_push", "idle", exprs[0]),
            beat(
                "approach",
                "approach",
                36,
                "trail",
                "medium_push",
                "walk_to",
                exprs[1],
                end_x=walk_end,
                end_speed=walk_speed,
            ),
            beat(
                "discover",
                "discover",
                12,
                "trail",
                "medium_push",
                "stop_at",
                exprs[2],
                end_x=stop_end,
            ),
            beat("react", "react", 18, "trail", "medium_push", "look_around", exprs[3]),
            beat("hold", "hold", 15, "trail", "medium_push", "look_around", exprs[4]),
        ],
    )


def _approach(start_x, walk_end, walk_speed, stop_end, zoom, exprs):
    """establish -> approach(walk) -> approach(stop) -> hold -> react on approach_suspense."""
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("focus", "point", position=(240, 470), depth=1.0),
        subject("beyond", "point", position=(245, 430), depth=0.85),
    ]
    views = [
        view("susp_push", "push_in", "focus", zoom, (220, 470), hold=(6, 16)),
    ]
    return (
        subjects,
        views,
        [
            beat("ready", "establish", 6, "focus", "susp_push", "idle", exprs[0]),
            beat(
                "creep",
                "approach",
                36,
                "focus",
                "susp_push",
                "walk_to",
                exprs[1],
                end_x=walk_end,
                end_speed=walk_speed,
            ),
            beat(
                "arrive", "approach", 18, "focus", "susp_push", "stop_at", exprs[2], end_x=stop_end
            ),
            beat("pause", "hold", 12, "beyond", "susp_push", "idle", exprs[3]),
            beat("react", "react", 18, "beyond", "susp_push", "react", exprs[4]),
        ],
    )


def _escape(start_x, walk_end, walk_speed, stop_end, run_end, run_speed, exprs):
    """establish -> approach(walk) -> discover(stop) -> react -> escape(run) on threat_escape."""
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
                end_x=walk_end,
                end_speed=walk_speed,
            ),
            beat("decide", "discover", 12, "shadow", "wide", "stop_at", exprs[2], end_x=stop_end),
            beat("scan", "react", 15, "shadow", "wide", "react", exprs[3]),
            beat(
                "bolt",
                "escape",
                30,
                "clearing",
                "run_follow",
                "run_to",
                exprs[4],
                end_x=run_end,
                end_speed=run_speed,
            ),
        ],
    )


def _resolve(start_x, walk_end, walk_speed, stop_end, zoom, exprs):
    """establish -> approach(walk) -> approach(stop) -> hold -> react on approach_suspense."""
    subjects = [
        subject("mellow", "actor", id="mellow"),
        subject("home", "point", position=(210, 500), depth=1.0),
        subject("calm", "point", position=(215, 450), depth=0.85),
    ]
    views = [
        view("settle", "push_in", "home", zoom, (205, 495), hold=(6, 18)),
    ]
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
                end_x=walk_end,
                end_speed=walk_speed,
            ),
            beat("stand", "approach", 18, "home", "settle", "stop_at", exprs[2], end_x=stop_end),
            beat("breathe", "hold", 12, "calm", "settle", "idle", exprs[3]),
            beat("relief", "react", 18, "calm", "settle", "look_around", exprs[4]),
        ],
    )


def seg(sid, title, desc, pattern, start_block, kit, expr0):
    subjects, views, beats = kit
    return sid, storyboard(title, desc, start_block, subjects, views, pattern, beats, expr0, "idle")


# ----------------------------------------------------------------- twenty segments, four acts
def build() -> dict:
    S = []  # (segment_id, storyboard)

    # ---- Act 1 — The Discovery (segments 1-5, frames 0-449) ----
    S.append(
        seg(
            "a1_dusk_arrival",
            "Dusk arrival",
            "Mellow steps onto the abandoned pathway at dusk.",
            "discovery_reaction",
            start((140, GROUND_Y)),
            _discovery(
                140, 180, 35, 187, MEDIUM, ("neutral", "neutral", "curious", "curious", "curious")
            ),
            "neutral",
        )
    )
    S.append(
        seg(
            "a1_first_glint",
            "A first glint",
            "A faint signal glints far down the trail.",
            "discovery_reaction",
            start((140, GROUND_Y)),
            _discovery(
                140, 180, 35, 187, MEDIUM, ("curious", "curious", "curious", "surprised", "curious")
            ),
            "curious",
        )
    )
    S.append(
        seg(
            "a1_slow_down",
            "Slowing down",
            "He slows, unsure, and studies the horizon.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _approach(
                165,
                201,
                30,
                210,
                MEDIUM,
                ("curious", "curious", "concerned", "concerned", "curious"),
            ),
            "curious",
        )
    )
    S.append(
        seg(
            "a1_look_around",
            "Looking around",
            "A careful look around the quiet orchard.",
            "discovery_reaction",
            start((140, GROUND_Y)),
            _discovery(
                140,
                180,
                35,
                187,
                MEDIUM,
                ("concerned", "curious", "curious", "surprised", "curious"),
            ),
            "concerned",
        )
    )
    S.append(
        seg(
            "a1_growing_curiosity",
            "Growing curiosity",
            "Curiosity wins; he fixes on the signal.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _approach(
                165, 201, 30, 210, CLOSER, ("curious", "curious", "excited", "excited", "curious")
            ),
            "curious",
        )
    )

    # ---- Act 2 — The Investigation (segments 6-10, frames 450-899) ----
    S.append(
        seg(
            "a2_cautious_step",
            "A cautious step",
            "He edges toward the signal, wary.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _approach(
                165,
                201,
                30,
                210,
                MEDIUM,
                ("concerned", "curious", "concerned", "concerned", "surprised"),
            ),
            "concerned",
        )
    )
    S.append(
        seg(
            "a2_closer_look",
            "A closer look",
            "The framing tightens as he nears it.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _approach(
                165, 201, 30, 210, CLOSER, ("curious", "curious", "excited", "excited", "surprised")
            ),
            "curious",
        )
    )
    S.append(
        seg(
            "a2_reach_the_spot",
            "Reaching the spot",
            "He arrives right at the source.",
            "discovery_reaction",
            start((140, GROUND_Y)),
            _discovery(
                140, 180, 35, 187, MEDIUM, ("curious", "curious", "excited", "surprised", "excited")
            ),
            "curious",
        )
    )
    S.append(
        seg(
            "a2_the_unexpected",
            "The unexpected",
            "Something unexpected: he recoils in surprise.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _approach(
                165,
                201,
                30,
                210,
                CLOSER,
                ("excited", "excited", "surprised", "surprised", "surprised"),
            ),
            "excited",
        )
    )
    S.append(
        seg(
            "a2_taking_it_in",
            "Taking it in",
            "He takes it in, uneasy about what it means.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _approach(
                165,
                201,
                30,
                210,
                MEDIUM,
                ("surprised", "concerned", "concerned", "concerned", "surprised"),
            ),
            "surprised",
        )
    )

    # ---- Act 3 — The Escape (segments 11-15, frames 900-1349) ----
    S.append(
        seg(
            "a3_sense_danger",
            "Sensing danger",
            "A shadow moves; danger is sensed.",
            "threat_escape",
            start((140, GROUND_Y)),
            _escape(
                140,
                168.5,
                40,
                176.5,
                216.5,
                80,
                ("concerned", "concerned", "determined", "concerned", "determined"),
            ),
            "concerned",
        )
    )
    S.append(
        seg(
            "a3_the_decision",
            "The decision",
            "He steels himself and decides to run.",
            "threat_escape",
            start((140, GROUND_Y)),
            _escape(
                140,
                168.5,
                40,
                176.5,
                216.5,
                80,
                ("concerned", "concerned", "determined", "determined", "determined"),
            ),
            "concerned",
        )
    )
    S.append(
        seg(
            "a3_the_run",
            "The run",
            "A full run down the pathway.",
            "threat_escape",
            start((140, GROUND_Y)),
            _escape(
                140,
                168.5,
                40,
                176.5,
                216.5,
                80,
                ("determined", "determined", "determined", "concerned", "determined"),
            ),
            "determined",
        )
    )
    S.append(
        seg(
            "a3_pause_and_check",
            "Pause and check",
            "He pauses to check his surroundings.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _approach(
                165,
                201,
                30,
                210,
                MEDIUM,
                ("determined", "concerned", "concerned", "concerned", "determined"),
            ),
            "determined",
        )
    )
    S.append(
        seg(
            "a3_a_safe_way",
            "A safe way",
            "He spots a possible safe direction.",
            "discovery_reaction",
            start((140, GROUND_Y)),
            _discovery(
                140,
                180,
                35,
                187,
                MEDIUM,
                ("determined", "determined", "curious", "excited", "determined"),
            ),
            "determined",
        )
    )

    # ---- Act 4 — The Resolution (segments 16-20, frames 1350-1799) ----
    S.append(
        seg(
            "a4_reaching_safety",
            "Reaching safety",
            "He walks to a safe spot at last.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _resolve(
                165, 201, 30, 210, MEDIUM, ("determined", "determined", "happy", "happy", "happy")
            ),
            "determined",
        )
    )
    S.append(
        seg(
            "a4_catching_breath",
            "Catching breath",
            "He catches his breath, relieved.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _resolve(165, 201, 30, 210, MEDIUM, ("happy", "happy", "happy", "tired", "happy")),
            "happy",
        )
    )
    S.append(
        seg(
            "a4_the_meaning",
            "The meaning",
            "He investigates what the signal meant.",
            "discovery_reaction",
            start((140, GROUND_Y)),
            _discovery(
                140, 180, 35, 187, MEDIUM, ("happy", "curious", "curious", "excited", "happy")
            ),
            "happy",
        )
    )
    S.append(
        seg(
            "a4_a_small_smile",
            "A small smile",
            "Understanding dawns; a small smile.",
            "approach_suspense",
            start((165, GROUND_Y)),
            _resolve(165, 201, 30, 210, CLOSER, ("happy", "happy", "happy", "happy", "excited")),
            "happy",
        )
    )
    S.append(
        seg(
            "a4_closing_pose",
            "Closing pose",
            "An expressive, confident closing pose.",
            "discovery_reaction",
            start((140, GROUND_Y)),
            _discovery(
                140, 180, 35, 187, MEDIUM, ("happy", "excited", "excited", "happy", "determined")
            ),
            "happy",
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
        else Path(__file__).resolve().parents[1] / "examples/productions/yellow_mellow_60s.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=2) + "\n")
    print("wrote", out, f"({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
