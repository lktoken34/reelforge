# ReelForge V2 — Phase 6B: Cinematography and Scene Direction

## Approved baseline

Repository: https://github.com/lktoken34/reelforge

Approved Phase 6A commit:
`ca35dad8a006d04601db0d0885b6484348c8f54f`

Create local branch:
`phase6b-cinematic-direction`

**Phase 6A has passed standard GitHub CI: 862 tests passed.**

Do not rebuild Phase 6A or earlier engine components.

## Objective

Develop a reusable cinematic-direction system that lets a weaker AI agent describe how an existing scene should be filmed through validated JSON.

Phase 6A controls **what Rowan does and where he moves**.

Phase 6B must control **how the camera presents that action**.

The desired result is a more deliberate cinematic experience, using composition, tracking, anticipation, reveals and shot changes rather than arbitrary camera movement.

This is an engine-capability milestone, not automatic script interpretation.

## Task 1 — Cinematic direction contract

Introduce an experimental, strictly versioned `direction-0.1` contract.

It should reference or embed an approved scene, environment, composition or blocking specification without changing those original contracts.

Support a bounded, explicit camera-shot timeline with:

- Shot IDs and start/end frames
- Camera framing modes
- Subject or validated focal-point selection
- Target position and bounded zoom
- Pan, push-in and tracking movement
- Optional look-ahead for a moving character
- Controlled camera holds
- Hard-cut shot transitions
- Bounded composition and framing offsets

Use continuous global frame time for character motion.

A camera cut must not accidentally restart Rowan's locomotion or change his physical world position.

All input values must have defined units and validated ranges.

## Task 2 — Reusable cinematic camera behaviors

Implement a focused set of trusted camera behaviors.

**Establishing:** Reveal the environment, its spatial arrangement and the character's position.

**Character follow:** Track Rowan with controllable screen-space lead while he walks or runs.

**Push-in:** Gradually move closer to a subject or important location.

**Reaction framing:** Emphasize Rowan's existing acting and expression presets.

**Object reveal:** Shift attention toward a registered or JSON-authored object.

**Suspense hold:** Use restrained framing, negative space and a deliberate camera hold.

These behaviors should be composable through a validated plan, not implemented as one-off logic for each demonstration.

Do not introduce unrestricted camera scripts or mathematical expressions.

## Task 3 — Camera mathematics and determinism

Camera state must be evaluated directly from absolute frame time.

Requirements:

1. Smooth, bounded interpolation of camera position and zoom within each shot.
2. Correct parallax behavior across approved depth layers.
3. No double application of camera transforms.
4. Consistent actor/ground registration.
5. Stable subject positioning where tracking is requested.
6. Explicit hard-cut semantics at shot boundaries.
7. No dropped, repeated or inserted timeline frames.
8. Out-of-order evaluation must produce identical results.
9. No mutable frame-history dependency.
10. No unbounded per-frame caching.

Use the existing camera/scene transform architecture where practical.

A tracking camera must follow the actual Phase 6A world trajectory, not an unrelated visual approximation.

If an authored camera target or move exceeds supported bounds, reject it with a structured error.

## Task 4 — Framing and shot safety

Define clear framing constraints suitable for vertical 720 × 1280 output.

Include:

- Subject visibility and safe screen margins
- Character head/foot framing
- Reasonable camera lead room
- Readable object silhouettes
- Controlled foreground occlusion
- Bounded zoom and pan
- Intentional versus accidental cropping
- Shot continuity checks

Allow explicitly declared departures or reveals that intentionally move a subject out of the frame.

Do not silently reject every artistic crop; distinguish approved intentional framing from unsupported camera positions.

Keep the implementation grounded in the accepted 2D/2.5D projection model.

## Task 5 — Shot sequencing

Support a small number of contiguous shots within one 90-frame experimental film.

For this milestone, prioritize **one continuous underlying world and motion timeline** with different camera views.

This avoids prematurely building a generalized multi-location story editor.

Require:

- Explicit frame intervals
- No gaps or overlaps
- Deterministic cut boundaries
- Correct source-frame timing
- Continuous Rowan movement across cuts
- Continuous environment animation where supported
- Consistent object identity and placement

Hard cuts are sufficient for Phase 6B.

Do not implement complex crossfades, motion blur or postproduction transitions unless independently justified.

Preserve legacy `story-0.1` and `story-0.2` behavior exactly.

## Task 6 — Character and object integration

Demonstrate cinematic direction using the accepted:

- Phase 5B procedural environments
- Phase 5C original vector objects
- Phase 6A Rowan blocking and movement

Camera targets may reference validated actor positions, trusted scene anchors or explicitly bounded world points.

Do not infer physically meaningful attachment points from arbitrary decorative geometry.

Preserve existing painter order, parallax and resource accounting.

Do not add object interaction, physics or additional characters.

## Task 7 — Cinematic demonstration films

Produce three original 90-frame studies.

### Study A — Woodland suspense

Begin with an establishing view, follow Rowan along his supported route, then frame an important object or suspicious location.

Demonstrate a deliberate visual reveal.

### Study B — Settlement escape

Use Phase 6A's walk-to-run blocking.

