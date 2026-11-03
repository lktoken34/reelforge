# Yellow Mellow V2: technical verification and motion-quality report

Date: 2026-11-03. Host: WSL2 Ubuntu 24.04, Python 3.12.3, pycairo 1.29.2, FFmpeg 6.1.1, CPU only.
This is a development-host result. It is not a target-VM or deployment certification. Technical
checks do not prove artistic quality.

## Deliverables (outputs/yellow_mellow_v2/final)

| File | Content |
|---|---|
| `YellowMellow_V2_Animation_Showcase.mp4` | 450 frames, 15.000 s, 720x1280, 30 fps, H.264 Main yuv420p, no audio |
| `YellowMellow_V2_Character_Sheet.png` | front, three-quarter right/left views, proportion guide, 8 expressions |
| `YellowMellow_V2_Motion_Sheet.png` | 12 poses sampled from the performance (ghost = 4 frames earlier) |
| `YellowMellow_V2_Contact_Sheet.png` | 24 frames decoded from the delivered MP4 |
| `render_report.json`, `video_verification.json`, `motion_quality.json`, `motion_extra.json`, `determinism.json` | raw evidence |

Code: `src/reelforge/characters/yellow_mellow_v2/` (package), `tools/render_yellow_mellow_v2.py`,
`tools/yellow_mellow_v2_sheets.py`, `examples/characters/yellow_mellow_v2_example.py`,
`tests/test_yellow_mellow_v2.py`, `docs/YELLOW_MELLOW_V2.md`. No existing source file was modified.
V1 files and V1 outputs (`outputs/yellow_mellow_production/`) were left untouched.

## 1. V1 inspection: what caused the problems

| V1 defect | Cause in V1 code | V2 fix |
|---|---|---|
| Knees bent backward in crouch/landing | `solve_vertical_leg_ik` returns a positive hip angle, which rotates the thigh toward -X while the shoes point +X | General 2D two-bone IK with explicit bend direction: outward in front view, forward in three-quarter view, foreshortened between |
| Stiff, mechanical poses | Five hard-coded pose functions with per-phase `smooth_step` between fixed numbers. Frame 27 snaps straight to `pose_rest()` | PCHIP keyframes that start from the actual previous pose, analytic physics for jumps, procedural locomotion and settle curves |
| Arms crossing the hoodie | Shoulders at +/-14 inside a +/-20 hoodie, with a rest angle of 0.08 rad, so the near arm is drawn across the torso | Shoulders moved to the hoodie edge, outward rest angle, depth-aware arm draw order |
| Stub sleeves not following arms | 12-unit sleeve shape, stick drawn over it | Raglan sleeve along the upper arm with ribbed cuff and sway |
| Feet mixed views | Shoes always pointed +X on a front-facing body | Shoe length/toe direction follow facing, symmetric in front view |
| Poor grounding | Only vertical IK. No toe/heel roll and no reach limit | `FootState` with roll about locked sole end points and a pelvis soft reach limit |
| Head lost against dark skyline | Pure black ellipse with black stroke | Blue-grey edge stroke, moonlight rim arc, sheen, plus a faint horizon glow in the environment |
| Character too small (about 25-30% of frame) | Scale 1.3 at logical 360x640 | Scale 2.3: 53-56% of frame height when standing |
| Rigid whole-body jumps | Legs symmetric. Arms interpolated between two fixed poses | Anticipation, push-off velocity matched to ballistic flight, toe-first landing, velocity-matched absorption, squash/stretch |

## 2. Showcase timeline (as built)

| Frames | Requests (public API) | Adjustment inside the interval |
|---|---|---|
| 0-44 | `idle` 10 (blink) + `wave` 35 (happy) | none |
| 45-89 | `hands_up` 22 + `hands_down` 23 | split into two presets |
| 90-134 | `look` 12 (curious, right) + `point` 33 | eyes/head lead before the arm |
| 135-194 | `jump` 60 | crouch 14 f, push 5 f, flight 15.6 f, absorb ~6 f, settle |
| 195-254 | `walk` 60 (left) | first 9 frames are a planted-foot turn from front-right to three-quarter-left |
| 255-314 | `run` 60 (stop) | merged with the walk. Accelerates over 16 f, decelerates in the last ~29 f, so both feet are planted at 312 |
| 315-359 | `jumping_jack` 45 | 6-frame turn-to-front preparation, 3 reps of 11.7 frames |
| 360-404 | `squat` 22 + `stretch` 23 | split into two presets |
| 405-449 | `dance` 45 | 4 beats of 8 frames, then a confident hands-on-hips finish |

