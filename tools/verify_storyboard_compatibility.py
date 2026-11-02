"""Legacy pixel/audio checks and exact PTS/decode evidence for Phase 7A."""

import json
from pathlib import Path

from review_geometry import sheet

from reelforge.audio.processing import mix_pcm, verify_audio
from reelforge.audio.registry import AudioRegistry
from reelforge.audio.transaction import private_directory
from reelforge.characters.study import character_frame
from reelforge.environments.scene import environment_frame
from reelforge.media.process import run_bounded
from reelforge.media.verify import verify_video
from reelforge.procedural.compiler import compile_environment
from reelforge.procedural.contract import load_environment
from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.diagnostic import color
from reelforge.resources.monitor import JobMonitor
from reelforge.scenes.contract import load_scene
from reelforge.scenes.graph import compile_scene, scene_frame
from reelforge.stories.contract import load_story
from reelforge.stories.sampling import story_frame

root = Path(__file__).resolve().parents[1]
out = root / "artifacts/phase7a"
work = root / "outputs/phase7a-compatibility"
work.mkdir(exist_ok=False)
result = {
    "scope": ("Accepted pixels and original AV; full new MP4 decode; legacy artifacts unchanged"),
    "pixels": {},
    "new_video_decodes": {},
}
renderer = CairoRenderer()


def pixel(commands):
    with renderer.surface(720, 1280) as s:
        renderer.draw(s, commands, background=color("243e49"), logical_size=(360, 640))
        return s.pixel_sha256()


