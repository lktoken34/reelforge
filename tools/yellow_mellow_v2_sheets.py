"""Character, motion and contact sheets for Yellow Mellow V2 (engineering review tooling).

Character and motion sheets are rendered from the public rig/motion API with the ReelForge
Cairo backend. The contact sheet is assembled only from frames decoded out of the finished
MP4, so it shows the delivered video, not a re-render.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import cairo

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from reelforge.characters.yellow_mellow_v2 import (  # noqa: E402
    EXPRESSIONS,
    Stage,
    draw_frame,
    evaluate,
)
from reelforge.characters.yellow_mellow_v2.character import CharacterFrame  # noqa: E402
from reelforge.characters.yellow_mellow_v2.rig import (  # noqa: E402
    HEAD_HEIGHT,
    STANDING_HEIGHT,
    standing_pose,
)
from reelforge.rendering.backends.cairo import CairoRenderer  # noqa: E402
from reelforge.rendering.diagnostic import color  # noqa: E402

GOLD = (1.0, 0.78, 0.23)
INK_BG = (0.07, 0.085, 0.13)
PANEL_BG = color("141a2b")


def _text(ctx, x, y, text, size=13, rgb=(0.85, 0.88, 0.95), bold=False):
    ctx.select_font_face(
        "Sans",
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
    )
    ctx.set_font_size(size)
    ctx.set_source_rgb(*rgb)
    ctx.move_to(x, y)
    ctx.show_text(text)


def _panel(ctx, renderer, commands, x, y, w, h, *, ground=None):
    """Render commands into a w x h panel (logical == pixel) and composite it."""
    with renderer.surface(w, h) as surf:
        renderer.draw(surf, tuple(commands), background=PANEL_BG, logical_size=(w, h))
        native = surf._open()
        native.flush()
        ctx.save()
        ctx.set_source_surface(native, x, y)
        ctx.paint()
        ctx.restore()
    ctx.set_source_rgb(0.22, 0.28, 0.42)
    ctx.set_line_width(1.0)
    ctx.rectangle(x + 0.5, y + 0.5, w - 1, h - 1)
    ctx.stroke()
    if ground is not None:
        ctx.set_source_rgba(0.45, 0.55, 0.75, 0.45)
        ctx.move_to(x + 10, y + ground + 0.5)
        ctx.line_to(x + w - 10, y + ground + 0.5)
        ctx.stroke()


def _frame_for(pose, face_name="neutral", face=None):
    state = evaluate(pose)
    f = face or EXPRESSIONS[face_name]
    return CharacterFrame(0, "sheet", state, f, 0.0)


def build_character_sheet(out_png: Path) -> None:
    W, H = 1500, 1080
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*INK_BG)
    ctx.paint()
    renderer = CairoRenderer()
    _text(ctx, 30, 46, "YELLOW MELLOW V2 - CHARACTER SHEET", 26, GOLD, True)
    _text(
        ctx,
        30,
        72,
        f"Code-authored vector rig | standing height {STANDING_HEIGHT:.1f} u = "
        f"{STANDING_HEIGHT / HEAD_HEIGHT:.2f} black-head heights | "
        "3 supported views, 8 expressions",
        13,
    )
    views = (
        ("FRONT (facing 0.05)", 0.05, "neutral"),
        ("THREE-QUARTER RIGHT (0.92)", 0.92, "happy"),
        ("THREE-QUARTER LEFT (-0.92)", -0.92, "neutral"),
        ("FRONT, RELAXED SMILE (0.25)", 0.25, "happy"),
    )
    pw, ph = 345, 520
    scale = 2.85
    for i, (label, facing, face) in enumerate(views):
        x = 30 + i * (pw + 15)
        y = 95
        pose = standing_pose(0.0, facing)
        cf = _frame_for(pose, face)
        stage = Stage(x=pw / 2, ground_y=ph - 50, scale=scale)
        _panel(ctx, renderer, draw_frame(cf, stage), x, y, pw, ph, ground=ph - 50)
        _text(ctx, x + 12, y + 24, label, 13, GOLD, True)
    # Proportion guide on the first panel.
    gx = 30 + 18
    top = 95 + (ph - 50) - STANDING_HEIGHT * scale
    ctx.set_source_rgba(1, 1, 1, 0.35)
    ctx.set_line_width(1)
    for k in range(5):
        yy = 95 + (ph - 50) - k * HEAD_HEIGHT * scale
        if yy < top - 1:
            break
        ctx.move_to(gx, yy)
        ctx.line_to(gx + 14, yy)
        ctx.stroke()
        _text(ctx, gx + 16, yy - 2, f"{k}", 10, (0.8, 0.85, 0.95))
    ctx.move_to(gx, top)
    ctx.line_to(gx + 14, top)
    ctx.stroke()
    _text(ctx, gx + 16, top + 4, "3.56", 10, GOLD)

    # Expressions: head close-ups rendered from the same rig and artwork.
    _text(ctx, 30, 650, "EXPRESSIONS (numeric FaceState presets; blendable)", 16, GOLD, True)
    names = [
        "neutral",
        "happy",
        "excited",
        "curious",
        "surprised",
        "concerned",
        "determined",
        "tired",
    ]
    ew, eh = 172, 190
    for i, name in enumerate(names):
        x = 30 + i * (ew + 9)
        y = 665
        pose = standing_pose(0.0, 0.12)
        if name == "curious":
            pose = replace(pose, head=0.14, look_x=0.6, head_yaw=0.2)
        if name == "tired":
            pose = replace(pose, head=-0.08, look_y=0.4)
        if name == "surprised":
            pose = replace(pose, look_y=-0.2)
        cf = _frame_for(pose, name)
        stage = Stage(x=ew / 2, ground_y=eh + 222, scale=3.0)
        _panel(ctx, renderer, draw_frame(cf, stage, shadows=False), x, y, ew, eh)
        _text(ctx, x + 10, y + eh + 18, name.upper(), 12, (0.9, 0.92, 1.0), True)
    notes = [
        "Identity kept from V1: black rounded head, glowing white oval eyes, white brows, "
        "red knit beanie with",
        "thick folded brim and pom, oversized golden hoodie with white drawstrings and "
        "kangaroo pocket, charcoal",
        "shorts with white side stripes, thin black stick limbs, mitten hands, big rounded "
        "shoes. No nose/ears/hair.",
        "V2 polish: cleaner curves, skinned hoodie with folds/side shading/ribbed hem, "
        "slim raglan sleeves with",
        "ribbed cuffs, four mitten shapes, rolling shoes with white soles, moonlight rim "
        "+ edge separation strokes.",
    ]
    for k, line in enumerate(notes):
        _text(ctx, 30, 905 + k * 20, line, 13)
    _text(
        ctx,
        30,
        1030,
        "Views are the rig's supported facings (front .. three-quarter, mirrored for left). "
        "A true profile view is not supported.",
        12,
        (0.7, 0.75, 0.85),
    )
    surface.write_to_png(str(out_png))
    surface.finish()


MOTION_POSES = (
    (29, "WAVE (far hand, wrist lag)"),
    (118, "POINT (straight elbow, hand on hip)"),
    (148, "JUMP: ANTICIPATION CROUCH"),
    (162, "JUMP: AIRBORNE APEX"),
    (173, "LAND: KNEE COMPRESSION"),
    (232, "WALK: CONTACT / ARM SWING"),
    (283, "RUN: FLIGHT PHASE"),
    (296, "RUN: PUSH-OFF"),
    (338, "JUMPING JACK: OUT"),
    (370, "SQUAT: BOTTOM"),
    (395, "STRETCH OVERHEAD ON TOES"),
    (449, "CONFIDENT FINISH"),
)


def airborne_frame(perf, lo: int, hi: int) -> int:
    """First frame in [lo, hi] where both soles are clearly off the ground."""
    for f in range(lo, hi + 1):
        s = perf.sample(f).state
        if all(max(p[1] for p in s.sole_points(side)) < -0.6 for side in ("near", "far")):
            return f
    raise SystemExit(f"no airborne frame in {lo}..{hi}")


def build_motion_sheet(perf, out_png: Path) -> None:
    global MOTION_POSES
    poses = list(MOTION_POSES)
    poses[6] = (airborne_frame(perf, 272, 305), "RUN: FLIGHT PHASE (both feet off)")
    MOTION_POSES = tuple(poses)
    cols, rows = 6, 2
    pw, ph = 245, 400
    W = 30 + cols * (pw + 12)
    H = 110 + rows * (ph + 44)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*INK_BG)
    ctx.paint()
    renderer = CairoRenderer()
    _text(ctx, 30, 46, "YELLOW MELLOW V2 - MOTION SHEET", 26, GOLD, True)
    _text(
        ctx,
        30,
        72,
        "Poses sampled from the showcase performance through the public API "
        "(Performance.sample); ground line = y 0; ghost = pose 4 frames earlier",
        13,
    )
    for i, (frame, label) in enumerate(MOTION_POSES):
        x = 30 + (i % cols) * (pw + 12)
        y = 95 + (i // cols) * (ph + 44)
        cf = perf.sample(frame)
        ghost = perf.sample(max(0, frame - 4))
        stage = Stage(x=pw / 2 - 2.0 * cf.state.pose.pelvis_x, ground_y=ph - 40, scale=2.0)
        ghost_cmds = tuple(
            replace(
                c,
                fill=_fade(c.fill),
                stroke=replace(c.stroke, paint=_fade(c.stroke.paint)) if c.stroke else None,
            )
            for c in draw_frame(ghost, stage, shadows=False)
        )
        _panel(ctx, renderer, ghost_cmds + draw_frame(cf, stage), x, y, pw, ph, ground=ph - 40)
        _text(ctx, x + 6, y + ph + 18, label, 11, GOLD, True)
        _text(ctx, x + 6, y + ph + 34, f"frame {frame}  action={cf.action}", 10, (0.75, 0.8, 0.9))
    surface.write_to_png(str(out_png))
    surface.finish()


def _fade(paint):
    from reelforge.rendering.model import Color, LinearGradient

    if paint is None:
        return None
    if isinstance(paint, Color):
        return Color(paint.r, paint.g, paint.b, paint.a * 0.16)
    if isinstance(paint, LinearGradient):
        return LinearGradient(
            paint.start,
            paint.end,
            tuple((o, Color(c.r, c.g, c.b, c.a * 0.16)) for o, c in paint.stops),
        )
    return paint


def decode_frames(mp4: Path, frames, workdir: Path) -> list[Path]:
    expr = "+".join(f"eq(n\\,{f})" for f in frames)
    pattern = workdir / "f_%03d.png"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(mp4),
            "-vf",
            f"select={expr}",
            "-fps_mode",
            "passthrough",
            str(pattern),
        ],
        check=True,
    )
    out = sorted(workdir.glob("f_*.png"))
    if len(out) != len(frames):
        raise SystemExit(f"decoded {len(out)} frames, expected {len(frames)}")
    return out


def build_contact_sheet(mp4: Path, out_png: Path, frames, labels) -> None:
    cols = 6
    tw, th = 216, 384
    rows = (len(frames) + cols - 1) // cols
    W = 24 + cols * (tw + 10)
    H = 96 + rows * (th + 40)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*INK_BG)
    ctx.paint()
    _text(ctx, 24, 42, "YELLOW MELLOW V2 - SHOWCASE CONTACT SHEET", 24, GOLD, True)
    _text(
        ctx,
        24,
        68,
        f"Frames decoded from {mp4.name} with FFmpeg (720x1280, 30 fps, 450 frames)",
        13,
    )
    with tempfile.TemporaryDirectory(dir=out_png.parent) as tmp:
        pngs = decode_frames(mp4, frames, Path(tmp))
        for i, (png, f) in enumerate(zip(pngs, frames, strict=True)):
            x = 24 + (i % cols) * (tw + 10)
            y = 84 + (i // cols) * (th + 40)
            img = cairo.ImageSurface.create_from_png(str(png))
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(tw / img.get_width(), th / img.get_height())
            ctx.set_source_surface(img, 0, 0)
            ctx.paint()
            ctx.restore()
            img.finish()
            ctx.set_source_rgb(0.25, 0.3, 0.45)
            ctx.rectangle(x + 0.5, y + 0.5, tw - 1, th - 1)
            ctx.stroke()
            _text(ctx, x + 2, y + th + 16, f"F{f}  {f / 30:.2f}s", 11, GOLD, True)
            _text(ctx, x + 2, y + th + 31, labels.get(f, ""), 10, (0.8, 0.84, 0.92))
    surface.write_to_png(str(out_png))
    surface.finish()


def build_sheets(out: Path) -> None:
    from render_yellow_mellow_v2 import build

    out.mkdir(parents=True, exist_ok=True)
    perf, _ = build()
    build_character_sheet(out / "YellowMellow_V2_Character_Sheet.png")
    build_motion_sheet(perf, out / "YellowMellow_V2_Motion_Sheet.png")
    print("sheets written to", out)
