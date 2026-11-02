# ReelForge V2 — Phase 7A engineering report

Date: 2 November 2026. Status: **implemented and exported for independent review**.
The local gate is not green: the one full suite retained two established audio cleanup
restoration failures, and two proof CLI jobs retained encoder cleanup restoration errors.
Their complete MP4 media is preserved and fully decoded. No failed test/encode was retried.
This report is not deployment approval or a claim of Stickocalypse-quality parity.

## Baseline and additive scope

Approved Phase 6B commit: `930cd75bf77778ffb7f16594b7aa4994ed950c46`.
Local branch: `phase7a-narrative-storyboard`. The supplied assignment is preserved in
`PHASE7A_ASSIGNMENT.md`; the final commit SHA accompanies the download.

New `src/reelforge/storyboards/` provides a versioned native-free contract/schema, three
narrative grammars, bounded input validation, cumulative beat scheduling, symbolic reference
resolution, carried actor state, accepted-plan generation, view coalescing, editorial cut
admission and inspectors. `tools/storyboard.py` exposes capabilities/schema/validate/beats/
compile/frame/render (including --stills-only). `STORYBOARDS.md` documents every field,
rule, unit, action, limitation and command.

**No existing runtime, tool, contract or test file was modified. No integration adapter was
needed.** All 142 accepted source/tool/test files were compared byte-for-byte with the
approved Git baseline. Earlier artwork/media/resources are likewise unchanged in the Git
diff. Only new modules/tools/tests/examples/evidence/docs and current README/AGENTS notes
are added. The production CLI remains unchanged and not render-ready.

## Why this is a compiler

The input is one storyboard, not an embedded direction document. It embeds one accepted
world once, defines local subject/view aliases once, and supplies timed narrative entries.
The compiler:

1. Validates a selected narrative grammar and supported type/action combinations.
2. Schedules beat durations into unique contiguous half-open intervals covering [0,90).
3. Carries Rowan's X/Y/facing and accepted endpoint velocity through generated segments;
   no later beat can supply a new starting location or implicitly stop him.
4. Expands supported action shorthand into explicit accepted walk/run/stop/idle segments
   with the authored expression, destination and timing.
5. Resolves local actor/node/point subjects against one world and expands camera views.
6. Coalesces adjacent beats with the same view into one shot, preserving easing and holds
   over that whole occurrence. Different views create hard cuts; a beat alone does not.
7. Generates real blocking-0.1 and direction-0.1 documents, then calls their unchanged
   validators/compiler. It remaps rejection paths to the authored action/view/world.
8. Rejects storyboard cut pan jumps over 60 logical units and validates all focal aliases,
   including node aliases that are not directly used by a camera.

The generated documents are delivered independently for every film and can be fed directly
to the older tools. Tests recompile them and compare actual geometry against the unified
result. The existing direction evaluator receives absolute global frames and the original
scene renderer streams one film, rather than stitching separately rendered clips.

Patterns are deterministic **planning grammars**, not an AI screenplay interpreter. They
require particular ordered observable stages and compile the explicit user-supplied actions.
They do not invent missing beats, choose objects, derive routes from prose or infer feelings.
Durations/artistic camera values remain explicit. Metadata descriptions never enter accepted
motion/camera documents. Alias-renaming and metadata-change tests prove the generated plan
is independent of those arbitrary labels/instructions. A held-out shelter seed also compiles.

## Micro-stories and editorial choices

| Film | Pattern / beat intervals | Camera allocation |
| --- | --- | --- |
| The Silent Signal | discovery_reaction: establish 0–9; approach 9–45; discover/stop 45–57; look-around reaction 57–75; hold 75–90 | One pan/push shot shared by all five beats, opening hold 9 frames and closing hold 15 |
| Abandoned Settlement | threat_escape: establish 0–6; explore 6–33; discover/stop 33–45; react 45–60; escape 60–90 | Four beats share the first fixed establishing composition; one matched cut at 60 starts the actual run follow |
| Shelter Entrance | approach_suspense: establish 0–6; walk 6–42; stop 42–60; hold 60–72; react 72–90 | One restrained entrance push shared across all beats; opening hold 6, closing hold 18 |