Total 450 frames, one continuous root trajectory. He walks and runs left toward the observatory, the
camera pans 409 logical px with parallax, and he ends next to the telescope dome.

## 3. Video verification (independent ffprobe/ffmpeg pass)

| Check | Result |
|---|---|
| Decoded frames | 450 (ReelForge `verify_video` framehash decode and an independent ffprobe frame list) |
| Duration | container 15.000 s, stream 15.000 s |
| Resolution / fps | 720x1280, avg and r frame rate 30/1 |
| Streams | 1 H.264 (Main, avc1) video, 0 audio |
| Pixel format | yuv420p |
| Timestamps | 0.000 to 14.967 s, every step 1/30 s (min 0.033333, max 0.033334) |
| Decode errors | none (`ffmpeg -xerror`, exit 0, empty stderr) |
| Unique decoded frames | 450 of 450 |
| Size | 3,743,059 bytes |

## 4. Resources and safety

- Render plus encode plus built-in verification: 12.98 s (34.7 fps). The wall clock for the whole
  command was 20.7 s.
- Peak RSS of the Python renderer process was 29.2 MB (`ru_maxrss`). `/usr/bin/time` reported a
  maximum resident set of 89.2 MB for the job, which includes the FFmpeg child.
- At most 309 draw commands per frame (limit 4096). One 720x1280 surface was reused. After the
  render, `allocated_bytes = 0` and `active_surfaces = 0` (no surface leak), and
  `confirm_cleanup()` passed.
- The encoder was used with its default owned temporary directory, no overwrite, and existing
  timeouts. No existing proof asset was overwritten (the tool refuses if the MP4 exists).
- Determinism: 9 sampled frames were re-rendered in a fresh process in reverse order. All
  surface SHA-256 values matched the video run.

## 5. Motion quality gates

Numbers are in character units: 1 unit is 2.3 logical px, which is 4.6 output px. Source:
`motion_quality.json`, `motion_extra.json`.

| # | Gate | Evidence | Result |
|---|---|---|---|
| 1 | Arms move independently | wave: far shoulder 0.15 to 2.21 rad while the near shoulder stays within 0.26 to 0.32. Dance alternates up/down arms. Point: pointing arm and hand-on-hip arm | pass |
| 2 | Elbows bend | elbow range -1.55 to +1.55 rad across sections (run pump 1.55, hand-on-hip -1.55, wave oscillation +/-0.42) | pass |
| 3 | Sleeves follow arms | sleeve and cuff are drawn in the shoulder frame (motion and contact sheets) | pass (visual) |
| 4 | Walking alternates foot contacts | walk landings: far at 213 and 246, near at 230. Run: near 261/282/296/303, far 272/291/299/310 | pass |
| 5 | Run differs from fast walk | run peak 3.3 u/f vs walk 1.55, cadence about 3 steps/s vs 1.8, 9 airborne frames vs 0, spine lean up to 0.30 rad vs 0.15, elbows at 1.55, fists, determined face | pass. Flight is short and low (max clearance 5.4 u) |
| 6 | Centre of mass shifts with support | pelvis follows the support feet in settle steps, dance sway is +/-2.2 u, walk pelvis bob comes from the reach limit, wave weight shift | pass |
| 7 | Jump has a clear airborne phase | 15 airborne frames (155-169), max foot clearance 39 u, pelvis 37.9 to 79.5 u | pass |
| 8 | Landing knee compression | minimum hip-ankle distance 29.0 u vs 42.4 standing | pass |
| 9 | Exercise articulates arms and legs | jumping jacks: 6 synchronous landings, 15 airborne frames, stance width +/-12, arms 0.3 to 2.5 rad. Squat: hip-ankle 25.4 u | pass |
| 10 | Head, beanie, hoodie stay attached | the neck-head distance stays within 13.9 to 16.1 u (spring head lag +/-1.1). Every part derives from one rig state | pass |
| 11 | Expressions readable | 8 presets on the character sheet. Eyes widen in flight and squint on impact. Blinks scheduled (28 frames >50% closed) | pass (visual) |
| 12 | Smooth transitions | at every clip boundary the joint step is 0.02 to 0.94x the local median. 1.15x at 255 is inside the merged locomotion clip | pass |
| 13 | Proportions consistent | rigid bones. Projected thigh 19.0 to 22.0 u (foreshortened near knee only), shin 17.8 to 21.0 u. Head and torso shapes are fixed except for squash at most 0.11 | pass |
| 14 | No joint flips / limb intersections | 0 knee-flip events, 0 clamped channel frames. Limb intersection is not measured numerically. In the three-quarter run the near arm crosses the hoodie by design | partial |
| 15 | No sliding or ground penetration | max planted-contact slide 0.038 u (0.18 output px), 0 events over 0.05 u, max penetration 0.000 u, max leg reach error 0.000 u | pass |

