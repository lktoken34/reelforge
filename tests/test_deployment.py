"""Deployment refusal/recovery contracts use mocked scarcity, never host memory pressure."""

import hashlib
import importlib
import json
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from reelforge.core.errors import OperationError
from reelforge.resources import deployment, monitor

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

cloud_validate = importlib.import_module("cloud_validate")
deployment_check = importlib.import_module("deployment_check")
wheelhouse = importlib.import_module("wheelhouse")


@pytest.fixture
def persistent_workspace():
    parent = Path(__file__).resolve().parents[1] / "outputs"
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="deploy-test-", dir=parent) as directory:
        yield Path(directory)


def fake_wheel(directory, name, version="1.0"):
    path = directory / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{name}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        )
    return path


@pytest.fixture
def sealed(tmp_path):
    for name in ("reelforge_v2", "pycairo", "jsonschema"):
        fake_wheel(tmp_path, name)
    wheelhouse.seal(tmp_path)
    return tmp_path


def test_sealed_wheels_are_stream_hash_verified(sealed):
    result = wheelhouse.verify(sealed)
    assert len(result["files"]) == 3
    assert "--hash=sha256:" in (sealed / "requirements.lock").read_text()


def test_changed_wheel_rejected(sealed):
    path = next(sealed.glob("*.whl"))
    with path.open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        wheelhouse.verify(sealed)


def test_unlisted_wheel_rejected(sealed):
    fake_wheel(sealed, "unexpected")
    with pytest.raises(ValueError, match="unlisted"):
        wheelhouse.verify(sealed)


def test_manifest_path_traversal_rejected(sealed):
    p = sealed / "manifest.json"
    data = json.loads(p.read_text())
    data["files"][0]["file"] = "../escape.whl"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unsafe"):
        wheelhouse.verify(sealed)


