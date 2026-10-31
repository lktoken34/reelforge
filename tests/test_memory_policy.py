"""Synthetic topology/pressure fixtures; never create real host memory pressure."""

import importlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

from reelforge.core.errors import OperationError
from reelforge.resources import deployment, memory, monitor

MIB = monitor.MIB
FALLBACK = "guest_procfs_fallback"
EVENTS = "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0"
HEADER = "#subsys_name hierarchy num_cgroups enabled\ncpu 0 2 1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
doctor = importlib.import_module("deployment_check")
cloud = importlib.import_module("cloud_validate")
wheels = importlib.import_module("wheelhouse")
recovery = importlib.import_module("recovery_check")


@pytest.fixture
def probes(monkeypatch):
    data = {
        "/proc/meminfo": (
            "MemTotal: 8120000 kB\nMemAvailable: 716800 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB"
        ),
        "/proc/self/cgroup": "0::/",
        "/proc/self/mountinfo": (
            "1 0 0:1 / / rw - ext4 /dev/vda rw\n10 1 0:2 / /cg ro - cgroup2 cgroup2 rw"
        ),
        "/proc/cgroups": HEADER,
        "/cg/cgroup.controllers": "cpu memory",
        "/cg/memory.max": str(512 * MIB),
        "/cg/memory.current": str(100 * MIB),
        "/cg/memory.events": EVENTS,
        "/proc/cpuinfo": "flags: hypervisor",
        "/sys/class/dmi/id/product_name": "KVM",
    }

    def read(path):
        value = data.get(path)
        if isinstance(value, dict):
            return value
        return {"status": "missing"} if value is None else {"status": "present", "value": value}

    monkeypatch.setattr(memory, "read_observation", read)
    monkeypatch.setattr(memory.os, "sched_getaffinity", lambda pid: set(range(4)))
    monkeypatch.setattr(memory.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        memory.platform,
        "freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "24.04", "PRETTY_NAME": "Synthetic guest"},
    )
    return data


def absent(data):
    for key in list(data):
        if key.startswith("/cg/memory."):
            del data[key]
    data["/cg/cgroup.controllers"] = "cpu"
    return data


@pytest.fixture
def workspace():
    parent = Path(__file__).resolve().parents[1] / "outputs"
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as directory:
        yield Path(directory)


@pytest.mark.parametrize("policy", memory.POLICIES)
def test_real_v2_limit_is_never_ignored(probes, policy):
    result = monitor.memory_snapshot(memory_policy=policy)
    assert result["effective_available_bytes"] == 412 * MIB
    assert result["memory_source"] == "guest_and_cgroup"
    assert result["fallback_used"] is False
    assert monitor.preflight_memory(snapshot=result, memory_policy=policy)


def test_unlimited_v2_still_requires_valid_usage(probes):
    probes["/cg/memory.max"] = "max"
    assert monitor.memory_snapshot()["effective_available_bytes"] == 700 * MIB
    del probes["/cg/memory.current"]
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


def test_visible_ancestor_headroom_is_respected(probes):
    probes["/proc/self/cgroup"] = "0::/child"
    probes["/cg/child/cgroup.controllers"] = ""
    probes["/cg/child/memory.max"] = "max"
    probes["/cg/child/memory.current"] = str(50 * MIB)
    probes["/cg/memory.current"] = str(500 * MIB)
    result = monitor.memory_snapshot(memory_policy=FALLBACK)
    assert result["effective_available_bytes"] == 12 * MIB
    with pytest.raises(OperationError, match="256 MiB"):
        monitor.preflight_memory(snapshot=result, memory_policy=FALLBACK)


def test_mount_root_mapping_and_escaped_paths(probes):
    probes["/proc/self/cgroup"] = "0::/slice/child"
    probes["/proc/self/mountinfo"] = "10 1 0:2 /slice /cg\\040space ro - cgroup2 cgroup2 rw"
    for path, value in list(probes.items()):
        if path.startswith("/cg/"):
            probes[path.replace("/cg/", "/cg space/")] = value
    probes["/cg space/child/cgroup.controllers"] = ""
    probes["/cg space/child/memory.max"] = "max"
    probes["/cg space/child/memory.current"] = "100"
    result = monitor.memory_snapshot()
    assert result["cgroup_root"] == "/cg space/child"
    assert result["effective_available_bytes"] == 412 * MIB


