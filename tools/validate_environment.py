"""Validate experimental environment data without loading Cairo; no episode rendering."""

import argparse
import json
from pathlib import Path

from reelforge.core.errors import InputError
from reelforge.environments.presets import load_preset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preset", type=Path)
    args = parser.parse_args()
    try:
        load_preset(args.preset)
    except (ValueError, InputError, OSError) as exc:
        print(json.dumps({"valid": False, "error": str(exc), "render_ready": False}))
        return 1
    print(json.dumps({"valid": True, "render_ready": False, "scope": "environment study only"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
