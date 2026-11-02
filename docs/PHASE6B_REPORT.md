# ReelForge V2 — Phase 6B engineering report

Date: 2 November 2026. Status: **implemented locally; independent review required**.
The single final local full-suite attempt is not green: one established development-host
cleanup-restoration failure remains visible. This report does not certify deployment or
reference-quality artistic parity.

## Scope and baseline

Approved baseline: `ca35dad8a006d04601db0d0885b6484348c8f54f` (Phase 6A, 862 accepted tests).
Local branch: `phase6b-cinematic-direction`. The supplied assignment is preserved in
`PHASE6B_ASSIGNMENT.md`. The final local commit SHA accompanies the downloadable archive.

Implemented `src/reelforge/direction/` with a strictly versioned native-free contract,
immutable shot/target values, schema discovery, analytical camera solve, framing admission,
absolute-frame evaluation, and frame inspection. `tools/direction.py` exposes capabilities,
schema, validation, timeline inspection, frame inspection, still rendering and MP4 rendering.
`CINEMATIC_DIRECTION.md` specifies every field, unit, limit, equation and known exclusion.

The only edit to existing runtime implementation is the optional `camera_override` argument
in `scenes.graph.evaluate_layers`. Without it, the exact prior camera evaluation path is used.
No changes to characters, blocking, contact solving, locomotion, audio, encoder, renderer,
resources, transaction ownership, earlier contracts or accepted tests. An exact baseline
comparison covered 61 protected implementation/test files (`baseline_integrity.json`).

## Camera behavior and timing

One embedded accepted world is compiled once. Up to six contiguous half-open shots cover
[0,90). Pan/focal offsets and zoom use bounded smoothstep endpoints and explicit opening/end
holds. Registered actor/node origins or bounded depth-aware points are valid focal targets.
Actor look-ahead is signed accepted world velocity times 0..0.35 seconds. Follow samples the
actual blocking trajectory; held targets freeze at shot start. No scripts or expressions.

The solver reuses `Camera.transform(depth)` and solves pan analytically for the requested
focal screen position. All layers retain painter order, identity and parallax; actor and
supporting ground receive exactly the same projection at their shared depth. The original
blocking presentation crop is intentionally replaced, never stacked with the new camera.
World/pose/environment time remains global `frame/30`; cuts never restart motion or breeze.
There is no mutable camera history, smoothing integrator, frame cache or new render surface.

Safety admits bounded zoom (0.9..1.7), solved pan (±240 logical units/axis), frame-step pan
speed (<=240 logical units/s), zoom speed (<=1.5/s), margins, actor head/foot bounds, node
size/visibility, declared cropping, conservative foreground overlap and cut continuity.
Logical coordinates are 360×640; output pixels are twice those coordinates. Full framing,
explicit foot crops and explicit actor departures/focus-away crops are distinct permissions.
The bounded projection model does not imply perspective, physically correct 3D cameras,
automatic eyeline editing, semantic occlusion or attachment sockets.

## Three cinematic studies

| Study | Shots / frame ranges | Direction and continuity |
| --- | --- | --- |
| Woodland suspense | establish 0–24; follow 24–60; reveal 60–90 | Seed-417 woodland, Phase 5C authored mast/cart/radio. Actual walk/stop route, 0.15 s lead, then pan/push attention to the receiver. All actor framing full. |
| Settlement escape | follow 0–64; held departure 64–90 | Accepted walk-to-run blocking, 0.22 s lead and screen-space lead room. Intentional hard cut to fixed composition; Rowan runs toward and partly through the right edge. |
| Shelter discovery | wide 0–24; entrance push 24–66; reaction 66–90 | Accepted horizontal approach/stop route, focal entrance push with opening/end holds, then a held reaction composition. Embedded stationary segments select accepted `react` acting rather than the earlier turn; original Phase 6A examples remain unchanged. |

Deliverables under `artifacts/phase6b/`: three films plus a selected woodland repeat;
full-resolution 0/45/89 stills and seven transparent depth layers per study; full-resolution
frames on both sides of every cut; individual boundary sheets; combined source/decoded
contact sheets; annotated camera X/Y/zoom trajectories; 90-row camera reports per study;
complexity, timing, resource, compatibility, test and repeat reports.

