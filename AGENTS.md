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
Current assigned engineering scope is Phase 4B: registered frame-grid narration/effect audio,
reusing the accepted video sequence, renderer, encoder and resource policy. Keep drawing/video
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

Phase 2C.1 is approved at 84eee4a; target deployment remains blocked. Phase 3A is
development-host work only; no deployment/security/resource-policy changes are authorized.
Read docs/TARGET_VM_DEPLOYMENT.md before cloud tests. Never manufacture memory pressure,
lower safety thresholds to pass, change host swap/memory controls, or run competing jobs.
Actual target-VM evidence and external review remain required; development results do not
certify deployment. Read docs/MEMORY_OBSERVABILITY.md and
docs/TARGET_VM_PHASE2C1_PROMPT.md before target work. Use strict policy by default; the
explicit guest fallback flag never ignores a discovered limit. Do not deploy to Muse Spark
during Phase 3A. Review docs/CHARACTER_RIG.md. Stop after Phase 4B for independent review.

## Experimental character-preset work

When explicitly assigned a character study, use the six-field data contract in
`docs/CHARACTER_RIG.md` and `examples/characters/rowan_walk.json`. Validate with
`python tools/validate_character.py PATH` in the installed project environment. Select only
published IDs/actions/bounds; do not supply joint mathematics or alter artwork/engine source.
This validation does not make an episode render-ready. The fixed render_character.py proof
is an engineering tool, and no production episode rendering command is advertised.

## Experimental environment presets

Read `docs/CINEMATIC_ENVIRONMENT.md` and copy `examples/environments/orchard_push.json`.
Validate with `python tools/validate_environment.py PATH`. Select only published environment,
shot IDs and numeric bounds; never author paths/camera equations in scene data. The fixed
render_environment.py quality proof is engineering tooling, not a production episode command.
Phase 3B.1 passed external engineering/artistic review. Phase 4A passed review; Phase 4B is an unapproved audio review candidate.
Read docs/ENVIRONMENT_POLISH.md. Use --basetemp outputs/pytest-phase3b1 for pytest so
media integration tests satisfy the existing persistent-workspace policy. No GitHub push
or individual source/binary publishing is authorized for this local export assignment.

## Experimental story timeline workflow

Read docs/SHOT_TIMELINE.md. Copy examples/stories/last_farm.json and change only supported
fields/IDs. Validate with python tools/validate_story.py PATH; render the experimental
study with python tools/render_story.py PATH --output-dir outputs/NAME. Keep the installed
production episode CLI not render-ready. Timeline JSON cannot contain paths, code, equations,
arbitrary audio paths, arbitrary assets or policy overrides. Use pytest --basetemp outputs/pytest-phase4a.
Stop after Phase 4B; no push or deployment is authorized.

## Phase 4B audio candidate

Read docs/AUDIO_SYNC.md and docs/PHASE4B_REPORT.md. story-0.1 is unchanged; story-0.2
selects registered WAV asset IDs and bounded frame/gain values. Registry import is an operator
action, never agent-supplied code or FFmpeg expressions. Use pytest --basetemp outputs/pytest-phase4b.
The post-repeat cleanup regression must remain visible; do not skip it or claim the gate passed.
Do not advance past Phase 4B until all cleanup guarantees and review requirements pass.

## Phase 4B.1 cleanup investigation

Current assignment is transaction cleanup only on phase4b-cleanup-fix. Read
docs/CLEANUP_REPAIR.md. Ownership hardening is implemented but persistent pathname restoration
still blocks acceptance; three full suites failed. Do not weaken or skip those assertions.
Stop after this investigation checkpoint; no Phase 4C, GitHub push or deployment.

## Current Phase 5A assignment

The user-approved baseline is cdd56d1c183eaacb65b8ba1a11d4dd5f36bfef2e; external Phase 4B.1
review supersedes historical blocked-status notes above. Implement only scene-0.1 graph/registry
adapters on phase5a-generalized-scene-graph. Read docs/SCENE_GRAPH.md and docs/PHASE5A_REPORT.md.
Preserve all ownership, media, resource, legacy contract and artwork behavior. Retain every legacy
test. Workspace restoration is an environment limitation: never weaken assertions or add speculative
cleanup patches. No agent delegation was authorized. No GitHub push, deployment, Phase 5B/5C or
script interpreter is authorized. Stop after local commit and Phase 5A ZIP for independent review.

## Current Phase 5B assignment

The approved baseline is e9a38b12806c2bbaa396b9d3577f3342b379d364. Explicit user Phase 5B
authorization supersedes historical phase-stop notes above. Work is limited to bounded
environment-0.1 procedural generators on phase5b-procedural-environments. Read
docs/PROCEDURAL_ENVIRONMENTS.md and docs/PHASE5B_REPORT.md. Preserve scene-0.1,
legacy artwork, audio/video, transaction ownership and resource policy; retain all tests.
Keep development-host restoration failures visible. No agent delegation, GitHub push,
deployment, or Phase 5C is authorized. Stop after local commit and complete ZIP export.

## Current Phase 5C assignment

Phase 5B passed independent validation; the user-approved baseline is
82ebbe08e57f7f13217e64c57b86df994da1541b. This authorization supersedes historical
phase-stop notes above. Implement only geometry-0.1/composition-0.1 on
phase5c-novel-vector-geometry. Read docs/NOVEL_GEOMETRY.md and docs/PHASE5C_REPORT.md.
Keep all 692 accepted tests and the legacy scene, environment, story, audio, renderer,
resource and transaction semantics. No delegation, push, deployment, or Phase 6A.
Stop after local commit and complete Phase 5C ZIP export for independent review.

## Current Phase 6A assignment

Phase 5C passed accepted-branch CI. The exact approved base is
15b17f795d65adf1eb9d35d28f349084681372b4; the new assignment supersedes historical
phase-stop/independent-diagnostic notes above. Work only on bounded blocking-0.1 on
phase6a-character-motion-blocking. Read docs/BLOCKING.md and docs/PHASE6A_REPORT.md.
Preserve all 795 tests and legacy outputs/policies. Use targeted tests during development
and exactly one final full local-suite attempt; retain restoration failures without reruns.
Publication uses one standard CI run, not a separate diagnostic branch by default.
No delegation, GitHub push, deployment, Muse Spark or Phase 6B is authorized.
Stop after the local commit and complete Phase 6A Git archive for independent review.