@pytest.mark.parametrize("policy,expected", [("strict", 0), (FALLBACK, 700 * MIB)])
def test_entirely_unavailable_controller_requires_authorization(probes, policy, expected):
    absent(probes)
    result = monitor.memory_snapshot(memory_policy=policy)
    assert result["effective_available_bytes"] == expected
    assert result["controller_state"] == "unavailable_in_observed_guest"
    assert result["fallback_used"] == (policy == FALLBACK)
    assert result["cgroup"]["memory.events"] is None


def test_no_cgroup_mounts_with_consistent_inventory(probes):
    absent(probes)
    probes["/proc/self/cgroup"] = ""
    probes["/proc/self/mountinfo"] = "10 1 0:2 / / rw - ext4 /dev/vda rw"
    result = monitor.memory_snapshot(memory_policy=FALLBACK)
    assert result["effective_available_bytes"] == 700 * MIB
    assert result["cgroup_root"] is None
    assert deployment.cgroup_capabilities(result)["path"] is None


@pytest.mark.parametrize("name", ["memory.max", "memory.current", "cgroup.controllers"])
@pytest.mark.parametrize("policy", memory.POLICIES)
def test_existing_unreadable_files_are_not_absence(probes, name, policy):
    probes[f"/cg/{name}"] = {"status": "unreadable", "error": "PermissionError"}
    result = monitor.memory_snapshot(memory_policy=policy)
    assert result["effective_available_bytes"] == 0
    assert not result["fallback_used"]
    assert "unreadable" in result["errors"][0]


@pytest.mark.parametrize(
    "path,value",
    [
        ("/proc/self/cgroup", "0::/../escape"),
        ("/proc/self/cgroup", "0::/\n0::/other"),
        ("/proc/self/cgroup", "1:memory:/"),
        ("/proc/self/mountinfo", "broken"),
        ("/proc/self/mountinfo", "10 1 0:2 /hidden /cg ro - cgroup2 cgroup2 rw"),
        ("/proc/self/mountinfo", "10 1 0:2 / /cg ro - tmpfs tmpfs rw"),
        (
            "/proc/self/mountinfo",
            (
                "10 1 0:2 / /cg ro - cgroup2 cgroup2 rw\n"
                "11 10 0:3 / /cg/memory.max ro - tmpfs tmpfs rw"
            ),
        ),
        ("/proc/cgroups", ""),
        ("/proc/cgroups", "#subsys_name hierarchy num_cgroups enabled\nmemory 2 1 1"),
        ("/cg/memory.current", "-1"),
        ("/cg/memory.current", str(600 * MIB)),
        ("/cg/memory.max", "unknown"),
    ],
)
def test_unknown_or_contradictory_topology_never_falls_back(probes, path, value):
    probes[path] = value
    result = monitor.memory_snapshot(memory_policy=FALLBACK)
    assert result["effective_available_bytes"] == 0
    assert result["errors"]
    assert not result["fallback_used"]


def test_enabled_but_unseen_controller_is_not_fallback_eligible(probes):
    absent(probes)
    probes["/proc/cgroups"] = HEADER + "\nmemory 0 1 1"
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


@pytest.mark.parametrize("value", ["-1", "nan", "1e309", "999999999999", "", "12 MB"])
def test_invalid_guest_available_rejected(probes, value):
    absent(probes)
    probes["/proc/meminfo"] = probes["/proc/meminfo"].replace("716800", value)
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


def test_missing_guest_available_rejected(probes):
    probes["/proc/meminfo"] = "MemTotal: 8120000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB"
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


