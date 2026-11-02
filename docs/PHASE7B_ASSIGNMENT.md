# ReelForge V2 — Phase 7B: End-to-End Audio-Synchronized Reel Workflow

## Approved baseline

Repository:
https://github.com/lktoken34/reelforge

Approved Phase 7A commit:
`763d8528a7526614703cec4ad1292d1b037bdfca`

Create local development branch:
`phase7b-integrated-reel-workflow`

Phase 7A has passed standard GitHub CI: **1,014 tests passed, zero failures**.

Do not rebuild the approved engine.

## Objective

Implement the first unified ReelForge workflow that generates a complete cinematic MP4 with synchronized narration and sound effects.

Input: One validated storyboard, together with references to operator-registered audio assets and explicit audio timing.

Output: One complete H.264/AAC cinematic MP4, with deterministic visual timing, validated audio synchronization, resource reports and safe output publication.

The workflow must reuse:

- Phase 7A storyboard compilation
- Phase 6B cinematic direction
- Phase 6A character blocking
- Phase 5B procedural environments
- Phase 5C agent-authored objects
- Phase 4B audio registry, mixing, muxing and verification
- Existing Cairo renderer and bounded FFmpeg pipeline

This is an **integration milestone**, not a new animation, rendering or audio engine.

## Task 1 — Inspect the accepted integration boundaries

Before writing code, inspect:

- `src/reelforge/storyboards/`
- `tools/storyboard.py`
- `src/reelforge/stories/audio_contract.py`
- `src/reelforge/audio/registry.py`
- `src/reelforge/audio/processing.py`
- `src/reelforge/audio/transaction.py`
- `tools/render_audio_story.py`
- `tools/register_audio.py`
- Existing scene/rendering tools
- Existing resource monitors, owned transactions and cleanup tests

Document which functions and types can be reused directly.

The accepted storyboard timeline is currently fixed at 90 frames.

The accepted audio system uses:

- Operator-owned PCM16 WAV registry
- Registered narration and SFX IDs
- Integer-frame audio cue timing
- 48 kHz stereo processing
- 1,600 audio samples per video frame
- AAC-LC 128 kbps output
- Existing PCM mixing, H.264 stream-copy muxing and synchronization verification

Preserve those semantics.

Do not force a `story-0.2` object to represent a storyboard using fabricated shot data. Introduce a narrow, typed integration adapter where required.

## Task 2 — Introduce `reel-0.1`

Build a strictly validated, separately versioned integration contract.

Suggested structure:

- `schema_version`: `reel-0.1`
- `title`
- `storyboard`: one complete accepted `storyboard-0.1` document
- `audio`: the accepted Phase 4B audio-plan structure

The audio section must use the existing semantic contract and validator rather than introducing an incompatible cue model.

Use exactly one 90-frame timeline at 30 FPS.

Require at least one valid narration or SFX track for an audio-enabled reel.

Do not accept arbitrary filenames, audio URLs, shell commands, FFmpeg fragments, external includes or Python expressions in the manifest.

The operator may register supplied PCM16 WAV files using the existing trusted audio registration tool. An agent can then select approved asset IDs.

Keep the registration trust boundary separate from untrusted reel planning.

Provide strict schema discovery and semantic validation.

## Task 3 — Unified timeline

Visual and audio timing must share the same absolute frame clock.

Use:

- 30 FPS
- 90 output video frames
- 3.000-second video interval
- 48,000 audio samples per second
- 1,600 audio samples per video frame
- 144,000 effective samples per channel

An audio cue at video frame F must begin at scheduled sample index:

`F × 1600`

Storyboard cuts, beats, movement and camera changes must not reset or shift audio playback.

Audio cues may occur before, during or after a narrative beat, subject to strict timeline bounds.

Preserve existing cue trim and gain constraints. Do not infer audio timing from descriptions.

Reject invalid, out-of-range or unsupported audio cues with actionable errors.

Do not synthesize narration from text or invent sounds.

## Task 4 — Integrated reel pipeline

Implement:

`reel-0.1 JSON`
→ strict validation
→ storyboard compilation
→ audio registry resolution
→ safe workspace/resource preflight
→ existing silent cinematic renderer
→ audio snapshot and PCM mixing
→ AAC muxing
→ full audiovisual verification
→ safe final publication

The workflow should render the cinematic visuals once.

Do not render separate MP4s for every narrative beat.

Do not concatenate independently encoded shot videos.

The accepted storyboard compiler and direction evaluator must retain one continuous character/world timeline.

Reuse existing low-memory rendering and audio-processing components.

Avoid duplicated media code and unnecessary temporary files.

## Task 5 — Transaction ownership and cleanup reliability

This task is especially important.

Historical development-host runs have sometimes reported `TRANSACTION_CLEANUP`, including cases where an owned temporary directory reappeared after native FFmpeg work.

Do not dismiss these failures as harmless.

Implement the integrated workflow using the accepted owned-directory and process-supervision contracts.

Requirements:

