"""Storyboard CLI proofs, beat allocation, native-frame determinism and editorial metrics."""

import hashlib
import json
import math
import sys
import time
from pathlib import Path

from review_blocking import contact_sheet

from reelforge.direction.sampling import direction_frame, direction_layers, inspect_frame
from reelforge.media.process import run_bounded
from reelforge.resources.monitor import JobMonitor
from reelforge.scenes.assets import cost
from reelforge.storyboards.compiler import inspect_plans, load_storyboard

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase7a"
NAMES = ("silent_signal", "abandoned_settlement", "shelter_entrance")


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def trajectory_chart(reports):
    import cairo

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1080, 1030)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.05, 0.12, 0.16)
    ctx.paint()
    colors = ((0.9, 0.65, 0.3), (0.3, 0.75, 0.8), (0.65, 0.85, 0.5))
    for row, (name, frames) in enumerate(reports.items()):
        y = 50 + row * 335
        ctx.set_source_rgb(0.9, 0.85, 0.7)
        ctx.set_font_size(18)
        ctx.move_to(45, y)
        ctx.show_text(name.replace("_", " ") + " / camera at absolute frame time")
        for j, (key, low, high, label) in enumerate(
            (
                ("x", -100, 160, "pan x (logical)"),
                ("y", -100, 160, "pan y (logical)"),
                ("zoom", 0.9, 1.7, "zoom"),
            )
        ):
            x = 60 + j * 345
            ctx.set_font_size(13)
            ctx.move_to(x, y + 27)
            ctx.show_text(label)
            for n, d in enumerate(frames):
                px = x + 2.9 * n
                py = y + 235 - (d["camera"][key] - low) / (high - low) * 170
                if n == 0 or d["cut"]:
                    if n:
                        ctx.stroke()
                        ctx.set_source_rgba(0.8, 0.8, 0.7, 0.5)
                        ctx.set_dash([3, 4])
                        ctx.move_to(px, y + 50)
                        ctx.line_to(px, y + 245)
                        ctx.stroke()
                        ctx.set_dash([])
                    ctx.set_source_rgb(*colors[j])
                    ctx.move_to(px, py)
                else:
                    ctx.line_to(px, py)
            ctx.stroke()
            ctx.set_source_rgb(0.9, 0.85, 0.7)
            ctx.move_to(x, y + 265)
            ctx.show_text("0             frame 45             89")
        ctx.set_font_size(12)
        ctx.move_to(60, y + 295)
        ctx.show_text(
            "Dashed: hard cut; curves are not joined across cuts. Same world/source clock."
        )
    surface.write_to_png(str(OUT / "camera_trajectories.png"))
    ctx = None
    surface.finish()


def beat_timeline():
    import cairo

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1180, 720)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.05, 0.12, 0.16)
    ctx.paint()
    palette = {
        "establish": (0.3, 0.6, 0.7),
        "approach": (0.65, 0.7, 0.45),
        "discover": (0.85, 0.65, 0.3),
        "react": (0.8, 0.45, 0.4),
        "escape": (0.65, 0.4, 0.65),
        "hold": (0.4, 0.65, 0.6),
    }
    ctx.select_font_face("sans-serif")
    ctx.set_font_size(22)
    ctx.set_source_rgb(0.94, 0.88, 0.72)
    ctx.move_to(50, 38)
    ctx.show_text("Narrative beats and compiled shots / 90 frames at 30 FPS")
    for row, name in enumerate(NAMES):
        plan = load_storyboard(ROOT / f"examples/storyboards/{name}.json")
        top = 90 + row * 205
        ctx.set_font_size(18)
        ctx.set_source_rgb(0.94, 0.88, 0.72)
        ctx.move_to(50, top)
        ctx.show_text(plan.title + " / " + plan.pattern)
        for beat in plan.beats:
            x, w = 50 + beat.start * 12, (beat.end - beat.start) * 12
            ctx.set_source_rgb(*palette[beat.kind])
            ctx.rectangle(x + 1, top + 20, w - 2, 50)
            ctx.fill()
            ctx.set_source_rgb(0.05, 0.12, 0.16)
            ctx.set_font_size(11)
            ctx.move_to(x + 4, top + 41)
            ctx.show_text(beat.kind[:3] + " " + str(beat.end - beat.start) + "f")
            ctx.move_to(x + 4, top + 59)
            ctx.show_text(str(beat.start) + "-" + str(beat.end))
        for shot, group in zip(plan.direction.shots, plan.shot_beat_indices, strict=True):
            x, w = 50 + shot.start * 12, (shot.end - shot.start) * 12
            ctx.set_source_rgb(0.2, 0.35, 0.43)
            ctx.rectangle(x + 1, top + 80, w - 2, 30)
            ctx.fill()
            ctx.set_source_rgb(0.94, 0.88, 0.72)
            ctx.set_font_size(12)
            ctx.move_to(x + 8, top + 100)
            ctx.show_text(shot.id + " / " + shot.behavior + " / " + str(len(group)) + " beats")
        ctx.set_font_size(12)
        for f in range(0, 91, 15):
            ctx.move_to(50 + f * 12, top + 135)
            ctx.show_text(str(f))
    ctx.set_font_size(13)
    ctx.move_to(50, 700)
    ctx.show_text(
        "Upper: beats. Lower: shots. Every film retains one world and global motion clock."
    )
    surface.write_to_png(str(OUT / "narrative_timeline.png"))
    ctx = None
    surface.finish()


