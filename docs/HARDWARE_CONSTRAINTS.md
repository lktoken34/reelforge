# CPU-only feasibility and hardware constraints

Phase 2A update: actual primitive-only measurements now appear in PHASE2A_REPORT.md and
artifacts/phase2a/benchmark_results.json. The Phase 1 analysis below remains the design baseline;
its proposed budgets have not become a production admission scheduler.

## Target and evidence limits

Design target: Ubuntu 24.04 LTS, Linux x86_64, 4 vCPUs, no GPU, often only **0.4–1.0 GiB
available RAM** for additional work. This is available memory, not necessarily the machine's
installed RAM or its container limit. The effective budget is the minimum of an operator cap,
cgroup remaining capacity and host available memory after a reserve. Other workloads can
change it during a job. Foundation tests are not constrained-host rendering benchmarks.

No production rendering, throughput target, Cairo benchmark or encoder benchmark was run in
Phase 1. All budgets below are proposed admission targets and arithmetic estimates. They are
not proof of reference-quality video at 0.4 GiB. Slower-than-real-time rendering is acceptable;
a quality-preserving scene design matters more than claiming real-time speed.

## Candidate comparison

These are engineering judgments based on API capabilities and deployment complexity, not
measured relative speed/RSS. Links are upstream sources, accessed 2026-10-31.