@pytest.mark.parametrize("available,passes", [(319, False), (320, True), (383, True)])
def test_ordinary_threshold_never_changes(probes, available, passes):
    absent(probes)
    probes["/proc/meminfo"] = probes["/proc/meminfo"].replace("716800", str(available * 1024))
    snapshot = monitor.memory_snapshot(memory_policy=FALLBACK)
    if passes:
        assert monitor.preflight_memory(snapshot=snapshot, memory_policy=FALLBACK)
    else:
        with pytest.raises(OperationError):
            monitor.preflight_memory(snapshot=snapshot, memory_policy=FALLBACK)


@pytest.mark.parametrize("marker", ["/.dockerenv", "/run/.containerenv", "/run/systemd/container"])
def test_known_container_marker_blocks_fallback(probes, marker):
    absent(probes)
    probes[marker] = "container"
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


def test_guest_environment_must_be_eligible(probes):
    absent(probes)
    probes["/proc/cpuinfo"] = "flags: normal"
    probes["/sys/class/dmi/id/product_name"] = "bare metal"
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


def test_cgroup_v1_hierarchical_limits(probes):
    probes["/proc/self/cgroup"] = "4:memory:/vm"
    probes["/proc/self/mountinfo"] = "10 1 0:2 / /legacy ro - cgroup cgroup rw,memory"
    probes["/proc/cgroups"] = HEADER + "\nmemory 4 2 1"
    for directory, limit, usage in (("/legacy", 1024, 100), ("/legacy/vm", 512, 100)):
        probes[directory + "/memory.limit_in_bytes"] = str(limit * MIB)
        probes[directory + "/memory.usage_in_bytes"] = str(usage * MIB)
        probes[directory + "/memory.use_hierarchy"] = "1"
    probes["/legacy/vm/memory.stat"] = f"hierarchical_memory_limit {512 * MIB}"
    result = monitor.memory_snapshot(memory_policy=FALLBACK)
    assert result["controller_version"] == "v1"
    assert result["effective_available_bytes"] == 412 * MIB
    assert result["cgroup"]["memory.events"] is None
    probes["/legacy/vm/memory.stat"] = f"hierarchical_memory_limit {256 * MIB}"
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


def test_runtime_guest_reserve_and_controller_loss(probes):
    absent(probes)
    with pytest.raises(OperationError, match="reserve"):
        with monitor.JobMonitor(memory_policy=FALLBACK) as guard:
            probes["/proc/meminfo"] = probes["/proc/meminfo"].replace("716800", "32768")
            for _ in range(10):
                guard.sample()
            assert guard.cancelled.is_set()
    assert guard.report()["minimum_effective_available_bytes"] == 32 * MIB


def test_visible_controller_cannot_disappear_into_fallback(probes):
    with pytest.raises(OperationError, match="disappeared|became unavailable"):
        with monitor.JobMonitor(memory_policy=FALLBACK) as guard:
            absent(probes)
            for _ in range(10):
                guard.sample()
            assert guard.cancelled.is_set()


def test_missing_and_malformed_oom_counters_are_unknown(probes):
    before = monitor.memory_snapshot()
    for value in (None, "oom -1\noom_kill 0", "oom 0\noom 1\noom_kill 0", "oom 0"):
        probes["/cg/memory.events"] = value
        report = deployment.memory_observability(before, monitor.memory_snapshot())
        assert not report["oom_counters_available"]
        assert not report["sufficient_for_technical_validation"]
        assert report["deployment_gate_approved"] is False


def test_policy_mismatch_and_unknown_mode_cannot_bypass(probes):
    absent(probes)
    snapshot = monitor.memory_snapshot(memory_policy=FALLBACK)
    with pytest.raises(OperationError, match="policy differ"):
        monitor.preflight_memory(snapshot=snapshot)
    with pytest.raises(OperationError):
        monitor.memory_snapshot(memory_policy="ignore_limits")