1. Only one clearly owned job transaction per reel, with bounded internal stages.
2. No unsafe deletion outside the job's owned workspace.
3. No directory-name reuse that can create ownership ambiguity.
4. Correct native child-process termination and reaping.
5. Safe cancellation during validation, rendering, audio mixing, muxing and verification.
6. No-clobber final output publication.
7. No publication of an unverified final MP4.
8. Explicit verification that owned temporary resources were cleaned after native work.
9. Accurate failure statuses when cleanup cannot be established.
10. Preservation of diagnostic evidence without changing a failed job into a successful one.

Inspect whether the accepted Phase 4B transaction sequencing can be reused without nested ownership or ambiguous publication timing.

Make the smallest safe integration-level changes necessary.

**Do not rewrite the global transaction manager or weaken existing cleanup safeguards.**

If the temporary-directory restoration issue originates outside the new integration layer, preserve the evidence and report it instead of introducing a speculative workaround.

## Task 6 — End-to-end audiovisual verification

The final MP4 must contain:

- Exactly one H.264 video stream
- Exactly one AAC audio stream
- 720 × 1280 resolution
- 30 FPS
- 90 video frames
- 3.000-second video presentation interval
- AAC-LC, 48 kHz stereo, 128 kbps

Verify:

- Complete video decoding
- Complete audio decoding
- Exact video PTS progression
- Unchanged H.264 video bitstream through muxing
- Matching decoded video frame hashes
- Correct audio stream start/duration
- Effective 144,000-sample/channel audio interval
- Only accepted bounded AAC encoder tail padding
- No unexpected audible drift
- Correct narration/SFX cue placement
- No invalid audio clipping or unintended silence

Use the existing accepted audio verification policy and tolerances. Do not silently replace it with weaker checks.

Report cue-onset errors in both samples and milliseconds.

Where overlapping audio makes individual cue onset measurements ambiguous, distinguish isolated from overlapping cues honestly.

## Task 7 — Weak-agent authoring workflow

A weaker AI agent should be able to:

1. Discover ReelForge's reel capabilities.
2. Inspect the integration schema.
3. See registered audio asset IDs and approved metadata.
4. Select an existing storyboard or author a supported new one.
5. Attach narration and SFX cues by registered ID.
6. Validate the full reel request without rendering.
7. Inspect the complete timeline.
8. Inspect a selected video frame and scheduled audio cues.
9. Render the final synchronized MP4.
10. Read a structured technical result and repair invalid input.

Provide a small, clear CLI such as:

`python tools/reel.py capabilities`

`python tools/reel.py schema`

`python tools/reel.py validate <manifest>`

`python tools/reel.py inspect <manifest>`

`python tools/reel.py render <manifest> --output-dir <new-directory>`

Use actual supported command names in the final documentation.

Validation and timeline inspection must work without importing Cairo or FFmpeg.

Registry metadata inspection should not silently execute native media tools or open unrelated files.

Never require weaker agents to modify trusted Python code.

## Task 8 — Three integrated cinematic reel proofs

Produce three original 90-frame audio-enabled reels using the public integration contract.

### Reel A — The Silent Signal

Reuse or adapt the accepted woodland storyboard.

Include:

- Rowan discovering the damaged radio
- A suitable registered narration cue
- A restrained signal/static sound effect
- Camera framing that reveals the device
- Verified cue timing relative to the visual reveal

### Reel B — Abandoned Settlement

Include:

- Rowan exploring or reacting to an unseen threat
- Narration or an appropriate registered atmospheric cue
- A distinct effect timed near the reaction
- Rowan beginning to escape
- One deliberately timed camera cut
- Continuous motion and synchronized audio across that cut

### Reel C — Shelter Entrance

Include:

- Rowan approaching the shelter
- A visible pause/reaction
- Registered narration and/or environmental SFX
- A restrained cinematic push or hold
- Correct synchronization throughout

Audio proofs must be original or otherwise appropriately licensed and explicitly supplied or registered.

If synthetic diagnostic tones are used, label them as diagnostic audio rather than professional voice acting.

Do not claim high-quality narration exists unless actual narration is provided.

Do not use AI image generation, AI video generation or AI voice generation to substitute for the code-rendered and registered-media workflow.

## Task 9 — Artistic and editorial quality

Critically inspect the synchronized output, not just individual silent frames.

Evaluate:

- Whether narration matches the visual action
- Whether important SFX coincide with narrative events
- Whether sound distracts from or supports suspense
- Whether cuts feel synchronized
- Whether the reveal and reaction are readable
- Whether Rowan's actions remain continuous
- Whether camera movements support the story
- Whether audio starts or ends abruptly

Do not claim sound proves an unseen threat exists visually.

The three-second limit remains an artistic constraint. Report when a longer sequence is required for meaningful pacing.

Keep the focus on working audiovisual integration, not a complete sound-design library.

## Task 10 — Resource and deployment constraints

Preserve:

- Ubuntu 24.04 / x86_64 compatibility
- Python 3.12
- CPU-only execution
- Existing pinned Cairo/Pycairo requirements
- No GPU
- Existing FFmpeg encoder
- Strict 256 MiB process-tree budget
- 64 MiB reserve
- Existing memory/cgroup admission and observation
- Existing bounded native logging and cancellation
- Existing rendering and geometry budgets
- Existing audio size/duration limits
- Existing no-clobber and cleanup safeguards

