"""Fixed sequential public-CLI proofs; no automatic retry of failed jobs."""

import json
import subprocess
import sys
import time
from pathlib import Path

from review_geometry import sheet

from reelforge.audio.processing import command
from reelforge.audio.registry import AudioRegistry
from reelforge.reels.contract import inspect_reel, load_reel, metadata_plan
from reelforge.resources.monitor import JobMonitor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase7b"
NAMES = ("silent_signal", "abandoned_settlement", "shelter_entrance")
JOBS = [(name, name) for name in NAMES] + [("signal_repeat", "silent_signal")]


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")


def run_proofs():
    (OUT / "proofs").mkdir(exist_ok=True)
    execution = {
        "policy": "Four preplanned jobs; final A repeat independent of earlier status; no retries",
        "planned_jobs": JOBS,
        "jobs": [],
        "retries": 0,
    }
    save("proof_execution.json", execution)
    started = time.perf_counter()
    with JobMonitor(workspace=OUT) as monitor:
        for job, name in JOBS:
            output = OUT / "proofs" / job
            args = [
                sys.executable,
                "tools/reel.py",
                "render",
                f"examples/reels/{name}.json",
                "--output-dir",
                str(output),
            ]
            tick = time.perf_counter()
            process = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=180)
            execution["jobs"].append(
                {
                    "job": job,
                    "manifest": name,
                    "command": args,
                    "exit_code": process.returncode,
                    "wall_seconds": time.perf_counter() - tick,
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                }
            )
            save("proof_execution.json", execution)
    execution["wall_seconds"] = time.perf_counter() - started
    save("proof_execution.json", execution)
    save("proof_resources.json", monitor.report())


def timeline(reports):
    import cairo

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1180, 1010)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.04, 0.10, 0.14)
    ctx.paint()
    ctx.select_font_face("sans-serif")

    def label(text, x, y, size=13):
        ctx.set_font_size(size)
        ctx.set_source_rgb(0.92, 0.89, 0.78)
        ctx.move_to(x, y)
        ctx.show_text(text)

    label("AV timeline / diagnostic audio / frames 0-90 / one shared 48 kHz clock", 35, 35, 21)
    left, width = 80, 1030

    def x(f):
        return left + f / 90 * width

    colors = [
        (0.25, 0.55, 0.65),
        (0.65, 0.65, 0.35),
        (0.78, 0.43, 0.34),
        (0.52, 0.42, 0.65),
        (0.3, 0.55, 0.48),
    ]
    for row, name in enumerate(NAMES):
        y = 90 + row * 300
        plan = load_reel(ROOT / f"examples/reels/{name}.json")
        cues = metadata_plan(plan, AudioRegistry(ROOT / "assets/audio"))
        label(plan.title, 35, y, 17)
        for index, beat in enumerate(plan.storyboard.beats):
            ctx.set_source_rgb(*colors[index % len(colors)])
            ctx.rectangle(x(beat.start) + 1, y + 15, x(beat.end) - x(beat.start) - 2, 32)
            ctx.fill()
            label(beat.kind, x(beat.start) + 4, y + 37, 11)
        for cue in inspect_reel(plan, cues)["audio_cues"]:
            yy = y + (60 if cue["role"] == "narration" else 95)
            ctx.set_source_rgb(0.62, 0.72, 0.46) if cue[
                "role"
            ] == "narration" else ctx.set_source_rgb(0.74, 0.5, 0.35)
            ctx.rectangle(
                x(cue["start_frame"]),
                yy,
                (cue["end_sample"] - cue["start_sample"]) / 1600 / 90 * width,
                22,
            )
            ctx.fill()
            label(cue["asset_id"], x(cue["start_frame"]) + 3, yy + 15, 11)
        report = reports.get(name, {})
        wave = report.get("audio_verification", {}).get("waveform", {})
        for key, color, yy in [
            ("reference_peak_envelope", (0.5, 0.8, 0.7), y + 165),
            ("decoded_peak_envelope", (0.85, 0.65, 0.4), y + 215),
        ]:
            values = wave.get(key, [])
            for index, value in enumerate(values):
                xx = x(index * 2400 / 1600)
                ctx.set_source_rgb(*color)
                ctx.move_to(xx, yy)
                ctx.line_to(xx, yy - min(1, value / 0.1) * 35)
                ctx.stroke()
        label("reference PCM / decoded AAC", left, y + 245, 11)
        for shot in plan.storyboard.direction.shots[1:]:
            ctx.set_source_rgb(0.95, 0.8, 0.4)
            ctx.set_dash([3, 3])
            ctx.move_to(x(shot.start), y + 10)
            ctx.line_to(x(shot.start), y + 225)
            ctx.stroke()
            ctx.set_dash([])
            label("cut " + str(shot.start), x(shot.start) + 4, y + 235, 11)
        for f in range(0, 91, 15):
            label(str(f), x(f) - 4, y + 270, 11)
    surface.write_to_png(str(OUT / "audiovisual_timeline.png"))
    ctx = None
    surface.finish()