def test_doctor_and_installer_share_fallback(probes, workspace, monkeypatch):
    absent(probes)
    strict = doctor.inspect_deployment(workspace)
    assert strict["errors"][0]["code"] == "MEMORY_PREFLIGHT"
    permitted = doctor.inspect_deployment(workspace, memory_policy=FALLBACK)
    assert permitted["memory"]["fallback_used"] is True
    assert permitted.get("native_checks") != "skipped_due_to_memory_refusal"
    monkeypatch.setattr(wheels, "verify", lambda path: {})
    process = importlib.import_module("reelforge.media.process")
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return 0, b"", b""

    monkeypatch.setattr(process, "run_bounded", run)
    result = wheels.install(workspace, workspace / "runtime", memory_policy=FALLBACK)
    assert result["admission_memory"]["fallback_used"]
    assert result["whole_install_memory"]["memory_policy"] == FALLBACK
    assert len(calls) == 2
    assert all(call[1]["cancelled"] is not None for call in calls)
    assert all(call[1]["env"]["TMPDIR"].startswith(str(workspace)) for call in calls)
    assert "--only-binary=:all:" in calls[1][0]


@pytest.mark.parametrize("mode", ["missing_oom", "observed", "long_insufficient", "worker_failed"])
def test_supervisor_propagates_policy_and_distinguishes_missing_oom(
    probes, workspace, monkeypatch, mode
):
    if mode != "observed":
        absent(probes)
    if mode == "long_insufficient":
        probes["/proc/meminfo"] = probes["/proc/meminfo"].replace("716800", str(383 * 1024))
    monkeypatch.setattr(cloud, "inspect_deployment", lambda *a, **kw: {"ok": True})
    policies = []

    def worker(args, **kwargs):
        policies.append(args[args.index("--memory-policy") + 1])
        if mode == "worker_failed":
            return 2, b"", b"fixture failure"
        report = {
            "transaction_clean": True,
            "whole_job_memory": {
                "encoder_peak_rss_bytes": 100,
                "estimated_simultaneous_tree_peak_rss_bytes": 200,
            },
            "verification": {"decoded_rgb_sha256": ["fixed", "moving", "rotating"]},
            "memory_observability": {
                "policy": FALLBACK,
                "sufficient_for_technical_validation": mode == "observed",
            },
        }
        Path(args[args.index("--report") + 1]).write_text(json.dumps(report))
        return 0, b"", b""

    monkeypatch.setattr(cloud, "run_bounded", worker)
    result = cloud.validate(
        workspace,
        workspace / "short",
        scope="development",
        long_frames=600,
        timeout=180,
        memory_policy=FALLBACK,
        short_only=mode != "long_insufficient",
    )
    if mode == "worker_failed":
        assert result["technical_rendering_success"] is False
        assert result["validation_status"] == "failed_or_incomplete"
        return
    if mode == "long_insufficient":
        assert result["technical_rendering_success"] is False
        assert policies == [FALLBACK] * 4
        assert len([j for j in result["jobs"] if j["status"].startswith("skipped")]) == 2
        return
    if mode == "observed":
        assert result["technical_run_passed"] is True
        assert result["validation_status"] == "validated"
        assert result["deployment_gate_approved"] is False
        return
    assert policies == [FALLBACK] * 4
    assert result["technical_rendering_success"] is True
    assert result["technical_run_passed"] is False
    assert result["validation_status"] == "rendered_with_observability_limitations"
    assert result["memory_observability"]["oom_event_delta"] is None
    assert result["deployment_gate_approved"] is False


def test_actual_worker_fallback_render_with_controlled_observations(probes, workspace):
    pytest.importorskip("cairo")
    import shutil

    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg unavailable")
    worker = importlib.import_module("render_video")
    absent(probes)
    result = worker.render_job(
        workspace / "fixture.mp4", width=360, height=640, frames=12, memory_policy=FALLBACK
    )
    assert result["technical_rendering_success"]
    assert result["verification"]["decoded_frames"] == 12
    assert result["memory_observability"]["fallback_used"]
    assert result["memory_observability"]["oom_event_delta"] is None
    assert result["transaction_clean"]
    assert not list(workspace.glob(".reelforge-encode-*"))


