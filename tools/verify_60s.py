"""Independent verification of the 60s MVP reel + a 20-panel contact sheet (one per segment).

ffprobe/ffmpeg checks against the one completed render and a decoded frame from the middle of
each 90-frame segment. Writes MVP_VERIFICATION.json fields and the 20-panel sheet.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cairo

FPS = 30
FRAMES = 1800
SEGMENTS = 20


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def verify(mp4: Path, plan_summary: dict | None = None):
    probe = run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(mp4)]
    )
    meta = json.loads(probe.stdout)
    video = [s for s in meta["streams"] if s["codec_type"] == "video"]
    audio = [s for s in meta["streams"] if s["codec_type"] == "audio"]
    v = video[0]
    frames = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=best_effort_timestamp_time",
            "-of",
            "csv=p=0",
            str(mp4),
        ]
    )
    stamps = [float(x.strip().rstrip(",")) for x in frames.stdout.split() if x.strip().rstrip(",")]
    deltas = [round(b - a, 6) for a, b in zip(stamps, stamps[1:], strict=False)]
    decode = run(["ffmpeg", "-v", "error", "-xerror", "-i", str(mp4), "-f", "null", "-"])
    duration = float(meta["format"]["duration"])

    labels = {}
    if plan_summary:
        for b in plan_summary.get("beats", []):
            labels[b["index"] - 1] = f"{b['preset'][:9]} {b['environment'][:6]}"

    sample_frames = [i * 90 + 45 for i in range(SEGMENTS)]
    thumbs = []
    black = []
    with tempfile.TemporaryDirectory(dir=str(mp4.parent)) as tmp:
        tmpd = Path(tmp)
        for seg, f in enumerate(sample_frames):
            png = tmpd / f"s_{seg:02d}.png"
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(mp4),
                    "-vf",
                    f"select=eq(n\\,{f})",
                    "-frames:v",
                    "1",
                    "-fps_mode",
                    "passthrough",
                    str(png),
                ]
            )
            h = hashlib.sha256(png.read_bytes()).hexdigest()[:16]
            thumbs.append((seg, f, png, h))
            st = run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    f"movie={png.as_posix()},signalstats",
                    "-show_entries",
                    "frame_tags=lavfi.signalstats.YAVG",
                    "-of",
                    "csv=p=0",
                    str(png),
                ]
            )
            try:
                yavg = float(st.stdout.split()[0]) if st.stdout.strip() else -1.0
            except ValueError:
                yavg = -1.0
            if 0 <= yavg < 16:
                black.append(f)
        hashes = [h for _s, _f, _p, h in thumbs]
        _sheet(thumbs, labels, mp4.parent / "YellowMellow_60s_contact_sheet.png")

    checks = {
        "1800_frames_header": v.get("nb_frames") == str(FRAMES),
        "1800_frames_decoded": len(stamps) == FRAMES,
        "duration_60_000": abs(duration - 60.0) < 2e-3,
        "resolution_720x1280": (v["width"], v["height"]) == (720, 1280),
        "fps_30": v["avg_frame_rate"] == "30/1",
        "one_h264_stream": len(video) == 1 and v["codec_name"] == "h264",
        "yuv420p": v["pix_fmt"] == "yuv420p",
        "no_audio_stream": len(audio) == 0,
        "no_decode_errors": decode.returncode == 0 and not decode.stderr.strip(),
        "timestamps_continuous": bool(deltas) and all(abs(d - 1 / FPS) < 1e-4 for d in deltas),
        "no_black_sampled_frames": not black,
        "all_segments_distinct": len(set(hashes)) >= SEGMENTS - 1,
    }
    report = {
        "file": mp4.name,
        "size_bytes": int(meta["format"]["size"]),
        "codec": v["codec_name"],
        "profile": v.get("profile"),
        "pix_fmt": v["pix_fmt"],
        "width": v["width"],
        "height": v["height"],
        "avg_frame_rate": v["avg_frame_rate"],
        "nb_frames_header": v.get("nb_frames"),
        "decoded_frames": len(stamps),
        "duration_s": duration,
        "audio_streams": len(audio),
        "decode_exit_code": decode.returncode,
        "timestamp_step_min_s": min(deltas) if deltas else None,
        "timestamp_step_max_s": max(deltas) if deltas else None,
        "editorial_cuts": [i * 90 for i in range(1, SEGMENTS)],
        "near_black_sampled_frames": black,
        "distinct_sampled_frames": len(set(hashes)),
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    return report


def _sheet(thumbs, labels, out_png):
    cols = 5
    rows = (len(thumbs) + cols - 1) // cols
    tw, th = 200, 356
    W = 20 + cols * (tw + 10)
    H = 70 + rows * (th + 36)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.04, 0.06, 0.12)
    ctx.paint()
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(22)
    ctx.set_source_rgb(1.0, 0.82, 0.4)
    ctx.move_to(20, 42)
    ctx.show_text("YELLOW MELLOW - THE SIGNAL ACROSS THE VALLEY (60s, 20 segments)")
    for i, (seg, f, png, _h) in enumerate(thumbs):
        x = 20 + (i % cols) * (tw + 10)
        y = 60 + (i // cols) * (th + 36)
        img = cairo.ImageSurface.create_from_png(str(png))
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(tw / img.get_width(), th / img.get_height())
        ctx.set_source_surface(img, 0, 0)
        ctx.paint()
        ctx.restore()
        img.finish()
        ctx.set_source_rgb(0.3, 0.38, 0.55)
        ctx.set_line_width(1.5)
        ctx.rectangle(x + 0.5, y + 0.5, tw - 1, th - 1)
        ctx.stroke()
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(12)
        ctx.set_source_rgb(0.95, 0.82, 0.45)
        ctx.move_to(x, y + th + 15)
        ctx.show_text(f"seg {seg + 1:02d}  {labels.get(seg, '')}")
        ctx.set_source_rgb(0.7, 0.75, 0.85)
        ctx.move_to(x, y + th + 29)
        ctx.show_text(f"f{f}  {f / FPS:.1f}s")
    surface.write_to_png(str(out_png))
    surface.finish()


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs")
    summary = None
    ps = base / "plan_60s_summary.json"
    if ps.is_file():
        summary = json.loads(ps.read_text())
    rep = verify(base / "YellowMellow_60s_MVP.mp4", summary)
    print(json.dumps(rep["checks"], indent=2))
    print("all_checks_passed:", rep["all_checks_passed"])
    print("distinct sampled frames:", rep["distinct_sampled_frames"], "/", SEGMENTS)
    (base / "_60s_media_verification.json").write_text(json.dumps(rep, indent=2))
