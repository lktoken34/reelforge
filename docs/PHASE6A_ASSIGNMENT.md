# ReelForge V2 — Phase 6A: Generalized Character Motion and Scene Blocking

## Approved baseline

Repository:
https://github.com/lktoken34/reelforge

Approved Phase 5C commit:
`15b17f795d65adf1eb9d35d28f349084681372b4`

Create local development branch:
`phase6a-character-motion-blocking`

Phase 5C has passed independent engineering validation and accepted-branch GitHub CI.

**Do not rebuild the existing engine.**

## Objective

Build a reusable system that allows an AI agent to describe how Rowan moves through a scene using a small, strictly validated motion plan.

The system must support convincing:

- Idle-to-walk transitions
- Walking along an authored route
- Walk-to-run acceleration
- Running
- Deceleration and stopping
- Turning and changing direction
- Standing still after movement
- Expressive acting before and after movement

The result should look like a character actually traveling through the environment, rather than walking in place while the background moves.

The new system must be reusable across the accepted Phase 5A, 5B and 5C scene-generation systems.

## 1. Reuse accepted character animation

The existing implementation already provides:

- Rowan's articulated skeleton and rig
- `CharacterPreset` actions
- Idle, walk and run posing
- The foot-contact and two-bone leg solver
- Heel/flat/toe/swing foot behavior
- `LocomotionClock`
- `transition_pose`
- Secondary motion and follow-through

Inspect these systems before implementing anything.

**Do not create a second independent animation engine.**

Refactor narrowly where necessary to support generalized travel trajectories and timing.

Preserve the existing artwork, joint semantics and legacy animation outputs.

## 2. Introduce a declarative motion contract

Create a separately versioned experimental motion/blocking contract, preferably `blocking-0.1`.

An AI agent should be able to specify a character's movement using validated JSON rather than writing Python animation code.

Support bounded instructions for:

- Character identity
- Scene reference or embedded accepted scene specification
- Starting position
- Ordered movement segments
- Segment start/end frames
- Motion mode: idle, walk, run, turn, stop
- Destination or bounded route points
- Facing direction
- Supported acting and expression controls
- Optional approved motion-transition parameters

Use one coherent timeline with explicit interpretation of time and position.

Support a useful subset first, but make that subset work end-to-end.

Validation must reject overlapping or contradictory motion commands rather than resolving them unpredictably.

Keep the contract separate from existing `scene-0.1`, `environment-0.1`, `geometry-0.1`, `composition-0.1` and story contracts.

Do not change the meaning of accepted manifests.

## 3. Generalized motion and gait synchronization

This is the most important engineering task.

Implement deterministic evaluation of Rowan's position, motion state and pose at any absolute frame.

Requirements:

1. Derive travel position and velocity from the validated motion timeline.
2. Synchronize walking/running cycles with actual travel distance.
3. Preserve planted-foot contact during stance whenever the approved planar model can represent it.
4. Smoothly handle acceleration and deceleration.
5. Avoid foot sliding during transitions as much as technically possible.
6. Avoid sudden pose discontinuities at movement boundaries.
7. Keep arm swing, torso movement and secondary motion coordinated with locomotion.
8. Preserve believable weight shifts while stopping.
9. Handle left/right direction changes without teleportation or abrupt rig deformation.
10. Ensure repeated or out-of-order frame evaluation produces identical poses and positions.

Do not advance animation using mutable frame-to-frame state.

Do not solve movement by blindly translating existing walk-cycle drawings without regard for gait speed.

Provide an explicit mathematical relationship between distance traveled, stride phase and contact anchors.

If exact zero foot drift is impossible for a particular turn or speed transition, quantify the error and explain the model's limitation.

## 4. Route and scene blocking

Allow Rowan to travel along a short, bounded route within an accepted scene.

Support:

- Starting and destination anchors
- Short routes with multiple segments
- Stops at authored positions
- Changing movement speed
- Direction changes
- Deterministic timeline evaluation

Implement smooth motion only within the currently supported 2D/2.5D planar movement model.

Do not silently invent:

- General terrain physics
- Walking on arbitrary slopes
- Stair climbing
- Depth-aware 3D navigation
- Obstacle avoidance
- Automatic collision detection
- Fully general IK

Where necessary, reject unsupported trajectories.