All four films fully decoded: **360 total frames, 90 each**, 3 seconds each, 720×1280,
30 FPS, H.264/yuv420p. Rational stream time-base checks require exactly `PTS[f]=f/30`
for every frame, without tolerances. Decoded hashes match render reports. Woodland repeat
matches every one of the 90 source pixel hashes and all 90 decoded RGB hashes. The checks
establish same-environment frame determinism, not portable codec-byte identity.

## Camera measurements and continuity

Predeclared analytical tracking tolerance: **1e-7 logical units** (2e-7 output pixels).
Measured maximum focal solve error: **0.0 logical units** across all 270 study frames.
This measures analytical registration of the chosen focal point; it does not assert
that perception, actor silhouette motion, or look-ahead placement has zero visual error.
The geometry test independently projects each depth layer from identity-camera coordinates
and verifies one application of the accepted transform. Actor/ground depths match.

Camera differences at cuts are explicitly excluded from smooth-movement speed metrics:

| Cut | Camera pan jump (logical) | Zoom change | Actual world travel since preceding frame |
| --- | ---: | ---: | ---: |
| Woodland 24 | 18.060 | 0.12 | 0.776241 |
| Woodland 60 | 124.795 | 0.00 | 0.631944 |
| Settlement 64 | 148.978 | 0.00 | 2.666667 |
| Shelter 24 | 7.808 | 0.04 | 0.937399 |
| Shelter 66 | 48.968 | 0.13 | 0.027778 |

All cuts declare intentional reframing. The large woodland/settlement reframes are visible
editing decisions, not concealed continuous pans or resets. Reports retain exact previous
and entering global frames. Pose/phase/secondary/world hashes use accepted global sampling.
Out-of-order re-evaluation includes repeated 89, 0, 45 and all cut neighborhoods; regenerated
pixels exactly match the original films. No frame-history dependence or missed timeline frame.

## Performance and resource accounting

Development-host measurements; not the constrained target-VM admission gate. Native versions:
Python 3.12.14, Pycairo 1.29.2 / Cairo 1.18.0, FFmpeg 6.1.1-3ubuntu5. The pinned Pycairo build
used installed Cairo and matching Ubuntu development headers extracted to scratch. No
alternate renderer or native fallback was introduced.

| Study | Encoded FPS | Render + decode seconds | Sampled render tree MiB | Max pan step speed (logical/s) | Max zoom step speed (/s) | Max paths / operations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| woodland_suspense | 12.66 | 8.900 | 98.96 | 113.389 | 0.2519 | 846 / 6222 |
| settlement_escape | 19.91 | 6.349 | 98.07 | 109.993 | 0.0571 | 613 / 3431 |
| shelter_discovery | 14.35 | 8.117 | 97.79 | 14.091 | 0.2699 | 438 / 3960 |

The seven sequential final proof CLI jobs took **45.084 seconds**;
whole orchestration peak sampled process-tree RSS was
**123.34 MiB**.
That scope includes parent, compilation/admission, native renderer/encoder children and
full decode. Diagnostic sheet generation is separately measured in `camera_metrics.json`;
the compatibility/decode job has its own monitor report. These are not summed into a
fabricated simultaneous peak. Sampling can miss short transients and double-count shared
pages; the existing report caveat applies. This host has substantially more available RAM
than the production target, so these measurements do not certify target deployment.

Maximum observed graph: **28 nodes, 20 instances, 7 layers, 846 paths, 6,222 operations**.
Caps remain 64 / 32 / 8 / 4,096 / 80,000. No geometry duplicated by cameras, no per-frame
cache, one bounded render surface, original streaming encoder and no-clobber publication.
All seven final CLI jobs reported success, no immediate cleanup error and zero live
surfaces/bytes after completion. Later checks found all four new movie output directories
clean. The strict 256 MiB budget +64 MiB reserve and all cgroup safeguards are unchanged.

## Compatibility and test evidence

- **324 exact legacy source-pixel checkpoints matched**: 18 procedural +9 graph +15 authored
  composition +12 original character/orchard/story checkpoints, and all 270 Phase 6A study
  source frames. Earlier stored artifacts were not modified.
- Legacy 12-second H.264/AAC verification passed: all video PTS unchanged, H.264 bitstream
  unchanged, 576,000 effective audio samples/channel, cue onset errors **0, −1, 0 samples**,
  audible drift **0 samples**. The accepted 512-sample AAC tail policy remains unchanged.
