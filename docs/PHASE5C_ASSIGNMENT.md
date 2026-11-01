# ReelForge V2 — Phase 5C: Safe Agent-Described Novel Vector Geometry

## Approved baseline

Repository:
https://github.com/lktoken34/reelforge

Approved Phase 5B commit:
`82ebbe08e57f7f13217e64c57b86df994da1541b`

Create development branch:
`phase5c-novel-vector-geometry`

**Phase 5B has passed independent validation and is published.**

Its accepted implementation includes:

- The Phase 5A generalized scene graph.
- `scene-0.1` for registered asset composition.
- `environment-0.1` for three procedural environment families.
- Trusted procedural drawing recipes.
- Sealed `GeneratedGeometry` integration.
- Cairo rendering and streaming FFmpeg encoding.
- Strict resource monitoring and transaction ownership.
- 692 existing tests.

Do not rebuild these systems.

## Strategic objective

We are building ReelForge as a dedicated, CPU-only 2D/2.5D cinematic animation engine before MVP integration.

The long-term target is open-ended script-driven visual generation with deterministic, validated execution.

Phase 5B can create new environments from trusted procedural recipes. However, agents still cannot invent objects outside the engine's predefined visual vocabulary.

**Phase 5C must establish the first safe declarative vector-object language.**

A weaker agent must be able to author original geometry using structured JSON, validate it, and place instances in a rendered scene without modifying engine Python.

This milestone is a bounded creative authoring system, not arbitrary code execution or a complete general-purpose illustration engine.

## Task 1 — Define an agent-authored geometry contract

Introduce a separately versioned experimental `geometry-0.1` JSON contract.

The contract must describe original vector assets using declarative data only.

Support a carefully limited vocabulary of:

- Closed and open vector paths.
- Move, line and cubic Bézier commands.
- Basic rectangle, ellipse and polygon primitives, if useful.
- Fill and stroke materials.
- A bounded palette and safe gradients.
- Ordered subshapes.
- Local transforms and nested visual groups where justified.
- Anchors and reference dimensions.
- Named reusable asset definitions and separately placed instances.

The design must enable compound objects with multiple materials, silhouettes and internal detail.

Do not merely provide a list of new named presets.

An agent should be able to describe an object that the engine developers did not anticipate.

Specify exact numerical ranges, shape counts, operation limits, grouping depth and total document size.

Use the accepted immutable drawing model where possible.

## Task 2 — Native-free validation and compilation

Implement a safe compiler:

`Agent JSON → strict validation → bounded geometry IR → DrawPath commands → sealed generated assets`

Requirements:

1. Reject all unknown fields.
2. Reject duplicate JSON keys.
3. Reject NaN, infinity, invalid integers and excessive coordinate magnitudes.
4. Reject malformed Bézier paths, invalid subpaths and unsupported commands.
5. Reject unbounded nesting, excessive primitives and degenerate geometry that cannot be rendered safely.
6. Validate fills, gradients, stroke widths and clipping operations.
7. Reject unsupported transforms rather than approximating them silently.
8. Produce structured JSON Pointer errors.
9. Compute conservative expansion costs before producing large geometry.
10. Verify actual DrawPath and operation counts afterward.

Validation and compilation must not require Cairo, FFmpeg or other native backends.

Do not evaluate formulas, expressions, Python, JavaScript, SVG scripts, shell commands or arbitrary user-provided code.

No external URLs, image assets, file includes, imports or dynamic plugins.

## Task 3 — Meaningful geometry freedom

Design the contract so an agent can create objects with recognizable structure, not just arbitrary colored polygons.

Support:

- Hierarchical silhouettes.
- Separate front, side and interior components.
- Repeated details with explicit bounded duplication, if justified.
- Controlled material variation.
- Depth-compatible object layers.
- Reusable local coordinates and anchors.
- Multiple instances of one newly authored object.
- Composition from independently authored subparts.

A weak agent should be able to express an object using a modest JSON document and understand validation errors.

If the proposed JSON language becomes excessively verbose, introduce a smaller collection of safe declarative geometric primitives rather than relaxing security restrictions.

