"""CLI smoke tests exercise installed entry points and observable JSON/exit behavior."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/foundation/project.json"


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "reelforge", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_capabilities_are_honest():
    result = run("capabilities")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["render_available"] is False
    assert data["commands"] == ["capabilities", "schema", "validate"]
    assert result.stderr == ""


def test_example_validation_is_reproducible():
    first = run("validate", EXAMPLE)
    second = run("validate", EXAMPLE)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    data = json.loads(first.stdout)
    assert data["total_frames"] == 150
    assert data["render_ready"] is False
    assert len(data["manifest_sha256"]) == 64


def test_schema_resource_is_available():
    result = run("schema")
    assert result.returncode == 0
    assert json.loads(result.stdout)["$id"] == "urn:reelforge:project:2.0-draft1"


@pytest.mark.parametrize("args", [[], ["render"], ["validate"], ["capabilities", "--magic"]])
def test_usage_errors_are_json(args):
    result = run(*args)
    assert result.returncode == 2
    assert json.loads(result.stdout)["errors"][0]["code"] == "CLI_USAGE"
    assert result.stderr == ""


def test_missing_file_is_distinct_io_error(tmp_path):
    result = run("validate", tmp_path / "missing.json")
    assert result.returncode == 3
    assert json.loads(result.stdout)["errors"][0]["code"] == "INPUT_IO"


def test_invalid_shape_is_not_traceback(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"scenes": [null]}')
    result = run("validate", path)
    assert result.returncode == 2
    assert json.loads(result.stdout)["ok"] is False
    assert result.stderr == ""


def test_help_is_conventional_text():
    result = run("--help")
    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_overflow_is_a_loader_error_before_schema_validation(tmp_path):
    path = tmp_path / "overflow.json"
    path.write_text('{"unknown": [1e309]}')
    result = run("validate", path)
    assert result.returncode == 2
    assert json.loads(result.stdout)["errors"][0]["code"] == "JSON_NONFINITE"
    assert result.stderr == ""
