# ReelForge V2

Phase 3A.1 builds on the approved Phase 1/2A foundation for an agent-operated, code-only 2D/2.5D
animation engine. An internal, trusted-Python Cairo vector backend and bounded FFmpeg pipe now produce
diagnostic MP4s, including one original articulated character with bounded motion presets.
They are not connected to episode manifests.
**No full cast, environment catalog, general animation timeline, lighting system, audio
synchronization, story-to-video production or advanced artistic QA is implemented.**

The long-term target is cinematic portrait storytelling on Ubuntu with 4 vCPUs, no GPU,
and only 0.4–1.0 GiB available RAM. The reference is an artistic target, not an achieved
quality level or proof of any particular authoring tool.

## Quick start

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). From this directory:

```bash
uv sync --frozen
uv run --frozen reelforge capabilities
uv run --frozen reelforge schema
uv run --frozen reelforge validate examples/foundation/project.json
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

`uv.lock` pins the full dependency graph and distribution hashes. Production foundation
installation can omit development packages with `uv sync --frozen --no-dev`.
No FFmpeg, Cairo, Pillow, NumPy, display server or GPU is needed for the foundation CLI.
The optional renderer extra is separate; see below.
An initial installation needs package access or an externally prepared wheel cache.
Validation itself is local and makes no network requests.

For package verification: `uv run --frozen python -m build --no-isolation` creates a wheel
and source archive. Install the wheel into a clean environment and run the same three CLI
commands from outside the repository; the schema is bundled inside the package.

## Current interface

Only `capabilities`, `schema` and `validate PATH` are supported. See
[AGENT_CONTRACT.md](docs/AGENT_CONTRACT.md) for the exact contract, examples and exit codes.
The supplied JSON describes ordered scene IDs, integer frame durations and human-readable
intent. Intent is documentation; it does not generate visual content.
Validation reports a manifest hash and **`render_ready: false`**. Output profiles are target
sizes, not measured hardware feasibility promises. No installed agent-facing command produces a video.

## Phase 2A engineering tools (retained)

Read [NATIVE_SETUP.md](docs/NATIVE_SETUP.md) for native setup, then:

```bash
uv sync --frozen --extra renderer
uv run --frozen --extra renderer pytest
uv run --frozen --extra renderer python tools/render_diagnostics.py --output-dir artifacts/phase2a
uv run --frozen --extra renderer python tools/benchmark_renderer.py --frames 500 --repeats 3 --output-dir artifacts/phase2a
```

[Completion report and measured results](docs/PHASE2A_REPORT.md),
[backend and surface contract](docs/CAIRO_BACKEND.md), and
[reference observations](docs/REFERENCE_STYLE.md). These tools are for trusted engineers;
weak agents still have only capabilities/schema/validate and `render_ready: false`.
CLI `phase: 1` continues to describe the exposed foundation interface, not this internal
engineering milestone. The renderer draws the same fixed 121-command scene at both sizes.

## Phase 2B video feasibility

[Pipeline contract and reproduction](docs/VIDEO_PIPELINE.md) ·
[Completion report](docs/PHASE2B_REPORT.md) · [Hardware measurements](docs/PHASE2B_HARDWARE.md)

```bash
mkdir -p outputs/phase2b
uv run --frozen --extra renderer python tools/render_video.py --width 720 --output outputs/phase2b/demo.mp4 --report outputs/phase2b/demo.json
uv run --frozen --extra renderer pytest --basetemp outputs/test-temp
```

FFmpeg with libx264 and ffprobe are required for this optional engineering workflow.
Sample 360p/720p MP4s, contact sheets and raw reports are under `artifacts/phase2b/`.
The sampler measures the renderer **and** child tools; renderer-only memory is not a job total.

## Architecture decision

Python 3.12 + JSON Schema Draft 2020-12, Pycairo/Cairo software image surfaces, and a
bounded raw-frame pipe to FFmpeg/libx264. Both adapters remain replaceable. Cairo drawing
and diagnostic encoding passed the earlier feasibility gates; actual target-VM safety and
future scene complexity remain separate gates.

- [Architecture and module boundaries](docs/ARCHITECTURE.md)
- [V1 source audit and reuse decisions](docs/V1_AUDIT.md)
- [Hardware budgets, alternatives and evidence](docs/HARDWARE_CONSTRAINTS.md)
- [Phased roadmap and review gates](docs/ROADMAP.md)
- [Stack decision record](docs/decisions/0001-foundation-stack.md)
- [Conventions and contribution checks](CONTRIBUTING.md)
- [Actual Phase 1 verification](docs/VERIFICATION.md)
- [Architectural review handoff](docs/PHASE1_HANDOFF.md)
- [Complete new-file list](docs/FILE_MANIFEST.md)

## Repository map

| Path | Purpose |
| --- | --- |
| `src/reelforge/contracts/` | Implemented schema, bounded loading and validation |
| `src/reelforge/core/` | Implemented diagnostic primitive |
| `src/reelforge/cli.py` | Implemented JSON CLI |
| `src/reelforge/characters/` | Original Rowan artwork, reusable skeleton, bounded motion and experimental preset schema |
| `src/reelforge/rendering/` | Trusted vector values, interface, Cairo adapter and diagnostic fixture |
| `tools/` | Engineering-only PNG and benchmark scripts |
| `artifacts/phase2a/` | Two diagnostic PNGs and raw six-trial benchmark JSON |
| `src/reelforge/media/` | Bounded encoder/process wrapper and technical verification |
| `src/reelforge/resources/` | Conservative Linux preflight and sampled process-tree metrics |
| `artifacts/phase2b/` | Diagnostic MP4s, checkpoints and measured job reports |
| `src/reelforge/{catalog,planning,animation,quality}/` | Documented future boundaries only |
| `examples/foundation/project.json` | Valid foundation manifest; no render claim |
| `tests/` | Validation, CLI and packaging-resource smoke tests |
| `docs/` | Audit, decisions, contracts, budgets and roadmap |
| `.github/workflows/ci.yml` | Frozen dependency installation and basic checks |

V1 code and the reference video are not embedded in this repository. The audit records
provenance. No V1 implementation is copied into the V2 runtime. No open-source distribution
license is assigned in this phase; the owner must choose one before external distribution.
Phase 2A and Phase 2B were approved. **Phase 2C tooling is complete; actual target-VM
validation is pending. Stop for external review after collecting that evidence.**

## Phase 2C deployment gate

Use [target deployment and exact commands](docs/TARGET_VM_DEPLOYMENT.md) and the
[Phase 2C evidence report](docs/PHASE2C_REPORT.md). The sequential harness checks both
sizes with 150/600 frames, repeats decoded-content comparisons, and records renderer,
encoder and supervisor memory. It retains the 256 MiB job / 64 MiB reserve policy.
Prebuilt, hashed wheelhouses are produced by the Ubuntu 24.04 CI job so the target need
not compile Pycairo. Native Cairo, FFmpeg/libx264 and Python 3.12 must already be available.

Development evidence is under `artifacts/phase2c/`. It does **not** demonstrate the actual
Muse Spark VM or operation in its 0.4–1.0 GiB available-memory window. No hard cgroup
limit is configured; the observed development cgroup mount is read-only.

## Phase 2C.1 memory compatibility

Phase 2C implementation was approved; the real VM attempt was blocked before rendering
because memory-controller telemetry was absent. [Memory policy and detection](docs/MEMORY_OBSERVABILITY.md)
adds an explicit, screened `--memory-policy guest_procfs_fallback` for the target guest;
strict remains default and real limits always apply. No safety thresholds were lowered.
[Exact cloud-operator steps](docs/TARGET_VM_PHASE2C1_PROMPT.md) start with a stdlib-only probe,
then new prebuilt wheels and short tests before long tests. Missing OOM telemetry yields an
observability-limited result, not deployment approval. See [Phase 2C.1 report](docs/PHASE2C1_REPORT.md).

## Phase 3A character study

One original character, **Rowan Vale**, now uses a shared 17-joint hierarchy and trusted
idle/walk/run presets. [Design and rig contract](docs/CHARACTER_RIG.md),
[agent preset](examples/characters/rowan_walk.json), and [measured/visual report](docs/PHASE3A_REPORT.md).
The episode CLI/manifest still advertise no general rendering capability. This is a
separate experimental preset interface, validated without importing native Cairo.

```bash
uv run --frozen python tools/validate_character.py examples/characters/rowan_walk.json
mkdir -p outputs/rowan-review
uv run --frozen --extra renderer python tools/render_character.py --output-dir outputs/rowan-review --stills-only
uv run --frozen --extra renderer python tools/render_character.py --output-dir outputs/rowan-review
```

Review proofs in `artifacts/phase3a/`: pose sheet, three full-resolution frames and a silent
5-second 720p MP4. Artistic acceptance is external; passing technical tests does not prove
reference-level quality. Target Muse Spark deployment remains blocked; its policies are
unchanged. **Stop after Phase 3A for review.**

## Phase 3A.1 motion quality review

Rowan now has planted transition contacts, heel/toe roll, torso/arm weight cues, bounded
satchel/hat/strap follow-through, and closed-menu acting additions. [Design and contract](docs/CHARACTER_POLISH.md)
· [report, measurements and remaining limits](docs/PHASE3A1_REPORT.md).
Compare [original left / refined right](artifacts/phase3a1/before_after.mp4),
[refined vertical clip](artifacts/phase3a1/rowan_refined.mp4) and
[annotated corrections](artifacts/phase3a1/review_sheet.png).
The original clip and 17-joint rig are preserved. The same six preset fields accept the
added look_around/react actions and surprised/frightened/determined expressions.
Artistic/catalog acceptance is pending independent review. Target deployment remains blocked;
no memory/security policy changed. Stop after Phase 3A.1.

### Phase 3B review candidate

One original code-authored orchard environment, bounded shot presets and six-second Rowan
integration are available for external review. See [environment contract](docs/CINEMATIC_ENVIRONMENT.md),
[technical/artistic assessment](docs/PHASE3B_REPORT.md) and [visual artifacts](artifacts/phase3b/).
Production episode rendering remains unavailable; target deployment remains blocked.

### Phase 3B.1 local artistic review candidate

The same orchard now has varied foliage/planting, attached local lighting, dusk material
grading and a separate bounded suspense shot. Original camera presets remain valid.
See [refinement contract](docs/ENVIRONMENT_POLISH.md),
[review and measurements](docs/PHASE3B1_REPORT.md), and [visual proofs](artifacts/phase3b1/).
The main A/B keeps the original framing/timing; the suspense demonstration is separate.
No production rendering, target deployment or later phase is approved.

### Phase 4A experimental multi-shot timelines

A weak agent can select existing assets, acting and three bounded compositions in JSON,
validate a contiguous integer-frame schedule, and stream one silent cinematic study:

```sh
python tools/validate_story.py examples/stories/last_farm.json
python tools/render_story.py examples/stories/last_farm.json --output-dir outputs/last-farm
```

See [timeline contract and workflow](docs/SHOT_TIMELINE.md),
[engineering/artistic review](docs/PHASE4A_REPORT.md) and [proofs](artifacts/phase4a/).
This experimental tool does not make the production episode CLI render-ready. No target
deployment or later milestone is approved.

### Phase 4B audio review candidate — cleanup gate blocked

Versioned story-0.2 JSON can select registered narration/effects, frame-grid trims and gains,
then stream-copy the H.264 video into a verified AAC MP4. Existing story-0.1 stays silent.
See [audio contract/workflow](docs/AUDIO_SYNC.md), [review report](docs/PHASE4B_REPORT.md),
and [audio evidence](artifacts/phase4b/). The local post-repeat temporary-file cleanup test
still fails; this is not an accepted Phase 4B gate or a production/batch rendering API.

Phase 4B.1 cleanup investigation remains blocked: see [CLEANUP_REPAIR.md](docs/CLEANUP_REPAIR.md)
for verified inode restoration, safety hardening and all three failed suite results. The ZIP is
a committed review checkpoint, not an approved reliability repair.

### Experimental scene graph — Phase 5A

The user has approved Phase 4B.1 at cdd56d1; older blocked notes above retain historical host
evidence. scene-0.1 now assembles registered components into distinct layouts with bounded groups,
transforms, layers, ground binding and camera references. See [authoring contract](docs/SCENE_GRAPH.md),
[engineering/visual report](docs/PHASE5A_REPORT.md), [JSON examples](examples/scenes/) and
[proofs](artifacts/phase5a/). Run python tools/scene.py capabilities, then validate/inspect/render.
Legacy story/audio contracts and the production episode CLI are unchanged. All new scene tests
pass locally; full-suite cleanup failures on this host still require isolated validation.

## Experimental procedural environments (Phase 5B)

Three original bounded environment families compile environment-0.1 requests into the
accepted scene graph. See [the authoring guide](docs/PROCEDURAL_ENVIRONMENTS.md) for
capabilities, exact fields and CLI examples, and [the review report](docs/PHASE5B_REPORT.md)
for visual evidence, measured costs and development-host validation limitations.
The production episode interface remains not render-ready.
