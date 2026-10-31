"""Read-only Linux deployment diagnostics and conservative workspace admission."""

import os
import platform
import shutil
import tempfile
from pathlib import Path

from reelforge.core.errors import OperationError
from reelforge.resources.monitor import MIB, memory_snapshot, preflight_memory


def pressure_snapshot() -> dict:
    result = {}
    for name in ("memory", "cpu", "io"):
        try:
            result[name] = Path(f"/proc/pressure/{name}").read_text().strip()
        except OSError:
            result[name] = None
    counters = {}
    try:
        for line in Path("/proc/vmstat").read_text().splitlines():
            key, value = line.split()
            if key.startswith("balloon_") or key in {"pgmajfault", "pswpin", "pswpout"}:
                counters[key] = int(value)
    except OSError:
        pass
    result["vmstat"] = counters
    result["balloon_note"] = (
        "Guest balloon counters only when exposed; lack of counters does "
        "not prove ballooning or host pressure is absent."
    )
    return result


def event_counts(snapshot: dict) -> dict[str, int]:
    raw = snapshot.get("cgroup", {}).get("memory.events")
    if not isinstance(raw, str):
        return {}
    try:
        return {line.split()[0]: int(line.split()[1]) for line in raw.splitlines()}
    except (ValueError, IndexError):
        return {}


def event_delta(before: dict, after: dict) -> dict[str, int] | None:
    old, new = event_counts(before), event_counts(after)
    if not old or set(old) != set(new):
        return None
    return {name: new[name] - old[name] for name in old}


def cgroup_capabilities(snapshot: dict) -> dict:
    root = Path(snapshot["cgroup_root"])
    info = {
        "path": str(root),
        "hard_enforcement": "not_configured",
        "delegation": "not_assumed",
        "controls_modified": False,
    }
    for name in ("cgroup.controllers", "cgroup.subtree_control", "cgroup.type"):
        try:
            info[name] = (root / name).read_text().strip()
        except OSError:
            info[name] = None
    try:
        info["mount_read_only"] = bool(os.statvfs(root).f_flag & os.ST_RDONLY)
        info["directory_write_access"] = os.access(root, os.W_OK)
    except OSError:
        info["mount_read_only"] = None
        info["directory_write_access"] = False
    info["note"] = (
        "Read/access checks are not proof of delegated unprivileged memory controls. "
        "No subgroup, memory.max, swap setting or cgroup.procs is changed."
    )
    return info


def cpu_snapshot(snapshot: dict) -> dict:
    affinity = len(os.sched_getaffinity(0))
    quota = snapshot.get("cgroup", {}).get("cpu.max")
    effective = float(affinity)
    if isinstance(quota, str):
        fields = quota.split()
        if len(fields) == 2 and fields[0] != "max":
            try:
                effective = min(effective, int(fields[0]) / int(fields[1]))
            except (ValueError, ZeroDivisionError):
                pass
    model = "unknown"
    try:
        model = next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        )
    except (OSError, StopIteration):
        pass
    return {
        "architecture": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "affinity_cpus": affinity,
        "effective_cpu_upper_bound": effective,
        "cpu_max": quota,
        "model": model,
    }


def check_workspace(
    workspace: Path, *, minimum_free_bytes: int = 256 * MIB, write_probe: bool = True
) -> dict:
    workspace = workspace.resolve()
    if workspace == Path("/tmp") or Path("/tmp") in workspace.parents:
        raise OperationError("WORKSPACE_TMP", "Choose a persistent project directory outside /tmp")
    if not workspace.is_dir():
        raise OperationError("WORKSPACE_MISSING", "Create the persistent workspace directory first")
    usage = shutil.disk_usage(workspace)
    if usage.free < minimum_free_bytes:
        raise OperationError(
            "DISK_PREFLIGHT", f"Workspace needs at least {minimum_free_bytes} free bytes"
        )
    if write_probe:
        path = None
        try:
            fd, name = tempfile.mkstemp(prefix=".reelforge-write-check-", dir=workspace)
            path = Path(name)
            with os.fdopen(fd, "wb") as handle:
                handle.write(b"reelforge-deployment-check\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise OperationError(
                "WORKSPACE_WRITE", "Workspace must permit ordinary-user writes/fsync"
            ) from error
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
    return {
        "path": str(workspace),
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "minimum_free_bytes": minimum_free_bytes,
        "write_probe": write_probe,
        "uid": os.getuid(),
        "root_not_required": True,
    }


def resource_readiness(workspace: Path) -> dict:
    snapshot = memory_snapshot()
    preflight_memory(snapshot=snapshot)
    return {
        "memory": snapshot,
        "cpu": cpu_snapshot(snapshot),
        "pressure": pressure_snapshot(),
        "workspace": check_workspace(workspace),
        "cgroup_capabilities": cgroup_capabilities(snapshot),
    }
