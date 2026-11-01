# Phase 3A.1 — character animation quality gate

Branch: `phase3a1-character-polish`, based on `05be54725926c14f30c897b7d70590c07de840be`.
Baseline verdict: engineering approved, artistic refinement required. Package 0.6.0;
dependency graph unchanged. Status: implemented and tested on development hardware;
**independent visual/architectural approval pending**. No Muse Spark deployment was attempted.

## Visual evidence

- [Before/after MP4](../artifacts/phase3a1/before_after.mp4): original **left**, refined **right**.
  Both panels are 720×1280, 30 FPS, 150 frames/5 seconds, at the same shot scale and timestamps.
- [Refined vertical MP4](../artifacts/phase3a1/rowan_refined.mp4).
- [Updated pose/acting sheet](../artifacts/phase3a1/rowan_pose_sheet.png).
- [Motion correction sheet with root/contact/accessory markers](../artifacts/phase3a1/review_sheet.png).
- [Transition sheet](../artifacts/phase3a1/transition_sheet.png) and
  [expression sheet](../artifacts/phase3a1/expression_sheet.png).
- Full-resolution stills: `frame_000.png`, `frame_060.png`, `frame_120.png` and six
  `transition_024/030/035/084/090/095.png` files under `artifacts/phase3a1/`.
- [Render/repeat report](../artifacts/phase3a1/report.json),
  [comparison encode/decode/resource report](../artifacts/phase3a1/comparison_report.json),
  [contact geometry comparison](../artifacts/phase3a1/contact_metrics.json) and
  [development hardware](../artifacts/phase3a1/development_host.json).

The original approved-baseline clip is preserved and SHA256 checked before comparison. Camera
travel, framing, duration and primary expression are held constant. Contact shadows and strap/
small artwork corrections are intentional differences. Gait phase is continuous in the new
clip, so poses at matching timestamps need not have matching cycle phase: that reset was one
of the original defects. There is no speed-up or cherry-picked alternate original render.

## Concrete refinements

- Idle feet remain fixed with pelvis/torso breathing over their support span. Walk support is
  more upright, with landing compression, weight shift and shoulder/arm/elbow coordination.
- Running uses compression/push/recovery and stronger phase-offset arm/wrist motion.
- Heel/flat/toe contact and swing roll preserve sole clearance. Continuous cadence and planted
  world anchors replace the old independently restarted cycles and raw leg-angle transition blend.
- Satchel and hat have bounded lag; the scarf has phase follow-through. Reaction accessories
  include an analytical decaying settle. The strap and buckle follow actual attachment geometry.
- Rounded elbow insets, glove thumbs and ground contact cues reduce cutout seams and floating
  impressions. Rowan's identity, palette, proportions and original 17-joint hierarchy remain.
- Added validated `look_around`/`react` actions and `surprised`/`frightened`/`determined` expressions.
  Existing six preset fields/bounds and earlier expressions remain valid. No arbitrary joint math.

Reviewed the original and refined clips through decoded samples, full-resolution idle and
transition frames (including 30/90/95), the matched full-resolution A/B at frame 95, and pose,
expression and correction sheets. This inspection supports the candidate changes; it does
not substitute for independent artistic acceptance or establish Stickocalypse-level quality.

## Contact evidence and scope

Geometry was measured using the approved source archived into an isolated temporary checkout
and the refined source, evaluating the same 150 frame indices. For frames 25–34, compute the
near sole point `(0,10)` in world space as FK point + analytical camera distance. The old
idle→walk blend moved that nominally planted point **7.767 design units (~20.51 screen pixels)**;
the refined controller's range was **2.14×10^-14 units**. Across both sole endpoints/all frames,
maximum below-floor overshoot changed from **0.7252 units (~1.91 pixels)** to floating-point
roundoff **1.43×10^-14 units**. These are coded-geometry checks, not optical-flow/biomechanical
measurements or a quality score. They do not prove every part of the character moves naturally.

## Tests and resource measurements

