# ReelForge V2 — Phase 5B: Procedural Environment Generation

## Approved engineering baseline

Repository: https://github.com/lktoken34/reelforge

Approved Phase 5A commit:
`e9a38b12806c2bbaa396b9d3577f3342b379d364`

Create development branch:
`phase5b-procedural-environments`

Phase 5A has passed external architectural and visual review, three independent 590-test suites on Ubuntu 24.04 / Python 3.12, and accepted-branch CI.

Do not rebuild Phase 5A, the character rig, Cairo renderer, FFmpeg pipeline, audio system or transaction ownership system.

## Strategic objective

ReelForge is being developed as a reusable, dedicated 2D/2.5D cinematic animation engine before MVP integration.

Our ultimate ambition is **open-ended scene creation with the reliability of a curated engine**.

A weaker AI agent should eventually be able to translate a new script into original locations, geometry, object arrangements, lighting and animation by writing validated declarative instructions.

Phase 5A established a generalized scene graph and reusable asset placement.

**Phase 5B must go beyond repositioning existing orchard assets.**

Its purpose is to introduce bounded procedural generators that construct materially different environments through original code-authored vector geometry.

This is not yet the unrestricted agent-authored geometry compiler planned for Phase 5C.

## Task 1 — Procedural environment architecture

Develop a reusable procedural environment subsystem with clear separation between:

1. Agent-authored, strictly validated generator parameters.
2. Deterministic environment planning.
3. Trusted procedural geometry recipes.
4. Compiled Phase 5A scene-graph nodes and drawing commands.
5. Existing camera, Cairo, streaming video and resource safeguards.

Prefer a small set of composable procedural primitives and environment rules rather than one large hard-coded render function for each location.

Document the boundary between scene-level layout and individual generated assets.

The same procedural component should be reusable across different environments.

Keep validation and planning native-free. Only import rendering/media backends when actual rendering begins.

## Task 2 — Three distinct environment families

Create three original environment families:

### A. Woodland survival trail

Generate a believable forest or overgrown walking corridor with:

- Varied tree silhouettes and trunk structures
- Branches, foliage and undergrowth
- A distinguishable ground path
- Layered vegetation and atmospheric depth
- Foreground occlusion and background continuity
- Composition designed to accommodate a character

It must not simply be the original orchard with the barn removed.

### B. Abandoned settlement street

Generate an original ruined rural or small-town street environment with:

- Procedural building silhouettes and architectural variation
- Rooflines, walls, doors and windows
- A street or road surface
- Structural wear and carefully bounded damage details
- Street-level objects and vegetation
- Distant architecture, foreground elements and cinematic depth

This should demonstrate that ReelForge can create a convincingly different built environment.

Do not attempt a complete general-purpose city generator in this milestone.

### C. Rocky shelter approach

Generate a rugged location suitable for an underground shelter or bunker approach, including:

- Layered rocky terrain
- Cliff or hillside silhouettes
- A constructed entrance structure
- Terrain transitions and paths
- Sparse vegetation
- Atmospheric perspective
- Foreground framing and readable access to the entrance

The architecture, shapes and composition must be original procedural artwork.

## Task 3 — Genuine procedural variation

For each environment family, support bounded, validated parameters controlling meaningful visual structure.

Possible controls include:

- Stable integer seed
- Terrain profile
- Vegetation or architecture density
- Structural variation
- Path curvature or alignment
- Foreground framing
- Horizon and silhouette distribution
- Atmosphere and lighting conditions
- Detail level within explicit resource limits

The seed must drive independent deterministic streams so adding one object does not unpredictably rearrange unrelated objects.

Use stable IDs and explicit seed derivation, not global mutable random state.

Generate multiple visibly different compositions from the same family.

**A changed seed must produce actual geometry and layout variation, not just a palette change.**

Do not allow procedural expansion to exceed declared graph or render complexity limits.

## Task 4 — Agent-facing authoring contract

Introduce a strictly versioned experimental procedural environment request.

An isolated `environment-0.1` specification that compiles into the accepted scene graph is preferable if it avoids unnecessary changes to `scene-0.1`.

An additive `scene-0.2` contract is acceptable only if a clear architectural need is demonstrated and compatibility is proven.

The authoring interface must let a weaker agent select an environment family, seed, bounded composition parameters and supported art direction.

Require:

- Strict unknown-field rejection
- Structured JSON Pointer diagnostics
- Finite numeric validation
- Explicit supported ranges
- Stable semantic errors
- Deterministic compilation
- Reproducible scene inspection
- Bounded input and expansion complexity
- No executable agent-supplied code

No arbitrary file paths, shaders, dynamic imports, scripts or runtime Python generation are allowed.

The agent must be able to discover the exact supported generator capabilities without reading the renderer source.

## Task 5 — Scene-graph integration

Procedural outputs must use or cleanly extend the Phase 5A scene graph.

Preserve:

- Stable node identities
- Parent-child hierarchy
- Deterministic painter order
- World transforms
- Depth and parallax
- Camera transforms
- Visibility inheritance
- Asset complexity accounting
- Character placement and support-ground metadata

Design the generated terrain interface so Rowan can be placed at meaningful supported ground positions.

Do not claim terrain physics, inverse kinematics, generalized collision detection or arbitrary object interactions.

If a generated surface does not support character placement, report that limitation explicitly.

Avoid forcing every environment into the old orchard coordinate system or reusing the original farm ground as a visually incorrect universal floor.

## Task 6 — Cinematic artistic quality

The quality target remains our Stickocalypse reference, although this phase is not expected to reach complete parity.

Focus on:

