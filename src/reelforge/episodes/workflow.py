"""One continuous silent encode, one global PCM mix and accepted audiovisual transaction."""

import time
from pathlib import Path
from threading import Event

from reelforge.core.errors import OperationError
from reelforge.direction.sampling import direction_frame
from reelforge.reels.workflow import cancelled_check, render_av

from .contract import Episode, frame_origin


def render_episode_video(
    plan: Episode, output: Path, *, encoder_staging: Path, cancelled: Event
) -> dict:
    from reelforge.media.encoder import FFmpegEncoder
    from reelforge.media.verify import verify_video
    from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
    from reelforge.rendering.diagnostic import color
    from reelforge.scenes.assets import cost

    output.mkdir(exist_ok=False)
    started = time.perf_counter()
    renderer = CairoRenderer()
    source = {}
    max_paths = max_ops = 0
    with FFmpegEncoder(
        output / "scene.mp4",
        width=720,
        height=1280,
        frames=plan.frames,
        staging_directory=encoder_staging,
        cancelled=cancelled,
        timeout=300,
    ) as encoder:
        with renderer.surface(720, 1280) as surface:
            for frame in range(plan.frames):
                cancelled_check(cancelled)
                segment, local = frame_origin(plan, frame)
                commands = direction_frame(segment.storyboard.direction, local)
                paths, ops = cost(commands)
                max_paths, max_ops = max(max_paths, paths), max(max_ops, ops)
                renderer.draw(
                    surface, commands, background=color("243e49"), logical_size=(360, 640)
                )
                source[str(frame)] = surface.pixel_sha256()
                encoder.write_surface(surface)
    encoded_seconds = time.perf_counter() - started
    verification = verify_video(
        output / "scene.mp4", width=720, height=1280, frames=plan.frames, cancelled=cancelled
    )
    if renderer.active_surfaces or renderer.allocated_bytes:
        raise OperationError("SURFACE_LEAK", "Episode retained a Cairo surface")
    return {
        "success": True,
        "frames": plan.frames,
        "versions": backend_versions(),
        "source_pixel_sha256": source,
        "verification": verification,
        "encoded_fps": plan.frames / encoded_seconds,
        "render_encode_seconds": encoded_seconds,
        "maximum_paths": max_paths,
        "maximum_ops": max_ops,
        "live_surfaces_after": 0,
        "surface_bytes_after": 0,
        "encoder_cleanup_deferred_to_job_owner": True,
        "editorial_cuts": [90 * i for i in range(1, len(plan.segments))],
        "encoding": (
            "One continuous stream; absolute video PTS, local storyboard clocks at explicit cuts"
        ),
    }


def render_episode(
    plan: Episode, output: Path, *, registry_root: Path, cancelled: Event | None = None
) -> dict:
    return render_av(
        plan,
        output,
        frames=plan.frames,
        visual_plan=plan,
        render_silent=render_episode_video,
        registry_root=registry_root,
        cancelled=cancelled,
        contract_version="episode-0.2" if plan.silent else "episode-0.1",
        silent=plan.silent,
    )
