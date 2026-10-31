# Phase 2B completion report

Status: complete; stop for external architectural review. No later milestone has begun.
Base: approved Phase 2A commit `c70d2f2788e08b96802792c17e30ce1e0fa9cff4`.
Branch: `phase2b-streaming`. Package version: 0.3.0; manifest remains `2.0-draft1`.

## Deliverables and design

Updated source, tests, two playable silent MP4s, two checkpoint PNGs and raw technical/hardware
reports are included. See PHASE2B_CHANGES.md for the exhaustive modified/added paths and
FILE_MANIFEST.md for the current repository inventory. VIDEO_PIPELINE.md defines the interface,
command, lifecycle, buffer contract, installation and reproduction. PHASE2B_HARDWARE.md explains
whole-job measurements and the conservative policy. No accepted renderer/contracts were rebuilt.

The Cairo adapter adds an opaque-proof flag and synchronous BGRA-to-fd transfer. Compatible
little-endian premultiplied ARGB32 is sent only with width×4 stride and proven global opacity.
No public memoryview, asynchronous borrowed-buffer callback, PNG intermediate, full-video RAM
store or unnecessary full-frame Python copy exists. Caller retains surface ownership; the
FFmpeg wrapper owns only process/pipes/output. One surface is reused across sequential frames.

The new media boundary uses CPU libx264, single codec/filter threads, restricted buffering,
bounded stderr, byte/count checks, timeouts/cancellation, process-group cleanup and atomic
same-filesystem publication. Existing files are protected unless overwrite is explicit.
No GPU, browser renderer, AI imagery/video, alternate codec fallback or audio is used.

The trusted frame-index function adds a moving translucent disc, a rotating/scaling foreground
card and a mild global camera-like push/translation to the accepted vector diagnostic. Fixed
painter ordering gives background/midground/foreground overlap. Time is exactly frame index,
not accumulated delta time. This is one diagnostic function, not a general timeline/scene library.

## Actual output and repeat verification

Two independent fresh encodes per size produced 150 frames at 30 fps, exactly 5.000 seconds:

| Size | Delivered file | Bytes | Format | Full decode |
| --- | --- | ---: | --- | --- |
| 360×640 | artifacts/phase2b/diagnostic_360x640.mp4 | 536332 | H.264 Main, avc1, yuv420p MP4 | 150/150 frames; exit 0 |
| 720×1280 | artifacts/phase2b/diagnostic_720x1280.mp4 | 1415235 | H.264 Main, avc1, yuv420p MP4 | 150/150 frames; exit 0 |

Both repeats at each size produced the same decoded RGB24 SHA-256 sequence. All 150 decoded
frames per clip were distinct. Source frame 0/75/149 hashes were distinct as well. Full decode
used `-xerror -err_detect explode`; there were no decoding errors. ffprobe confirmed dimensions,
codec, pixel format, avc1 tag, rate, frame count and duration. Bounded MP4 box inspection found
`ftyp, moov, free, mdat`: faststart metadata precedes media data.

Inspected both delivered contact sheets (frames 0,75,149 left to right). The red disc travels
left→center→right, the cyan card rotates/scales over the orange card, and the panel geometry
undergoes a small consistent camera-like push. Clips retain the diagnostic's composition,
curves, layering and alpha-over-opaque appearance. Chroma/lossy edge softening is expected.
This confirms intended diagnostic motion, not artistic/reference quality. Browser-compatible
format properties were verified; direct playback in a browser was not separately tested.

Byte-identical H.264 is not required across builds. Exact decoded visual equality here applies
to the same native FFmpeg/libx264 stack and settings. Raw commands/hashes/metadata are preserved
in artifacts/phase2b/benchmark_results.json. Repeat MP4 copies and per-worker intermediates remain
under ignored outputs/, not duplicated in the source artifacts.

## Whole-job measurements

Actual host: Ubuntu 24.04.3, 9 visible CPUs / 8-CPU cgroup quota, 8 GiB cgroup memory limit,
no host swap; **not the target 4-vCPU/0.4–1.0 GiB VM**. Initial effective capacity was about 7.64 GiB. Measured each renderer worker and all descendants through full technical decode.

| Size | Renderer peak range MiB | Encoder peak range MiB | Estimated tree peak range MiB | Render+encode time range | Effective encoded fps range |
| --- | ---: | ---: | ---: | ---: | ---: |
| 360×640 | 16.70–16.74 | 40.86–42.45 | 57.72–59.14 | 0.992–1.161 s | 129.17–151.27 |
| 720×1280 | 19.58–19.59 | 73.31–73.31 | 92.69–92.89 | 2.185–2.341 s | 64.07–68.66 |

