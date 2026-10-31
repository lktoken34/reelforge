"""Engineering-only static fixture generation; not installed as an agent command."""

import argparse
from pathlib import Path

from reelforge.rendering.backends.cairo import CairoRenderer
from reelforge.rendering.diagnostic import BACKGROUND, LOGICAL_SIZE, diagnostic_commands


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    renderer = CairoRenderer()
    commands = diagnostic_commands()
    for width, height in ((360, 640), (720, 1280)):
        path = args.output_dir / f"diagnostic_{width}x{height}.png"
        with renderer.surface(width, height) as target:
            renderer.draw(target, commands, background=BACKGROUND, logical_size=LOGICAL_SIZE)
            target.write_png(path)
            print(f"{path}: {target.pixel_sha256()}")
    assert renderer.allocated_bytes == renderer.active_surfaces == 0


if __name__ == "__main__":
    main()