The system must distinguish a visually drawn path from an actually supported walkable region.

## 5. Ground support and character placement

Phase 5A has conservative ground-support envelopes. Phase 5B adds procedural ground, but not a general terrain-height or collision system.

Introduce a bounded motion-support interface that allows a complete movement route to be checked against trusted ground information.

It should:

- Preserve existing stationary ground binding.
- Validate moving character support over the complete trajectory, not just at the endpoints.
- Keep character and supporting ground at compatible parallax depth.
- Maintain consistent contact coordinates through camera transforms.
- Reject unsupported or out-of-bounds travel.
- Prevent agent-authored decorative geometry from automatically becoming walkable terrain.

Prefer a limited, well-defined planar support corridor over a complex collision engine.

Demonstrate working routes in at least two different accepted procedural environment families.

Do not claim the full rendered ground is automatically traversable.

## 6. Scene and novel-object integration

Movement should work with the accepted scene graph and Phase 5C composition system.

Demonstrate Rowan:

- Walking past an original JSON-authored object.
- Approaching a constructed building or entrance.
- Stopping beside an object.
- Turning to face an object or direction.
- Running through a supported environment corridor.

These are **blocking and spatial staging demonstrations**, not physical object interactions.

No object pickup, pushing, carrying, opening doors, grabbing or hand-target IK is required in Phase 6A.

Those capabilities require separate engineering review.

Reuse accepted node identities, camera projection, painter order, depth and complexity accounting.

The agent should not need to modify trusted geometry or character Python code for a new valid blocking sequence.

## 7. Cinematic quality

Create clear, visually readable movement.

Pay special attention to:

- Character scale relative to the environment
- Grounded movement
- Foot contact during stops
- Body anticipation before acceleration
- Torso lean during running
- Smooth transitions into and out of motion
- Natural head and arm follow-through
- Readable facing-direction changes
- Avoiding obvious foreground clipping
- Good camera framing throughout travel
- Maintaining a recognizable silhouette

Avoid excessive movement speed simply to demonstrate animation.

The motion should feel deliberate and cinematic.

Use restrained camera choreography; do not use camera movement to disguise poor character blocking.

## 8. Camera and temporal integration

The existing scene graph supports locked, gentle-drift and approach camera presets.

Preserve their accepted behavior.

If Phase 6A requires an additional trusted follow-camera or tracking preset, implement it additively and document its bounds.

Camera and character movement must be evaluated consistently from the same absolute frame time.

Reject camera motion that sends the actor outside the supported world or creates invalid transforms.

Do not implement a general virtual cinematography director in this phase.

## 9. Strict execution and resource limits

Retain:

- CPU-only execution
- 720 × 1280 rendering
- 30 FPS
- Strict 256 MiB process-tree memory budget
- 64 MiB reserve
- Existing memory observability
- Streaming FFmpeg encoding
- No-clobber output publication
- Safe process cancellation
- Owned temporary-directory cleanup
- Existing geometry budgets

Current scene complexity caps remain:

- 64 nodes
- 32 visual instances
- 8 layers
- 4096 DrawPaths
- 80,000 path/clip operations

Do not increase them.

Motion timelines must have explicit bounded segment, route-point and frame counts.

Do not create an unbounded frame cache or allocate all rendered frames in memory.

The native-free compiler should validate routes, timing and support before opening rendering resources.

## 10. Test coverage

Preserve all **795 existing tests**.

Add targeted tests for:

- Strict motion-schema validation
- Duplicate, overlapping and conflicting timeline segments
- Malformed coordinates, times and unsupported actions
- Position and velocity continuity
- Gait-phase synchronization
- Planted-foot drift
- Idle/walk/run/stop transitions
- Facing-direction changes
- Out-of-order frame determinism
- Ground-support validation across complete routes
- Camera consistency
- Scene and procedural-environment integration
- Phase 5C composition compatibility
- Resource bounds and invalid-request rejection
- Render cancellation and cleanup
- Existing legacy pixel/audio preservation

Include numerical measurements for maximum foot drift and transition discontinuities.

Use meaningful thresholds justified by the accepted visual and mathematical model.

Do not invent passing thresholds after observing test results.

Do not weaken or remove legacy tests.

## 11. Visual acceptance proofs

Deliver at least three short original movement studies:

