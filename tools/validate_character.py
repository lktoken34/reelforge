"""Validate an experimental preset without importing native Cairo or changing episode CLI."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from reelforge.characters.presets import load_preset
from reelforge.core.errors import InputError
from reelforge.rendering.model import RenderError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preset", type=Path)
    args = parser.parse_args()
    try:
        preset = load_preset(args.preset)
    except (InputError, RenderError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error), "render_ready": False}))
        raise SystemExit(2) from error
    print(
        json.dumps(
            {
                "ok": True,
                "schema": "character-preset-0.1",
                "preset": asdict(preset),
                "render_ready": False,
                "scope": "Character preset validation only; no episode compilation",
            }
        )
    )


if __name__ == "__main__":
    main()
