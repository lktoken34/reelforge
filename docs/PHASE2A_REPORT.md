# Phase 2A completion and review report

Status: complete; **stop for external architectural review before Phase 2B**.
Date: 2026-10-31. Foundation version 0.2.0; agent manifest remains `2.0-draft1`.

## 1. Files created or changed

See PHASE2A_CHANGES.md for every changed/new path, and FILE_MANIFEST.md for the full source
inventory. Main additions are the drawing model/protocol/Cairo adapter, trusted diagnostic
fixture, engineering scripts, pixel/lifetime tests, two PNGs, raw benchmark JSON, reference
style observations, backend contract and native setup documentation. Foundation changes are
limited to numeric-overflow loading, optional dependency/version configuration, regressions,
CI and documentation/status. No working Phase 1 subsystem was rebuilt. Original attachments
were read only. The reference video/thumbnails, SDK, venvs and build caches are not bundled.

## 2. Interface/design

Backend-neutral frozen values describe M/L/C/Z paths, straight RGBA paints, padded linear
gradients, stroke joins/caps, local transforms and per-command clips. Explicit tuple order
is painter's order. Only trusted Python authors commands; JSON does not execute or dispatch
them. Renderer/Surface protocols expose owned targets, layout metadata, small pixel inspection,
no-copy hashing and static PNG writing. Cairo-specific objects stay inside one optional backend.
Default budget is 32 MiB for all simultaneously open owned targets, with stride-based accounting,
idempotent close, context-manager cleanup and use-after-close errors. It is not a whole-process
memory limiter. No caches, full-frame Python copies, supersampling or NumPy are used.

Pixel format is native-endian premultiplied ARGB32 (BGRA bytes on this little-endian host).
Actual strides are 1440 and 2880 bytes; target storage is 921600 and 3686400 bytes. Context,
path, gradient and clip/PNG scratch lifetimes/limitations are detailed in CAIRO_BACKEND.md.

The loader now rejects both positive and negative numeric overflow through `parse_float`,
including unknown/nested properties, before schema validation. Finite floats, JSON integer
semantics and existing schema constraints remain intact. Existing CLI commands remain exactly
capabilities/schema/validate; `render_available` and `render_ready` remain false. CLI `phase: 1`
continues to describe the exposed foundation interface rather than this internal experiment.

## 3–4. Actual memory and performance measurements

Available host: Ubuntu 24.04.3 LTS, x86_64, AMD EPYC 9V74; 9 logical CPUs visible/affined,
cgroup CPU quota `800000/100000` (8 CPU equivalents), cgroup RAM limit **8 GiB**. `/proc/meminfo`
reported ~9.73 GiB total and ~9.13 GiB available at the first worker observation; no swap.
These values come from different host/container views and are not a claim that 9 GiB was
available inside the 8 GiB limit. Python 3.12.14, Pycairo 1.29.2, Cairo 1.18.0. Native package
versions/checksum and build workaround are in NATIVE_SETUP.md.

Ran **3 fresh sequential worker processes per resolution**, each with 10 warm-up renders and
**500 measured renders**: 3000 measured + 60 warm-up frames in total. Each frame allocates a
new surface, draws the same 121-command fixture, hashes it and closes it. Frames/PNG bytes are
not collected; only first/last hashes, counters and 20 memory observations per worker remain.
Normal Python GC stays enabled. Each worker reported one thread, zero final owned surfaces,
zero accounted pixel bytes and zero swap.

| Resolution | Median allocation + drawing fps | Median full loop fps including hash | Initial RSS MiB range | Maximum measured peak RSS MiB | Final RSS MiB range |
| --- | ---: | ---: | ---: | ---: | ---: |
| 360×640 | 298.1 | 252.6 | 14.63–14.66 | 16.05 | 16.05–16.05 |
| 720×1280 | 120.6 | 94.3 | 14.62–14.63 | 18.70 | 18.69–18.70 |

Allocation + drawing excludes hash/PNG/release/sampling overhead; full-loop throughput includes
hashing, close and sampling but excludes warm-up, interpreter startup and PNG encoding. These
are static primitive-fixture rates, not animation/production-video fps. Shared-host load affects
trials: raw per-trial timing and samples are committed in artifacts/phase2a/benchmark_results.json.

Memory uses `/proc/self/status` VmRSS/VmHWM, live/released samples every 25 frames, plus Linux
`resource.getrusage(...).ru_maxrss`. The reported peak conservatively takes the largest of those
observations; the two kernel accounting views differ slightly, and both raw values are retained.
Initial RSS is after imports/fixture construction, final RSS after the last target closes;
result metadata/JSON serialization after that point is outside the measured render interval.
Renderer workers spawn no child processes, so this job's measured process tree is that single
worker, including its native allocations. The coordinating benchmark launcher is outside the
measured worker. Shared cgroup memory.current/peak includes other work and is recorded as context,
not falsely attributed to rendering. No dedicated per-job cgroup or 256 MiB hard cap was imposed.