- New targeted tests: **73 passed**, 27.33 s. They cover strict inputs, references, timeline,
  easing/holds, true trajectory tracking, cut/global-time continuity, parallax, registration,
  framing, bounds, unsupported commands, deterministic evaluation, budget envelopes,
  cancellation/reaping, failed encodes, no-clobber output and native-free inspection.
- **Exactly one final full local-suite attempt**: **934 passed, 1 failed**, 149.69 s pytest
  time (150.076 s driver wall). All 73 new cases passed; 861 accepted cases passed and one
  accepted cleanup regression failed. No fixture errors or skips. No tests were weakened.
- Failure: `tests/test_transaction_cleanup.py::test_two_audio_jobs_persistently_clean_after_native_work`.
  An already-removed owned audio temporary directory reappeared after subsequent FFmpeg
  native work. The independent legacy AV compatibility job likewise observed immediate
  cleanup success and later pathname reappearance. Both observations are retained. We did
  not rerun either failing check, modify cleanup implementation, sweep the restored path,
  create a diagnostic branch, or claim the local gate passed.
- Ruff lint and format checks passed (133 Python files). Wheel and sdist built successfully.
  Fresh installed wheel outside the checkout at `/tmp`, with no Cairo installed, validated
  all three schemas/plans and inspected all 270 camera frames without importing Cairo or
  subprocess. `uv pip check` passed. The production CLI still advertises only its unchanged
  foundation capabilities and `render_available: false`.

Full output, JUnit XML, command, status and full-suite attempt count are preserved in
`full_tests.txt`, `tests.xml` and `test_execution.json`. The initial targeted draft log
is also retained: it exposed a frame-guard ordering bug (corrected before native sampling),
two incorrectly chosen invalid fixtures (corrected without relaxing limits), and a missing
scratch test-parent directory (created). The passing targeted summary is recorded separately.
An initial review-report helper tried to read monitor final state before context exit;
it was corrected and diagnostics/sheets recomputed from existing successful films. No
encode was retried. Three initial scratch still previews preceded the seven final jobs.

## Actual visual review and remaining weaknesses

Reviewed all three cut-neighborhood contact sheets, representative source and decoded
sheets, camera trajectories, and full-resolution woodland frame 89 and shelter frame 66.
The woodland receiver has a clear silhouette and is closer in the final focus composition;
the cart/mast anchor the shared space. The settlement follow maintains useful space ahead
of the run and the fixed final shot permits a deliberate right-edge departure crop. The
shelter doorway remains legible during the restrained push; a held view gives the accepted
reaction time to read. Foreground upper-bound overlap measured 0 for all study frames.
Full head/foot bounds remain admitted except the settlement shot's declared departure.

These are capability studies, not Stickocalypse-quality parity. Three seconds leave little
room for sustained dread; environmental geometry is visibly layered/procedural. The radio
is already visible in the establishing shot, so its reveal is an attention/scale shift,
not the discovery of a previously invisible object. The woodland cut at 60 counter-reframes
strongly before its pan; settlement 64 is a conspicuous editing jump. The shelter reaction
is still a medium/full-body view, with modest facial expressiveness and much upper negative
space. Character scale changes at cuts are deliberate but noticeable. Tracking uses true
world movement and does not conceal a different gait; existing planar/horizontal motion
and the Phase 6A turn limitations remain. This study uses stationary accepted reaction
instead of representing a new 3D turn. Occlusion checks are conservative bounding boxes,
not pixel-alpha semantics; node focal origins are not physical attachment points. Human
artistic review remains necessary, including playback pacing and editorial intent.

## Handoff

The complete committed tracked tree is exported with `git archive` as
`ReelForge_Phase6B_Complete.zip`. It includes every earlier tracked file and all new source,
plans, documentation, films, stills and evidence. The archive is checked file-by-file
against Git blob identities and the working tree is clean at handoff. Final commit and ZIP
SHA-256 are supplied with the download rather than self-referentially embedded here.

No GitHub push, production deployment, Muse Spark integration, Phase 6C or Phase 7.
Stop for independent review. The publishing agent uses one normal GitHub CI run; additional
diagnostics require a meaningful unexplained failure/regression, not a default extra suite.