def main(diagnostics_only=False):
    OUT.mkdir(exist_ok=True)
    proofs = OUT / "proofs"
    proofs.mkdir(exist_ok=diagnostics_only)
    records = []
    if not diagnostics_only:
        start = time.perf_counter()
        with JobMonitor(workspace=OUT) as monitor:
            jobs = [
                (n, still, n + ("_stills" if still else "_video"))
                for n in NAMES
                for still in (True, False)
            ]
            jobs.append((NAMES[0], False, "signal_repeat"))
            for name, still, directory in jobs:
                command = [
                    sys.executable,
                    str(ROOT / "tools/storyboard.py"),
                    "render",
                    str(ROOT / f"examples/storyboards/{name}.json"),
                    "--output-dir",
                    str(proofs / directory),
                ] + (["--stills-only"] if still else [])
                rc, stdout, stderr = run_bounded(
                    command, timeout=180, max_bytes=65536, cancelled=monitor.cancelled
                )
                records.append(
                    dict(
                        command=command,
                        returncode=rc,
                        stdout=stdout.decode(),
                        stderr=stderr.decode(),
                    )
                )
                save(
                    OUT / "proof_execution.json",
                    {"policy": "One attempt per job; no retries", "jobs": records},
                )
        save(
            OUT / "review_job_resources.json",
            dict(
                scope=("Seven sequential CLI jobs: parent, compilation, render, encode and decode"),
                wall_seconds=time.perf_counter() - start,
                memory=monitor.report(),
            ),
        )
        if any(r["returncode"] for r in records):
            raise RuntimeError("Proof job failed; retained evidence, no automatic retry")
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    renderer = CairoRenderer()
    summaries, reports, cells = {}, {}, []
    with JobMonitor(workspace=OUT) as monitor:
        for name in NAMES:
            board = load_storyboard(ROOT / f"examples/storyboards/{name}.json")
            p = board.direction
            save(OUT / (name + "_compiled.json"), inspect_plans(board))
            save(OUT / (name + "_blocking.json"), json.loads(board.blocking_json))
            save(OUT / (name + "_direction.json"), json.loads(board.direction_json))
            frames, max_paths, max_ops, seen = [], 0, 0, {}
            movie = json.loads((proofs / (name + "_video") / "render_report.json").read_text())
            for f in range(90):
                d = inspect_frame(p, f)
                beat = next(b for b in board.beats if b.start <= f < b.end)
                d["beat"] = beat.id
                d["beat_type"] = beat.kind
                d["world_objects_sha256"] = hashlib.sha256(
                    json.dumps(
                        [
                            (
                                r.id,
                                r.world.x,
                                r.world.y,
                                r.world.scale,
                                r.world.angle,
                                r.depth,
                                r.layer,
                                r.visible,
                            )
                            for r in p.compiled.hierarchy
                            if r.kind != "character"
                        ],
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                cmd = direction_frame(p, f)
                paths, ops = cost(cmd)
                max_paths, max_ops = max(max_paths, paths), max(max_ops, ops)
                d["geometry_sha256"] = hashlib.sha256(repr(cmd).encode()).hexdigest()
                # Source world and accepted pose are independent of the selected shot.
                from reelforge.blocking.sampling import inspect_frame as motion_frame

                motion = motion_frame(p.blocking, f)
                d["motion_sha256"] = hashlib.sha256(
                    json.dumps(
                        {
                            k: motion[k]
                            for k in ("position", "velocity", "phase", "pose", "secondary")
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                frames.append(d)
            assert len({d["world_objects_sha256"] for d in frames}) == 1
            reports[name] = frames
            save(
                OUT / (name + "_frames.json"),
                dict(
                    units="World/logical: 360x640; output pixels = 2x logical; 30 FPS",
                    frames=frames,
                ),
            )
            checkpoints = sorted(
                {
                    0,
                    45,
                    89,
                    *[
                        max(0, min(89, s.start + delta))
                        for s in board.beats[1:]
                        for delta in (-1, 0, 1)
                    ],
                }
            )
            directory = proofs / (name + "_boundaries")
            directory.mkdir(exist_ok=diagnostics_only)
            for f in [89, 0, 45, 0, 89, *checkpoints]:
                with renderer.surface(720, 1280) as surface:
                    renderer.draw(
                        surface,
                        direction_frame(p, f),
                        background=color("243e49"),
                        logical_size=(360, 640),
                    )
                    digest = surface.pixel_sha256()
                    assert f not in seen or seen[f] == digest
                    assert movie["source_pixel_sha256"][str(f)] == digest
                    seen[f] = digest
                    if f in checkpoints:
                        surface.write_png(directory / f"frame_{f:03}.png")
            contact_sheet(
                [
                    (f"{name[:9]} / {f} / {frames[f]['beat']}", directory / f"frame_{f:03}.png")
                    for f in checkpoints
                ],
                OUT / (name + "_boundaries.png"),
                columns=3,
            )
            cells.extend(
                (name[:9] + f" / {f}", directory / f"frame_{f:03}.png") for f in (0, 45, 89)
            )
            pan_speed = zoom_speed = tracking = 0.0
            cuts = []
            for f, d in enumerate(frames):
                tracking = max(tracking, d["tracking_error_logical"])
                if not f:
                    continue
                a, b = frames[f - 1]["camera"], d["camera"]
                delta = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
                dz = abs(a["zoom"] - b["zoom"])
                if d["cut"]:
                    cuts.append(
                        dict(
                            frame=f,
                            pan_delta_logical=delta,
                            zoom_delta=dz,
                            previous_source=f - 1,
                            source=f,
                            world_delta=math.dist(d["actor_world"], frames[f - 1]["actor_world"]),
                            motion_clock_reset=False,
                        )
                    )
                else:
                    pan_speed, zoom_speed = max(pan_speed, delta * 30), max(zoom_speed, dz * 30)
            summaries[name] = dict(
                max_tracking_error_logical=tracking,
                max_tracking_error_output_pixels=2 * tracking,
                max_camera_step_speed_logical_per_second=pan_speed,
                max_zoom_step_speed_per_second=zoom_speed,
                cuts=cuts,
                maximum_paths=max_paths,
                maximum_ops=max_ops,
                nodes=len(p.compiled.hierarchy),
                instances=len(p.compiled.painter_ids),
                layers=len(direction_layers(p, 0)),
                max_foreground_bbox_overlap_upper=max(
                    d["foreground_bbox_overlap_upper"] for d in frames
                ),
                out_of_order_pixel_sha256=seen,
                encoded_fps=movie["encoded_fps"],
                sampled_render_peak_mib=movie["memory"][
                    "estimated_simultaneous_tree_peak_rss_bytes"
                ]
                / 1048576,
                render_and_decode_seconds=movie["wall_seconds"],
            )
    save(
        OUT / "camera_metrics.json",
        dict(
            predeclared=dict(
                tracking_error_logical=1e-7,
                max_pan_speed_logical_per_second=240,
                max_zoom_speed_per_second=1.5,
                safe_margin_logical=8,
                matched_cut_pan_logical=24,
                matched_cut_zoom=0.15,
                max_cut_zoom_ratio=1.8,
            ),
            studies=summaries,
            diagnostic_memory=monitor.report(),
        ),
    )
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    trajectory_chart(reports)
    beat_timeline()
    contact_sheet(cells, OUT / "studies_contact_sheet.png")
    a = json.loads((proofs / "silent_signal_video/render_report.json").read_text())
    b = json.loads((proofs / "signal_repeat/render_report.json").read_text())
    assert a["source_pixel_sha256"] == b["source_pixel_sha256"]
    assert a["verification"]["decoded_rgb_sha256"] == b["verification"]["decoded_rgb_sha256"]
    save(
        OUT / "repeat_consistency.json",
        dict(
            all_90_source_frames_equal=True,
            all_90_decoded_frames_equal=True,
            first_job_success=a["success"],
            repeat_job_success=b["success"],
        ),
    )
    print(json.dumps(summaries))


if __name__ == "__main__":
    main("--diagnostics-only" in sys.argv)
