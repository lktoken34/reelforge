"""Bounded storyboard/boundary proofs, exact timeline diagram and full repeat verification."""

import argparse
import json
import signal
from html import escape
from pathlib import Path

from render_story import render
from review_environment_polish import render_panels

from reelforge.environments.presets import EnvironmentPreset
from reelforge.environments.scene import environment_frame
from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
from reelforge.rendering.diagnostic import color
from reelforge.resources.deployment import check_workspace
from reelforge.resources.monitor import JobMonitor, preflight_memory
from reelforge.stories.contract import Story, load_story
from reelforge.stories.sampling import sample_story, story_frame


def timeline_svg(story: Story) -> str:
    colors = ("#b69b6c", "#879c83", "#52797a")
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300">',
        '<rect width="1200" height="300" fill="#142c34"/>',
        f'<text x="50" y="40" fill="#eddbb5" font-size="23">{escape(story.title)}</text>',
    ]
    for i, shot in enumerate(story.shots):
        x = 60 + 1080 * shot.start_frame / story.output.frames
        w = 1080 * shot.frames / story.output.frames
        svg.extend(
            [
                f'<rect x="{x}" y="90" width="{w - 2}" height="90" fill="{colors[i % 3]}"/>',
                f'<text x="{x + 10}" y="119" fill="#142c34" font-size="17">'
                f"{escape(shot.camera.replace('_', ' '))}</text>",
                f'<text x="{x + 10}" y="151" fill="#142c34" font-size="16">'
                f"[{shot.start_frame}, {shot.end_frame})</text>",
                f'<text x="{x}" y="215" fill="#eddbb5" font-size="17">'
                f"{shot.start_frame} / {shot.start_frame / 30:.2f}s</text>",
            ]
        )
    svg.extend(
        [
            '<text x="1140" y="215" text-anchor="end" fill="#eddbb5" font-size="17">'
            f"{story.output.frames} / {story.output.frames / 30:.2f}s</text>",
            '<text x="60" y="265" fill="#a5bbb2" font-size="17">'
            "30 FPS · integer frames · end-exclusive intervals · hard cuts · no audio</text>",
            "</svg>",
        ]
    )
    return "\n".join(svg) + "\n"


def proofs(story: Story, directory: Path) -> dict:
    check_workspace(directory)
    preflight_memory()
    renderer = CairoRenderer()
    with JobMonitor(workspace=directory) as monitor:
        representatives = [s.start_frame + s.frames // 2 for s in story.shots]
        boundaries = {0, story.output.frames - 1}
        boundaries.update(s.start_frame for s in story.shots[1:])
        boundaries.update(s.start_frame - 1 for s in story.shots[1:])
        for frame in sorted(set(representatives) | boundaries):
            with renderer.surface(720, 1280) as surface:
                renderer.draw(
                    surface,
                    story_frame(story, frame),
                    background=color("243e49"),
                    logical_size=(360, 640),
                )
                surface.write_png(directory / f"frame_{frame:03}.png")
        panels = tuple(
            (sample_story(story, f).shot.camera.replace("_", " ").upper(), story_frame(story, f))
            for f in representatives
        )
        render_panels(
            renderer,
            directory,
            "storyboard.png",
            panels,
            min(3, len(panels)),
            cancelled=monitor.cancelled,
        )
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    (directory / "timeline.svg").write_text(timeline_svg(story))
    report = monitor.report()
    report["encoder_peak_rss_bytes"] = None
    report["root_role"] = "storyboard utility; sequential PNG composition children"
    return report


def compatibility(before_path: Path, directory: Path) -> None:
    before = json.loads(before_path.read_text())
    renderer, hashes = CairoRenderer(), {}
    for key in before["hashes"]:
        shot, frame = key.split(":")
        with renderer.surface(720, 1280) as surface:
            renderer.draw(
                surface,
                environment_frame(int(frame), EnvironmentPreset(shot=shot)),
                background=color("243e49"),
                logical_size=(360, 640),
            )
            hashes[key] = surface.pixel_sha256()
    match = before["hashes"] == hashes
    report = {
        "approved_base_commit": "b8aa300b06e1123eeafd300f87fa553d34b58e3d",
        "before_versions": before["versions"],
        "after_versions": backend_versions(),
        "all_16_legacy_checkpoints_equal": match,
        "before": before["hashes"],
        "after": hashes,
        "scope": "Same-host/native build, captured before and after the clock refactor",
    }
    (directory / "compatibility_report.json").write_text(json.dumps(report, indent=2) + "\n")
    if not match:
        raise RuntimeError("Legacy environment pixels changed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeat-dir", type=Path)
    parser.add_argument("--legacy-before", type=Path)
    args = parser.parse_args()

    def interrupt(signum, frame):
        raise KeyboardInterrupt("Story review interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    story = load_story(args.story)
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    memory = proofs(story, directory)
    (directory / "proof_report.json").write_text(json.dumps(memory, indent=2) + "\n")
    if args.legacy_before:
        compatibility(args.legacy_before, directory)
    if args.repeat_dir:
        first = json.loads((directory / "report.json").read_text())
        second = render(story, args.repeat_dir)
        source = first["source_surface_sha256"] == second["source_surface_sha256"]
        decoded = (
            first["verification"]["decoded_rgb_sha256"]
            == second["verification"]["decoded_rgb_sha256"]
        )
        if not source or not decoded or first["story_digest"] != second["story_digest"]:
            raise RuntimeError("Story repeat differs")
        result = {
            "all_source_frames_equal": source,
            "all_decoded_frames_equal": decoded,
            "frames": story.output.frames,
            "repeat_render_encode_seconds": second["render_encode_seconds"],
            "repeat_whole_job_memory": second["whole_job_memory"],
            "repeat_cpu_seconds": second["cpu_seconds"],
            "scope": "Exact same-host/native source and decoded pixels; not codec byte identity",
        }
        (directory / "repeat_consistency.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"proofs": True, "repeat": bool(args.repeat_dir)}))


if __name__ == "__main__":
    main()