**276 tests passed**, preserving all 232 prior tests and adding 44 cases for contacts, transitions,
joint attachment, timing/inverse-phase boundaries, bounded/reordered secondary evaluations,
strap attachment, decay, schema/parameter compatibility, expressions, repeated native pixels,
review sheets, and failure/no-clobber cleanup of the comparison utility.
Base installed wheel without Cairo: **213 passed, 11 skipped**. Rig/acting/schema work outside
the checkout; foundation capabilities/schema/validate remain native-free and render unavailable.
Ruff lint/format checks and wheel/source builds passed. JSON examples remain data only.

Two complete refined encodes passed metadata and full decoding; all 150 decoded RGB hashes
matched between repeats on this FFmpeg build. The original, refined and combined comparison
all passed full decode/frame count/format verification. Standalone output is H.264/avc1,
yuv420p, 720×1280, 30/1 FPS, duration 5.000000s and faststart MP4. No cross-build H.264 byte
identity is promised. Final-source checkpoint pixels match the delivered clip's saved hashes.

| Measurement | Refined first / repeat |
| --- | --- |
| Render + encode wall time | 2.652 / 2.812 s |
| Encoded FPS | 56.56 / 53.34 |
| First geometry / draw / stream-write time | 0.499 / 1.697 / 0.361 s |
| First whole job through full decode | 4.193 s |
| First renderer CPU / child user / child system | 2.753 / 3.218 / 0.268 s |
| First renderer peak RSS | 20.91 MiB |
| First encoder peak RSS | 66.30 MiB |
| First sampled simultaneous whole-job tree peak | **87.19 MiB** |
| Combined A/B comparison whole-job tree peak | **127.49 MiB** |
| Refined MP4 size | 935,053 bytes |
| Remaining live surfaces / surface bytes | 0 / 0 |

The comparison report measures its utility plus FFmpeg descendants through verification;
its encoder PID is not separately registered, so that field is null rather than a zero-memory
claim. Separate component peaks must not be added to invent a simultaneous total. Timings
include concurrent CPU encoding; these are not isolated rasterizer microbenchmarks. Sampled
RSS can miss transients and double-count shared pages. It is not hard cgroup enforcement.

Host: Ubuntu 24.04.3 x86_64, Python 3.12.14, Cairo 1.18.0, Pycairo 1.29.2, FFmpeg 6.1.1;
9 affinity CPUs / 8-CPU-equivalent quota, 8 GiB cgroup cap, ample available RAM and UID 0.
This is not low-available-memory or actual Muse Spark validation. Both jobs stayed below the
unchanged provisional 256 MiB envelope on this host. No resource, deployment, surface,
renderer or encoder source was modified; no host setting, swap or cgroup policy changed.

## Source and reproduction

[CHARACTER_POLISH.md](CHARACTER_POLISH.md) documents controller mathematics, role bindings,
contract additions and exact commands. New sources: `characters/contact.py`, `secondary.py`,
`transition.py`, `review.py`; updated character presets/artwork/study/schema. New engineering
utility: `tools/review_character_polish.py`; `render_character.py` only changes report labels.
Added tests/examples/docs and CI proof generation; project/lock changes are version metadata.
`characters/rig.py`, native rendering/media/resources and production contracts remain unchanged.

## Remaining limits and catalog recommendation

This remains a stylized, calibrated flat-floor cutout. There is no mass/COM model, terrain,
cloth deformation, genuine body/head yaw, multi-angle art, full hand articulation or physical
secondary simulation. Shoulder silhouette uses the existing joints and overlap; large novel
poses may still need art-specific overlap review. Eye/gaze/face changes are discrete presets;
there is no general expression-transition or dialogue system. A three-quarter reflection is
still not a true left/right perspective view. Exact contact does not certify acting, weight,
timing or reference-level cinematic polish. Sudden interruption/host loss retains the prior
infrastructure's documented limits, and the target VM remains blocked.

**Recommendation:** Rowan is ready as a *provisional first catalog candidate* for this bounded
front-cutout preset set. Submit these proofs for independent visual acceptance before registering
or freezing a production catalog entry. Keep `catalog_ready=false` and artistic approval false
until that review; do not implement a cast/catalog system as part of this milestone. Request
specific notes on weight, stride, accessory lag, emotion readability and residual cutout feel.
Stop after Phase 3A.1 for independent review.