All three use the existing seed-417 procedural family appropriate to their setting.
Woodland and settlement each embed original Phase 5C-authored geometry/placements. Woodland
includes mast/cart/radio, with a local broken-aerial radio variation; settlement includes
watchtower/cart/radio. No generic compiler logic names those objects. Shelter uses the
accepted generated environment and an explicitly declared doorway/unseen focal point.
There are no invented threat actors, sounds, pickups, collisions or navigation.

The woodland radio is now **entirely outside the opening canvas**, then becomes fully visible
by frame 75 and remains readable at the end. This is an actual offscreen-to-visible reveal,
not a claim that an already-visible object was newly discovered. Bounds/visibility assertions
and actual decoded frames support that statement. The damaged mast remains visible earlier,
providing spatial context. Foreground framing was explicitly opened through the accepted
world parameter before final proof rendering to clear the radio's silhouette.

Across all three films there is **one camera cut**, versus five cuts in the earlier Phase 6B
studies. That is an editorial design comparison, not a controlled artistic rating. The sole
cut at settlement frame 60 moves camera pan by **2.2729716 logical units**, changes zoom by
0.06, and occurs while Rowan is stationary at the end of his reaction. His actual world
position is unchanged across frames 59/60; the run then accelerates from that same point.
It satisfies the original stricter matched-cut thresholds as well as the new 60-unit cap.

## Native-free agent workflow and safety

Input rejects unknown fields, duplicate JSON keys, unsafe reference forms, nonfinite values,
invalid numeric types, nesting over 32, input over 1 MiB, more than 100000 values for direct
Python callers, invalid references, unknown patterns/actions and unsupported combinations.
Direct compilation additionally bounds canonical ASCII input size. Local symbols never
load files or URLs. Descriptions are bounded strings, not commands; explicit expressions
select only accepted character presets. View holds, zoom, lead, offsets, crops, foreground
permissions and continuity remain under Phase 6B admission.

Exactly one Rowan is inherited from the validated world. Decorative geometry does not gain
support/physics privileges. Travel uses the original horizontal level-field corridor,
Hermite velocity/acceleration and calibrated contact solver. Stationary-only stories and
turn/reversal are deliberately not exposed in storyboard-0.1; it requires an admitted travel
bout. Minimum 6-frame beats and 12-frame reaction/escape beats do not bypass gait admission.
No data field can increase memory, geometry, resolution, duration or character count.

The compiled plan is immutable, with sealed JSON strings for inspection documents, not a
mutable reference to the caller's dictionary. There is no wall-clock randomness, motion
restart, frame-history state, unbounded frame cache or new native surface. All source motion,
acting and environmental breeze still sample global `frame/30` at the accepted evaluator.
The static graph inspector is explicitly labelled a registration reference; actual world
motion and direction camera are available from the selected-frame inspector.

Fresh installed-wheel smoke tests ran outside the checkout at `/tmp`, without Cairo:
all three schemas validated, all three plans compiled, generated plans were inspected and
all **270 absolute frames** were inspected without importing Cairo or subprocess. The
production CLI continued to advertise only unchanged foundation capabilities and
`render_available: false`. `uv pip check` passed. These checks do not certify target-VM
installation or add audio to the new contract; films are explicitly silent.

## Proof media, timing and determinism

Four final MP4s exist under `artifacts/phase7a/proofs/`: three films and `signal_repeat`.
All four fully decode: **90 frames each, 360 total**, 3 seconds, 30 FPS, 720×1280,
H.264/yuv420p. FFprobe rational stream-time-base checks require every PTS exactly equal
`frame/30`, with no timing tolerance. Full decoded frame hashes match each stored render
report, including the two reports whose overall status is false because of later cleanup.