**Study A — Woodland traversal**

Rowan starts idle, walks along a supported route, stops and looks around.

**Study B — Settlement escape**

Rowan walks, accelerates into a run and exits the composition with suitable camera framing.

**Study C — Shelter approach**

Rowan approaches a shelter entrance, slows down, stops and changes facing direction.

At least one study must include an agent-authored Phase 5C object.

Produce:

- Three 90-frame cinematic MP4s
- Start/middle/end frames
- A contact sheet of motion transitions
- Frame-by-frame movement/foot-contact diagnostics
- Route and support visualizations
- Pose and position hashes
- At least one repeat-render determinism proof
- Decode verification
- Whole-job resource and cleanup reports

If a 90-frame study cannot show a transition clearly, improve its choreography within the approved experimental duration constraints instead of silently changing the output contract.

Inspect individual frames around heel strikes, speed changes, turns and stops.

All final frames must come from ReelForge's code renderer. Do not use AI-generated images or video.

## 12. Agent-facing interface

Provide simple commands for:

- Discovering blocking capabilities
- Reading the schema
- Validating a blocking request
- Inspecting the motion timeline
- Inspecting the position/pose at a specific frame
- Rendering a movement study
- Diagnosing invalid routes or unsupported terrain

The validator and trajectory inspector must function without Cairo or FFmpeg.

A weaker agent should be able to author a supported movement plan using documentation and examples alone.

Do not require agents to edit engine Python code.

## 13. Engineering and artistic report

Document:

- Motion architecture
- Timeline and trajectory mathematics
- Stride-phase integration
- Foot-contact stability
- Ground-support contract
- Camera and scene integration
- Agent authoring workflow
- Visual strengths and limitations
- Resource measurements
- Performance
- Determinism
- Legacy compatibility
- Test outcomes
- Known unsupported movement cases

Report real measurements rather than qualitative claims alone.

Clearly distinguish an experimental motion-capability demonstration from production-ready general character navigation.

## 14. Credit-efficient testing policy

We are deliberately reducing unnecessary testing expenses.

Follow this process:

**During implementation**

Run targeted tests covering the changed components.

Use the existing regression checks selectively where relevant.

Do not repeatedly run the entire suite after small edits.

**At final handoff**

Perform one complete local suite run when the workspace can execute it reliably.

If the known external temporary-directory restoration problem appears, retain the failure evidence. Do not repeatedly rerun the same failing suite.

Report the results honestly.

The publication agent will perform **one standard full GitHub CI run** on the accepted development branch.

Do not create a separate independent Ubuntu diagnostic branch by default.

Only recommend additional validation if there is a concrete unexplained failure, security concern or regression.

Do not change transaction ownership safeguards or suppress cleanup assertions.

## 15. Scope restrictions

Do not implement:

- New character rigs
- General multi-character choreography
- Object pickup or interaction physics
- Automatic pathfinding
- Arbitrary collision solving
- Terrain IK or walking on slopes
- Full 3D movement
- Automatic screenplay interpretation
- General camera direction
- New audio systems
- Production deployment
- Muse Spark integration

These remain future engineering milestones.

## 16. Completion and handoff

1. Implement Phase 6A on `phase6a-character-motion-blocking`.
2. Preserve the approved baseline and all existing tests.
3. Complete targeted validation and one final full-suite attempt.
4. Inspect and decode all three cinematic proofs.
5. Record actual performance, complexity, contact drift and sampled memory.
6. Commit the finished implementation locally.
7. Export the complete tracked repository using `git archive`.
8. Name the archive `ReelForge_Phase6A_Complete.zip`.
9. Include all tracked source, tests, documentation, rendered MP4s, PNGs and proof reports.
10. Attach the ZIP and report the exact commit SHA.

Do not push to GitHub.

Do not start Phase 6B.

Do not deploy Muse Spark.

Stop for independent review.

## Final acceptance criterion

ReelForge must demonstrate that an AI agent can author a valid declarative movement sequence and produce a cinematic scene in which Rowan **physically travels along a bounded supported route with convincing gait synchronization, stable contact, smooth transitions and deterministic rendering**.

The system must reuse the accepted character rig and scene graph rather than implement one-off animation tricks.

A successful Phase 6A creates the reusable foundation for future character-object interactions, cinematic direction and script-driven animation.