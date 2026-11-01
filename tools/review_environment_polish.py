"""Phase 3B.1 bounded proof assembly; matched A/B excludes the separate suspense shot."""

import argparse
import hashlib
import json
import os
import signal
import tempfile
from dataclasses import replace
from pathlib import Path

from reelforge.characters.presets import CharacterPreset, sample_pose
from reelforge.characters.rowan import draw_character
from reelforge.characters.secondary import preset_secondary
from reelforge.characters.study import label
from reelforge.environments import artwork as art
from reelforge.environments import polish
from reelforge.environments.presets import EnvironmentPreset
from reelforge.environments.scene import camera_at, environment_frame, layers_at, transform_command
from reelforge.media.process import run_bounded
from reelforge.media.verify import verify_video
from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.diagnostic import color
from reelforge.rendering.model import DrawPath
from reelforge.resources.deployment import check_workspace, memory_observability
from reelforge.resources.monitor import JobMonitor, preflight_memory

ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "ef27965967e78c025a2526def415a22975e3b5c1"
BASELINE = ROOT / "artifacts/phase3b/orchard_cinematic.mp4"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(65536):
            h.update(block)
    return h.hexdigest()


def render_panels(
    renderer: CairoRenderer,
    directory: Path,
    filename: str,
    panels: tuple[tuple[str, tuple[DrawPath, ...]], ...],
    columns: int,
    *,
    scale: float = 1,
    labels: bool = True,
    cancelled=None,
) -> None:
    """Intrinsic surface clipping intersects viewport with every existing material clip.

    Native-free DrawPath has one clip. Tiling separate flattened proof cells avoids
    substituting a viewport clip for a material clip or allowing overscan to cross cells.
    Only proof PNGs are composed; the runtime environment never imports raster assets.
    """
    if not 1 <= len(panels) <= 10 or not 1 <= columns <= 5 or scale not in (1, 1.5):
        raise ValueError("Unsupported bounded proof layout")
    cw, ch = int(360 * scale), int(640 * scale)
    step = int((700 if labels else 640) * scale)
    width, height = columns * cw, ((len(panels) + columns - 1) // columns) * step
    with tempfile.TemporaryDirectory(prefix=".reelforge-panels-", dir=directory) as temp:
        temp = Path(temp)
        command = ["ffmpeg", "-nostdin", "-v", "error"]
        titles = []
        layout = []
        for i, (name, commands) in enumerate(panels):
            cell = temp / f"cell_{i}.png"
            with renderer.surface(cw, ch) as surface:
                renderer.draw(
                    surface, commands, background=color("233c40"), logical_size=(360, 640)
                )
                surface.write_png(cell)
            command += ["-threads", "1", "-i", str(cell)]
            x, y = i % columns * cw, i // columns * step
            layout.append(f"{x}_{y}")
            if labels:
                titles.extend(
                    label(name, x + 12 * scale, y + 661 * scale, 1.4 * scale, color("e8d2a9"))
                )
        if labels:
            title_file = temp / "titles.png"
            with renderer.surface(width, height) as surface:
                renderer.draw(
                    surface,
                    tuple(titles),
                    background=color("132c32", 0),
                    logical_size=(width, height),
                )
                surface.write_png(title_file)
            command += ["-threads", "1", "-i", str(title_file)]
        n = len(panels)
        graph = "".join(f"[{i}:v]" for i in range(n))
        graph += (
            f"xstack=inputs={n}:layout={'|'.join(layout)}:fill=0x233c40,"
            f"pad={width}:{height}:0:0:color=0x132c32"
        )
        if labels:
            graph += f"[cells];[cells][{n}:v]overlay=0:0[out]"
        else:
            graph += "[out]"
        command += [
            "-filter_complex_threads",
            "1",
            "-filter_complex",
            graph,
            "-map",
            "[out]",
            "-frames:v",
            "1",
            "-threads:v",
            "1",
            "-y",
            str(directory / filename),
        ]
        rc, _, err = run_bounded(command, timeout=60, max_bytes=65536, cancelled=cancelled)
        if rc:
            raise RuntimeError(err.decode(errors="replace"))


def draw_sheets(directory: Path) -> dict:
    check_workspace(directory)
    preflight_memory()
    renderer = CairoRenderer()
    with JobMonitor(workspace=directory) as monitor:
        p = EnvironmentPreset()
        depth = tuple(
            (layer.id.replace("_", " ").upper(), environment_frame(90, only_layer=layer.id))
            for layer in layers_at(p, 90)
        )
        render_panels(
            renderer, directory, "depth_breakdown.png", depth, 5, cancelled=monitor.cancelled
        )
        contact = tuple(("", environment_frame(frame)) for frame in (0, 90, 179))
        render_panels(
            renderer,
            directory,
            "camera_contact_sheet.png",
            contact,
            3,
            labels=False,
            cancelled=monitor.cancelled,
        )
        with renderer.surface(1080, 1920) as surface:
            renderer.draw(
                surface, environment_frame(90), background=color("243e49"), logical_size=(360, 640)
            )
            surface.write_png(directory / "hero_1080x1920.png")
        p = EnvironmentPreset()
        cp = CharacterPreset(action="look_around", expression="concerned")
        rowan = draw_character(
            sample_pose(cp, 3),
            position=(165, 498),
            scale=0.69,
            expression=cp.expression,
            secondary=preset_secondary(cp, 3),
        )
        camera = camera_at(p, 90)
        light = tuple(
            transform_command(c, camera.transform(0.85))
            for c in art.placed(polish.barn_light(p.warmth), 257, 405, 0.91)
        )
        light += environment_frame(90, only_layer="door_light")
        haze = tuple(
            transform_command(c, camera.transform(0.18)) for c in polish.haze(p.atmosphere)
        )
        panels = (
            ("COOL AMBIENT", environment_frame(90, replace(p, warmth=0, atmosphere=0))),
            ("WARMTH AND HAZE", environment_frame(90)),
            ("SURFACE LIGHT", light),
            ("VALLEY HAZE", haze),
            ("ROWAN MATERIALS", tuple(transform_command(c, camera.transform(1)) for c in rowan)),
            ("ROWAN IN DUSK", environment_frame(90, only_layer="rowan")),
        )
        render_panels(
            renderer,
            directory,
            "lighting_atmosphere_breakdown.png",
            panels,
            3,
            scale=1.5,
            cancelled=monitor.cancelled,
        )
        suspense = EnvironmentPreset(shot="orchard_suspense")
        contact = tuple(("", environment_frame(frame, suspense)) for frame in (0, 90, 179))
        render_panels(
            renderer,
            directory,
            "suspense_contact_sheet.png",
            contact,
            3,
            labels=False,
            cancelled=monitor.cancelled,
        )
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    metrics = monitor.report()
    metrics["encoder_peak_rss_bytes"] = None
    metrics["root_role"] = "proof utility; sequential PNG tiling children, not a video encoder"
    return metrics


def comparison(after: Path, directory: Path) -> dict:
    """Same bounded FFmpeg hstack procedure as the accepted character review utility."""
    preflight_memory()
    output = directory / "before_after.mp4"
    with JobMonitor(workspace=directory) as monitor:
        before = verify_video(
            BASELINE, width=720, height=1280, frames=180, cancelled=monitor.cancelled
        )
        refined = verify_video(
            after, width=720, height=1280, frames=180, cancelled=monitor.cancelled
        )
        with tempfile.TemporaryDirectory(prefix=".reelforge-comparison-", dir=directory) as temp:
            pending = Path(temp) / "pending.mp4"
            command = [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-threads",
                "1",
                "-i",
                str(BASELINE),
                "-threads",
                "1",
                "-i",
                str(after),
                "-filter_complex_threads",
                "1",
                "-filter_complex",
                "[0:v]setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]hstack=inputs=2[v]",
                "-map",
                "[v]",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-threads:v",
                "1",
                "-x264-params",
                "rc-lookahead=0:sync-lookahead=0:bframes=0",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-frames:v",
                "180",
                "-r",
                "30",
                "-f",
                "mp4",
                str(pending),
            ]
            rc, _, errors = run_bounded(
                command, timeout=120, max_bytes=65536, cancelled=monitor.cancelled
            )
            if rc:
                raise RuntimeError(errors.decode(errors="replace"))
            verification = verify_video(
                pending, width=1440, height=1280, frames=180, cancelled=monitor.cancelled
            )
            with pending.open("rb") as handle:
                os.fsync(handle.fileno())
            os.link(pending, output)
            pending.unlink()
        # Exact source stills, no scaling or color adjustment in either A/B panel.
        rc, _, errors = run_bounded(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-threads",
                "1",
                "-i",
                str(ROOT / "artifacts/phase3b/frame_090.png"),
                "-threads",
                "1",
                "-i",
                str(directory / "frame_090.png"),
                "-filter_complex_threads",
                "1",
                "-filter_complex",
                "hstack=inputs=2",
                "-frames:v",
                "1",
                "-threads:v",
                "1",
                str(directory / "before_after.png"),
            ],
            timeout=30,
            cancelled=monitor.cancelled,
        )
        if rc:
            raise RuntimeError(errors.decode(errors="replace"))
    observability = memory_observability(monitor.initial, monitor.final)
    if observability["oom_events_changed"] or not monitor.oom_telemetry_continuous:
        raise RuntimeError("Comparison memory telemetry did not remain sufficient")
    metrics = monitor.report()
    metrics["encoder_peak_rss_bytes"] = None
    metrics["root_role"] = (
        "comparison utility; sequential media children, encoder PID not registered"
    )
    return {
        "scope": "Left: unchanged Phase 3B; right: Phase 3B.1; identical orchard_push camera",
        "baseline_commit": BASELINE_COMMIT,
        "baseline_sha256": digest(BASELINE),
        "after_sha256": digest(after),
        "same_resolution_per_panel": [720, 1280],
        "same_frames": 180,
        "same_fps": 30,
        "before_verification": before,
        "after_verification": refined,
        "comparison_verification": verification,
        "whole_job_memory": metrics,
        "memory_observability": observability,
        "artistic_approval": False,
        "deployment_gate_approved": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)

    def interrupt(signum, frame):
        raise KeyboardInterrupt("Environment review interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    sheet_memory = draw_sheets(directory)
    result = comparison(directory / "orchard_cinematic.mp4", directory)
    result["proof_sheet_memory"] = sheet_memory
    (directory / "comparison_report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparison": True, "sheets": True}))


if __name__ == "__main__":
    main()
