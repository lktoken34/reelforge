"""Linux memory context plus sampled simultaneous process-tree RSS; no cgroup mutation."""

import os
import resource
import shutil
import threading
import time
from pathlib import Path

from reelforge.core.errors import OperationError
from reelforge.resources.memory import check_policy, observe_memory, oom_counts

MIB = 1024 * 1024


def memory_snapshot(*, memory_policy: str = "strict") -> dict:
    return observe_memory(policy=memory_policy)


def preflight_memory(
    *,
    budget_bytes: int = 256 * MIB,
    reserve_bytes: int = 64 * MIB,
    snapshot: dict | None = None,
    memory_policy: str = "strict",
) -> dict:
    check_policy(memory_policy)
    snapshot = memory_snapshot(memory_policy=memory_policy) if snapshot is None else snapshot
    if snapshot.get("memory_policy", memory_policy) != memory_policy:
        raise OperationError("MEMORY_POLICY", "Snapshot and requested memory policy differ")
    if budget_bytes <= 0 or reserve_bytes < 0:
        raise OperationError("MEMORY_CONFIG", "Invalid memory budget/reserve")
    if snapshot["effective_available_bytes"] < budget_bytes + reserve_bytes:
        raise OperationError(
            "MEMORY_PREFLIGHT",
            "Need 256 MiB job headroom plus 64 MiB reserve "
            "under the default policy; memory capacity may be unavailable",
        )
    return snapshot


def procfs_pid() -> int:
    """PID as exposed by this procfs mount, which can differ from os.getpid()."""
    return int(os.readlink("/proc/self"))


def namespace_pid(proc_pid: int) -> int:
    try:
        for line in Path(f"/proc/{proc_pid}/status").read_text().splitlines():
            if line.startswith("NSpid:"):
                return int(line.split()[-1])
    except (OSError, ValueError):
        pass
    return proc_pid


