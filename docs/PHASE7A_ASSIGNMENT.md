# ReelForge V2 — Phase 7A: Narrative Planning and Storyboard Compilation

## Approved baseline

Repository:
https://github.com/lktoken34/reelforge

Approved Phase 6B commit:
`930cd75bf77778ffb7f16594b7aa4994ed950c46`

Create local branch:
`phase7a-narrative-storyboard`

Phase 6B is accepted. Its standard GitHub CI passed all 935 renderer tests.

Do not rebuild previous engine components.

## Objective

Build the first unified, agent-facing story-planning layer for ReelForge.

Existing capabilities:

- Phase 5A: Generalized scene graph
- Phase 5B: Procedural environments
- Phase 5C: Agent-authored vector objects
- Phase 6A: Character movement and blocking
- Phase 6B: Cinematic direction and camera cuts
- Phase 4B: Existing story audio and synchronization

Today these are separate experimental contracts and tools.

Phase 7A must create a **single declarative storyboard workflow** that coordinates the relevant visual systems and produces a complete short cinematic sequence.

An AI agent should specify narrative beats, selected assets, Rowan's actions, movement timing and shot intentions without editing engine source code.

This is a structured storyboard compiler, not a general natural-language screenplay interpreter.

## Task 1 — Introduce storyboard-0.1

Create a strictly validated, versioned experimental `storyboard-0.1` contract.

It should represent:

- Story title
- One accepted world/environment
- Approved or authored visual assets
- One Rowan character
- Ordered narrative beats
- Beat timing and durations
- Character actions and motion
- Camera emphasis and shot intent
- Important objects or focal subjects
- Optional descriptive metadata for the agent or reviewer

For this milestone, keep the output to a bounded 90-frame, 30-FPS cinematic sequence.

Use explicit narrative beat types such as:

- Establish
- Discover
- Approach
- React
- Escape
- Hold

These labels must have documented meanings or validated constraints. Do not pretend the engine understands arbitrary emotional language.

Description fields are metadata only unless a deterministic, documented compilation rule uses them.

Avoid requiring agents to repeat unnecessarily large nested JSON structures.

Consider local symbolic references to definitions embedded within the same document, but no filesystem includes, URLs or executable logic.

## Task 2 — Build a real storyboard compiler

Implement:

`Storyboard JSON → validation → narrative/timing plan → accepted blocking and direction plans → scene evaluation → existing renderer`

Reuse the approved implementation rather than creating a parallel pipeline.

The storyboard compiler must add real value beyond wrapping an existing `direction-0.1` document.

It should coordinate:

- Beat scheduling
- Subject references
- Motion timing
- Shot allocation
- Supported camera choices
- Cross-beat continuity
- Compiler-generated accepted intermediate plans

Expose the resulting blocking and direction plans for inspection.

Use deterministic compilation rules. Where artistic decisions cannot be made reliably from provided data, require the agent to specify them.

Do not silently invent characters, locations, props, movements or emotional performances.

## Task 3 — Narrative timing

Make the 90-frame micro-story timeline explicit.

Support multiple narrative beats with:

- Strict ordered intervals
- No gaps or overlaps
- Unique beat identifiers
- Valid subject references
- Character action continuity
- Consistent movement timing
- Cinematic shot boundaries

The underlying Rowan world timeline must not restart when a camera shot changes.

Require enough time for supported walk, run, stop and reaction behaviors.

Reject impossible short-duration transitions rather than breaking the Phase 6A contact solver.

Do not assume every narrative beat requires a camera cut.

## Task 4 — Asset and environment integration

Compile storyboards using the existing scene, environment and geometry systems.

Support at least:

- All three Phase 5B procedural environment families
- Phase 5C JSON-authored objects
- Rowan's accepted character rig
- Phase 6A blocking where routes are valid
- Phase 6B cinematography

Preserve:

- Stable object identity
- Depth and parallax
- Existing painter order
- Geometry budgets
- Supporting-ground restrictions
- Object registration and anchors

Agent-authored decorative geometry must not gain walkability or physical interaction privileges.

Do not implement general object collision, pickup, physics or automatic navigation.

## Task 5 — Continuity and story coherence

Build explicit structural continuity checks.

For example:

- Rowan cannot begin a movement from an unrelated location without a supported transition.
- An object referenced by a camera must exist in the compiled scene.
- A discovery beat must identify a valid subject.
- An escape beat must describe a supported route and timing.
- Shot cuts must preserve the underlying character timeline.
- Object IDs must remain stable across beats.
- Unsupported movement, framing or visibility must produce actionable errors.

These checks establish structural coherence, not automatic understanding of what makes a good story.

Provide structured error codes and JSON Pointer paths.

## Task 6 — Reusable story-planning presets

Introduce a small library of deterministic cinematic narrative patterns, such as:

1. Discovery and reaction
2. Approach and suspense
3. Threat and escape

These are planning patterns, not hard-coded final videos.

An AI agent must be able to select a pattern, provide supported world and subject choices, and vary its timing within validated limits.

Do not hard-code one example's object IDs or artwork into general compiler logic.

Keep presets understandable to weaker AI agents.

## Task 7 — Produce three original micro-stories

Demonstrate three distinct sequences.

### Film A — The Silent Signal

Rowan moves through a woodland environment, notices a damaged communication device and cautiously investigates it.

### Film B — Abandoned Settlement

Rowan explores a deserted street, reacts to a suspected threat and begins to escape.

### Film C — Shelter Entrance

Rowan approaches a rocky shelter, pauses near the entrance and responds to something unseen.

Each should be authored using the new public storyboard contract.

All three must compile into real engine plans.

At least two films must include original Phase 5C authored objects.

