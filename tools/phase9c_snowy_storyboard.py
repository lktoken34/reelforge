"""Phase 9C - "Yellow Mellow: The Last Light of Frost Peak" storyboard preview (corrected).

Stage-1 preview tooling. Authors five storyboard-0.1 segments over the registered Frost Peak
environment and renders one key frame of each 3-second (90-frame) shot through the REAL
production path: compile_storyboard -> direction_frame -> CairoRenderer, the same per-frame call
the audited episode renderer makes. Stills only; no video is rendered.

Shot 3 is measured, not assumed: the Yellow Mellow fingertip (blocking.sampling.fingertip_world)
is compared with the registered beacon activation socket (environments.snowy.BEACON_SOCKET).

Usage (WSL Ubuntu, Python 3.12 with pycairo):
    python3 tools/phase9c_snowy_storyboard.py --out outputs/phase9c_snowy
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cairo

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from reelforge.blocking.sampling import fingertip_world  # noqa: E402
from reelforge.characters.yellow_mellow_v2.episode import DEFAULT_DRAW_SCALE  # noqa: E402
from reelforge.characters.yellow_mellow_v2.motions import (  # noqa: E402
    ACTIVATE_HEIGHT,
    ACTIVATE_REACH,
)
from reelforge.direction.sampling import direction_frame, inspect_frame  # noqa: E402
from reelforge.environments.snowy import BEACON_SOCKET  # noqa: E402
from reelforge.rendering.backends.cairo import CairoRenderer  # noqa: E402
from reelforge.rendering.diagnostic import color  # noqa: E402
from reelforge.storyboards.compiler import compile_storyboard  # noqa: E402

WIDTH, HEIGHT = 720, 1280
LOGICAL = (360, 640)
BACKGROUND = color("0b1630")
GOLD = (1.0, 0.82, 0.4)
INK_BG = (0.04, 0.06, 0.12)
GROUND_Y = 470.0
OUT = {
    "width": 720,
    "height": 1280,
    "fps": 30,
    "frames": 90,
    "codec": "h264",
    "pixel_format": "yuv420p",
}

# Scale shared by every close-to-camera shot; the walk/stop distances below are calibrated for it.
ACTOR_SCALE = 0.75
CHAR_K = ACTOR_SCALE * DEFAULT_DRAW_SCALE  # world logical units per V2 canonical unit
# Shot 3 contact staging: the beacon is sized and placed so its registered activation socket
# sits exactly on the activate fingertip target (reach forward, height above ground).
STOP_X = 180.0
BEACON_SCALE = (ACTIVATE_HEIGHT * CHAR_K) / -BEACON_SOCKET[1]
BEACON_X = STOP_X + ACTIVATE_REACH * CHAR_K - BEACON_SOCKET[0] * BEACON_SCALE


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


def snowy_scene(
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
    """Frost Peak scene-0.1. ``beacon`` = (variant, layer, x, y, scale)."""
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
    variant, layer, bx, by, bs = beacon
    nodes.append(
        _node("beacon", "asset", layer, 9, _t(bx, by, bs), asset_id="beacon_01", variant=variant)
    )
    return {
        "schema_version": "scene-0.1",
        "title": title,
        "output": OUT,
        "camera": "locked",
        "art_direction": {k: art[k] for k in ("warmth", "atmosphere", "breeze")},
        "nodes": nodes,
    }


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


def storyboard(title, description, world, start_x, subjects, views, pattern, beats):
    return {
        "schema_version": "storyboard-0.1",
        "title": title,
        "description": description,
        "world": world,
        "rowan": {
            "actor_id": "mellow",
            "support_id": "ridge",
            "character": "yellow_mellow_v2",
            "start": {"position": [start_x, GROUND_Y], "facing": "right"},
        },
        "subjects": [{"id": "mellow", "target": {"kind": "actor", "id": "mellow"}}] + subjects,
        "views": views,
        "pattern": pattern,
        "beats": beats,
    }


# Calibrated scale-0.75 travel: walk 38 units (end 36 u/s) then stop 22 units = 1.25 gait cycles.
def travel(start_x, view_id, subject, expression):
    return [
        beat(
            "walk",
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


PINES = (
    ("pine_a", "pine_snow_01", "tall", 60, 430, 0.9),
    ("pine_b", "pine_snow_01", "short", 300, 436, 0.7),
    ("pine_c", "pine_snow_01", "cluster", 330, 432, 0.6),
    ("rock_a", "frost_rocks_01", "cliff", 40, 448, 0.9),
)


def shot1():
    art = {"warmth": 0.1, "atmosphere": 0.7, "breeze": 0.35, "expression": "curious"}
    world = snowy_scene(
        "Frost Peak - lonely ridge",
        art=art,
        actor_x=150,
        actor_scale=0.5,
        beacon=("buried", "structures", 250, 452, 0.62),
        props=PINES,
    )
    return storyboard(
        "The Lonely Mountain",
        "Mellow crosses a snowy ridge and notices a faint red light.",
        world,
        120,
        [{"id": "trail", "target": {"kind": "point", "position": [248, 452], "depth": 1.0}}],
        [view("wide", "establishing", "trail", (1.0, 1.1), (230, 452), hold=(6, 10), crop="full")],
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
                "curious",
                end_x=150,
                end_speed=30,
            ),
            beat("spot", "discover", 18, "trail", "wide", "stop_at", "curious", end_x=159),
            beat("look", "react", 18, "trail", "wide", "look_around", "curious"),
        ],
    )


def shot2():
    art = {"warmth": 0.12, "atmosphere": 0.55, "breeze": 0.5, "expression": "concerned"}
    world = snowy_scene(
        "Frost Peak - reaction",
        art=art,
        actor_x=150,
        actor_scale=ACTOR_SCALE,
        beacon=("buried", "structures", 330, 452, 0.5),
    )
    beats = [beat("settle", "establish", 6, "mellow", "close", "idle", "neutral")]
    beats += travel(150, "close", "ahead", "concerned")
    beats += [beat("register", "react", 30, "mellow", "close", "look_around", "concerned")]
    return storyboard(
        "Something in the Snow",
        "Close on Mellow: his eyes narrow with concern at the light.",
        world,
        150,
        [{"id": "ahead", "target": {"kind": "point", "position": [300, 430], "depth": 1.0}}],
        [
            view(
                "close",
                "close_up",
                "mellow",
                (4.6, 4.8),
                (176, 296),
                offset=(0, -54),
                hold=(4, 6),
                foreground="declared_overlap",
            )
        ],
        "discovery_reaction",
        beats,
    )


def shot3():
    art = {"warmth": 0.18, "atmosphere": 0.45, "breeze": 0.4, "expression": "curious"}
    # The beacon shares the actor's depth-1.0 terrain layer so fingertip/button contact holds on
    # screen under any camera (no parallax between hand and control).
    world = snowy_scene(
        "Frost Peak - the buried beacon",
        art=art,
        actor_x=150,
        actor_scale=ACTOR_SCALE,
        beacon=("buried", "terrain", BEACON_X, GROUND_Y, BEACON_SCALE),
    )
    beats = [beat("arrive", "establish", 6, "device", "reveal", "idle", "curious")]
    beats += travel(STOP_X - 60, "reveal", "device", "curious")
    beats += [beat("press", "react", 30, "device", "reveal", "activate", "determined")]
    return storyboard(
        "The Buried Beacon",
        "Mellow crouches at the half-buried beacon and presses its activation button.",
        world,
        STOP_X - 60,
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


def shot4():
    art = {"warmth": 0.9, "atmosphere": 0.6, "breeze": 1.0, "expression": "surprised"}
    # Low framing: the lit beacon looms in the foreground layer at lower left.
    world = snowy_scene(
        "Frost Peak - the mountain answers",
        art=art,
        actor_x=160,
        actor_scale=ACTOR_SCALE,
        fg="storm",
        beacon=("active", "foreground", 118, 505, 1.05),
        props=(("rock_a", "frost_rocks_01", "cliff", 320, 448, 1.0),),
    )
    beats = [beat("flare", "establish", 6, "mellow", "low", "idle", "surprised")]
    beats += travel(160, "low", "glow", "surprised")
    beats += [beat("jolt", "react", 30, "mellow", "low", "react", "surprised")]
    return storyboard(
        "The Mountain Answers",
        "The beacon blazes to life in a gust; Mellow is jolted back two steps and stares.",
        world,
        160,
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


def shot5():
    art = {"warmth": 0.55, "atmosphere": 0.5, "breeze": 0.45, "expression": "determined"}
    world = snowy_scene(
        "Frost Peak - a signal of hope",
        art=art,
        actor_x=150,
        actor_scale=ACTOR_SCALE,
        answer=(300, 285, 2.0),
        beacon=("active", "terrain", 132, GROUND_Y, BEACON_SCALE),
        props=(("pine_a", "pine_snow_01", "tall", 330, 436, 0.8),),
    )
    beats = [beat("steady", "establish", 6, "mellow", "hope", "idle", "concerned")]
    beats += travel(150, "hope", "answer", "determined")
    beats += [beat("relief", "react", 30, "mellow", "hope", "look_around", "happy")]
    return storyboard(
        "A Signal of Hope",
        "The beacon holds steady and a far light answers from the peaks; Mellow brightens.",
        world,
        150,
        [{"id": "answer", "target": {"kind": "point", "position": [300, 285], "depth": 0.18}}],
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
        "discovery_reaction",
        beats,
    )


# (number, title, size, builder, key frame, story beat, viewer reads)
SHOTS = [
    (
        1,
        "The Lonely Mountain",
        "wide establishing",
        shot1,
        45,
        "Alone on a snowy ridge under towering peaks, Mellow spots a faint red light ahead.",
        "Place and danger; a lone, fully visible figure who has noticed something.",
    ),
    (
        2,
        "Something in the Snow",
        "close-up reaction",
        shot2,
        80,
        "Tight on Mellow's face: his eyes narrow and his brow knits as he registers the light.",
        "The emotional beat, readable on a phone; restrained concern, not arms-out surprise.",
    ),
    (
        3,
        "The Buried Beacon",
        "object close-up / interaction",
        shot3,
        82,
        "At the half-buried beacon Mellow crouches, leans in and presses its red button.",
        "He found an emergency device and is deliberately activating it.",
    ),
    (
        4,
        "The Mountain Answers",
        "low foreground beacon",
        shot4,
        76,
        "The beacon blazes in the foreground as the wind rises; Mellow is jolted back and stares.",
        "Activation causes a dramatic change; surprise, not flight.",
    ),
    (
        5,
        "A Signal of Hope",
        "medium hero / outcome",
        shot5,
        80,
        "The beacon holds steady behind him and a far light answers from the peaks.",
        "His action worked: help has seen the signal; concern turns to relief.",
    ),
]


def render_still(renderer, sb_dict, frame, out_png):
    sb = compile_storyboard(sb_dict)
    cmds = direction_frame(sb.direction, frame)
    with renderer.surface(WIDTH, HEIGHT) as surface:
        renderer.draw(surface, cmds, background=BACKGROUND, logical_size=LOGICAL)
        surface.write_png(out_png)
    return len(cmds), sb, inspect_frame(sb.direction, frame)


def contact_report(sb, frames=range(60, 90)):
    """Fingertip vs beacon socket over the activate beat, in world and output pixels."""
    plan = sb.direction.blocking
    node = next(r for r in sb.direction.compiled.hierarchy if r.id == "beacon")
    sx, sy = node.world.point(*BEACON_SOCKET)
    rows = []
    for f in frames:
        fx, fy = fingertip_world(plan, f)
        zoom = inspect_frame(sb.direction, f)["camera"]["zoom"]
        d = math.hypot(fx - sx, fy - sy)
        rows.append(
            {
                "frame": f,
                "fingertip_world": [round(fx, 3), round(fy, 3)],
                "distance_world": round(d, 4),
                "distance_output_px": round(d * zoom * 2, 2),
            }
        )
    return {"socket_world": [round(sx, 3), round(sy, 3)], "frames": rows}


# ---------------------------------------------------------------- sheets
def _text(ctx, x, y, s, size=13, rgb=(0.85, 0.88, 0.95), bold=False):
    ctx.select_font_face(
        "Sans",
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
    )
    ctx.set_font_size(size)
    ctx.set_source_rgb(*rgb)
    ctx.move_to(x, y)
    ctx.show_text(s)


def _wrap(ctx, text, max_w, size):
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if ctx.text_extents(trial).width > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _paste(ctx, png, x, y, w, h):
    img = cairo.ImageSurface.create_from_png(str(png))
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(w / img.get_width(), h / img.get_height())
    ctx.set_source_surface(img, 0, 0)
    ctx.paint()
    ctx.restore()
    img.finish()
    ctx.set_source_rgb(0.3, 0.38, 0.55)
    ctx.set_line_width(1.5)
    ctx.rectangle(x + 0.5, y + 0.5, w - 1, h - 1)
    ctx.stroke()


def contact_sheet(stills, out_png, title, subtitle):
    tw, th, gap = 288, 512, 14
    W = 48 + 5 * tw + 4 * gap
    H = 110 + th + 60
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*INK_BG)
    ctx.paint()
    _text(ctx, 24, 46, title, 28, GOLD, True)
    _text(ctx, 24, 78, subtitle, 15)
    for i, s in enumerate(stills):
        x, y = 24 + i * (tw + gap), 110
        _paste(ctx, s["png"], x, y, tw, th)
        ctx.set_source_rgba(0, 0, 0, 0.55)
        ctx.rectangle(x, y, tw, 30)
        ctx.fill()
        _text(ctx, x + 8, y + 21, f"SHOT {s['num']} - {s['title'].upper()}", 13, GOLD, True)
        _text(
            ctx,
            x,
            y + th + 22,
            s["size"].upper(),
            12,
            (0.95, 0.82, 0.45),
            True,
        )
        _text(
            ctx,
            x,
            y + th + 40,
            f"{s['num'] * 3 - 3}-{s['num'] * 3}s  .  key frame {s['frame']}",
            11,
            (0.78, 0.82, 0.9),
        )
    surface.write_to_png(str(out_png))
    surface.finish()


def before_after(stills, before_dir, out_png):
    tw, th, gap = 216, 384, 12
    W = 48 + 5 * tw + 4 * gap
    H = 100 + 2 * (th + 40) + 20
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*INK_BG)
    ctx.paint()
    _text(ctx, 24, 44, "FROST PEAK - BEFORE / AFTER VISUAL CORRECTION", 24, GOLD, True)
    _text(
        ctx,
        24,
        72,
        "Top: previous review stills (midpoint frames).  Bottom: corrected stills "
        "(key frames).  Same engine path.",
        13,
    )
    for row, label in ((0, "BEFORE"), (1, "AFTER")):
        y = 100 + row * (th + 40)
        for i, s in enumerate(stills):
            x = 24 + i * (tw + gap)
            png = before_dir / s["png"].name if row == 0 else s["png"]
            _paste(ctx, png, x, y, tw, th)
            _text(
                ctx,
                x,
                y + th + 18,
                f"{label}  shot {s['num']}",
                12,
                (0.95, 0.82, 0.45) if row else (0.7, 0.75, 0.85),
                True,
            )
    surface.write_to_png(str(out_png))
    surface.finish()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="outputs/phase9c_snowy")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    renderer = CairoRenderer()
    stills, report = [], {"story": "Yellow Mellow - The Last Light of Frost Peak", "shots": []}
    for num, title, size, builder, frame, story, reads in SHOTS:
        png = out / f"snowy_shot_{num:02d}.png"
        n, sb, info = render_still(renderer, builder(), frame, png)
        stills.append(
            {
                "num": num,
                "title": title,
                "size": size,
                "png": png,
                "frame": frame,
                "story": story,
                "reads": reads,
            }
        )
        entry = {
            "shot": num,
            "title": title,
            "size": size,
            "file": png.name,
            "key_frame": frame,
            "draw_commands": n,
            "behavior": info["behavior"],
            "camera": info["camera"],
            "actor_bounds_logical": info["actor_bounds_logical"],
            "node_bounds_logical": info["node_bounds_logical"],
        }
        if num == 3:
            entry["contact"] = contact_report(sb)
        report["shots"].append(entry)
        print(
            f"shot {num}: {png.name} frame={frame} behavior={info['behavior']} "
            f"zoom={info['camera']['zoom']:.2f} commands={n}"
        )
    contact_sheet(
        stills,
        out / "snowy_mountain_contact_sheet.png",
        "YELLOW MELLOW - THE LAST LIGHT OF FROST PEAK",
        "Corrected storyboard preview  |  five 3-second shots  |  key-frame engine "
        "stills via the production pipeline (720x1280)",
    )
    before = out / "before"
    if before.is_dir():
        before_after(stills, before, out / "snowy_mountain_before_after.png")
    (out / "snowy_preview_report.json").write_text(json.dumps(report, indent=2))
    c = report["shots"][2]["contact"]["frames"]
    worst = max(r["distance_output_px"] for r in c if r["frame"] >= 78)
    print(
        f"shot 3 contact: socket={report['shots'][2]['contact']['socket_world']} "
        f"max fingertip gap (frames 78-89) = {worst} output px"
    )


if __name__ == "__main__":
    main()