def process_rss(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return 0


def process_tree(pid: int) -> set[int]:
    # /task/*/children is optional (and absent in this host). Build ancestry from stat PPid.
    parents = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            parents[int(entry.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
    found = {pid}
    while True:
        added = {child for child, parent in parents.items() if parent in found} - found
        if not added:
            return found
        found.update(added)


class JobMonitor:
    """10ms RSS sampling, bounded summaries, cooperative pressure/budget cancellation."""

    def __init__(
        self,
        *,
        budget_bytes: int = 256 * MIB,
        reserve_bytes: int = 64 * MIB,
        cancelled: threading.Event | None = None,
        workspace: Path | None = None,
        disk_reserve_bytes: int = 64 * MIB,
        memory_policy: str = "strict",
    ):
        self.memory_policy = check_policy(memory_policy)
        self.memory_sources: set[str] = set()
        self.oom_telemetry_continuous = True
        self.pid = procfs_pid()
        self.budget_bytes, self.reserve_bytes = budget_bytes, reserve_bytes
        self.cancelled = cancelled if cancelled is not None else threading.Event()
        self.stop = threading.Event()
        self.renderer_peak = self.children_peak = self.tree_peak = self.encoder_peak = 0
        self.encoder_pid: int | None = None
        self.limit_reason: str | None = None
        self.samples = 0
        self.workspace = workspace
        self.disk_reserve_bytes = disk_reserve_bytes
        self.available_min = self.available_max = 0
        self.memory_observations = 0
        self.disk_free_min: int | None = None
        self._thread = threading.Thread(target=self._run, name="job-rss", daemon=True)

    def observe(self, observation: dict) -> int:
        source = observation.get("memory_source", "unavailable")
        if "guest_and_cgroup" in self.memory_sources and source != "guest_and_cgroup":
            self.limit_reason = "previously visible memory controller became unavailable"
            self.cancelled.set()
        old_paths = {c["path"] for c in getattr(self, "initial", {}).get("constraints", [])}
        new_paths = {c["path"] for c in observation.get("constraints", [])}
        if not old_paths <= new_paths:
            self.limit_reason = "previously visible ancestor accounting disappeared"
            self.cancelled.set()
        self.memory_sources.add(source)
        events = oom_counts(observation.get("cgroup", {}).get("memory.events"))
        self.oom_telemetry_continuous &= {"oom", "oom_kill"} <= events.keys()
        return observation["effective_available_bytes"]

    def sample(self) -> None:
        pids = process_tree(self.pid)
        values = {pid: process_rss(pid) for pid in pids}
        own = values.get(self.pid, 0)
        tree = sum(values.values())
        self.renderer_peak = max(self.renderer_peak, own)
        self.children_peak = max(
            self.children_peak, sum(v for p, v in values.items() if p != self.pid)
        )
        self.encoder_peak = max(
            self.encoder_peak,
            0,
            *(values[p] for p in values if namespace_pid(p) == self.encoder_pid),
        )
        self.tree_peak = max(self.tree_peak, tree)
        self.samples += 1
        if own <= 0:
            self.limit_reason = "renderer RSS is unavailable"
            self.cancelled.set()
        if tree > self.budget_bytes:
            self.limit_reason = "sampled process-tree RSS exceeded the budget"
            self.cancelled.set()
        if self.samples % 10 == 0:
            observation = memory_snapshot(memory_policy=self.memory_policy)
            available = self.observe(observation)
            self.available_min = min(self.available_min, available)
            self.available_max = max(self.available_max, available)
            self.memory_observations += 1
            if available < self.reserve_bytes:
                self.limit_reason = "available memory fell below the reserve"
                self.cancelled.set()
            if self.workspace is not None:
                free = shutil.disk_usage(self.workspace).free
                self.disk_free_min = (
                    free if self.disk_free_min is None else min(self.disk_free_min, free)
                )
                if free < self.disk_reserve_bytes:
                    self.limit_reason = "workspace disk free space fell below reserve"
                    self.cancelled.set()

    def _run(self) -> None:
        while not self.stop.wait(0.01):
            try:
                self.sample()
            except (OSError, ValueError, KeyError):
                self.limit_reason = "memory monitoring became unavailable"
                self.cancelled.set()
                return

    def __enter__(self):
        self.initial = memory_snapshot(memory_policy=self.memory_policy)
        preflight_memory(
            snapshot=self.initial,
            memory_policy=self.memory_policy,
            budget_bytes=self.budget_bytes,
            reserve_bytes=self.reserve_bytes,
        )
        self.observe(self.initial)
        self.available_min = self.available_max = self.initial["effective_available_bytes"]
        self.memory_observations = 1
        if self.workspace is not None:
            self.disk_free_min = shutil.disk_usage(self.workspace).free
        self.initial_renderer_rss = process_rss(self.pid)
        self.started = time.perf_counter()
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop.set()
        self._thread.join(timeout=2)
        self.sample()
        self.seconds = time.perf_counter() - self.started
        self.final = memory_snapshot(memory_policy=self.memory_policy)
        self.observe(self.final)
        if self.final["effective_available_bytes"] < self.reserve_bytes:
            self.limit_reason = "available memory fell below the reserve"
            self.cancelled.set()
        self.available_min = min(self.available_min, self.final["effective_available_bytes"])
        self.available_max = max(self.available_max, self.final["effective_available_bytes"])
        self.memory_observations += 1
        self.final_renderer_rss = process_rss(self.pid)
        if self.limit_reason:
            raise OperationError("RESOURCE_GUARD", self.limit_reason)

    def report(self) -> dict:
        return {
            "oom_telemetry_continuous": self.oom_telemetry_continuous,
            "memory_policy": self.memory_policy,
            "observed_memory_sources": sorted(self.memory_sources),
            "initial_memory": self.initial,
            "final_memory": self.final,
            "initial_renderer_rss_bytes": self.initial_renderer_rss,
            "final_renderer_rss_bytes": self.final_renderer_rss,
            "renderer_peak_rss_bytes": self.renderer_peak,
            "waited_child_max_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            * 1024,
            "encoder_peak_rss_bytes": self.encoder_peak,
            "all_children_peak_rss_bytes": self.children_peak,
            "estimated_simultaneous_tree_peak_rss_bytes": self.tree_peak,
            "sampling_interval_seconds": 0.01,
            "samples": self.samples,
            "job_budget_bytes": self.budget_bytes,
            "reserve_bytes": self.reserve_bytes,
            "limit_reason": self.limit_reason,
            "minimum_effective_available_bytes": self.available_min,
            "maximum_effective_available_bytes": self.available_max,
            "memory_observations": self.memory_observations,
            "minimum_workspace_free_bytes": self.disk_free_min,
            "disk_reserve_bytes": self.disk_reserve_bytes if self.workspace is not None else None,
            "wall_seconds": self.seconds,
            "caveat": "Sampled sum of RSS can miss transient peaks and double-count shared pages; "
            "cgroup counters are shared, not a dedicated job limit.",
        }