Demonstrate different camera timing and narrative structures, not three visually identical templates.

Use only actually supported character actions. If the intended narrative implies hearing a sound, describe that through the visible reaction or metadata; do not claim audio is present when it is not.

## Task 8 — Cinematic quality

Review the rendered sequences for:

- Clear beginning, development and ending
- Readable subject motivation
- Consistent character placement
- Camera continuity
- Effective shot duration
- Clear focal hierarchy
- Environmental depth
- Useful suspense and negative space
- Believable character movement
- Avoidance of needless camera cuts

Phase 6B demonstrated technically correct camera control but also some overly abrupt reframing and reveals of already-visible objects.

Phase 7A should improve **editorial intent**, not merely add more camera movements.

Critically inspect full-resolution frames and actual decoded videos.

Do not claim Stickocalypse-quality parity unless the work genuinely supports it.

## Task 9 — Native-free planning and validation

The storyboard validator and compiler-planning inspector must function without Cairo or FFmpeg.

Implement commands to:

1. Discover capabilities
2. Retrieve JSON schema
3. Validate a storyboard
4. Inspect its narrative beats
5. Inspect compiled scene, blocking and camera plans
6. Inspect a selected absolute frame
7. Render storyboard stills
8. Render an MP4

Prevent:

- Unknown fields
- Duplicate JSON keys
- Invalid numeric types
- Nonfinite values
- Excessive nesting
- Invalid object references
- Unsafe external paths
- Arbitrary scripts or expressions
- Unsupported timeline combinations
- Resource-budget bypasses

Do not allow untrusted narrative descriptions to become executable instructions.

## Task 10 — Preserve accepted engine limits

Retain:

- CPU-only rendering
- 720 × 1280 output
- 30 FPS
- Existing 256 MiB process-tree budget
- 64 MiB reserve
- Existing memory observability
- 64 nodes
- 32 instances
- 8 depth layers
- 4096 DrawPaths
- 80,000 path/clip operations
- Streaming FFmpeg encoding
- Bounded frame surfaces
- Safe cancellation and process reaping
- No-clobber output publication
- Strict temporary-directory ownership

Do not alter existing renderer, audio, transaction-cleanup or resource policies.

Do not extend the duration or number of simultaneous characters in this milestone.

## Task 11 — Compatibility

Preserve all **935 accepted tests**.

Do not change the meaning of:

- `story-0.1`
- `story-0.2`
- `scene-0.1`
- `environment-0.1`
- `geometry-0.1`
- `composition-0.1`
- `blocking-0.1`
- `direction-0.1`

The new storyboard layer must be additive.

If a small integration adapter is necessary, document precisely why it is required.

Preserve legacy visual checkpoints, audio synchronization and existing rendering semantics.

Do not declare the production episode CLI render-ready.

## Task 12 — Tests and proof artifacts

Add targeted tests covering:

- Storyboard validation
- Beat scheduling and references
- Narrative pattern expansion
- Deterministic plan compilation
- Motion and camera continuity
- Scene and authored-object integration
- Invalid instructions and unsupported combinations
- Resource-budget rejection
- Legacy compatibility
- Rendering failure handling
- Output protection and cleanup

Deliver:

- Three storyboard JSON examples
- Three final 90-frame cinematic MP4s
- Start/middle/end frames
- Beat-boundary frames
- Source and decoded contact sheets
- A narrative-beat timeline diagram
- Compiled blocking and direction reports
- Frame and object determinism evidence
- At least one repeat-render check
- FFprobe/full-decoding verification
- Performance and resource measurements
- A candid artistic-review report

Do not use image-generation or video-generation models to create final frames.

## Task 13 — Credit-efficient validation

We have deliberately reduced redundant testing.

During implementation:

- Run targeted tests for changed code.
- Reuse existing regression evidence where appropriate.
- Avoid unnecessary repeated full-suite runs.

At final handoff:

- Attempt the complete local suite once, if feasible.
- Preserve any known development-host cleanup-restoration failure without rerunning it.
- Never weaken cleanup assertions or modify unrelated resource code.

The publishing agent will perform **one normal GitHub CI run** on the accepted Phase 7A branch.

Do not create a separate diagnostic branch or run three complete test suites by default.

Additional validation is justified only by a concrete failure or important security/regression concern.

## Task 14 — Exclusions

Do not implement:

- General free-form screenplay interpretation
- Automatic AI screenplay-to-JSON generation inside the engine
- Multi-location episode orchestration
- Multiple characters
- Object interaction physics
- General navigation or terrain walking
- New character artwork
- New sound generation
- Unrestricted external media
- A new renderer or encoder
- Production deployment
- Muse Spark integration

Those are separate future milestones.

Phase 7A is about making accepted components work together through one reliable structured narrative interface.

## Completion protocol

1. Implement on `phase7a-narrative-storyboard`.
2. Preserve approved Phase 6B behavior.
3. Run targeted tests.
4. Perform at most one final full-suite attempt.
5. Inspect and decode all three films.
6. Record real timing, resource and visual-quality measurements.
7. Commit locally.
8. Export the complete committed tree using `git archive`.
9. Name the archive `ReelForge_Phase7A_Complete.zip`.
10. Attach the ZIP, commit SHA and engineering report.

Do not push to GitHub.

Do not begin Phase 7B or deploy Muse Spark.

Stop for review.

## Final success criterion

An AI agent must be able to author **one structured narrative storyboard** and obtain a deterministic short cinematic film combining:

- A generated environment
- Previously authored objects
- Rowan's motion or acting
- Meaningful camera direction
- Correct narrative beat timing
- Preserved scene continuity

The work must be reusable, bounded, safe, compatible with all accepted earlier phases and demonstrably better than manually stitching unrelated demonstration clips.