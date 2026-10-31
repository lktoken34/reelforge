"""Fresh-process engineering benchmark. No encoder, frame collection or animation timeline."""

import argparse
import gc
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
from reelforge.rendering.diagnostic import BACKGROUND, LOGICAL_SIZE, diagnostic_commands


def proc_memory() -> dict[str, int]:
    values = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"VmRSS", "VmHWM", "VmSwap", "Threads"}:
            values[key] = int(value.split()[0])
    return values


def environment() -> dict:
    cpu = next(
        (
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        "unknown",
    )
    mem = {
        line.split(":", 1)[0]: int(line.split()[1])
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.split()[0] in {"MemTotal:", "MemAvailable:", "SwapTotal:", "SwapFree:"}
    }
    cgroup = {}
    for name in ("cpu.max", "memory.max", "memory.current", "memory.peak"):
        path = Path("/sys/fs/cgroup") / name
        try:
            cgroup[name] = path.read_text().strip()
        except OSError:
            cgroup[name] = "unavailable"
    return {
        "os": platform.platform(),
        "distribution": platform.freedesktop_os_release().get("PRETTY_NAME", "unknown"),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "cpu_model": cpu,
        "logical_cpus_visible": os.cpu_count(),
        "affinity_cpus": len(os.sched_getaffinity(0)),
        "memory_kib": mem,
        "cgroup_observations_shared_not_job_peaks": cgroup,
        **backend_versions(),
    }


def worker(width: int, height: int, frames: int) -> dict:
    renderer = CairoRenderer()
    commands = diagnostic_commands()
    initial = proc_memory()
    samples = []
    reference = None
    gc_enabled = gc.isenabled()
    # Keep normal Python garbage collection enabled; production cannot rely on disabling it.
    for _ in range(10):
        with renderer.surface(width, height) as target:
            renderer.draw(target, commands, background=BACKGROUND, logical_size=LOGICAL_SIZE)
            reference = target.pixel_sha256()
    warm = proc_memory()
    draw_seconds = 0.0
    mismatches = 0
    first_hash = last_hash = ""
    started = time.perf_counter()
    for index in range(frames):
        frame_start = time.perf_counter()
        with renderer.surface(width, height) as target:
            renderer.draw(target, commands, background=BACKGROUND, logical_size=LOGICAL_SIZE)
            draw_seconds += time.perf_counter() - frame_start
            digest = target.pixel_sha256()
            mismatches += digest != reference
            if index == 0:
                first_hash = digest
            last_hash = digest
            if (index + 1) % 25 == 0:
                live = proc_memory()
                surface_bytes = target.layout.size_bytes
        if (index + 1) % 25 == 0:
            samples.append(
                {
                    "frame": index + 1,
                    "live_rss_kib": live["VmRSS"],
                    "released_rss_kib": proc_memory()["VmRSS"],
                }
            )
        if renderer.allocated_bytes != 0 or renderer.active_surfaces != 0:
            raise RuntimeError("Surface ownership did not return to zero")
    wall = time.perf_counter() - started
    final = proc_memory()
    rusage_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss = max(final["VmHWM"], rusage_peak, *(sample["live_rss_kib"] for sample in samples))
    stable = [sample["released_rss_kib"] for sample in samples]
    tail = stable[len(stable) // 2 :]
    # Retention is reported as actual delta/range. Finite-run plateaus cannot prove no leaks.
    return {
        "width": width,
        "height": height,
        "frames": frames,
        "warmup_frames": 10,
        "command_count": len(commands),
        "environment": environment(),
        "initial_memory": initial,
        "after_warmup_memory": warm,
        "final_memory": final,
        "peak_rss_kib": peak_rss,
        "rusage_peak_rss_kib": rusage_peak,
        "final_minus_initial_rss_kib": final["VmRSS"] - initial["VmRSS"],
        "final_minus_warm_rss_kib": final["VmRSS"] - warm["VmRSS"],
        "released_rss_tail_range_kib": max(tail) - min(tail),
        "released_rss_tail_delta_kib": tail[-1] - tail[0],
        "samples": samples,
        "surface_bytes": surface_bytes,
        "draw_allocation_seconds": draw_seconds,
        "allocation_draw_fps": frames / draw_seconds,
        "loop_including_hash_seconds": wall,
        "loop_including_hash_fps": frames / wall,
        "first_pixel_sha256": first_hash,
        "last_pixel_sha256": last_hash,
        "hash_mismatches": mismatches,
        "gc_enabled": gc_enabled,
        "owned_surface_bytes_final": renderer.allocated_bytes,
        "live_surfaces_final": renderer.active_surfaces,
        "below_256_mib_rss": peak_rss < 256 * 1024,
        "scope": "single renderer process and its native allocations; no children or encoder",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2, type=int, metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--frames", type=int, default=500)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/phase2a"))
    args = parser.parse_args()
    if args.frames < 500 or args.repeats < 1:
        parser.error("Use at least 500 measured frames and one repetition")
    if args.worker:
        print(json.dumps(worker(*args.worker, args.frames), sort_keys=True))
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for width, height in ((360, 640), (720, 1280)):
        for repeat in range(args.repeats):
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    str(width),
                    str(height),
                    "--frames",
                    str(args.frames),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=600,
            )
            data = json.loads(result.stdout)
            data["repeat"] = repeat + 1
            results.append(data)
            print(
                f"{width}x{height} trial {repeat + 1}: "
                f"{data['allocation_draw_fps']:.1f} allocation+draw fps, "
                f"{data['peak_rss_kib'] / 1024:.2f} MiB peak RSS",
                flush=True,
            )
    report = {
        "milestone": "2A",
        "results": results,
        "note": "Harness is outside measured renderer worker; cgroup values are shared. "
        "No 4-vCPU/0.4-GiB VM or cgroup restriction was imposed.",
    }
    (args.output_dir / "benchmark_results.json").write_text(json.dumps(report, indent=2) + "\n")
    if any(item["hash_mismatches"] for item in results):
        raise RuntimeError("Determinism failure")


if __name__ == "__main__":
    main()
