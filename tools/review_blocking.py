"""Fixed Phase 6A studies, exact diagnostics and bounded public-CLI proof jobs."""

import hashlib
import json
import math
import resource
import sys
import time
from pathlib import Path

from reelforge.blocking.contract import load_blocking
from reelforge.blocking.sampling import blocking_frame, inspect_frame, sample
from reelforge.media.process import run_bounded
from reelforge.resources.monitor import JobMonitor
from reelforge.scenes.assets import cost

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase6a"
NAMES = ("woodland_traversal", "settlement_escape", "shelter_approach")


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def contact_sheet(cells, path, columns=3):
    import cairo

    w = 360 if columns == 3 else 240
    h = int(w * 1280 / 720) + 40
    surface = cairo.ImageSurface(
        cairo.FORMAT_ARGB32, columns * w, math.ceil(len(cells) / columns) * h
    )
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.06, 0.14, 0.18)
    ctx.paint()
    ctx.select_font_face("sans-serif")
    ctx.set_font_size(13)
    for i, (label, image) in enumerate(cells):
        x = i % columns * w
        y = i // columns * h
        ctx.set_source_rgb(0.91, 0.85, 0.7)
        ctx.move_to(x + 6, y + 23)
        ctx.show_text(label)
        src = cairo.ImageSurface.create_from_png(str(image))
        ctx.save()
        ctx.translate(x, y + 35)
        ctx.scale(w / 720, w / 720)
        ctx.set_source_surface(src)
        ctx.paint()
        ctx.restore()
        src.finish()
    surface.write_to_png(str(path))
    ctx = None
    surface.finish()


