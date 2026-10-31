"""JSON-only stdout for agents; no backend imports or implicit network access."""

import argparse
import json
from pathlib import Path

from reelforge import __version__
from reelforge.contracts.project import (
    MAX_INPUT_BYTES,
    MAX_ISSUES,
    MAX_NESTING,
    MAX_TOTAL_FRAMES,
    SCHEMA_VERSION,
    load_project,
    project_digest,
    project_schema,
    validate_project,
)
from reelforge.core.errors import InputError, Issue


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError(Issue("CLI_USAGE", "", message))


def main(argv: list[str] | None = None) -> int:
    parser = Parser(prog="reelforge", description="Phase 1 manifest tools; no renderer")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities", help="List implemented features and contract limits")
    commands.add_parser("schema", help="Print the local foundation JSON Schema")
    validate = commands.add_parser("validate", help="Validate a foundation manifest only")
    validate.add_argument("project", type=Path)
    try:
        args = parser.parse_args(argv)
        if args.command == "schema":
            result = project_schema()
        elif args.command == "capabilities":
            result = {
                "ok": True,
                "engine_version": __version__,
                "phase": 1,
                "schema_versions": [SCHEMA_VERSION],
                "commands": ["capabilities", "schema", "validate"],
                "render_available": False,
                "limits": {
                    "input_bytes": MAX_INPUT_BYTES,
                    "issues": MAX_ISSUES,
                    "nesting": MAX_NESTING,
                    "total_frames": MAX_TOTAL_FRAMES,
                },
                "profiles": {"preview_360p": [360, 640], "target_720p": [720, 1280]},
            }
        else:
            data = load_project(args.project)
            issues = validate_project(data)
            if issues:
                print(
                    json.dumps(
                        {"ok": False, "errors": [issue.as_dict() for issue in issues]},
                        sort_keys=True,
                    )
                )
                return 2
            result = {
                "ok": True,
                "schema_version": SCHEMA_VERSION,
                "manifest_sha256": project_digest(data),
                "scene_count": len(data["scenes"]),
                "total_frames": sum(scene["duration_frames"] for scene in data["scenes"]),
                "render_ready": False,
            }
        print(json.dumps(result, sort_keys=True))
        return 0
    except InputError as error:
        print(json.dumps({"ok": False, "errors": [error.issue.as_dict()]}, sort_keys=True))
        return 2
    except OSError:
        issue = Issue("INPUT_IO", "", "Cannot read manifest; check path and permissions")
        print(json.dumps({"ok": False, "errors": [issue.as_dict()]}, sort_keys=True))
        return 3