The intended cloud VM has limited available memory, no swap and constrained `/tmp`.

Do not stage large intermediate data in `/tmp` or buffer all uncompressed video frames in RAM.

Use the existing approved workspace/storage-preflight approach.

Report sampled memory and storage usage accurately without claiming it proves the strict target-VM deployment gate.

## Task 11 — Compatibility

Preserve all **1,014 accepted tests** and every published contract.

No changes to the meaning of:

- `story-0.1`
- `story-0.2`
- `scene-0.1`
- `environment-0.1`
- `geometry-0.1`
- `composition-0.1`
- `blocking-0.1`
- `direction-0.1`
- `storyboard-0.1`

Avoid modifications to character, geometry, scene, blocking, direction, audio and renderer internals unless an integration adapter cannot achieve the required behavior.

Document every modification to pre-existing runtime modules.

Preserve the legacy 12-second audiovisual proof and all existing visual checkpoint suites.

Do not change the production episode CLI to `render_available: true`.

## Task 12 — Targeted tests

Add tests for:

- Strict reel contract validation
- Existing storyboard compatibility
- Registered audio lookup
- Invalid audio asset references
- Malformed or unsupported audio requests
- Cue scheduling and sample/frame conversion
- Timeline synchronization
- Storyboard cut continuity
- Correct integrated rendering
- Correct AAC/H.264 muxing
- Exact source/decoded video preservation
- Audio trim, gain and clipping rejection
- Failed asset snapshot handling
- FFmpeg failures
- Resource and storage limits
- Output no-clobber semantics
- Cancellation and native-process cleanup
- Historical transaction-restoration failure behavior
- Deterministic visual output
- Legacy audio/video regression preservation

Use targeted tests during development.

Do not invent new relaxed tolerances to make failures pass.

## Task 13 — Technical proof artifacts

Deliver:

- Three complete `reel-0.1` JSON manifests
- Three synchronized MP4s
- Compiled storyboard and direction inspection reports
- Frame/audio timeline diagrams
- Narration/SFX cue schedules
- FFprobe metadata
- Full video/audio decode results
- Video frame and stream-copy hash comparisons
- Audio onset/drift reports
- PCM clipping and peak/RMS statistics
- Temporary storage observations
- Whole-process-tree memory measurements
- Cleanup and publication reports
- At least one repeat-render determinism proof
- Full development test results and JUnit evidence
- A candid audiovisual/artistic review report

If an integrated job produces decodable media but returns a cleanup failure, retain its original failure status.

Do not report a failed job as successful solely because its MP4 exists.

## Task 14 — Credit-saving validation policy

We are minimizing unnecessary engineering-agent usage.

During implementation:

- Run targeted tests only where useful.
- Reuse accepted historical proofs.
- Do not repeatedly rerun the complete suite.

At final handoff:

- Perform one complete local full-suite attempt, if feasible.
- Preserve any development-host cleanup-restoration failure.
- Do not automatically retry the same failed test or render.
- Do not suppress cleanup assertions.

The publication agent will run **one standard GitHub CI gate**.

No independent three-run diagnostic phase unless an actual unexplained regression or high-risk change justifies it.

## Task 15 — Explicit exclusions

Do not implement:

- General raw screenplay interpretation
- Automatic LLM-powered script-to-JSON generation inside the engine
- Text-to-speech
- Speech-to-text
- Automatic timestamp extraction from narration
- Automatic sound selection
- New audio codecs
- New rendering backends
- Multiple characters
- Object physics
- Full 3D camera movement
- Long-form scene scheduling
- Arbitrary-duration storyboard expansion
- Production deployment
- Muse Spark integration

Longer reels, automatic script interpretation and cloud execution are future milestones.

This phase must deliver a reliable 3-second integrated audiovisual foundation first.

## Task 16 — Completion protocol

1. Implement on `phase7b-integrated-reel-workflow`.
2. Preserve the approved Phase 7A baseline.
3. Run targeted tests.
4. Produce and inspect three synchronized reels.
5. Verify all media streams and timestamps.
6. Preserve any failed cleanup evidence.
7. Attempt at most one final full local suite.
8. Report accurate performance, resource and storage measurements.
9. Commit the completed implementation locally.
10. Export the entire committed tracked repository using `git archive`.
11. Name the archive `ReelForge_Phase7B_Complete.zip`.
12. Verify archive integrity, committed file counts and artifact hashes.
13. Attach the ZIP, commit SHA and engineering report.

Do not push to GitHub.

Do not begin Phase 7C or production deployment.

Stop for independent review.

## Final success criterion

Using one validated reel manifest and registered audio assets, ReelForge must generate a complete deterministic cinematic MP4 containing:

- A procedural environment
- Original authored objects
- Rowan's motion and acting
- Cinematic camera direction
- Continuous storyboard timing
- Synchronized narration/SFX
- Verified H.264/AAC output
- Resource-safe execution
- Truthful transaction-cleanup and publication results

The new workflow must reuse the accepted engine components rather than create a parallel production system.
