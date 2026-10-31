# ReelForge V2

Phase 2B builds on the approved Phase 1/2A foundation for an agent-operated, code-only 2D/2.5D
animation engine. An internal, trusted-Python Cairo vector backend and bounded FFmpeg pipe now produce
diagnostic MP4s. They are not connected to episode manifests.
**No character rigs, environments, animation timelines, lighting, audio synchronization,
story-to-video production or advanced artistic QA is implemented.**

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
sizes, not measured hardware feasibility promises. No command produces a video.

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

Python 3.12 + JSON Schema Draft 2020-12 now; recommend Pycairo/Cairo software image surfaces
for the later vector backend and a bounded raw-frame pipe to FFmpeg/libx264 for later
encoding. Keep both adapters replaceable. Cairo has passed the Phase 2A primitive experiment on this session host; actual target-VM
and future encoder/scene complexity remain separate gates.

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
Phase 1 was approved with changes; Phase 2A addresses those changes and adds the renderer
experiment. **Phase 2A was approved. Stop after Phase 2B for external review.**