The selected signal repeat matches **all 90 source pixel hashes and all 90 decoded RGB
hashes**. Out-of-order regeneration of representative/beat-boundary frames exactly matches
original movie source pixels. Per-frame reports record active beat/type, global frame,
camera/target/projection, accepted motion hashes and geometry hashes. Non-character world
registration/identity hashes remain exactly constant across all 90 frames of each film;
static objects are never recreated or moved between beats. Existing breeze can still animate
its own geometry at global time. Repeat evidence is same-environment frame determinism,
not a portable codec-byte identity claim.

Delivered evidence includes three public storyboard JSONs; standalone generated blocking
and direction documents; combined scene/narrative inspections; three 90-row frame reports;
start/middle/end stills; seven transparent layers per film; full-resolution frames around
every beat boundary; source/decoded sheets; camera curves; a narrative-beat/shot timeline;
16-frame timestamped decoded motion strips per film; repeat/decode/PTS/resource reports;
full test/JUnit evidence and an artifact SHA-256 manifest.

Analytical focal-position tolerance was inherited/predeclared at **1e-7 logical units**.
Maximum measured error was **5.684341886e-14 logical units** (1.136868377e-13 output pixels).
Maximum observed actor foreground bounding-box overlap was 0. This remains a conservative
framing proxy, not a pixel-alpha occlusion measurement or semantic quality guarantee.
No subject is intentionally cropped in these examples; incidental environmental edge crops
remain part of the wider composition.

## Performance and complexity

Development-host measurements, not constrained-target deployment approval. Native versions:
Python 3.12.14; Pycairo 1.29.2; Cairo 1.18.0; FFmpeg 6.1.1-3ubuntu5. Renderer/encoder/audio/
resource/transaction code and strict policies are unchanged.

| Film | Encoded FPS | Render + decode seconds | Sampled render tree MiB | Max pan step speed (logical/s) | Max paths / operations |
| --- | ---: | ---: | ---: | ---: | ---: |
| silent_signal | 20.05 | 5.583 | 98.61 | 72.668 | 846 / 6224 |
| abandoned_settlement | 31.82 | 3.830 | 97.46 | 99.456 | 708 / 3794 |
| shelter_entrance | 30.06 | 4.038 | 96.95 | 8.673 | 438 / 3960 |

Seven sequential final public-CLI jobs took **26.314 seconds**.
Whole orchestration peak sampled process-tree RSS was
**125.08 MiB**,
including parent, compilation/admission, rendering, encoder children and full decode.
Diagnostic/sheet generation, compatibility/decode and decoded artistic strips have separate
monitor reports; those scopes are not summed into a fictitious simultaneous peak. Sampling
can miss transients and double-count shared pages; this is not a dedicated per-job cgroup.
The host has much more available memory than the intended low-memory VM.

Maximum observed complexity: **28 nodes, 20 instances, 7 layers, 846 DrawPaths, 6224 operations**.
Unchanged caps: 64 / 32 / 8 / 4096 / 80000. The extra two operations relative to the earlier
radio are its explicitly authored broken aerial. Strict process-tree budget remains 256 MiB
with 64 MiB reserve. Each render report records zero live surfaces and zero surface bytes
after completion. One bounded surface streams through the original encoder.

## Tests, compatibility and retained cleanup failures

- New targeted suite: **79 passed**, 21.15 seconds. Initial 75-case run also passed; four
  focused additions cover the new editorial limit, actual offscreen reveal, unsupported
  stationary-only stories and a held-out environment seed. No existing assertions changed.
- Exactly one full local attempt: **1012 passed, 2 failed**, 126.69 s pytest / 127.078 s
  driver wall. All 79 new tests passed; 933 accepted tests passed and two accepted audio
  cleanup checks failed. No fixture errors, skips, full-suite retries or diagnostic branch.
- Failed accepted tests:
  `tests/test_audio.py::test_real_pcm_mix_aac_mux_repeat_and_clock` and
  `tests/test_transaction_cleanup.py::test_two_audio_jobs_persistently_clean_after_native_work`.
  Both failures occur at existing assertions that previously removed audio temporary
  directories remain absent after later native work. Encoding/audio/timing checks preceding
  those assertions passed. Complete stdout, JUnit XML, command, exit code and attempt count
  are preserved. We did not change unrelated cleanup code, sweep restored paths or rerun them.
