"""Foundation manifest validation. Validation does not interpret or execute intent."""

import hashlib
import json
import math
from importlib.resources import files
from itertools import islice
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from reelforge.core.errors import InputError, Issue

SCHEMA_VERSION = "2.0-draft1"
MAX_INPUT_BYTES = 1_048_576
MAX_NESTING = 32
MAX_ISSUES = 32
MAX_TOTAL_FRAMES = 18_000


def project_schema() -> dict[str, Any]:
    resource = files("reelforge.contracts").joinpath("project.schema.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(Issue("JSON_DUPLICATE_KEY", "", "Duplicate object key is forbidden"))
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise InputError(Issue("JSON_NONFINITE", "", f"Non-finite number {value} is forbidden"))


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise InputError(Issue("JSON_NONFINITE", "", "Numeric overflow is forbidden"))
    return number


def _check_nesting(text: str) -> None:
    """Bound container nesting before parsing; ignore brackets inside JSON strings."""
    depth = 0
    quoted = False
    escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_NESTING:
                raise InputError(Issue("JSON_INVALID", "", "JSON nesting exceeds 32 containers"))
        elif char in "]}":
            depth -= 1


def load_project(path: Path) -> Any:
    # Bounded read also covers files growing after stat; no asset/file references are followed.
    with path.open("rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise InputError(Issue("INPUT_TOO_LARGE", "", "Manifest exceeds 1048576 bytes"))
    try:
        text = raw.decode("utf-8")
        _check_nesting(text)
        return json.loads(
            text, object_pairs_hook=_object, parse_constant=_nonfinite, parse_float=_finite_float
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, InputError):
            raise
        raise InputError(Issue("JSON_INVALID", "", "Expected bounded, valid UTF-8 JSON")) from error


def _pointer(parts: Any) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def validate_project(data: Any) -> list[Issue]:
    validator = Draft202012Validator(project_schema())
    issues = [
        Issue(
            f"SCHEMA_{error.validator.upper()}", _pointer(error.absolute_path), error.message[:240]
        )
        for error in islice(validator.iter_errors(data), MAX_ISSUES)
    ]
    if issues:
        return sorted(issues, key=lambda item: (item.path, item.code, item.message))
    seen: set[str] = set()
    for index, scene in enumerate(data["scenes"]):
        if scene["id"] in seen:
            issues.append(
                Issue("SCENE_ID_DUPLICATE", f"/scenes/{index}/id", "Use a unique scene ID")
            )
        seen.add(scene["id"])
    if sum(scene["duration_frames"] for scene in data["scenes"]) > MAX_TOTAL_FRAMES:
        issues.append(Issue("TIMELINE_LIMIT", "/scenes", "Total duration exceeds 18000 frames"))
    return issues[:MAX_ISSUES]


def project_digest(data: Any) -> str:
    """Stable for identical JSON values and numeric forms, regardless of object key order."""
    canonical = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()