def test_even_rehashed_remote_requirement_is_rejected(sealed):
    lock = sealed / "requirements.lock"
    lock.write_text("unexpected @ https://example.invalid/file.whl\n")
    p = sealed / "manifest.json"
    data = json.loads(p.read_text())
    data["requirements_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="exactly the sealed"):
        wheelhouse.verify(sealed)


def test_existing_environment_never_overwritten(sealed, tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="never overwritten"):
        wheelhouse.install(sealed, existing)


def test_duplicate_distributions_rejected(tmp_path):
    for name in ("reelforge_v2", "pycairo", "jsonschema"):
        fake_wheel(tmp_path, name)
    fake_wheel(tmp_path, "pycairo", "2.0")
    with pytest.raises(ValueError, match="one wheel"):
        wheelhouse.seal(tmp_path)


def test_low_disk_refuses_before_write_probe(persistent_workspace, monkeypatch):
    monkeypatch.setattr(
        deployment.shutil, "disk_usage", lambda p: SimpleNamespace(free=1, total=100)
    )
    with pytest.raises(OperationError) as caught:
        deployment.check_workspace(persistent_workspace)
    assert caught.value.code == "DISK_PREFLIGHT"
    assert not list(persistent_workspace.iterdir())


def test_tmp_is_not_a_deployment_workspace():
    with pytest.raises(OperationError) as caught:
        deployment.check_workspace(Path("/tmp/project"))
    assert caught.value.code == "WORKSPACE_TMP"


def test_ordinary_workspace_probe_cleans_up(persistent_workspace):
    result = deployment.check_workspace(persistent_workspace)
    assert result["write_probe"] and result["root_not_required"]
    assert not list(persistent_workspace.iterdir())


def test_low_memory_doctor_never_starts_native_probes(persistent_workspace, monkeypatch):
    monkeypatch.setattr(
        deployment_check,
        "memory_snapshot",
        lambda **kwargs: {"effective_available_bytes": 319 * monitor.MIB},
    )

    def forbid(*args, **kwargs):
        raise AssertionError("Native process should not start under memory refusal")

    monkeypatch.setattr(deployment_check, "run_bounded", forbid)
    result = deployment_check.inspect_deployment(persistent_workspace)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "MEMORY_PREFLIGHT"
    assert result["target_vm_verified"] is False


def test_missing_media_tools_have_actionable_errors(persistent_workspace, monkeypatch):
    monkeypatch.setattr(deployment_check.shutil, "which", lambda name: None)
    result = deployment_check.inspect_deployment(persistent_workspace)
    assert any(e["code"] == "MEDIA_TOOL_MISSING" for e in result["errors"])
    assert result["target_vm_verified"] is False


def test_cgroup_access_is_not_assumed_delegation(persistent_workspace):
    (persistent_workspace / "cgroup.controllers").write_text("cpu memory")
    result = deployment.cgroup_capabilities({"cgroup_root": str(persistent_workspace)})
    assert result["delegation"] == "not_assumed"
    assert result["controls_modified"] is False
    assert result["hard_enforcement"] == "not_configured"


def test_oom_event_deltas_and_unavailable_counts():
    a = {"cgroup": {"memory.events": "oom 1\noom_kill 0"}}
    b = {"cgroup": {"memory.events": "oom 2\noom_kill 1"}}
    assert deployment.event_delta(a, b) == {"oom": 1, "oom_kill": 1}
    assert deployment.event_delta(a, {"cgroup": {}}) is None


def test_workspace_lock_refuses_competing_validation(persistent_workspace):
    with cloud_validate.workspace_lock(persistent_workspace):
        with pytest.raises(OperationError) as caught:
            with cloud_validate.workspace_lock(persistent_workspace):
                pass
    assert caught.value.code == "VALIDATION_BUSY"


def test_supervisor_reconciles_only_reaped_private_transactions(persistent_workspace):
    transaction = persistent_workspace / ".reelforge-encode-fixture"
    transaction.mkdir()
    (transaction / "pending.mp4").write_bytes(b"partial")
    successful = persistent_workspace / "complete.mp4"
    successful.write_bytes(b"keep")
    removed = cloud_validate.reconcile_case(persistent_workspace)
    assert len(removed) == 1 and not transaction.exists()
    assert successful.read_bytes() == b"keep"


def test_resource_pressure_is_mocked_and_cancels_cleanly(monkeypatch):
    counter = 0

    def snapshot(**kwargs):
        nonlocal counter
        counter += 1
        return {"effective_available_bytes": (700 if counter == 1 else 32) * monitor.MIB}

    monkeypatch.setattr(monitor, "memory_snapshot", snapshot)
    guard = monitor.JobMonitor()
    with pytest.raises(OperationError) as caught:
        with guard:
            deadline = time.monotonic() + 1
            while not guard.cancelled.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert guard.cancelled.is_set()
    assert caught.value.code == "RESOURCE_GUARD"
    assert guard.report()["minimum_effective_available_bytes"] == 32 * monitor.MIB


def test_unsafe_run_path_rejected_before_job(persistent_workspace):
    with pytest.raises(OperationError) as caught:
        cloud_validate.validate(
            persistent_workspace,
            Path("/tmp/escape"),
            scope="development",
            long_frames=600,
            timeout=180,
        )
    assert caught.value.code == "RUN_PATH"


def test_runtime_low_disk_is_mocked_and_cancels(persistent_workspace, monkeypatch):
    calls = 0

    def usage(path):
        nonlocal calls
        calls += 1
        return SimpleNamespace(free=(512 if calls == 1 else 32) * monitor.MIB)

    monkeypatch.setattr(monitor.shutil, "disk_usage", usage)
    guard = monitor.JobMonitor(workspace=persistent_workspace)
    with pytest.raises(OperationError) as caught:
        with guard:
            deadline = time.monotonic() + 1
            while not guard.cancelled.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
    assert caught.value.code == "RESOURCE_GUARD"
    assert guard.report()["minimum_workspace_free_bytes"] == 32 * monitor.MIB


def test_manifest_distribution_cannot_inject_requirements(sealed):
    p = sealed / "manifest.json"
    data = json.loads(p.read_text())
    data["files"][0]["distribution"] = "package @ https://example.invalid/remote.whl"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="metadata differs"):
        wheelhouse.verify(sealed)
