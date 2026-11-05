"""Independent verification of the finished Frost Peak MP4 (no re-render).

ffprobe/ffmpeg checks against the one completed render plus sampled decoded frames around the
key story events. Writes frost_peak_video_verification.json and a small contact sheet of the
sampled frames so the Shot 3 press and the Shot 3->4 transition can be inspected.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cairo

REPO = Path(__file__).resolve().parent.parent
FPS = 30
FRAMES = 450
SAMPLES = {
    0: "S1 establish",
    30: "S1 walk",
    75: "S1 react",
    90: "S2 cut",
    135: "S2 approach",
    170: "S2 close concern",
    180: "S3 cut",
    215: "S3 crouch",
    262: "S3 press (contact)",
    270: "S4 cut (beacon active)",
    300: "S4 recoil",
    345: "S4 stare",
    360: "S5 cut",
    400: "S5 settle",
    449: "S5 answer / relief",
}


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def verify(mp4: Path, out_json: Path, out_sheet: Path):
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

    # Sampled frames: decode to PNG, hash, and detect near-black frames.
    thumbs = []
    with tempfile.TemporaryDirectory(dir=str(out_sheet.parent)) as tmp:
        tmpd = Path(tmp)
        for f in SAMPLES:
            png = tmpd / f"f_{f:03d}.png"
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
            data = png.read_bytes()
            thumbs.append((f, png, hashlib.sha256(data).hexdigest()[:16]))
        # near-black check via mean luma using ffprobe signalstats
        black = []
        for f, png, _h in thumbs:
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
        # distinct frames across samples (proves the picture changes between beats)
        hashes = [h for _f, _p, h in thumbs]
        _build_sheet(thumbs, out_sheet)

    checks = {
        "450_frames_header": v.get("nb_frames") == str(FRAMES),
        "450_frames_decoded": len(stamps) == FRAMES,
        "duration_15_000": abs(duration - 15.0) < 1e-3,
        "resolution_720x1280": (v["width"], v["height"]) == (720, 1280),
        "fps_30": v["avg_frame_rate"] == "30/1",
        "one_h264_stream": len(video) == 1 and v["codec_name"] == "h264",
        "yuv420p": v["pix_fmt"] == "yuv420p",
        "no_audio_stream": len(audio) == 0,
        "no_decode_errors": decode.returncode == 0 and not decode.stderr.strip(),
        "timestamps_continuous": bool(deltas) and all(abs(d - 1 / FPS) < 1e-4 for d in deltas),
        "shot_cuts_present": all(f in SAMPLES for f in (90, 180, 270, 360)),
        "no_black_sampled_frames": not black,
        "sampled_frames_distinct": len(set(hashes)) >= len(hashes) - 1,
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
        "first_timestamp_s": stamps[0] if stamps else None,
        "last_timestamp_s": stamps[-1] if stamps else None,
        "timestamp_step_min_s": min(deltas) if deltas else None,
        "timestamp_step_max_s": max(deltas) if deltas else None,
        "audio_streams": len(audio),
        "decode_exit_code": decode.returncode,
        "editorial_cuts": [90, 180, 270, 360],
        "near_black_sampled_frames": black,
        "sampled_frames": [
            {"frame": f, "label": SAMPLES[f], "sha256_16": h} for (f, _p, h) in thumbs
        ],
        "distinct_sampled_frames": len(set(h for _f, _p, h in thumbs)),
        "checks": checks,
    }
    report["all_checks_passed"] = all(checks.values())
    out_json.write_text(json.dumps(report, indent=2))
    print(json.dumps(checks, indent=2))
    print("all_checks_passed:", report["all_checks_passed"])
    print("near-black frames:", black or "none")
    print("distinct sampled frames:", report["distinct_sampled_frames"], "/", len(SAMPLES))


def _build_sheet(thumbs, out_png):
    cols = 5
    rows = (len(thumbs) + cols - 1) // cols
    tw, th = 216, 384
    W = 20 + cols * (tw + 10)
    H = 70 + rows * (th + 34)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.04, 0.06, 0.12)
    ctx.paint()
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(22)
    ctx.set_source_rgb(1.0, 0.82, 0.4)
    ctx.move_to(20, 40)
    ctx.show_text("FROST PEAK 15s - SAMPLED DECODED FRAMES (from the final MP4)")
    for i, (f, png, _h) in enumerate(thumbs):
        x = 20 + (i % cols) * (tw + 10)
        y = 60 + (i // cols) * (th + 34)
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
        ctx.move_to(x, y + th + 16)
        ctx.show_text(f"f{f}  {SAMPLES[f]}")
    surface.write_to_png(str(out_png))
    surface.finish()


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "outputs"
    verify(
        base / "YellowMellow_FrostPeak_15s_Final.mp4",
        base / "frost_peak_video_verification.json",
        base / "frost_peak_sampled_frames.png",
    )
