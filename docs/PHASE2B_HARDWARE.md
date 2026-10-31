# Phase 2B — whole-job hardware evidence

The production target is Ubuntu 24.04, 4 vCPUs, no GPU/swap, 0.4–1.0 GiB available RAM,
a small `/tmp` and a large persistent home/workspace disk. **This target VM was not tested.**

## Actual host and native stack

The session host is Ubuntu 24.04.3 LTS, x86_64, AMD EPYC 9V74 80-Core Processor (host model
string), 9 logical CPUs visible/affined, cgroup CPU quota `800000 100000` (8 CPU equivalents).
Memory.max is 8589934592 bytes (8 GiB). The first final worker observed host MemTotal
10451427328 bytes and MemAvailable 9813487616 bytes; these host views do not imply more than
the container's 8 GiB limit is usable. SwapTotal/SwapFree were both zero. Cgroup swap.current
was zero; swap.max was `max` (the job did not change it or configure host swap).

Tested Python 3.12.14, Pycairo 1.29.2, Cairo 1.18.0 and Ubuntu FFmpeg/ffprobe 6.1.1-3ubuntu5,
with libx264 available. Cairo/native setup is retained in NATIVE_SETUP.md. The Python lock does
not pin FFmpeg, libx264, Cairo, pixman or the complete native OS build.

## Measurement scope and method

Four **fresh worker processes**, two per size, each produced 150 frames/5 seconds and verified
the result by ffprobe and complete RGB24 checksum decode. The job root includes the Python
renderer, monitor/stderr threads, encoder, capability probe, ffprobe and full-decode FFmpeg tools.
Those tools are sequentially owned descendants. No worker frame list is retained. The batch
launcher is outside worker measurements, as it is not required to run one rendering job.

At a nominal 10ms interval, read VmRSS for the root and live descendant processes, sum the
same observation, and retain the maximum sum. Individual renderer and encoder maxima are
also retained, but are **not added and presented as a simultaneous observation**. RSS can
include shared pages in more than one process; summing can overestimate physical memory.
Sampling can miss short transient spikes. The waited-child Linux ru_maxrss maximum is recorded
separately; it is neither a simultaneous sum nor a sum across children. Kernel accounting views
can differ slightly. Results are estimates, not a hard memory certification.

This host exposes procfs PIDs different from `os.getpid()`/Popen PID values. Use `/proc/self`'s
exposed PID, ancestry from procfs stat PPid, and NSpid mapping to identify the encoder. The
optional `/task/*/children` file is absent here. A regression test verifies a live allocating
child contributes to both encoder and tree measurements. An early exploratory monitor run
that reported zero/renderer-only RSS was discarded; **none of those invalid measurements is
in the committed final benchmark report**.

Raw initial/final host/cgroup snapshots, renderer RSS, encoder RSS, sample counts, timings,
file sizes, statuses, commands and verification hashes are in
`artifacts/phase2b/benchmark_results.json`. Measurements end after full technical verification,
before report JSON serialization. Contact-sheet extraction is a later inspection step, outside
worker measurements. No dedicated per-job cgroup was imposed or modified.

## Conservative admission and pressure policy

Effective available = min(host MemAvailable, max(0, cgroup memory.max − memory.current)) when
cgroup max is numeric. If explicitly unlimited, host available is used; unknown container capacity
is rejected. Cache already charged to a cgroup counts against headroom conservatively.

Default admission requires **256 MiB job headroom + 64 MiB reserve = 320 MiB effective available**.
This intentionally does not assume the observed ~93 MiB fixture covers all future jobs, and
may double-count the already-running worker. A 0.4 GiB available host can pass; one with only
300 MiB available is rejected rather than gambling on this small fixture's average footprint.

The sampler requests cancellation if sampled tree RSS exceeds 256 MiB. Available capacity is
rechecked every ten samples; below 64 MiB reserve also requests cancellation. Writes/encoder
waits check the event at bounded intervals, then terminate/reap the owned process group.
Trusted drawing and synchronous filesystem syscalls are not asynchronously preemptible.
A racing native allocation or another workload can still exhaust memory before the next sample.
**This policy reduces risk but cannot guarantee avoidance of host OOM without an enforced,
dedicated cgroup/VM limit.** `-max_alloc 67108864` guards FFmpeg-managed individual allocations;
it is not an RSS cap and does not bound all external-library mallocs.

One renderer process and one encoder, with codec/filter thread limits and zero lookahead/B-frames,
are used. The kernel pipe, one reused Cairo target and native encoder buffers are bounded in
count. There is no job multiprocessing, Python frame prefetch queue, NumPy effect array or PNG
intermediate. Dependency compilation/installation is not part of the runtime budget. Pending
video storage is destination-adjacent on the workspace disk; no video temporary goes to `/tmp`.

## Final observed results

All memory values below are MiB (1048576 bytes). Rows are individual jobs, not independent
maxima added together. Render+encode time includes capability checking, frame generation,
transfer, encoder finalization and atomic publication, but excludes subsequent verification.
Full workflow time including verification is present in raw JSON.

| Size / trial | Initial effective available | Renderer peak RSS | Encoder peak RSS | Estimated simultaneous tree peak | Render+encode s | Encoded fps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 360×640 / 1 | 7820.60 | 16.70 | 42.45 | 59.14 | 0.992 | 151.27 |
| 360×640 / 2 | 7819.91 | 16.74 | 40.86 | 57.72 | 1.161 | 129.17 |
| 720×1280 / 1 | 7819.70 | 19.58 | 73.31 | 92.89 | 2.341 | 64.07 |
| 720×1280 / 2 | 7817.82 | 19.59 | 73.31 | 92.69 | 2.185 | 68.66 |

All four estimated tree peaks were below the provisional 256 MiB envelope, with a maximum
of **92.89 MiB**. This is renderer **plus** encoder/technical child tools, not the Phase 2A
renderer-only figure. Runtime reserve/budget cancellation was not triggered. No OOM event or
swap usage was observed. The diagnostic's measured success on this larger host is not a
claim that complex future scenes or the actual low-memory VM are certified.

Cgroup context at the first final worker: memory.current **389439488 bytes**, historical
memory.peak **827715584 bytes**, memory.max **8589934592 bytes**. Raw memory.events showed zero
OOM/OOM-kill counters. The shared historical cgroup peak exceeds 256 MiB and includes unrelated
session work; it is **not** attributed to this job. Initial/final observations for every run
are retained, rather than using a shared absolute peak as a render benchmark.

## Remaining deployment evidence needed

Run the same worker on the actual 4-vCPU/no-swap VM, with realistic competing workloads,
low available memory and the intended persistent disk. Add a delegated per-job cgroup and
longer/complex-scene stress evidence before promising a hard production resource envelope.
Exercise disk pressure and process termination on that deployment. Keep current sampling
uncertainty, native buffering, CPU contention and platform layout limits visible to operators.
