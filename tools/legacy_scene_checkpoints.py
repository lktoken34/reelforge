"""Fixed full-resolution checkpoints, usable against an archived approved Python source tree."""

import argparse
import json
from pathlib import Path

from reelforge.characters.study import character_frame
from reelforge.environments.scene import environment_frame
from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
from reelforge.rendering.diagnostic import color
from reelforge.stories.contract import load_story
from reelforge.stories.sampling import story_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    story = load_story(root / "examples/stories/last_farm.json")
    renderer = CairoRenderer()
    result = {}
    for name, function, frames in (
        ("orchard", environment_frame, (0, 90, 179)),
        ("rowan", character_frame, (0, 74, 149)),
        ("story", lambda f: story_frame(story, f), (0, 119, 120, 239, 240, 359)),
    ):
        result[name] = {}
        for frame in frames:
            with renderer.surface(720, 1280) as surface:
                renderer.draw(
                    surface, function(frame), background=color("243e49"), logical_size=(360, 640)
                )
                result[name][str(frame)] = surface.pixel_sha256()
    assert renderer.active_surfaces == renderer.allocated_bytes == 0
    args.output.write_text(
        json.dumps({"versions": backend_versions(), "pixels": result}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