def route_diagram(plans):
    import cairo

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1080, 930)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(0.06, 0.14, 0.18)
    ctx.paint()
    ctx.select_font_face("sans-serif")
    for row, (name, p) in enumerate(plans.items()):
        top = 45 + row * 305
        ctx.set_font_size(19)
        ctx.set_source_rgb(0.91, 0.85, 0.7)
        ctx.move_to(45, top)
        ctx.show_text(name.replace("_", " ") + " / horizontal world support")

        def point(x, y, top=top):
            return 70 + 2.6 * x, top + 35 + (y - 420) * 0.9

        def box(bounds, color):
            left, t, r, b = bounds
            x, y = point(left, t)
            xx, yy = point(r, b)
            ctx.set_source_rgba(*color)
            ctx.rectangle(x, y, xx - x, yy - y)
            ctx.fill()

        box(p.support, (0.25, 0.38, 0.38, 0.8))
        box(p.corridor, (0.52, 0.62, 0.49, 0.6))
        for s in p.segments:
            x, y = point(s.x0, s.y)
            xx, yy = point(s.x1, s.y)
            ctx.set_source_rgb(0.9, 0.66, 0.35)
            ctx.set_line_width(3)
            ctx.move_to(x, y)
            ctx.line_to(xx, yy)
            ctx.stroke()
        for frame in (0, 30, 60, 89):
            d = inspect_frame(p, frame)
            x, y = point(*d["position"])
            ctx.set_source_rgb(0.92, 0.84, 0.65)
            ctx.arc(x, y, 4, 0, math.tau)
            ctx.fill()
            ctx.set_font_size(12)
            ctx.move_to(x - 10, y + 18 + (frame // 30 % 2) * 13)
            ctx.show_text(str(frame))
        ctx.set_font_size(12)
        ctx.set_source_rgb(0.8, 0.85, 0.8)
        ctx.move_to(70, top + 265)
        ctx.show_text(
            "Dark: support. Light: center corridor. Orange: route. No collision/pathfinding."
        )
    surface.write_to_png(str(OUT / "route_support.png"))
    ctx = None
    surface.finish()


def main(diagnostics_only=False):
    proofs = OUT / "proofs"
    proofs.mkdir(exist_ok=diagnostics_only)
    plans = {n: load_blocking(ROOT / f"examples/blocking/{n}.json") for n in NAMES}
    if not diagnostics_only:
        records = []
        started = time.perf_counter()
        cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
        with JobMonitor(workspace=OUT) as monitor:
            for name in NAMES:
                for still in (True, False):
                    command = [
                        sys.executable,
                        str(ROOT / "tools/blocking.py"),
                        "render",
                        str(ROOT / f"examples/blocking/{name}.json"),
                        "--output-dir",
                        str(proofs / (name + ("_stills" if still else "_video"))),
                    ] + (["--stills-only"] if still else [])
                    rc, stdout, stderr = run_bounded(
                        command, timeout=180, max_bytes=65536, cancelled=monitor.cancelled
                    )
                    records.append(
                        {
                            "command": command,
                            "returncode": rc,
                            "stdout": stdout.decode(),
                            "stderr": stderr.decode(),
                        }
                    )
                    save(
                        OUT / "proof_execution.json",
                        {
                            "scope": "One attempt per job; cleanup errors retained, no retry",
                            "jobs": records,
                        },
                    )
            command = [
                sys.executable,
                str(ROOT / "tools/blocking.py"),
                "render",
                str(ROOT / "examples/blocking/woodland_traversal.json"),
                "--output-dir",
                str(proofs / "woodland_repeat"),
            ]
            rc, stdout, stderr = run_bounded(
                command, timeout=180, max_bytes=65536, cancelled=monitor.cancelled
            )
            records.append(
                {
                    "command": command,
                    "returncode": rc,
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                }
            )
            save(
                OUT / "proof_execution.json",
                {"scope": "Three studies and one controlled repeat, no retries", "jobs": records},
            )
        end = resource.getrusage(resource.RUSAGE_CHILDREN)
        save(
            OUT / "review_job_resources.json",
            {
                "scope": "All seven public-CLI jobs including parent, planning and native children",
                "wall_seconds": time.perf_counter() - started,
                "children_cpu_seconds": end.ru_utime + end.ru_stime - cpu.ru_utime - cpu.ru_stime,
                "memory": monitor.report(),
            },
        )
    from reelforge.rendering.backends.cairo import CairoRenderer
    from reelforge.rendering.diagnostic import color

    renderer = CairoRenderer()
    summaries = {}
    cells = []
    with JobMonitor(workspace=OUT) as monitor:
        for name, p in plans.items():
            diag = []
            anchors = {}
            drift = contact_error = screen_error = turn_set = turn_labels = 0.0
            max_paths = max_ops = 0
            for f in range(90):
                d = inspect_frame(p, f)
                d["pose_sha256"] = hashlib.sha256(
                    json.dumps(d["pose"], sort_keys=True).encode()
                ).hexdigest()
                d["position_sha256"] = hashlib.sha256(
                    json.dumps(d["position"]).encode()
                ).hexdigest()
                commands = blocking_frame(p, f)
                d["geometry_sha256"] = hashlib.sha256(repr(commands).encode()).hexdigest()
                paths, ops = cost(commands)
                max_paths = max(max_paths, paths)
                max_ops = max(max_ops, ops)
                turn_set = max(turn_set, d["turn_contact_set_error_world"])
                turn_labels = max(turn_labels, d["turn_side_label_exchange_world"])
                for foot in d["contacts"]:
                    if foot["error"] is None:
                        continue
                    contact_error = max(contact_error, foot["error"])
                    screen_error = max(
                        screen_error, 2 * math.dist(foot["screen"], foot["expected_screen"])
                    )
                    if d["mode"] == "turn":
                        continue
                    key = (d["facing"], foot["side"], foot["cycle_start"], foot["state"])
                    if key in anchors:
                        drift = max(drift, math.dist(foot["world"], anchors[key]))
                    anchors[key] = foot["world"]
                diag.append(d)
            save(
                OUT / (name + "_frames.json"),
                {
                    "units": (
                        "World/logical coordinates; output pixels are twice "
                        "the projected logical coordinates"
                    ),
                    "frames": diag,
                },
            )
            boundaries = []
            for a, b in zip(p.segments, p.segments[1:], strict=False):
                t = b.start / 30
                left = sample(p, t - 1e-6)[2]
                right = sample(p, t + 1e-6)[2]
                boundaries.append(
                    {
                        "frame": b.start,
                        "position_residual": abs(a.position(t) - b.position(t)),
                        "velocity_residual": abs(a.velocity(t) - b.velocity(t)),
                        "epsilon_seconds": 1e-6,
                        "pose_root_span": math.hypot(
                            left.root.x - right.root.x, left.root.y - right.root.y
                        ),
                        "pose_angle_span": max(
                            abs(dict(left.angles).get(k, 0) - v) for k, v in right.angles
                        ),
                    }
                )
            heel_hits = [
                d["frame"]
                for d in diag
                if any(
                    foot["state"] == "heel"
                    and (d["frame"] == 0 or diag[d["frame"] - 1]["contacts"][i]["state"] != "heel")
                    for i, foot in enumerate(d["contacts"])
                )
            ][:2]
            checkpoints = sorted(
                set(
                    [0, 45, 89]
                    + ([74, 75, 76] if name == "shelter_approach" else [])
                    + [max(0, min(89, f + d)) for f in heel_hits for d in (-1, 0, 1)]
                    + [max(0, min(89, s.start + d)) for s in p.segments[1:] for d in (-1, 0, 1)]
                )
            )
            checkpoint_dir = proofs / (name + "_transitions")
            checkpoint_dir.mkdir(exist_ok=diagnostics_only)
            seen = {}
            for f in [89, 0, 45, 0, 89, *checkpoints]:
                commands = blocking_frame(p, f)
                with renderer.surface(720, 1280) as surface:
                    renderer.draw(
                        surface, commands, background=color("243e49"), logical_size=(360, 640)
                    )
                    digest = surface.pixel_sha256()
                    assert f not in seen or seen[f] == digest
                    seen[f] = digest
                    if f in checkpoints:
                        surface.write_png(checkpoint_dir / f"frame_{f:03}.png")
                original = json.loads(
                    (proofs / (name + "_video") / "render_report.json").read_text()
                )
                assert original["source_pixel_sha256"][str(f)] == digest
            contact_sheet(
                [(name[:9] + f" / {f}", checkpoint_dir / f"frame_{f:03}.png") for f in checkpoints],
                OUT / (name + "_transitions.png"),
                columns=4,
            )
            compact = sorted(
                set(
                    [0, 45, 89]
                    + [s.start + 1 for s in p.segments[1:]]
                    + ([75] if name == "shelter_approach" else [])
                )
            )
            cells.extend(
                (name[:9] + f" / {f}", checkpoint_dir / f"frame_{f:03}.png") for f in compact
            )
            summaries[name] = {
                "contact_error_world": contact_error,
                "stance_drift_world": drift,
                "camera_compensated_contact_error_output_pixels": screen_error,
                "turn_unordered_contact_set_error_world": turn_set,
                "turn_near_far_label_exchange_world": turn_labels,
                "turn_label_exchange_output_pixels": 2 * turn_labels,
                "boundary_metrics": boundaries,
                "maximum_paths": max_paths,
                "maximum_ops": max_ops,
                "node_count": len(p.compiled.scene.nodes),
                "instances": len(p.compiled.painter_ids),
                "path_allowance": p.compiled.path_allowance,
                "operation_allowance": p.compiled.operation_allowance,
                "out_of_order_pixel_sha256": seen,
                "deterministic": True,
            }
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    save(
        OUT / "motion_metrics.json",
        {
            "thresholds_predeclared": {
                "contact_error_world": 1e-7,
                "boundary_root_epsilon_span_rig": 0.005,
                "boundary_angle_epsilon_span_radians": 0.001,
            },
            "studies": summaries,
            "diagnostic_memory": monitor.report(),
        },
    )
    contact_sheet(
        [(n.replace("_", " "), proofs / (n + "_stills") / "frame_045.png") for n in NAMES],
        OUT / "studies_contact_sheet.png",
    )
    contact_sheet(cells, OUT / "motion_transitions.png", columns=4)
    route_diagram(plans)
    a = json.loads((proofs / "woodland_traversal_video/render_report.json").read_text())
    b = json.loads((proofs / "woodland_repeat/render_report.json").read_text())
    assert (
        a["source_pixel_sha256"] == b["source_pixel_sha256"]
        and a["verification"]["decoded_rgb_sha256"] == b["verification"]["decoded_rgb_sha256"]
    )
    save(
        OUT / "repeat_consistency.json",
        {
            "all_90_source_frames_equal": True,
            "all_90_decoded_frames_equal": True,
            "first_job_success": a["success"],
            "repeat_job_success": b["success"],
        },
    )


if __name__ == "__main__":
    main(diagnostics_only="--diagnostics-only" in sys.argv)