- Readable silhouettes
- Cohesive color palettes
- Atmospheric perspective
- Convincing depth separation
- Balanced compositions
- Controlled highlights and shadows
- Material distinction between wood, stone, terrain and vegetation
- Clear character scale relative to buildings and terrain
- Deliberate negative space and foreground framing
- Camera motion suited to the composition

Avoid repetitive procedural noise, excessive random clutter, disconnected ground patches, unnatural floating objects, obvious copy-paste patterns and awkward object overlap.

Assess the rendered pixels at full resolution rather than assuming correct geometry guarantees good art.

Where necessary, add bounded environment-aware lighting or shading rules without rebuilding the approved renderer.

Do not introduce an unrestricted shader language.

## Task 7 — Determinism and resource safety

Retain the established operating constraints:

- CPU-only rendering
- 720 × 1280 output at 30 FPS
- 256 MiB strict whole-job budget
- 64 MiB reserve
- Existing cgroup/memory observability requirements
- One bounded render surface and streamed frames
- Existing FFmpeg safeguards
- No-clobber output publication
- Owned temporary-directory cleanup
- Safe cancellation and child-process reaping

The accepted scene-graph limits are currently 64 nodes, 32 instances, 8 layers, 4096 DrawPaths and 80000 path/clip operations.

If generated geometry requires changes to these caps, provide actual resource measurements, a mathematically conservative expansion bound and a specific justification. Do not silently raise them.

Prefer improving geometric efficiency or compiling generated detail into bounded trusted asset recipes over raising resource limits.

No unbounded recursion, geometry accumulation across frames or unlimited frame caching.

All frame evaluation must depend on absolute time, not prior frame history.

## Task 8 — Visual acceptance proofs

Create at least six declarative procedural examples:

- Woodland trail: two substantially different seeds
- Abandoned settlement: two substantially different seeds
- Rocky shelter: two substantially different seeds

Produce full-resolution representative images for all six.

For each environment family, generate at least one short 90-frame cinematic MP4 through the accepted rendering pipeline.

Provide:

- Contact sheets
- Start/middle/end frames
- Layer breakdowns
- Generated graph inspections
- Procedural parameter manifests
- Source geometry and image hashes
- Determinism evidence
- Frame and object complexity accounting
- Render timings and sampled whole-job memory
- Detailed artistic self-review

The examples must look like three distinct categories of environment, not three variations of the original farm.

No AI-generated images or video. All final frames must come from the code-authored ReelForge engine.

## Task 9 — Compatibility and regression

Preserve all 590 existing Phase 5A tests.

Add rigorous coverage for:

- Generator schema validation
- Deterministic seeds and stable IDs
- Geometry construction and bounds
- Distinct seed outputs
- Ground support and character scaling
- Parallax and painter order
- Out-of-order frame evaluation
- Complexity rejection before rendering
- Unexpected asset/parameter rejection
- Controlled output publication
- Subprocess failure cleanup
- Resource monitoring
- Invalid or unsupported generation requests
- Legacy scene compatibility

Verify that the existing Phase 5A scenes continue to render correctly.

Preserve legacy Rowan, orchard and story pixel checkpoints where rendering dependencies match the approved pinned environment.

Preserve Phase 4A/4B audio and video timing and exact existing manifest semantics.

No existing test may be deleted, skipped or weakened to obtain a pass.

## Task 10 — Honest scope boundaries

Do not implement the following prematurely:

- General-purpose arbitrary SVG or vector programs authored by AI
- Unrestricted procedural cities
- Novel character rigs
- Character-object interaction or physics
- Full 3D rendering
- Automatic screenplay interpretation
- Story-to-scene compilation
- New audio systems
- Cloud production deployment
- Muse Spark integration

These belong to later milestones.

Phase 5B demonstrates procedural environment families and an extensible generator architecture—not unlimited creative coverage.

## Task 11 — Reports and documentation

Create clear engineering documentation including:

- Generator architecture and dependency boundaries
- The experimental authoring contract
- Capability discovery
- Environment family parameters
- Seed and determinism rules
- Geometry and lighting methods
- Scene-graph integration
- Validation and resource limits
- Known unsupported scene requests
- Visual strengths and weaknesses
- Performance measurements
- Full test results
- Compatibility evidence
- Future extension points for Phase 5C

A weaker AI agent must be able to author and validate new environment requests using the documentation and examples alone.

## Development-host warning

Previous development environments exhibited unexpected restoration of deleted temporary paths.

Phase 5A passed three consecutive full 590-test suites on an independent GitHub-hosted Ubuntu 24.04 environment.

If the current workspace exhibits the same external filesystem behavior, retain all failures as evidence.

Do not modify the transaction ownership safeguards, weaken cleanup assertions, retry indefinitely or perform unrelated filesystem sweeps.

Independent Ubuntu validation remains a separate acceptance requirement.

## Completion and handoff

1. Implement Phase 5B on `phase5b-procedural-environments`.
2. Inspect the generated artwork and MP4s.
3. Run all feasible engineering tests.
4. Clearly distinguish full-suite passes from development-host cleanup failures.
5. Preserve unchanged existing engine and resource safeguards.
6. Commit the implementation locally.
7. Export the complete committed tree using `git archive`.
8. Name the export `ReelForge_Phase5B_Complete.zip`.
9. Attach the ZIP with all tracked source, tests, reports, stills and video proofs.
10. Report commit SHA, tests, render performance, maximum memory, asset complexity and known limitations.

**Do not push to GitHub or start Phase 5C.**

A separate local PC agent handles GitHub publication after independent engineering and artistic review.

## Success criterion

ReelForge can accept a validated procedural environment request and produce multiple genuinely different, coherent, deterministic 2D/2.5D locations through trusted geometry generators and the accepted scene graph, without manually rewriting scene-specific renderer code.

The results must demonstrate reusable creative capability—not merely more named presets.