Encoder exit status was **0** in every successful run. Every observed job was below 256 MiB;
that observation is not a hard guarantee. RSS sums are simultaneous sampled estimates, can
count shared pages twice and may miss brief peaks. Shared cgroup counters are recorded as
context; their historical peak is not presented as the job peak. PID-namespace-aware ancestry
and a live-child regression avoid renderer-only/zero-RSS mismeasurement. Details, raw initial/
final snapshots, kernel child high-water values and uncertainty are in PHASE2B_HARDWARE.md.

Default preflight requires 320 MiB effective capacity (256 MiB budget + 64 MiB reserve). Runtime
sampling requests cancellation above budget or below reserve. It does not change a shared
cgroup or guarantee host OOM avoidance under racing external/native allocations. FFmpeg's
64 MiB max_alloc is per allocation, not whole-process enforcement. Temp output is explicitly
on the destination workspace filesystem, addressing the small-/tmp deployment requirement.

## Tests actually performed

- Full foundation, Cairo, resource, failure and real-video suite: **103 tests passed**.
- Original Phase 1/2A tests remain present and passing; the installed agent CLI/schema are unchanged.
- Failure coverage: missing FFmpeg/libx264, invalid dimensions, format/byte-order/stride errors,
  byte-count mismatch, opaque-alpha rejection, early exit, broken pipe, blocked write and
  finalization deadlines, bounded tool/log output, failed publication, cancellation,
  KeyboardInterrupt, existing-output protection, child reaping and surface ownership/release.
- Raw transfer test confirms exact BGRA bytes after alpha-over-opaque compositing, without
  retaining a complete frame in the test consumer. Pure geometry is deterministic out of order.
- Real integration test performs two short encode/full-decode runs, compares decoded content,
  verifies metadata/faststart and rejects an incorrect expected frame count.
- Four full five-second measured encodes and four complete decodes succeeded, with repeated
  visual equality at both requested sizes. Both first/middle/final contact sheets were inspected.
- Clean base environment: **49 passed, 3 optional Cairo/video modules skipped**.
- Ruff lint/format, frozen lock consistency and wheel/sdist build passed. A clean installed
  wheel outside the checkout ran all three CLI commands without Cairo; with the pinned optional
  backend it completed an encode/full-decode smoke and returned owned surfaces to zero.
- One intermediate test invocation met a reused-scratch output collision; the no-clobber guard
  rejected publication. The final isolated full suite passed all 103 tests. No overwrite bypass
  was introduced.

## Reproduction

See VIDEO_PIPELINE.md for Ubuntu native installation and the full FFmpeg argument array.
From the repository with native prerequisites and `uv sync --frozen --extra renderer`:

```bash
mkdir -p outputs/phase2b-new
uv run --frozen --extra renderer python tools/render_video.py --width 720 \
  --output outputs/phase2b-new/demo.mp4 --report outputs/phase2b-new/demo.json
uv run --frozen --extra renderer python tools/benchmark_video.py \
  --output-dir outputs/phase2b-reviewed --scratch-dir outputs/phase2b-repeats-new
uv run --frozen --extra renderer pytest --basetemp outputs/test-temp
```

Choose fresh output paths; no-clobber is intentional. Encoder pending files are destination-
adjacent, never in /tmp. No network/model calls occur during render or technical verification.

## Unresolved risks and next milestone recommendation

Hard memory enforcement, actual target-VM contention/low-memory behavior, longer/complex-scene
load and native-build portability remain unverified. Soft sampling has races; draw/fsync/file
operations are not asynchronously preemptible. Big-endian/padded/nonopaque transfer is rejected,
not converted. Native codec buffers and file-cache use extend beyond target-surface counters.
Atomic publication requires local same-filesystem hard-link/rename support; filesystem failure
can prevent cleanup. Full verification occurs after a completed encode is published, so a later
verification failure can leave a completed file for diagnosis. No cross-build bit-exactness or
full color-management guarantee is made. The Linux/process implementation is not portable to
Windows. No story compilation, rigs, environments, general timeline, subtitles/audio, lighting
system or artistic auto-approval was added, and manifests still report render_ready:false.

Recommend the next **reviewed** engineering milestone focus on target-VM resource hardening:
a dedicated per-job cgroup, longer encode/cancellation/disk-pressure trials on the intended VM,
and explicit admission evidence under competing memory usage. Follow with separately scoped
code-authored character/rig work only after that review. No next-phase work is implemented here.

Cleanup hardening: explicit pending-file unlink precedes directory removal. The batch launcher
also reconciles only the known transaction path of each successfully reaped worker. Stale
exploratory leftovers were manually removed; source/review artifacts exclude transactions. A
fresh real render and a later filesystem audit passed. Abrupt external SIGKILL/host interruption
has no automatic recovery/scavenger in this milestone. Final benchmark rows above include this fix.
