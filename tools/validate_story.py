"""Validate experimental story JSON without Cairo, FFmpeg or renderer execution."""

import argparse
import json
from pathlib import Path

from reelforge.core.errors import InputError
from reelforge.stories.contract import load_story


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story", type=Path)
    args = parser.parse_args()
    try:
        story = load_story(args.story)
    except InputError as exc:
        print(json.dumps({"valid": False, "render_ready": False, "issue": exc.issue.as_dict()}))
        return 2
    except OSError as exc:
        print(
            json.dumps(
                {
                    "valid": False,
                    "render_ready": False,
                    "issue": {"code": "STORY_IO", "path": "", "message": str(exc)},
                }
            )
        )
        return 2
    print(
        json.dumps(
            {
                "valid": True,
                "render_ready": False,
                "scope": "experimental shot timeline",
                "schema_version": story.schema_version,
                "frames": story.output.frames,
                "shots": len(story.shots),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
