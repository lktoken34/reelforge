"""Minimal example: animate Yellow Mellow V2 through the public API only.

No rig, artwork or motion code is edited here; the example only lists actions. Run inside
WSL Ubuntu with pycairo available:

    python3 examples/characters/yellow_mellow_v2_example.py outputs/yellow_mellow_v2/example

It writes three PNG stills and a 3-second 720x1280 MP4 (90 frames) using the existing
ReelForge Cairo renderer and FFmpeg encoder.
"""

import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from reelforge.characters.yellow_mellow_v2 import ActionRequest, Stage, YellowMellowV2  # noqa: E402
from reelforge.characters.yellow_mellow_v2.environment import observatory_background  # noqa: E402
from reelforge.media.encoder import FFmpegEncoder  # noqa: E402
from reelforge.media.verify import verify_video  # noqa: E402
from reelforge.rendering.backends.cairo import CairoRenderer  # noqa: E402
from reelforge.rendering.diagnostic import color  # noqa: E402


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    mellow = YellowMellowV2(facing=0.25)
    show = mellow.animate(
        [
            ActionRequest("wave", 30, expression="happy", params={"hand": "near", "waves": 1.5}),
            ActionRequest("surprise", 15, expression="surprised"),
            ActionRequest("hands_up", 20, expression="excited"),
            ActionRequest("hands_down", 15, expression="happy"),
            ActionRequest("head_tilt", 10, expression="curious", params={"angle": -0.2}),
        ]
    )
    stage = Stage(x=180, ground_y=575, scale=2.3)
    renderer = CairoRenderer()
    background = color("060914")
    for frame in (10, 40, 60):
        with renderer.surface(720, 1280) as surface:
            commands = observatory_background(0.0, stage.ground_y) + show.draw(frame, stage)
            renderer.draw(surface, commands, background=background, logical_size=(360, 640))
            surface.write_png(out / f"example_{frame:03d}.png")
    mp4 = out / "yellow_mellow_v2_example.mp4"
    if mp4.exists():
        print("exists, not overwriting:", mp4)
        return
    cancelled = threading.Event()
    with FFmpegEncoder(mp4, width=720, height=1280, frames=show.frames, cancelled=cancelled) as enc:
        with renderer.surface(720, 1280) as surface:
            for frame in range(show.frames):
                commands = observatory_background(0.0, stage.ground_y) + show.draw(frame, stage)
                renderer.draw(surface, commands, background=background, logical_size=(360, 640))
                enc.write_surface(surface)
    result = verify_video(mp4, width=720, height=1280, frames=show.frames, cancelled=cancelled)
    print("frames", show.frames, "decoded", result["decoded_frames"], "->", mp4)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/yellow_mellow_v2/example"))
