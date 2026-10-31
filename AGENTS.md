# ReelForge agent instructions

## Operating an episode (weaker agents)

1. Run `reelforge capabilities`. Use only advertised commands and schema versions.
2. Read `docs/AGENT_CONTRACT.md`; copy `examples/foundation/project.json` into your project.
3. Change only the manifest for episode work. Supply explicit values; never invent fields.
4. Run `reelforge validate PATH`. Parse stdout JSON and inspect the process exit code.
5. Repair the field at each error's JSON Pointer path. Retry at most three times; if a
   feature is unavailable, report it to the operator with the diagnostics.
6. For the currently exposed foundation interface, deliver the validated manifest and stop. `render_ready: false` is expected.
   Do not call hypothetical render commands or claim video output/artistic quality.

Do not edit `src/`, schemas, dependency files or tests to make an episode validate. Do not
insert Python, shell commands, expressions, network URLs or executable plugins into scene
data. No AI-generated imagery/video and no external raster-art shortcut. Future assets
must come from approved code-authored catalog recipes. Recorded audio will be a separate
local input in a later contract version, not a feature of this manifest.

## Engineering work (explicitly assigned engineers)

Episode restrictions above do not prevent an engineer from changing engine code for an
explicit engine-development task. Read architecture, hardware constraints and roadmap first.
Current approved engineering scope is Phase 2C.1: read-only memory topology detection,
explicit guest fallback compatibility, propagation, regression tests and target evidence. Keep drawing/video
commands out of manifests and the installed CLI. Do not begin the next milestone without a new
assignment following external review. Do not delegate to other agents unless explicitly requested.

- Keep contract validation independent of rendering and system executables.
- Use typed public functions, narrow modules, snake_case IDs and explicit errors.
- Reject unknown fields; never silently guess, coerce or substitute a visual fallback.
- Treat manifests as data, never code. Never use `eval`, dynamic imports or shell execution
  driven by manifest text. Future paths must be confined to project roots including symlinks.
- No wall-clock randomness. Future random streams derive from stable project/scene/entity
  identifiers and seed; never Python's randomized `hash()`.
- Do not add frame lists, scene-process pools, NumPy full-frame float effects or unbounded
  caches. Every future allocation/cache needs a documented budget.
- Bump draft contract IDs for incompatible changes and update example, docs and tests together.
- Add dependencies through `uv add` or edit pyproject + `uv lock`; commit the lock, not `.venv`.
- Run `uv sync --frozen --extra renderer`, pytest, Ruff lint/format checks, and wheel/sdist build.
  Also verify the base installation works without Cairo. Check the
  installed wheel from outside the checkout when package resources or packaging change.
- Document actual evidence and remaining uncertainty. Technical success does not prove art quality.

Phase 2B was approved at 7133f244. Phase 2C does not authorize visual systems.
Read docs/TARGET_VM_DEPLOYMENT.md before cloud tests. Never manufacture memory pressure,
lower safety thresholds to pass, change host swap/memory controls, or run competing jobs.
Actual target-VM evidence and external review remain required; development results do not
certify deployment. Read docs/MEMORY_OBSERVABILITY.md and
docs/TARGET_VM_PHASE2C1_PROMPT.md before target work. Use strict policy by default; the
explicit guest fallback flag never ignores a discovered limit. Stop after Phase 2C.1.