Demonstrate camera tracking with suitable lead room, followed by an intentional departure or hard cut.

### Study C — Shelter discovery

Begin with a wider environmental composition, move toward the shelter entrance, then frame Rowan's reaction.

Demonstrate focal-point control and restrained camera motion.

At least one study must contain a Phase 5C JSON-authored object.

Deliver three fully decoded MP4s, representative stills, shot-boundary frames, contact sheets, annotated camera trajectories and frame-by-frame camera reports.

Produce one deterministic repeat-render proof for a selected study.

All rendered frames must come from ReelForge's CPU renderer. No AI-generated images or videos.

## Task 8 — Artistic acceptance

The target remains cinematic storytelling comparable in intent to the supplied Stickocalypse reference.

Assess:

- Clear visual storytelling
- Subject readability
- Natural camera speed and easing
- Useful negative space
- Strong establishing compositions
- Deliberate suspense
- Effective shot progression
- Smooth tracking
- Consistent character scale
- Environmental depth
- Avoidance of distracting crops
- Visual continuity across cuts

Critically inspect the actual frames.

Avoid camera movement that exists only to demonstrate a feature.

Do not disguise character-motion limitations through aggressive tracking or excessive zoom.

Report remaining artistic weaknesses rather than claiming reference-quality parity.

## Task 9 — Compatibility and resource safety

Preserve all 862 accepted tests and existing contracts.

Retain:

- CPU-only rendering
- 720 × 1280 at 30 FPS
- 256 MiB strict process-tree budget
- 64 MiB reserve
- Existing memory/cgroup safeguards
- Existing scene and geometry limits
- Single bounded rendering surface
- Streaming FFmpeg encoder
- Safe cancellation and process reaping
- No-clobber output publication
- Strict temporary-file ownership and cleanup

Do not alter the audio system.

Do not change the accepted character rig, foot-contact solver or locomotion mathematics.

Preserve all existing legacy pixel and audiovisual compatibility checkpoints.

If a new camera needs additive graph-evaluation hooks, ensure legacy evaluation uses exactly its previous path by default.

## Task 10 — Testing

Add targeted tests for:

- Strict JSON validation
- Shot timeline contiguity
- Camera interpolation
- Tracking accuracy
- Target references
- Scene-depth/parallax consistency
- Actor framing
- Cut boundaries
- Motion continuity across cuts
- Out-of-order determinism
- Unsupported camera commands
- Resource and geometry budgets
- Cancellation, output protection and cleanup
- Legacy pixel/audio compatibility

Measure tracking error and camera discontinuities using predeclared tolerances.

Do not weaken existing tests.

### Credit-saving testing policy

During development, run targeted tests for changed functionality.

Perform only **one final local full-suite attempt** if feasible.

If the established development-host temporary-directory restoration issue occurs, preserve the failure evidence and stop repeating the same test.

The publishing agent will use **one normal GitHub CI run**.

Do not create independent diagnostic branches or run three complete test suites by default.

Additional diagnostics are justified only by an unexplained failure, meaningful security concern or regression.

## Task 11 — Agent interface

Provide commands for:

1. Camera capabilities
2. Schema discovery
3. Direction-plan validation
4. Shot-timeline inspection
5. Camera inspection at a specific frame
6. Stills rendering
7. Cinematic MP4 rendering

Validation and camera inspection must operate without Cairo or FFmpeg.

A weaker agent should author supported camera direction entirely through validated JSON.

## Task 12 — Documentation and reports

Document:

- Contract and supported shot types
- Camera and projection mathematics
- Shot timing
- Motion/shot continuity
- Tracking and framing safety
- Known unsupported cinematography
- Determinism evidence
- Visual review
- Render performance
- Memory measurements
- Complexity accounting
- Legacy compatibility
- Tests and cleanup outcomes

Use real measured evidence.

## Explicit exclusions

Do not implement:

- Automatic script interpretation
- AI-generated camera instructions from raw audio
- New character rigs or motion systems
- Object interaction physics
- General multi-character direction
- Unrestricted camera scripting
- Full 3D camera movement
- New audio synchronization features
- Production deployment
- Muse Spark integration

Keep Phase 6B focused on cinematic camera control and shot presentation.

## Completion protocol

1. Implement on `phase6b-cinematic-direction`.
2. Preserve the Phase 6A baseline.
3. Run targeted tests.
4. Complete at most one final local full-suite attempt.
5. Inspect and decode all cinematic proofs.
6. Report camera metrics, complexity, FPS and sampled memory.
7. Commit the complete implementation locally.
8. Export the committed tracked repository using `git archive`.
9. Name it `ReelForge_Phase6B_Complete.zip`.
10. Attach the ZIP, final SHA and engineering report.

Do not push to GitHub.

Do not start Phase 6C or Phase 7.

Stop for independent review.

## Final success criterion

ReelForge must allow an AI agent to describe a short cinematic shot plan through validated JSON and render a deterministic film where **camera framing, subject tracking, shot cuts, scene depth and continuous character movement work together correctly**.

The implementation must remain reusable, bounded, CPU-only and compatible with every accepted earlier phase.