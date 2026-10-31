"""Linux memory context plus sampled simultaneous process-tree RSS; no cgroup mutation."""

import os
import resource
import threading
import time
from pathlib import Path

from reelforge.core.errors import OperationError

MIB = 1024 * 1024


def memory_snapshot() -> dict:
    mem = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.split()[0] in {"MemAvailable:", "MemTotal:", "SwapTotal:", "SwapFree:"}:
            mem[line.split(":")[0]] = int(line.split()[1]) * 1024
    counters = {}
    root = Path("/sys/fs/cgroup")
    relative = next(
        (
            line.split("::", 1)[1]
            for line in Path("/proc/self/cgroup").read_text().splitlines()
            if "::" in line
        ),
        "",
    )
    nested = root / relative.lstrip("/")
    if (nested / "memory.max").is_file():
        root = nested
    for name in (
        "memory.max",
        "memory.current",
        "memory.peak",
        "memory.events",
        "memory.swap.max",
        "memory.swap.current",
        "cpu.max",
    ):
        try:
            value = (root / name).read_text().strip()
            counters[name] = int(value) if value.isdigit() else value
        except OSError:
            counters[name] = None
    available = mem.get("MemAvailable", 0)
    maximum, current = counters["memory.max"], counters["memory.current"]
    if isinstance(maximum, int) and isinstance(current, int):
        available = min(available, max(0, maximum - current))
    elif maximum != "max":
        available = 0  # Unknown container capacity is not evidence of safe headroom.
    return {
        "host": mem,
        "cgroup_root": str(root),
        "cgroup": counters,
        "effective_available_bytes": available,
    }


def preflight_memory(
    *, budget_bytes: int = 256 * MIB, reserve_bytes: int = 64 * MIB, snapshot: dict | None = None
) -> dict:
    snapshot = memory_snapshot() if snapshot is None else snapshot
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
    ):
        self.pid = procfs_pid()
        self.budget_bytes, self.reserve_bytes = budget_bytes, reserve_bytes
        self.cancelled = cancelled if cancelled is not None else threading.Event()
        self.stop = threading.Event()
        self.renderer_peak = self.children_peak = self.tree_peak = self.encoder_peak = 0
        self.encoder_pid: int | None = None
        self.limit_reason: str | None = None
        self.samples = 0
        self._thread = threading.Thread(target=self._run, name="job-rss", daemon=True)

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
            if memory_snapshot()["effective_available_bytes"] < self.reserve_bytes:
                self.limit_reason = "available memory fell below the reserve"
                self.cancelled.set()

    def _run(self) -> None:
        while not self.stop.wait(0.01):
            try:
                self.sample()
            except OSError:
                self.limit_reason = "memory monitoring became unavailable"
                self.cancelled.set()
                return

    def __enter__(self):
        self.initial = memory_snapshot()
        self.initial_renderer_rss = process_rss(self.pid)
        self.started = time.perf_counter()
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop.set()
        self._thread.join(timeout=2)
        self.sample()
        self.seconds = time.perf_counter() - self.started
        self.final = memory_snapshot()
        self.final_renderer_rss = process_rss(self.pid)

    def report(self) -> dict:
        return {
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
            "wall_seconds": self.seconds,
            "caveat": "Sampled sum of RSS can miss transient peaks and double-count shared pages; "
            "cgroup counters are shared, not a dedicated job limit.",
        }
