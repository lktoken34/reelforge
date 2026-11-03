# Yellow Mellow V2 character system

Package: `src/reelforge/characters/yellow_mellow_v2/`. V1 (`characters/yellow_mellow/`) is
unchanged and still renders its original jump test. V2 imports only the accepted
`reelforge.characters.rig` hierarchy (`Joint`, `Skeleton`, `Pose`, `Rigid`), the drawing model
(`DrawPath`, `PathOp`, `Transform`, `LinearGradient`, `Stroke`), the Cairo backend, the FFmpeg
encoder and the V1 environment layers. No core ReelForge module was modified.

| Module | Role |
|---|---|
| `rig.py` | Proportions, `MellowPose` channels, joint limits, FK skeleton, two-bone leg IK, foot roll, pelvis reach limit |
| `artwork.py` | Code-authored vector artwork generated from a solved rig state |
| `expressions.py` | Numeric `FaceState`, 8 presets, blending, deterministic blinks |
| `transitions.py` | Easing curves, PCHIP keyframe tracks, pose blending, foot-settling steps |
| `motions.py` | Motion preset library (`PRESETS`) and the merged locomotion clip |
| `character.py` | Public API: `YellowMellowV2`, `ActionRequest`, `Performance`, `Stage`, `FollowCamera` |
| `environment.py` | Moonlit Observatory adapter with parallax camera pan |
| `quality.py` | Numerical contact, continuity and joint checks |
| `catalog.py` | Character catalog entry and Rowan-style command adapter (not episode-integrated) |

## Quick start (another agent)

```python
from reelforge.characters.yellow_mellow_v2 import ActionRequest, Stage, YellowMellowV2
from reelforge.characters.yellow_mellow_v2.environment import observatory_background

mellow = YellowMellowV2(facing=0.25)          # 0.25 = front, slightly turned right
show = mellow.animate([
    ActionRequest("wave", 30, expression="happy", params={"hand": "far"}),
    ActionRequest("hands_up", 25, expression="excited"),
    ActionRequest("walk", 60, expression="happy", params={"direction": "right"}),
    ActionRequest("run", 45, expression="determined", params={"stop": True}),
    ActionRequest("dance", 45, expression="happy"),
])
stage = Stage(x=180, ground_y=575, scale=2.3)     # logical 360x640 frame units
commands = observatory_background(0.0, 575) + show.draw(frame=40, stage=stage)
# renderer.draw(surface, commands, background=..., logical_size=(360, 640))
```

`examples/characters/yellow_mellow_v2_example.py` is a runnable version that writes stills and a
90-frame MP4 through the existing renderer and encoder.

- `Performance.sample(frame)` returns a `CharacterFrame` (solved `RigState`, `FaceState`, blink).
  Sampling is random access and deterministic. Frame order does not matter.
- `Performance.draw(frame, stage)` returns `DrawPath` tuples (shadows + character).
- `FollowCamera(perf, stage)` gives a smoothed horizontal camera that stays still until the
  character leaves a deadzone. `observatory_background(camera_x)` draws the environment for it.
- Requests contain only an action ID, an integer duration in frames, an optional expression and
  bounded parameters. Unknown actions, parameters, expressions or out-of-range values raise
  `RenderError`.

## Rig

- Proportions: standing height 142.5 units, black head 40 units tall, giving 3.56 head heights. Legs
  22 + 21, arms 21 + 20, ankle 5.5 above the sole.
- Hierarchy (FK, accepted `Skeleton`): pelvis -> spine -> chest -> neck -> head -> beanie;
  chest -> {near, far} shoulder -> elbow -> wrist (hand). Legs: pelvis hip points -> analytic
  two-bone IK -> ankle -> shoe.
- Channels (`MellowPose`): pelvis x (world), pelvis height, pelvis tilt, spine, chest, neck, head,
  head yaw, facing, squash, eye look x/y, per-arm shoulder/elbow/wrist and hand shape
  (`relaxed|open|fist|point`), per-foot `FootState(x, lift, pitch)`.
- Arm values are side-relative: `shoulder > 0` raises outward (pi is straight up).
- `facing` is in [-1, 1]. 0 is front, about 0.92 is three-quarter, and negative values mirror about
  the pelvis. Near/far labels are depth labels. Turning through the front swaps them so physical
  limbs keep their positions (`motions.swap_sides`).
- Feet: a planted foot keeps its world `x`. `pitch > 0` rolls the heel up about the toe tip and
  `pitch < 0` rolls the toe up about the heel. The pivot never moves and the sole never dips below
  the ground.
- Pelvis reach limit: a C1 soft limit lowers the pelvis so grounded feet are always reachable.
  Lifted feet fade out of this limit.
- Knees: the far knee bends toward canonical +X. The near knee bends outward in front view, forward
  in three-quarter view, and is foreshortened in between. This is continuous and does not flip.