def test_recovery_preflight_uses_selected_policy(probes, workspace, monkeypatch):
    received = []

    def refuse(**kwargs):
        received.append(kwargs["memory_policy"])
        raise OperationError("STOP_FIXTURE", "No process should start in this test")

    monkeypatch.setattr(recovery, "preflight_memory", refuse)
    with pytest.raises(OperationError, match="No process"):
        recovery.check_recovery(workspace, memory_policy=FALLBACK)
    assert received == [FALLBACK]


def test_long_worker_keeps_384_mib_threshold(probes, workspace):
    pytest.importorskip("cairo")
    worker = importlib.import_module("render_video")
    absent(probes)
    probes["/proc/meminfo"] = probes["/proc/meminfo"].replace("716800", str(383 * 1024))
    with pytest.raises(OperationError) as caught:
        worker.render_job(
            workspace / "long.mp4", width=360, height=640, frames=450, memory_policy=FALLBACK
        )
    assert caught.value.code == "LONG_MEMORY_PREFLIGHT"
    assert not (workspace / "long.mp4").exists()
    assert not list(workspace.glob(".reelforge-encode-*"))


def test_telemetry_gap_does_not_become_zero_oom_claim(probes):
    with monitor.JobMonitor() as guard:
        probes["/cg/memory.events"] = None
        for _ in range(10):
            guard.sample()
        probes["/cg/memory.events"] = EVENTS
    assert guard.oom_telemetry_continuous is False


def test_controller_probe_read_errors_distinguish_missing(monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("fixture")

    monkeypatch.setattr(memory.Path, "open", denied)
    assert memory.read_observation("/any")["status"] == "unreadable"


def test_masked_container_like_root_blocks_fallback(probes):
    absent(probes)
    probes["/proc/self/mountinfo"] = probes["/proc/self/mountinfo"].replace(
        "- ext4 /dev/vda rw", "- overlay overlay rw"
    )
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


@pytest.mark.parametrize("policy", memory.POLICIES)
def test_preinstall_probe_is_stdlib_only_and_accepts_explicit_policy(workspace, policy):
    import subprocess

    script = Path(__file__).resolve().parents[1] / "tools/memory_probe.py"
    output = workspace / "probe.json"
    proc = subprocess.run(
        [sys.executable, "-S", str(script), "--memory-policy", policy, "--report", str(output)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode in (0, 2), proc.stderr
    data = json.loads(output.read_text())
    assert data["memory"]["memory_policy"] == policy
    assert data["deployment_gate_approved"] is False


@pytest.mark.parametrize("name", ["memory.events", "memory.peak", "memory.swap.current"])
def test_partial_telemetry_never_proves_controller_absence(probes, name):
    absent(probes)
    probes["/cg/" + name] = "0"
    assert monitor.memory_snapshot(memory_policy=FALLBACK)["effective_available_bytes"] == 0


def test_reaped_worker_private_reconciliation_preserves_success(workspace):
    pytest.importorskip("cairo")
    worker = importlib.import_module("render_video")
    output = workspace / "existing.mp4"
    output.write_bytes(b"existing success")
    directory = workspace / ".reelforge-encode-private"
    directory.mkdir()
    pending = directory / "pending.mp4"
    pending.write_bytes(b"retained private partial")
    worker.confirm_transaction_cleanup(pending, output)
    assert output.read_bytes() == b"existing success"
    assert not directory.exists()


def test_private_reconciliation_refuses_unexpected_content_and_symlinks(workspace):
    pytest.importorskip("cairo")
    worker = importlib.import_module("render_video")
    output = workspace / "existing.mp4"
    directory = workspace / ".reelforge-encode-private"
    directory.mkdir()
    unexpected = directory / "unrecognized"
    unexpected.write_bytes(b"keep")
    with pytest.raises(OperationError):
        worker.confirm_transaction_cleanup(directory / "pending.mp4", output)
    assert unexpected.read_bytes() == b"keep"
    unexpected.unlink()
    (directory / "pending.mp4").symlink_to(output)
    with pytest.raises(OperationError):
        worker.confirm_transaction_cleanup(directory / "pending.mp4", output)