Keep all generated shapes strictly deterministic.

## Task 4 — Integrate with accepted scene composition

New agent-authored assets must work with the accepted scene-graph architecture.

Support placing them into:

- Existing declarative layouts.
- Phase 5B woodland environments.
- Phase 5B abandoned settlement environments.
- Phase 5B rocky shelter environments.

Use an explicitly versioned additive composition contract if needed.

Do not change the meaning of `scene-0.1`, `environment-0.1`, `story-0.1` or `story-0.2`.

Prefer reusing the Phase 5B sealed geometry interface rather than introducing a parallel rendering system.

Agent-authored asset names must not override trusted registered or private generated assets.

All instances must participate in normal:

- Transform composition.
- Stable painter order.
- Depth and parallax.
- Camera projection.
- Visibility.
- Complexity budgeting.
- Resource monitoring.

Agent-authored ground surfaces must **not automatically become character-supporting or walkable surfaces**. Support metadata requires a separately validated, bounded contract and explicit proof; otherwise mark it unsupported.

Do not implement general physics, collision detection or object interaction in this phase.

## Task 5 — Demonstrate truly novel objects

Create at least four distinct original compound assets authored through the new JSON geometry contract.

Suggested demonstrations:

1. A damaged roadside communications mast with equipment and cabling.
2. An improvised survival water cart with wheels, frame and container.
3. A damaged checkpoint watchtower or observation platform.
4. A portable emergency radio station or generator.

These examples must be authored through the public geometry contract.

Do not implement their shapes as special-case Python recipes or hard-coded asset IDs.

At least two objects must be reusable in more than one scene.

At least one scene must combine multiple original assets with the Phase 5B procedural environment generator.

Provide an additional held-out authoring demonstration: construct a previously unimplemented object from a fresh textual description using only the documented contract, with no engine source modifications.

Document what still requires manual vector design and what can be inferred reliably from a textual object description.

Do not claim that the geometry language itself automatically understands natural language.

## Task 6 — Geometry and material quality

Aim for recognizable cinematic silhouettes and cohesive 2D/2.5D artwork.

Prioritize:

- Readable proportions.
- Consistent perspective cues within the accepted 2.5D vocabulary.
- Logical structural connections.
- Materials with visible distinctions.
- Controlled shading and edge highlights.
- Foreground/background separation.
- Legible details at 720 × 1280.
- Sensible visual hierarchy.
- Consistent scale next to Rowan and existing buildings.

Avoid disconnected lines, malformed shapes, invisible objects, clipped essential details, excessively flat palettes and random decorative noise.

Use the existing renderer and material semantics.

Do not introduce unrestricted shaders, path filters or raster-image imports.

## Task 7 — Preserve resource and execution limits

Retain the accepted constraints:

- CPU-only rendering.
- 720 × 1280 output at 30 FPS.
- Strict 256 MiB whole-job process-tree budget.
- 64 MiB reserve.
- Existing memory observability.
- 64 graph nodes.
- 32 visual instances.
- 8 depth layers.
- 4096 DrawPaths.
- 80,000 path/clip operations.
- Bounded frame surfaces.
- Streaming FFmpeg encoding.
- No-clobber output publication.
- Owned transaction cleanup.
- Safe subprocess cancellation and reaping.

Budget newly authored geometry together with all trusted scene and environment components.

Check both per-asset and aggregate expansion limits.

Prevent repeated references to one asset from bypassing total scene costs.

No general increase to existing limits without quantitative justification and explicit review.

## Task 8 — Test security and determinism

Preserve all 692 accepted tests.

Add targeted tests for:

- Strict JSON parsing and schema validation.
- Primitive and Bézier construction.
- Compound-object hierarchy.
- Fill, stroke, gradient and clipping behavior.
- Transform correctness.
- Invalid geometry and degenerate paths.
- Numeric overflow and complexity expansion.
- Stable generated IDs.
- Unknown asset references.
- Collision with trusted asset namespaces.
- Reusing one asset across multiple placements.
- Out-of-order frame determinism.
- Scene graph integration.
- Environment integration.
- Character-support restrictions.
- Atomic output protection.
- Resource monitoring.
- Native render failure cleanup.
- Existing visual/audio regression checkpoints.