def collect():
    reports = {}
    metrics = {}
    all_cells = []
    frames = (0, 30, 45, 60, 72, 89)
    scratch = ROOT / "outputs/phase7b-decoded-review"
    scratch.mkdir(exist_ok=True)
    if any(scratch.iterdir()):
        raise RuntimeError("Review directory must be empty; never overwrite decoded review files")
    # Select only completed published primary jobs. Any missing proof remains visibly missing.
    for name in NAMES:
        path = OUT / "proofs" / name / "report.json"
        if not path.exists():
            continue
        report = json.loads(path.read_text())
        reports[name] = report
        plan = load_reel(ROOT / f"examples/reels/{name}.json")
        resolved = metadata_plan(plan, AudioRegistry(ROOT / "assets/audio"))
        save(name + "_plans.json", inspect_reel(plan, resolved))
        save(name + "_frames.json", [inspect_reel(plan, resolved, f) for f in range(90)])
        old = json.loads(
            (ROOT / f"artifacts/phase7a/proofs/{name}_video/render_report.json").read_text()
        )
        vr = report.get("video_report", {})
        metrics[name] = {
            "source_job": name,
            "success": report["success"],
            "all_90_source_frames_match_phase7a": vr.get("source_pixel_sha256")
            == old["source_pixel_sha256"],
        }
        movie = path.parent / "reel.mp4"
        if not report["media_verified"] or not report["published"] or not movie.exists():
            continue
        cells = []
        for frame in frames:
            target = scratch / f"{name}_{frame:03}.png"
            command(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-threads",
                    "1",
                    "-i",
                    str(movie),
                    "-vf",
                    f"select=eq(n\\,{frame})",
                    "-frames:v",
                    "1",
                    "-threads:v",
                    "1",
                    "-n",
                    str(target),
                ]
            )
            cells.append((f"{name} decoded frame {frame}", target))
            if frame in (0, 45, 89):
                all_cells.append(cells[-1])
        sheet(cells, OUT / (name + "_decoded.png"))
        av = report["audio_verification"]
        metrics[name].update(
            {
                "cue_timing": av["cue_timing"],
                "audible_drift_samples": av["audible_drift_samples"],
                "audible_drift_ms": av["audible_drift_samples"] / 48,
                "mix": report["mix"]["statistics"],
                "decoded_pcm": av["decoded_pcm"],
                "terminal_padding_samples": av["terminal_padding_samples"],
                "total_wall_seconds": report["total_wall_seconds"],
                "workflow_fps": report["workflow_fps"],
                "encoded_fps": vr["encoded_fps"],
                "memory": report["end_to_end_memory"],
                "storage": report["temporary_storage"],
                "stream_copy_unchanged": av["h264_bitstream_unchanged"],
                "exact_pts": report["streams"]["exact_video_pts"],
            }
        )
    if all_cells:
        sheet(all_cells, OUT / "decoded_contact_sheet.png")
    timeline(reports)
    save("audiovisual_metrics.json", metrics)
    a = reports.get("silent_signal")
    repeatpath = OUT / "proofs/signal_repeat/report.json"
    b = json.loads(repeatpath.read_text()) if repeatpath.exists() else None
    repeat = {
        "first_status": None if a is None else a["success"],
        "repeat_status": None if b is None else b["success"],
    }
    if a and b and a["media_verified"] and b["media_verified"]:
        repeat.update(
            {
                "all_90_source_frames_equal": a["video_report"]["source_pixel_sha256"]
                == b["video_report"]["source_pixel_sha256"],
                "all_90_decoded_frames_equal": a["verification"]["decoded_rgb_sha256"]
                == b["verification"]["decoded_rgb_sha256"],
                "mixed_pcm_equal": a["mix"]["statistics"]["sha256"]
                == b["mix"]["statistics"]["sha256"],
                "decoded_aac_pcm_equal": a["audio_verification"]["decoded_pcm"]["sha256"]
                == b["audio_verification"]["decoded_pcm"]["sha256"],
            }
        )
    save("repeat_consistency.json", repeat)
    save(
        "cleanup_followup.json",
        {
            job: {
                "path": json.loads((OUT / "proofs" / job / "report.json").read_text()).get(
                    "transaction_path"
                ),
                "restored_private_paths": [
                    str(p) for p in (OUT / "proofs" / job).glob(".reelforge-*")
                ],
                "scope": (
                    "Read-only after later native work; "
                    "original return statuses unchanged; no sweep"
                ),
            }
            for job, _ in JOBS
            if (OUT / "proofs" / job / "report.json").exists()
        },
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--collect-only"]:
        collect()
    else:
        run_proofs()
        collect()