| Option | Suitability | Tradeoffs and decision |
| --- | --- | --- |
| Pycairo + Cairo image surfaces | Preferred CPU vector backend for curves, strokes, clipping, transforms and alpha | Native install/build requirements; premultiplied native-endian buffers; effect/text work needed. Benchmark first. [Image surfaces](https://cairographics.org/manual/cairo-Image-Surfaces.html), [Pycairo setup](https://pycairo.readthedocs.io/en/latest/getting_started.html) |
| Pillow/ImageDraw | Simple CPU raster fallback and possible conversion utility; V1 familiarity | Primitive edge quality and expressive vector paths need evaluation; whole-frame supersampling costs memory. Do not carry NumPy full-frame float effects by default. [ImageDraw](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html), [image transforms](https://pillow.readthedocs.io/en/stable/reference/Image.html) |
| Skia CPU raster via a suitable binding | Strong alternative if Cairo fails quality/effect requirements | Rich drawing API, but binding packaging/build footprint and actual memory must be tested. Native text layout is still a separate concern. [Skia API](https://skia.org/docs/user/api/), [CPU architecture](https://skia.googlesource.com/skia/+/refs/heads/main/docs/architecture/CPU.md) |
| Generated SVG + librsvg/Cairo | Possible source/interchange format for code-authored paths | Parsing/caching SVG each frame adds work and another format boundary; external references/fonts require confinement. Prefer direct draw commands for first backend. [librsvg](https://gnome.pages.gitlab.gnome.org/librsvg/) |
| Headless Chromium Canvas/SVG | Familiar JS ecosystem and text/layout tooling | Browser/process infrastructure is an unnecessary memory variable under this target; not selected. This is a design judgment, not a measured Chromium minimum. [Headless Chrome](https://developer.chrome.com/docs/chromium/headless) |
| Blender CPU | Useful 3D system, poorly aligned with constrained cutout engine | Official desktop minimum lists 8 GB RAM; headless scene use can differ, but no evidence supports this tiny available budget. Not selected. [Requirements](https://www.blender.org/download/requirements/) |
| FFmpeg drawing/filter graphs alone | Good later encoder/muxer, limited maintainable authoring surface for rigs | Keep encoding separate from graphics. Avoid story logic in enormous generated filter strings. [Formats/rawvideo](https://ffmpeg.org/ffmpeg-formats.html#rawvideo), [codec options](https://ffmpeg.org/ffmpeg-codecs.html) |

Recommendation: Python for contracts/control/catalog logic; Cairo in native code for future
software rasterization; raw-frame pipe to FFmpeg/libx264 later. Do not install every alternative
in the foundation environment. Rust/C++ is a later optimization option behind the same boundary
if profiling identifies Python overhead; rewriting the whole engine early would raise costs
without measured evidence. Manim/MoviePy-style high-level timelines are not chosen as the core
because explicit buffer/process lifetime control is a central requirement.

## Buffer arithmetic

For tightly packed pixels, bytes = width × height × channels. MiB = bytes / 1048576. Cairo
allocation must use actual stride × height. ARGB32 uses four bytes per pixel; the channels are
premultiplied, and native byte order matters.

| Portrait size | One 4-byte surface | Four such surfaces | Packed RGB24 frame |
| --- | ---: | ---: | ---: |
| 360×640 | 0.879 MiB | 3.516 MiB | 0.659 MiB |
| 720×1280 | 3.516 MiB | 14.063 MiB | 2.637 MiB |
| 1080×1920 (not a Phase 1 profile) | 7.910 MiB | 31.641 MiB | 5.933 MiB |

2× supersampling in both dimensions costs 4× surface storage, before downsampling temporaries.
A single float64 full-size 720p plane uses 7.03 MiB; multi-plane/intermediate NumPy effects can
quickly multiply that. Streaming RGB24 720p/30 carries ~79.1 MiB/s through the pipe, even though
only a bounded amount is resident. Python conversion/copy cost and encoder consumption matter.
Storing 90 seconds at 30fps in RGBA would require ~9.27 GiB. Never store a full frame sequence.

## Proposed low-memory envelope (not implemented)

Use **256 MiB total process-tree peak** as the initial experimental admission target for the
0.4 GiB case; leave ~154 MiB nominal headroom. The same budget need not consume all 4 cores.
Initial partition, to be revised from measurements:

| Bucket | Proposed ceiling |
| --- | ---: |
| Python, schema, compiled scene data and geometry | 64 MiB |
| Active drawing/conversion/scratch surfaces | 32 MiB |
| Byte-accounted catalog/geometry/raster caches combined | 24 MiB |
| FFmpeg encoder/filter process allocations | 96 MiB |
| Pipe, diagnostics and unclassified allocation margin | 40 MiB |
| **Total experiment target** | **256 MiB** |

These are accounting targets, not enforced per-component OS limits. Cgroup accounting may
include page cache; summing RSS may double-count shared pages. Record both process-tree peak
and cgroup memory peak where available. If a basic 720p probe cannot meet the target, explicitly
mark target720 unavailable for that budget and retain preview360 as a separate validated option.
Do not silently downscale or lower quality. At 1.0 GiB available, test a 512 MiB total envelope
with a larger reserve before increasing any cache/worker count. Swap must not be necessary.

Proposed scheduling: one drawing process, one encoder, one codec thread initially, explicit
filter thread counts, no scene-level multiprocessing, no frame prefetch beyond one owned frame.
Use compact vector geometry, native-resolution antialiasing and byte-bounded caches; reuse
buffers and release scene-specific resources on scene boundaries. Blurs/lighting/particles
are later scoped operations with bounded temporary regions, not default full-frame arrays.
Cache keys include recipe version, seed, dimensions and all parameters; track memory and
invalidate deterministically. Quality styles and catalog complexity must respect the budget.

Future preflight must account for scene complexity, transform expansion, font caches, clips,
mask sizes, encoder lookahead/reference buffers, maximum input dimensions and output disk
space. Compilation, installation and wheel building can themselves need more RAM than runtime;
prepare native wheels on a roomier Ubuntu build host rather than compiling on the tiny worker.

## Phase 2 measurement protocol

1. Record OS/CPU/architecture, Python, Cairo/Pycairo/FFmpeg versions and codec availability,
   input fixture hash, flags, thread counts, cgroup limit, swap and host memory availability.
2. On the actual 4-vCPU worker, run separate primitive-only Cairo and fallback experiments at
   360p and 720p. No characters, world generation or full story pipeline yet. Evaluate alpha,
   curves, strokes, clipping, transforms and repeated surface lifetime.
3. Measure wall time and peak total memory over enough repeated frames to expose cache growth.
   Use cgroup v2 memory.peak if delegated; otherwise a process-tree sampler plus `/usr/bin/time -v`
   per process with its limitations disclosed. Test 256/512 MiB limits if the host permits.
4. Once a later media adapter is separately authorized, repeat with FFmpeg backpressure and
   child-process accounting. Drawing-only RSS does not certify encoded-job feasibility.
5. Acceptance: no OOM/swap dependence, peak within approved envelope, stable repeated-frame
   memory, repeatable frame hashes on the pinned environment and inspected edge/alpha quality.
   Record observed fps without promising real-time output. If a target fails, document it and
   revisit backend/complexity/profile before building rigs or environments.

## Outstanding risks

Fonts/shaping and bundled licenses; Cairo-to-encoder copy cost and color handling; native wheel
availability; weak-agent scene complexity; encoder memory; cache lifetime and partial failures;
shared-host memory pressure; portable determinism. Phase 1 deliberately does not pretend these
are solved by having a JSON schema and a successful unit test suite.