- Joint limits (`rig.LIMITS`) clamp out-of-range values and report them in `RigState.clamped`.
- Squash/stretch scales the hoodie about the pelvis and the head by only 22% of that amount, so the
  head silhouette stays recognisable.
- Secondary motion: beanie tilt, pom bounce, drawstring swing, hem sway and head lag. These come
  from a damped-spring impulse response convolved with the base acceleration of head, chest and
  pelvis over the previous 16 frames. The result is linear and deterministic with no integration
  state. The primary-state cache holds at most 48 rig states per `Performance`.

## Motion presets

All presets start from the actual previous pose. Keyframes use monotone PCHIP interpolation (C1,
no overshoot between keys, zero velocity at clip ends). `motions.PRESET_DOCS` lists parameters.

| Action | Notes / parameters |
|---|---|
| `idle`, `blink` | breathing (chest, squash, shoulders), weight sway, scheduled blink |
| `look` | eyes lead, then head yaw, body facing. `direction left|right`, `amount` |
| `head_tilt` | `angle` within +/-0.4 rad |
| `wave` | one arm. `hand near|far`, `waves`, `lower` |
| `hands_up` / `hands_down` | anticipation dip, staggered raise onto toes / elbow-led lowering with overshoot |
| `point` | straight elbow and finger, other hand on hip. `hand`, `elevation`, `lower` |
| `surprise` | flinch, then arms open, eyes widen |
| `stretch` | on toes, V-arms overhead, eyes closed. `toes`, `eyes_closed` |
| `crouch`, `squat`, `land`, `recover` | planted-foot knee work. `depth`, `reps`, `wobble` |
| `jump` | anticipation, Hermite push-off, ballistic flight (g = 0.85 u/frame^2), toe-first landing, velocity-matched absorption, settle. `height`, `crouch`, `travel`, `land_depth` |
| `jumping_jack` | hops between narrow/wide stances, arms down/overhead. `reps`, `width`, `hop` |
| `dance` | beat bounces, hip sway, alternating fist pumps, toe taps, confident finish. `beats`, `beat_frames`, `finish` |
| `confident` | hands on hips, chest out |
| `turn` | planted-foot facing change. `to front|left|right` |
| `walk`, `run`, `start_walk`, `stop` | merged locomotion (below) |

### Locomotion

Consecutive `walk/run/start_walk/stop` requests merge into one `LocomotionClip`, so walk to run to
stop is continuous:

- A speed profile (smoothstep between keys) is integrated at quarter frames for travel distance
  and a phase clock. Cadence comes from speed divided by a speed-dependent stride. Duty factor
  (stance fraction) is walk 0.6 to 0.9 at low speed, run 0.32, fixed per step at landing.
- Footstep anchors sit at the travel distance at mid-stance. Stance feet are exactly fixed, with
  heel-strike and toe-off rolls about locked pivots. Swing feet ease between anchors on a lift arc
  that clears faster when running.
- The final phase is nudged during deceleration so both feet are planted when speed reaches zero.
  A sequence must end with `stop=True` or a `stop` action.
- A turn on planted feet is inserted when the start facing differs from the travel direction.
- Arms counter-swing from the actual foot positions: the same-side arm moves opposite its leg.
  Running adds lean, bent elbows, fists, a different pelvis bob phase and a flight phase.

## Expressions

`neutral, happy, excited, curious, surprised, concerned, determined, tired`. Each is a `FaceState`
(eye size, open, upper/lower lid, brow raise/tilt/asymmetry, mouth curve/open/width/roundness).
Clips may add bounded adjustments, for example eyes widen in flight and squint on impact. Blinks are
scheduled from a SHA-256 stream of the seed and suppressed during closed-eye or high-effort moments.

## Rendering restrictions

- Supported views are front to three-quarter, mirrored for left. There is no true profile view or
  back view.
- The near arm draws in front of the hoodie but behind the head, so a raised hand can pass behind
  the head. Below |facing| 0.45 the far arm also draws in front of the hoodie, and above it the far
  arm goes behind. The switch is instantaneous but only happens with arms clear of the torso in the
  showcase.
- Shoe length interpolates with facing. A turning planted foot changes shape around its ankle
  instead of rotating in 3D.
- Direction changes inside one locomotion sequence are rejected. Insert a non-locomotion action
  (for example `turn`) between them.
- The environment adapter redraws the V1 railing and floor so tile seams move with the ground line
  during camera pans. The skyline is tiled and repeats when the camera pans far.

## Episode integration status

`catalog.CATALOG["yellow_mellow_v2"].episode_integrated` is `False`. `catalog.command_source` returns
commands at a ground origin in the same shape as `rowan.draw_character`. No episode, scene,
storyboard or reel contract references Yellow Mellow yet, and no episode-level test exists.

## Tools and tests

- `python3 tools/render_yellow_mellow_v2.py stills|video|verify|contact|sheets|quality --out DIR`
- `pytest tests/test_yellow_mellow_v2.py --basetemp outputs/pytest-ym2` (37 focused tests)
