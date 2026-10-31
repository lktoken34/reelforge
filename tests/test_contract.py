"""Behavioral checks for the public foundation boundary, not future rendering."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from reelforge.contracts.project import (
    MAX_INPUT_BYTES,
    load_project,
    project_digest,
    project_schema,
    validate_project,
)
from reelforge.core.errors import InputError

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/foundation/project.json"


@pytest.fixture
def manifest():
    return load_project(EXAMPLE)


def test_schema_and_example_agree(manifest):
    Draft202012Validator.check_schema(project_schema())
    assert validate_project(manifest) == []


@pytest.mark.parametrize(
    ("path", "value", "code", "pointer"),
    [
        (("schema_version",), "1.0", "SCHEMA_CONST", "/schema_version"),
        (("seed",), True, "SCHEMA_TYPE", "/seed"),
        (("seed",), -1, "SCHEMA_MINIMUM", "/seed"),
        (("seed",), 2147483648, "SCHEMA_MAXIMUM", "/seed"),
        (("output", "fps"), 60, "SCHEMA_ENUM", "/output/fps"),
        (("output", "profile"), "8k", "SCHEMA_ENUM", "/output/profile"),
        (("output", "magic"), True, "SCHEMA_ADDITIONALPROPERTIES", "/output"),
        (("project_id",), "bad\n", "SCHEMA_PATTERN", "/project_id"),
        (("project_id",), "unsafe/id", "SCHEMA_PATTERN", "/project_id"),
        (("scenes",), [], "SCHEMA_MINITEMS", "/scenes"),
        (("scenes", 0), [], "SCHEMA_TYPE", "/scenes/0"),
        (("scenes", 0, "duration_frames"), 0, "SCHEMA_MINIMUM", "/scenes/0/duration_frames"),
        (("scenes", 0, "duration_frames"), 1.5, "SCHEMA_TYPE", "/scenes/0/duration_frames"),
        (("scenes", 0, "duration_frames"), True, "SCHEMA_TYPE", "/scenes/0/duration_frames"),
        (("scenes", 0, "intent"), "  \n", "SCHEMA_PATTERN", "/scenes/0/intent"),
        (("scenes", 0, "intent"), "x" * 2001, "SCHEMA_MAXLENGTH", "/scenes/0/intent"),
    ],
)
def test_invalid_field_has_repair_location(manifest, path, value, code, pointer):
    target = manifest
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert any(issue.code == code and issue.path == pointer for issue in validate_project(manifest))


def test_duplicate_scene_ids(manifest):
    manifest["scenes"][1]["id"] = manifest["scenes"][0]["id"]
    assert validate_project(manifest)[0].code == "SCENE_ID_DUPLICATE"
    assert validate_project(manifest)[0].path == "/scenes/1/id"


def test_total_timeline_limit(manifest):
    manifest["scenes"] = [
        {"id": f"shot_{i}", "duration_frames": 1800, "intent": "Hold"} for i in range(11)
    ]
    assert validate_project(manifest)[0].code == "TIMELINE_LIMIT"
    manifest["scenes"].pop()
    assert validate_project(manifest) == []


def test_no_defaults_or_legacy_compatibility(manifest):
    del manifest["seed"]
    manifest["narration"] = "voice.wav"
    codes = {issue.code for issue in validate_project(manifest)}
    assert {"SCHEMA_REQUIRED", "SCHEMA_ADDITIONALPROPERTIES"} <= codes


def test_hash_is_stable_and_sensitive(manifest):
    reordered = dict(reversed(list(manifest.items())))
    assert project_digest(manifest) == project_digest(reordered)
    changed = copy.deepcopy(manifest)
    changed["seed"] += 1
    assert project_digest(manifest) != project_digest(changed)


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b'{"seed": 1, "seed": 2}', "JSON_DUPLICATE_KEY"),
        (b'{"seed": NaN}', "JSON_NONFINITE"),
        (b'{"seed": 1e309}', "JSON_NONFINITE"),
        (b'{"nested": [-1e309]}', "JSON_NONFINITE"),
        (b'{"seed": Infinity}', "JSON_NONFINITE"),
        (b'{"seed": -Infinity}', "JSON_NONFINITE"),
        (b"{", "JSON_INVALID"),
        (b"\xff", "JSON_INVALID"),
        (b"[" * 33 + b"]" * 33, "JSON_INVALID"),
        (b" " * (MAX_INPUT_BYTES + 1), "INPUT_TOO_LARGE"),
    ],
)
def test_loader_rejects_unusable_json(tmp_path, raw, code):
    path = tmp_path / "input.json"
    path.write_bytes(raw)
    with pytest.raises(InputError) as caught:
        load_project(path)
    assert caught.value.issue.code == code


def test_diagnostics_are_capped(manifest):
    manifest["scenes"] = [{"id": f"s_{i}", "duration_frames": 0, "intent": ""} for i in range(40)]
    issues = validate_project(manifest)
    assert 0 < len(issues) <= 32
    assert all(len(issue.message) <= 240 for issue in issues)


def test_input_not_mutated(manifest):
    before = json.dumps(manifest)
    validate_project(manifest)
    assert json.dumps(manifest) == before


def test_nesting_check_ignores_quoted_brackets(tmp_path, manifest):
    manifest["scenes"][0]["intent"] = "Brackets: [" * 40 + ' escaped quote: " and slash: \\'
    path = tmp_path / "quoted.json"
    path.write_text(json.dumps(manifest))
    assert validate_project(load_project(path)) == []


def test_finite_float_json_remains_accepted(tmp_path):
    path = tmp_path / "finite.json"
    path.write_text('{"x": 1e308, "y": 30.0, "z": 1e-309}')
    assert load_project(path) == {"x": 1e308, "y": 30.0, "z": 1e-309}