- Seven proof CLI jobs: **five success statuses, two retained cleanup error statuses**.
  Settlement and shelter each encoded and fully decoded a valid 90-frame MP4, then reported
  `TRANSACTION_CLEANUP` because their removed encoder directory reappeared. Original reports
  retain `success: false` and the cleanup error. Their outer success-summary file is therefore
  not emitted; original inner render reports and the whole orchestration monitor preserve
  performance/resource evidence. Later native-work checks still observe those two directories;
  signal and its repeat remain clean. No encode was retried. Diagnostics-only processing
  continued from the valid retained media, without replacing failure statuses.
- Restored private directories remain excluded from committed review artifacts by the
  **pre-existing unchanged ignore rules**. Their failure paths and statuses remain in logs;
  no private transaction content was deleted or disguised as a successful job.
- **594 exact legacy source pixels matched**: 54 pre-6A checkpoints, all 270 Phase 6A frames,
  and all 270 Phase 6B frames. Original stored artifacts are unchanged.
- Accepted legacy 12-second audiovisual verification passed: unchanged H.264 bitstream and
  all video PTS, cue onset errors **0, −1, 0 samples**, audible drift **0 samples**, unchanged
  accepted AAC tail policy. Its immediate and post-native cleanup checks both passed in this
  compatibility job; that does not override failures observed in other jobs/the full suite.
- Ruff lint/format passed (141 Python files); wheel/sdist built with pinned build tooling.
  Installed native-free wheel/production CLI checks passed as described above.

The two final film cleanup errors, two full-suite failures and passing compatibility checks
are separate observations. No overall all-green engineering gate is claimed.

## Candid visual review

Reviewed actual final media through full decoding, the decoded 0/45/89 contact sheet and
three timestamped 16-frame motion strips (0.2-second samples plus frame 89). Also inspected
source beat-boundary sheets, the sole matched-cut neighborhood, the beat/shot diagram and
full-resolution signal frame 89 and shelter frame 73. No AI-generated image or video was
used; all film frames came from the original CPU engine.

The signal composition now reveals a previously offscreen radio through one continuous
move and holds it in shared space with Rowan. Its aerial damage and mast remain readable;
opening the authored foreground parameter improved the final silhouette. The camera does
not restart when approach becomes stop, reaction or hold. Settlement uses a stable space
for its stop/flinch, then a small matched cut for true acceleration/follow; it avoids the
large counter-reframes of the earlier studies. Shelter builds from approach into a quiet
pause and a held visible reaction, without inserting a cut for each narrative label.

Remaining limitations are material: three seconds compress motivation and suspense; the
unseen threat in the silent settlement is subtle and not semantically obvious without the
beat metadata. Reactions remain modest full-body cutout performances, with limited eyeline
control. The woodland radio is still off to Rowan's right and he investigates at a distance;
there is no reaching, pickup or physical interaction. Several compositions retain substantial
upper negative space; the cart/mast can compete for attention, and environmental silhouettes
are visibly procedural/depth-layered. Rowan's accepted gait and horizontal ground restriction
remain visible. The shelter approach never claims to enter the doorway or traverse depth.
The more restrained editing and actual reveal improve editorial intent, but do not establish
reference-quality parity or automatic story understanding. Independent playback/artistic
review remains required.

## Handoff

The committed tracked repository is exported with `git archive` as
`ReelForge_Phase7A_Complete.zip`, including every earlier tracked file and all new code,
examples, documentation, films, stills and evidence. File names and each archived Git blob
are checked against the commit; the evidence manifest is verified; working tree is clean.
Final commit and archive SHA-256 accompany the download, avoiding self-referential hashes.

No GitHub push, production deployment, Muse Spark integration or Phase 7B. Stop for review.
The publishing agent performs one normal GitHub CI run. Additional complete suites or
independent diagnostic branches are not the default validation policy.