Include hostile and malformed JSON inputs designed to exercise the trust boundary.

A rejected input must not cause native allocation, partial artifact publication or unintended filesystem access.

## Task 9 — Visual acceptance evidence

Deliver:

- At least four original JSON-authored objects.
- One held-out new-object example.
- Full-resolution asset showcase images.
- At least three distinct scene compositions containing new objects.
- Layer/depth breakdowns.
- At least two short 90-frame cinematic MP4s.
- Complete decoded-video verification.
- Source geometry/pixel determinism.
- Resource and geometry complexity measurements.
- A visual comparison showing the objects reused at different positions and scales.
- A frank artistic limitations report.

All frames must be code-generated through ReelForge.

No AI image/video generator may be used to create output frames.

The held-out example should prove that the authoring system is general enough to express an object outside the implementation's example set.

## Task 10 — Agent usability

Provide documented commands for:

1. Discovering `geometry-0.1` capabilities.
2. Fetching the schema.
3. Validating an authored object.
4. Inspecting its compiled geometry.
5. Previewing it as a static asset.
6. Placing it into a scene.
7. Rendering a scene containing it.
8. Resolving common validation errors.

Expose concise machine-readable capability information appropriate for a weaker AI agent.

Documentation must include complete valid JSON examples and intentionally invalid examples with the expected error codes.

Keep validation and inspection usable without Cairo.

## Task 11 — Legacy preservation

The accepted Phase 5B procedural environments must remain functional and deterministic.

Preserve the original Rowan artwork, scene graph, environment generator, story pipeline, audio synchronization, encoder, monitoring and cleanup safeguards.

Compare existing pixel checkpoints in a matching pinned native environment.

Do not modify accepted tests or relax existing policies to accommodate the new geometry contract.

The production episode CLI remains unchanged unless an independently justified, explicitly additive extension is required. Do not prematurely advertise production readiness.

## Task 12 — Engineering report and handoff

Provide a complete review package containing:

- Contract/schema documentation.
- Safe compiler architecture.
- Trust-boundary diagram.
- Original JSON objects.
- Scene and placement examples.
- Security and complexity test results.
- Determinism evidence.
- Visual proofs and audiovisual proofs.
- Resource measurements.
- Compatibility report.
- Known creative and technical limitations.

The current development host has previously exhibited external restoration of private temporary transaction paths.

If this occurs again, preserve the failure evidence. Do not modify unrelated cleanup code or weaken assertions.

Independent Ubuntu/Python 3.12 validation will remain mandatory before acceptance.

## Explicit exclusions

Do not implement:

- Arbitrary executable drawing scripts.
- Direct untrusted SVG rendering.
- Natural-language screenplay interpretation.
- General character locomotion or interactions.
- Automatic skeletal rig generation.
- Physics or full 3D modeling.
- Arbitrary external assets.
- Unrestricted cities or environments.
- New audio features.
- Muse Spark deployment.
- MVP application integration.

These are future milestones.

## Completion protocol

1. Implement on `phase5c-novel-vector-geometry`.
2. Run all feasible tests.
3. Inspect and decode every generated proof.
4. Clearly report any development-host reliability failures.
5. Commit the complete implementation locally.
6. Export the tracked committed repository using `git archive`.
7. Name the export `ReelForge_Phase5C_Complete.zip`.
8. Attach the complete ZIP.
9. Report implementation SHA, test totals, maximum scene complexity, sampled memory, render performance and limitations.

Do not push to GitHub.

Do not begin Phase 6A.

Stop for independent engineering, security and artistic review.

## Final acceptance criterion

ReelForge must allow an agent to describe a structurally recognizable **previously unknown vector object** through validated JSON and render it within the accepted scene/environment system.

It must do this without changing trusted Python artwork recipes, weakening resource guarantees or introducing executable agent-authored code.

A successful Phase 5C proves that ReelForge has moved beyond selecting and varying predefined visual components toward genuinely extensible, safe object creation.