Rendered-frame inspection: I reviewed frames from every section, plus the turn (196-206), the stop
(304-312) and the jumping-jack turn-in (316-322), in development grids. The final contact sheet
uses frames decoded from the delivered MP4.

## 6. Tests and lint

- `tests/test_yellow_mellow_v2.py`: 37 passed in 1.2 s. They cover proportions, flat standing feet,
  IK reach and bend direction, front/three-quarter knees, foot-roll pivot, joint limits, mirroring,
  pelvis reach limit, expressions and blinks, real joint motion and start continuity for all 19
  presets, parameter validation, planted locomotion feet, alternation, run flight and stop, a walk
  without flight, 450-frame determinism, showcase quality gates, draw-command validity and mirroring,
  and the catalog adapter. The run used `--basetemp outputs/pytest-ym2`.
- Ruff lint and format checks pass on all new files.
- I did not run the full historical suite, as instructed. Wheel/sdist builds and the
  no-Cairo base install were not re-checked because no packaging or dependency files changed.

## 7. Improvements over Yellow Mellow V1

- V1 was a single 30-frame jump script with hard-coded per-frame phases. V2 is a reusable
  character package: 19 presets plus merged walk/run/start/stop locomotion, 8 blendable
  expressions, random-access sampling, and an agent-facing request API with validation.
- The rig went from vertical-only IK (which bent knees backward) to general two-bone IK with a
  bend-direction policy, heel/toe roll, pelvis reach limits, joint limits, mirroring, squash/stretch
  and spring follow-through.
- Motion went from linear segments that snapped to rest to physics-timed jumps, footstep-planned
  locomotion with exact planted feet, anticipation, overlapping action and settles.
- The design is the same. The artwork gained a skinned hoodie with folds and ribbed hem, raglan
  sleeves with cuffs, four mitten shapes, ribbed beanie crown and brim, a pom with tufts, rolling
  shoes, and edge/rim lighting for separation on dark backgrounds.
- Framing went from about 25-30% of frame height to 53-56%, with a parallax follow camera in the
  same Moonlit Observatory environment.

## 8. Known limitations and remaining uncertainty

- The run flight phase is real but brief and low: 9 frames, at most 5.4 u (25 output px) of
  clearance. A stronger bounding run would need a higher pelvis arc.
- Only front to three-quarter views are supported. Turning is a 2.5D cheat: shoe length
  interpolates and near/far labels swap through the front view.
- The near knee is foreshortened, not rigid, between front and three-quarter facing.
- The far arm's draw order switches at |facing| 0.45. In the showcase this happens with arms clear
  of the torso, but other sequences could show a pop.
- Hands raised past the head pass behind it, because the near arm draws behind the head.
- Peak hand speed is about 29 u/frame in jumping jacks and the dance, with no motion blur.
- The skyline layer is tiled during pans. A repeat is possible for much longer pans than in this
  showcase.
- Episode integration is not done. The catalog adapter exists, but no episode contract or
  episode-level test uses Yellow Mellow.
- Artistic quality was judged only by my own frame inspection. It needs independent review.
