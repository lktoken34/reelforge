"""Pure global-frame lookup and bounded composition; no accumulation or native objects."""

from dataclasses import dataclass

from reelforge.characters.presets import smooth
from reelforge.environments.scene import Camera, compose_layers, transform_command
from reelforge.rendering.model import DrawPath, RenderError, finite

from .contract import Shot, Story


@dataclass(frozen=True)
class Sample:
    shot: Shot
    global_frame: int
    local_frame: int
    progress: float
    action_seconds: float
    environment_seconds: float
    camera: Camera


def shot_camera(shot: Shot, progress: float) -> Camera:
    # Values are trusted catalog recipes; JSON cannot supply camera equations or transforms.
    finite(progress)
    if not 0 <= progress <= 1:
        raise RenderError("Camera progress must be in [0, 1]")
    u = smooth(progress)
    offset = shot.environment.framing * 8
    if shot.camera == "establishing_wide":
        return Camera(-4 + 5 * u + offset, -u, 0.95 + 0.08 * u)
    if shot.camera == "character_reaction":
        return Camera(25 + 4 * u + offset, 28 + 4 * u, 1.72 + 0.16 * u)
    if shot.camera == "suspense_reveal":
        v = smooth(max(0, min(1, (progress - 0.1) / 0.8)))
        return Camera(70 + 24 * v + offset, 35 + 7 * v, 2.05 + 0.25 * v)
    raise RenderError("Unsupported trusted story camera")


def sample_story(story: Story, frame: int) -> Sample:
    if type(frame) is not int or not 0 <= frame < story.output.frames:
        raise RenderError(f"Story frame must be an integer in [0, {story.output.frames - 1}]")
    for shot in story.shots:  # At most eight shots; no frame-index table or mutable cursor.
        if shot.start_frame <= frame < shot.end_frame:
            local = frame - shot.start_frame
            progress = local / (shot.frames - 1)
            return Sample(
                shot, frame, local, progress, local / 30, frame / 30, shot_camera(shot, progress)
            )
    raise RenderError("Unvalidated story has an uncovered frame")


def story_frame(story: Story, frame: int) -> tuple[DrawPath, ...]:
    sample = sample_story(story, frame)
    layers = compose_layers(
        sample.shot.environment,
        sample.camera,
        sample.environment_seconds,
        sample.shot.character,
        acting_seconds=sample.action_seconds,
    )
    return tuple(
        transform_command(command, sample.camera.transform(layer.depth))
        for layer in layers
        for command in layer.commands
    )