Maximum observed peak (~18.70 MiB) is below the proposed 256 MiB renderer-job envelope. It does
not include a future scene compiler, agent, media process or encoder and does not establish
an entire-engine process-tree budget. No target 4-vCPU/0.4–1.0 GiB VM trial was performed.

Final minus post-warm-up RSS was 4–12 KiB across workers. Released RSS range over each worker's
last 250 frames was **0 KiB in all six trials**. This is a small warm-up/instrumentation plateau,
not sustained per-frame growth in these runs. Allocator retention means final RSS need not fall
to initial RSS after close. Finite trials do not prove absence of all possible leaks.

All 3000 measured frame hashes matched their warm-up reference; all three independent process
trials agreed per resolution. Layout-qualified pixel hashes:

- 360×640: `ab7c0bad67cc6bd486b12abd583fd8070a77a2de2b73c1230decff50761815fb`
- 720×1280: `49f65e59085d15a9a1134c39979ae592aba33f0f9f794f16a8f0548ef8f5c962`

These are same-native-stack pixel results, not a cross-platform or PNG-encoding guarantee.

## 5. Tests and verification

- Full optional-backend suite: **71 passed in 1.59s**. Original 42 Phase 1 cases remain present.
- Clean foundation environment without Pycairo: **46 passed, 1 renderer module skipped**; CLI
  capabilities succeeds without importing Cairo.
- Pixel tests exercise premultiplication, source-over, transparent clearing on reuse, curve edge
  antialiasing, clipping/state isolation, local transform order, resolution scaling, painter order,
  joins, gradient channels/transparency and repeatable output.
- Lifecycle tests exercise byte/dimension admission, multiple live surfaces, release after escaped
  exceptions and PNG I/O failure, idempotent close, foreign-owner rejection and use after close.
- Overflow regressions cover positive, negative/nested overflow, CLI error classification and
  continued acceptance of finite floats. Loader/schema behavior otherwise preserved.
- Ruff lint/format and frozen sync/lock checks passed. Wheel and sdist built successfully,
  with the wheel built from the sdist. A clean wheel-only environment ran all three CLI
  commands from `/tmp` without Cairo; after adding the pinned optional Pycairo, both installed
  fixture sizes rendered with hashes matching the recorded diagnostics. Schema/data resources
  were available outside the checkout. These are completed local checks, not future requirements.
- New GitHub Actions Cairo job is configured; remote CI execution is not claimed in this report.

## 6. Diagnostic PNGs and visual review

Both images are in artifacts/phase2a: diagnostic_360x640.png and diagnostic_720x1280.png.
Inspected both actual PNGs: smooth ribbon/ellipse edges, clean clipped stripe boundary, distinct
stroke joins, visible alpha swatches and consistent composition at both resolutions. Thin lines
and diagonals remain native-resolution samples rather than being resized from a larger frame.
This is a renderer diagnostic, not a character/environment/story or artistic reference match.

REFERENCE_STYLE.md documents 14 scene samples and three short bursts (21 unique timestamps),
including character simplification, thin/selective outlines, warm/dark interiors, haze/depth,
shot variety, caption treatment and directly observed local motion. No creator-tool inference.

## 7. Native installation

Standard Ubuntu development setup:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends libcairo2-dev pkg-config python3-dev build-essential
uv sync --frozen --extra renderer
uv run --frozen --extra renderer pytest
```

See NATIVE_SETUP.md for the actual restricted-host workaround, headless build setting,
exact observed native versions, low-memory wheel preparation and reproducibility boundaries.

## 8. Remaining limitations

No episode renderer, scene compiler, catalogs, characters, environment library, animation timeline,
choreography, lights/effects, text shaping, audio, encoder or production video. Per-paint alpha is
supported but group opacity/blend modes/nested clip stacks are not. Native clip/PNG scratch is
measured in RSS but not controlled by the explicit target-byte counter. Separate renderer instances
and arbitrary future scene complexity require a later job-level policy. Python/native build tools,
fonts and portable native environment pinning are not solved. Big-endian behavior is documented
but untested. Longer/more complex stress tests and target-VM deployment remain future gates.

## 9. Recommendation and stopping point

**Accept Cairo as the first CPU primitive backend for continued reviewed development.** The
available-host evidence supports clean native-resolution vector primitives and low memory for
this fixture. No evidence currently justifies introducing an alternative backend. Keep target-VM,
complex-scene, text/color and future-encoder feasibility as separate gates. Phase 2A is complete;
do not begin Phase 2B until the external architect reviews this implementation and report.
