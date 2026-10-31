# ReelForge V2

Phase 1 repository foundation for an agent-operated, code-only 2D/2.5D animation engine.
**No renderer, character rigs, environments, animation, lighting, audio synchronization,
production video or artistic QA is implemented in this version.**

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
No FFmpeg, Cairo, Pillow, NumPy, display server or GPU is needed for Phase 1.
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

## Architecture decision

Python 3.12 + JSON Schema Draft 2020-12 now; recommend Pycairo/Cairo software image surfaces
for the later vector backend and a bounded raw-frame pipe to FFmpeg/libx264 for later
encoding. Keep both adapters replaceable. Confirm Cairo quality, packaging and total
process-tree memory on the actual host before accepting that backend in Phase 2.

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
| `src/reelforge/{catalog,planning,animation,rendering,media,resources,quality}/` | Documented future boundaries only |
| `examples/foundation/project.json` | Valid foundation manifest; no render claim |
| `tests/` | Validation, CLI and packaging-resource smoke tests |
| `docs/` | Audit, decisions, contracts, budgets and roadmap |
| `.github/workflows/ci.yml` | Frozen dependency installation and basic checks |

V1 code and the reference video are not embedded in this repository. The audit records
provenance. No V1 implementation is copied into the V2 runtime. No open-source distribution
license is assigned in this phase; the owner must choose one before external distribution.
Stop at this foundation and obtain architectural review before Phase 2.