with JobMonitor(workspace=work) as monitor:
    for request in sorted((root / "examples/procedural").glob("*.json")):
        _, c = compile_environment(load_environment(request))
        old = json.loads(
            (root / f"artifacts/phase5b/{request.stem}/stills_report.json").read_text()
        )["source_pixel_sha256"]
        current = {str(f): pixel(scene_frame(c, f)) for f in (0, 45, 89)}
        assert current == old
        result["pixels"][request.stem] = current
    for name in ("rural_outpost", "tree_path", "barn_approach"):
        c = compile_scene(load_scene(root / f"examples/scenes/{name}.json"))
        old = json.loads((root / f"artifacts/phase5a/{name}/stills_report.json").read_text())[
            "source_pixel_sha256"
        ]
        current = {str(f): pixel(scene_frame(c, f)) for f in (0, 45, 89)}
        assert current == old
        result["pixels"][name] = current
    from reelforge.geometry.composition import compile_composition, load_composition

    for name in (
        "woodland_relay",
        "settlement_checkpoint",
        "shelter_supply",
        "orchard_checkpoint",
        "heldout_station",
    ):
        c = compile_composition(load_composition(root / f"examples/compositions/{name}.json"))
        old = json.loads(
            (root / f"artifacts/phase5c/proofs/{name}_stills/stills_report.json").read_text()
        )["source_pixel_sha256"]
        current = {str(f): pixel(scene_frame(c, f)) for f in (0, 45, 89)}
        assert current == old
        result["pixels"][name] = current
    story = load_story(root / "examples/stories/last_farm.json")
    old = json.loads((root / "artifacts/phase5b/legacy_current_pixels.json").read_text())["pixels"]
    for name, func, frames in [
        ("orchard", environment_frame, (0, 90, 179)),
        ("rowan", character_frame, (0, 74, 149)),
        ("story", lambda f: story_frame(story, f), (0, 119, 120, 239, 240, 359)),
    ]:
        current = {str(f): pixel(func(f)) for f in frames}
        assert current == old[name]
        result["pixels"][name] = current
    from reelforge.blocking.contract import load_blocking
    from reelforge.blocking.sampling import blocking_frame

    for name in ("woodland_traversal", "settlement_escape", "shelter_approach"):
        p = load_blocking(root / f"examples/blocking/{name}.json")
        old = json.loads(
            (root / f"artifacts/phase6a/proofs/{name}_video/render_report.json").read_text()
        )["source_pixel_sha256"]
        current = {str(f): pixel(blocking_frame(p, f)) for f in range(90)}
        assert current == old
        result["pixels"]["phase6a_" + name] = current
    from reelforge.direction.contract import load_direction
    from reelforge.direction.sampling import direction_frame

    for name in ("woodland_suspense", "settlement_escape", "shelter_discovery"):
        p = load_direction(root / f"examples/direction/{name}.json")
        old = json.loads(
            (root / f"artifacts/phase6b/proofs/{name}_video/render_report.json").read_text()
        )["source_pixel_sha256"]
        current = {str(f): pixel(direction_frame(p, f)) for f in range(90)}
        assert current == old
        result["pixels"]["phase6b_" + name] = current
    cells = []
    for name in (
        "silent_signal_video",
        "abandoned_settlement_video",
        "shelter_entrance_video",
        "signal_repeat",
    ):
        path = out / "proofs" / name / "scene.mp4"
        v = verify_video(path, width=720, height=1280, frames=90, cancelled=monitor.cancelled)
        old = json.loads((path.parent / "render_report.json").read_text())["verification"]
        assert v["decoded_rgb_sha256"] == old["decoded_rgb_sha256"]
        result["new_video_decodes"][name] = v
        from fractions import Fraction

        rc, raw, err = run_bounded(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=time_base:frame=best_effort_timestamp",
                "-of",
                "json",
                str(path),
            ],
            cancelled=monitor.cancelled,
        )
        assert rc == 0, err
        stamps = json.loads(raw)
        base = Fraction(stamps["streams"][0]["time_base"])
        pts = [int(f["best_effort_timestamp"]) * base for f in stamps["frames"]]
        assert pts == [Fraction(i, 30) for i in range(90)]
        v["all_90_pts_frame_exact"] = True
        if name == "signal_repeat":
            continue
        rc, _, err = run_bounded(
            [
                "ffmpeg",
                "-v",
                "error",
                "-threads",
                "1",
                "-i",
                str(path),
                "-vf",
                "select=eq(n\\,0)+eq(n\\,45)+eq(n\\,89)",
                "-fps_mode",
                "passthrough",
                "-threads",
                "1",
                str(work / (name + "-%02d.png")),
            ],
            cancelled=monitor.cancelled,
        )
        assert rc == 0, err
        cells.extend(
            (name[:10] + f" decoded / {f}", work / (name + f"-{i + 1:02d}.png"))
            for i, f in enumerate((0, 45, 89))
        )
    a = load_story(root / "examples/stories/last_farm_audio.json")
    registry = AudioRegistry(root / "assets/audio")
    with private_directory(work) as private:
        resolved = registry.resolve(a.audio, 360, cancelled=monitor.cancelled, workspace=private)
        reference = private / "reference.f32"
        decoded = private / "decoded.f32"
        mix_pcm(
            resolved,
            360,
            {r.asset.id: r.path for r in resolved},
            reference,
            cancelled=monitor.cancelled,
        )
        result["legacy_av"] = verify_audio(
            root / "artifacts/phase4a/story.mp4",
            root / "artifacts/phase4b/story.mp4",
            reference,
            decoded,
            resolved,
            360,
            cancelled=monitor.cancelled,
        )
    result["immediate_legacy_audio_cleanup"] = not private.exists()
    verify_video(
        out / "proofs/silent_signal_video/scene.mp4",
        width=720,
        height=1280,
        frames=90,
        cancelled=monitor.cancelled,
    )
    result["legacy_audio_cleanup_after_native_decode"] = not private.exists()
result["memory"] = monitor.report()
result["all_594_legacy_pixels_preserved"] = True
assert renderer.active_surfaces == renderer.allocated_bytes == 0
result["proof_cleanup_after_subsequent_native_work"] = {
    name: not list((out / "proofs" / name).glob(".reelforge-*"))
    for name in (
        "silent_signal_video",
        "abandoned_settlement_video",
        "shelter_entrance_video",
        "signal_repeat",
    )
}
sheet(cells, out / "decoded_contact_sheet.png")
(out / "compatibility_and_decode.json").write_text(json.dumps(result, indent=2) + "\n")
print(
    "594 legacy pixels and 360 new decoded frames match. AV onset errors:",
    [c["onset_error_samples"] for c in result["legacy_av"]["cue_timing"]],
)
print(
    "Audio cleanup immediate/later",
    result["immediate_legacy_audio_cleanup"],
    result["legacy_audio_cleanup_after_native_decode"],
)
