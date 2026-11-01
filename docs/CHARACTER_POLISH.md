# Rowan motion and acting — Phase 3A.1

Approved engineering baseline: `05be54725926c14f30c897b7d70590c07de840be`.
The 17-joint skeleton, bone lengths, pivots, Cairo vocabulary/backend, surface ownership,
FFmpeg encoder, resource monitoring/admission and production episode contract are unchanged.
This milestone refines the character's motion/art binding and supplies review evidence.

## Motion and contact

`contact.py` defines bounded `FootPlacement` values and a planar two-bone foot solve. Idle
feet stay fixed while the pelvis shifts slightly within their support span; breathing changes
height/torso rather than moving the shoes. Walk uses more upright support, compression at
contact, torso counter-motion and phase-offset arm/elbow motion. Run adds landing compression,
push, higher recovery and wrist follow-through. Bone geometry is not scaled or disconnected.

Heel strike rotates about the heel, midstance holds the sole flat, and toe-off rotates about
the toe. Swing position/roll have matching endpoint continuity. Both sole endpoints are kept
out of the flat floor. The pelvis is lowered as necessary to keep targets reachable; a small
C1 reach projection avoids a hard vertical clamp. This is a calibrated planar contact solve,
not terrain collision, mass-based balance, a dynamics engine or general retargeting system.
Defaults match Rowan's existing 42/45-unit legs and -8/19/10-unit boot sole calibration.
Future artwork sharing this skeleton/profile can reuse the controller; new proportions need
validated reach/art calibration rather than agent-supplied joints.

`transition.py` retains the proof's original starts (0.85/2.85s), 0.30s ramps and analytical
camera/ground distance. A continuous phase clock blends cadence without restarting a cycle.
For each foot, landing/toe-off/next landing and world-space anchors are derived from that
clock. Bounded bisection inverts the monotonic phase; there is no previous-frame state or
unbounded cache. First-step anchors start at the idle feet. Swing moves between anchors;
stance anchors remain constant even during acceleration/action changes. Upper-body poses
are blended, then legs are solved against those targets. The tracking camera is removed only
after the world-space solve, so contact cannot be faked by arbitrary per-frame screen offsets.

This is a small idle/walk/run transition controller, not an event scheduler or general story
animation timeline. Public sample times remain bounded 0–600 seconds; the review clip remains
exactly 150 frames. Phase-normalized body evaluation also works at the long time boundary.

## Secondary movement and artwork

`secondary.py` supplies bounded phase-lag signals and an analytical, decaying recoil response
with smooth onset. Idle, gait and reaction follow-through are deterministic direct evaluations.
Satchel angle/height, hat angle/height, strap sag and gaze have explicit limits; nothing is
integrated over time. Internal `SecondaryMotion` values are not fields in agent JSON.

Artwork `Part` values can bind a named accessory role and local pivot. The bag pivots from its
upper attachment; the hat rocks around its brim. This leaves the skeleton unchanged and lets
future art bind the same signals to its own pivots. The strap is a small cubic ribbon anchored
to shoulder and moving bag coordinates. Its buckle is positioned/oriented along that same
curve, so neither end nor hardware drifts away when the bag moves. Sleeve elbow insets soften
internal hinge seams; glove thumbs are less paddle-like. Rowan's palette, head, hat, patch,
satchel, boots and proportions remain recognizable. No traced or generated raster assets.

Simple contact-shadow ellipses now sit on the actual sole plane and follow grounded boots.
This is a vector cue on the existing proof stage, not a new lighting/environment system.

## Additive acting menu; same six-field contract

The original `character/action/direction/speed/expression/intensity` fields and bounds remain.
All previous presets validate. Unknown fields (including raw joint/secondary controls), IDs,
nonfinite/overflow values, invalid types and out-of-range numbers still fail validation.
The experimental schema remains backward-compatible `urn:reelforge:character-preset:0.1`.

| Selector | Available options |
| --- | --- |
| character | `rowan_01` |
| action | Existing `idle`, `walk`, `run`; added `look_around`, `react` |
| expression | Existing `calm`, `concerned`, `focused`; added `surprised`, `frightened`, `determined` |
| direction | `left`, `right` reflection |
| speed | 0.5–1.5, preset time multiplier |
| intensity | 0.5–1.0, gait amplitude / bounded acting strength |

`look_around` uses a head tilt and eye movement; it does not create a new perspective view.
`react` anticipates/recoils, raises the arms, settles and holds, with bounded accessory decay.
Expressions alter eyes/brows/mouth within the same face. There is no lip-sync or dialogue.
Examples: `examples/characters/rowan_look_around.json`, `rowan_react.json`, `rowan_run.json`.

```bash
uv run --frozen python tools/validate_character.py examples/characters/rowan_react.json
```

Trusted `preset_commands(data, frame_index)` derives poses, secondary movement and artwork.
Weak agents choose the menu values; they never author joint math, graphics commands or Python.
The main A/B clip deliberately keeps the same concerned expression to isolate motion/art
changes. Acting alternatives are demonstrated in the pose, expression and correction sheets.
The installed episode CLI remains capabilities/schema/validate, with general rendering false.

## Matched review and reproduction

```bash
uv sync --frozen --extra renderer
mkdir -p outputs/rowan-polish outputs/rowan-polish-review
uv run --frozen --extra renderer python tools/render_character.py --output-dir outputs/rowan-polish --stills-only
uv run --frozen --extra renderer python tools/render_character.py --output-dir outputs/rowan-polish
uv run --frozen --extra renderer python tools/review_character_polish.py --output-dir outputs/rowan-polish-review --after outputs/rowan-polish/rowan_idle_walk_run.mp4
```

Use new directories on reruns; final MP4s are not overwritten. The comparison verifies the
archived Phase 3A clip's SHA256 against its committed report and fully decodes both sources.
It places **original left / refined right**, each at native 720×1280, 30 FPS and 5 seconds,
without scale/time changes. The combined review file is 1440×1280. The original clip remains
unchanged at `artifacts/phase3a/rowan_idle_walk_run.mp4`.

The refined render uses the accepted streamed opaque Cairo→FFmpeg path. The review comparison
uses a fixed CPU FFmpeg hstack command through the existing bounded process runner, one codec
thread, one filter thread, strict JobMonitor, timeout, workspace temporary file, full decode
and atomic no-clobber publication. It does not add a production backend/encoder. Source videos
and frames are not collected in Python RAM. Working files stay in the persistent project.
SIGTERM unwinds the handled cleanup path; tests cover comparison failure and existing output.

Read PHASE3A1_REPORT.md for actual measurements and limits. All artistic and deployment approval
fields remain false. This work is development-only; Muse Spark accounting/deployment stays
blocked. The 256 MiB job budget and 64 MiB reserve are unchanged. Stop after Phase 3A.1.
