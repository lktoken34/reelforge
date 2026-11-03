"""Yellow Mellow V2 showcase runner (engineering proof tool, not an episode command).

Usage (WSL Ubuntu, Python 3.12 with pycairo):
    python tools/render_yellow_mellow_v2.py stills 0 30 60 --out outputs/yellow_mellow_v2/dev
    python tools/render_yellow_mellow_v2.py video --out outputs/yellow_mellow_v2
    python tools/render_yellow_mellow_v2.py sheets --out outputs/yellow_mellow_v2
    python tools/render_yellow_mellow_v2.py quality --out outputs/yellow_mellow_v2

The showcase is ordinary public-API usage: a list of ActionRequest values.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from reelforge.characters.yellow_mellow_v2 import (  # noqa: E402
    ActionRequest,
    FollowCamera,
    Stage,
    YellowMellowV2,
)
from reelforge.characters.yellow_mellow_v2.environment import observatory_background  # noqa: E402
from reelforge.rendering.diagnostic import color  # noqa: E402

FPS = 30
FRAMES = 450
STAGE = Stage(x=180.0, ground_y=575.0, scale=2.3)
BACKGROUND = color("060914")
# Camera keeps him slightly left of centre after the walk so the observatory stays visible.
CAMERA_ANCHOR = 150.0
CAMERA_DEADZONE = 22.0

SECTIONS = (
    (0, 44, "Idle, blink, smile, one-hand wave"),
    (45, 89, "Raise both hands, lower naturally"),
    (90, 134, "Look right, point, curiosity"),
    (135, 194, "Crouch, jump, land, absorb"),
    (195, 254, "Turn and walk with planted feet"),
    (255, 314, "Accelerate into a run, decelerate, stop"),
    (315, 359, "Jumping jacks"),
    (360, 404, "Squat, stand, stretch overhead"),
    (405, 449, "Celebration bounce, confident pose"),
)


def showcase_requests() -> list[ActionRequest]:
    A = ActionRequest
    return [
        A("idle", 10, "neutral"),
        A("wave", 35, "happy", {"hand": "far", "waves": 2.0}),
        A("hands_up", 22, "excited"),
        A("hands_down", 23, "happy"),
        A("look", 12, "curious", {"direction": "right"}),
        A("point", 33, "curious", {"hand": "far", "elevation": 1.15, "lower": True}),
        A("jump", 60, "excited", {"height": 26.0, "crouch": 13.0}),
        A("walk", 60, "happy", {"direction": "left"}),
        A("run", 60, "determined", {"direction": "left", "stop": True}),
        A("jumping_jack", 45, "determined", {"reps": 3}),
        A("squat", 22, "determined", {"depth": 17.0}),
        A("stretch", 23, "tired"),
        A("dance", 45, "happy", {"beats": 4}),
    ]


def build():
    mellow = YellowMellowV2(start_x=0.0, facing=0.25)
    perf = mellow.animate(showcase_requests())
    if perf.frames != FRAMES:
        raise SystemExit(f"Showcase must be {FRAMES} frames, got {perf.frames}")
    cam = FollowCamera(perf, STAGE, anchor=CAMERA_ANCHOR, radius=20, deadzone=CAMERA_DEADZONE)
    return perf, cam


def frame_commands(perf, cam, frame: int):
    cx = cam.at(frame)
    stage = Stage(STAGE.x, STAGE.ground_y, STAGE.scale, cx)
    return observatory_background(cx, STAGE.ground_y) + perf.draw(frame, stage)


def render_png(
    renderer, commands, path: Path, size=(720, 1280), logical=(360, 640), background=BACKGROUND
):
    with renderer.surface(*size) as surface:
        renderer.draw(surface, commands, background=background, logical_size=logical)
        surface.write_png(path)


def cmd_stills(args):
    from reelforge.rendering.backends.cairo import CairoRenderer

    perf, cam = build()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    renderer = CairoRenderer()
    for f in args.frames:
        render_png(renderer, frame_commands(perf, cam, f), out / f"frame_{f:03d}.png")
    print(json.dumps({"stills": args.frames, "out": str(out)}))


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def cmd_video(args):
    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.media.verify import verify_video
    from reelforge.rendering.backends.cairo import CairoRenderer

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    mp4 = out / "YellowMellow_V2_Animation_Showcase.mp4"
    if mp4.exists():
        raise SystemExit(f"{mp4} exists; refusing to overwrite an existing proof asset")
    started = time.perf_counter()
    perf, cam = build()
    renderer = CairoRenderer()
    cancelled = threading.Event()
    hashes = []
    max_cmds = 0
    with FFmpegEncoder(
        mp4, width=720, height=1280, frames=FRAMES, timeout=900, cancelled=cancelled
    ) as enc:
        with renderer.surface(720, 1280) as surface:
            for f in range(FRAMES):
                cmds = frame_commands(perf, cam, f)
                max_cmds = max(max_cmds, len(cmds))
                renderer.draw(surface, cmds, background=BACKGROUND, logical_size=(360, 640))
                if f % 50 == 0:
                    hashes.append((f, surface.pixel_sha256()))
                enc.write_surface(surface)
    render_s = time.perf_counter() - started
    enc.confirm_cleanup()
    leak = {
        "allocated_bytes": renderer.allocated_bytes,
        "active_surfaces": renderer.active_surfaces,
    }
    verification = verify_video(mp4, width=720, height=1280, frames=FRAMES, cancelled=cancelled)
    report = {
        "file": mp4.name,
        "frames_rendered": FRAMES,
        "render_seconds": round(render_s, 3),
        "render_fps": round(FRAMES / render_s, 2),
        "peak_rss_mb": round(peak_rss_mb(), 1),
        "max_draw_commands_per_frame": max_cmds,
        "surface_state_after_render": leak,
        "sample_surface_sha256": hashes,
        "verify_video": {k: v for k, v in verification.items() if k != "decoded_rgb_sha256"},
        "unique_decoded_frames": verification["unique_decoded_frames"],
    }
    (out / "render_report.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {k: report[k] for k in ("render_seconds", "peak_rss_mb", "unique_decoded_frames")}
        )
    )


def cmd_verify(args):
    """Independent ffprobe/ffmpeg checks of the delivered MP4 (no re-render)."""
    import subprocess

    out = Path(args.out)
    mp4 = out / "YellowMellow_V2_Animation_Showcase.mp4"

    def run(cmd):
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    probe = run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(mp4)]
    )
    meta = json.loads(probe.stdout)
    video = [s for s in meta["streams"] if s["codec_type"] == "video"]
    audio = [s for s in meta["streams"] if s["codec_type"] == "audio"]
    frames = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=best_effort_timestamp_time,pkt_duration_time",
            "-of",
            "csv=p=0",
            str(mp4),
        ]
    )
    stamps = [float(line.split(",")[0]) for line in frames.stdout.split() if line.strip()]
    deltas = [round(b - a, 6) for a, b in zip(stamps, stamps[1:], strict=False)]
    decode = run(["ffmpeg", "-v", "error", "-xerror", "-i", str(mp4), "-f", "null", "-"])
    v = video[0]
    duration = float(meta["format"]["duration"])
    report = {
        "file": mp4.name,
        "size_bytes": int(meta["format"]["size"]),
        "video_streams": len(video),
        "audio_streams": len(audio),
        "codec": v["codec_name"],
        "profile": v.get("profile"),
        "pix_fmt": v["pix_fmt"],
        "width": v["width"],
        "height": v["height"],
        "avg_frame_rate": v["avg_frame_rate"],
        "r_frame_rate": v["r_frame_rate"],
        "nb_frames_header": v.get("nb_frames"),
        "decoded_frames": len(stamps),
        "container_duration_s": duration,
        "stream_duration_s": float(v.get("duration", 0)),
        "first_timestamp_s": stamps[0] if stamps else None,
        "last_timestamp_s": stamps[-1] if stamps else None,
        "timestamp_step_min_s": min(deltas) if deltas else None,
        "timestamp_step_max_s": max(deltas) if deltas else None,
        "timestamps_continuous": bool(deltas) and all(abs(d - 1 / 30) < 1e-4 for d in deltas),
        "decode_exit_code": decode.returncode,
        "decode_stderr": decode.stderr.strip(),
        "checks": {
            "450_frames": len(stamps) == FRAMES,
            "duration_15_000": abs(duration - 15.0) < 1e-3,
            "720x1280": (v["width"], v["height"]) == (720, 1280),
            "30_fps": v["avg_frame_rate"] == "30/1",
            "one_h264_stream": len(video) == 1 and v["codec_name"] == "h264",
            "yuv420p": v["pix_fmt"] == "yuv420p",
            "no_audio": len(audio) == 0,
            "no_decode_errors": decode.returncode == 0 and not decode.stderr.strip(),
        },
    }
    report["all_checks_passed"] = all(report["checks"].values()) and report["timestamps_continuous"]
    (out / "video_verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["checks"]), "continuous:", report["timestamps_continuous"])


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("stills")
    s.add_argument("frames", type=int, nargs="+")
    s.add_argument("--out", default="outputs/yellow_mellow_v2/dev")
    v = sub.add_parser("video")
    v.add_argument("--out", default="outputs/yellow_mellow_v2")
    sh = sub.add_parser("sheets")
    sh.add_argument("--out", default="outputs/yellow_mellow_v2")
    q = sub.add_parser("quality")
    q.add_argument("--out", default="outputs/yellow_mellow_v2")
    vf = sub.add_parser("verify")
    vf.add_argument("--out", default="outputs/yellow_mellow_v2")
    cs = sub.add_parser("contact")
    cs.add_argument("--out", default="outputs/yellow_mellow_v2")
    args = parser.parse_args()
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "contact":
        sys.path.insert(0, str(REPO / "tools"))
        from yellow_mellow_v2_sheets import build_contact_sheet

        out = Path(args.out)
        frames = [
            0,
            28,
            60,
            80,
            96,
            118,
            148,
            162,
            174,
            205,
            232,
            262,
            284,
            300,
            312,
            338,
            352,
            370,
            395,
            404,
            415,
            428,
            440,
            449,
        ]
        labels = {}
        for start, end, label in SECTIONS:
            for f in frames:
                if start <= f <= end:
                    labels[f] = label[:34]
        build_contact_sheet(
            out / "YellowMellow_V2_Animation_Showcase.mp4",
            out / "YellowMellow_V2_Contact_Sheet.png",
            frames,
            labels,
        )
        return None
    if args.command == "stills":
        cmd_stills(args)
    elif args.command == "video":
        cmd_video(args)
    elif args.command == "sheets":
        sys.path.insert(0, str(REPO / "tools"))
        from yellow_mellow_v2_sheets import build_sheets  # type: ignore

        build_sheets(Path(args.out))
    elif args.command == "quality":
        from reelforge.characters.yellow_mellow_v2.quality import analyse

        perf, cam = build()
        report = analyse(perf, sections=SECTIONS)
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / "motion_quality.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
