# Experimental planar character blocking — blocking-0.1

This contract lets an agent stage one existing Rowan through an accepted scene without editing
artwork, rig, renderer or camera mathematics. It is an experimental horizontal floor-plane
controller, not terrain navigation or a production episode compiler. All accepted scene-0.1,
environment-0.1, geometry-0.1, composition-0.1 and story contracts retain their meanings.

## Workflow

Use the pinned Python 3.12 environment, `uv sync --frozen --extra renderer`, and repository root:

```bash
python tools/blocking.py capabilities
python tools/blocking.py schema
python tools/blocking.py validate examples/blocking/woodland_traversal.json
python tools/blocking.py inspect examples/blocking/woodland_traversal.json
python tools/blocking.py frame examples/blocking/woodland_traversal.json --frame 45
python tools/blocking.py render examples/blocking/woodland_traversal.json --stills-only --output-dir outputs/walk-stills
python tools/blocking.py render examples/blocking/woodland_traversal.json --output-dir outputs/walk-video
```

Every destination must be new, even for separate still/movie calls. Validation and inspection
are native-free: no Cairo, FFmpeg, file includes, executable expressions or arbitrary media.
The command-line manifest path is operator-selected; JSON cannot name filesystem paths.
Runtime rendering uses the accepted scene tool with a trusted character-frame evaluator.
Production episode capabilities remain not render-ready.

## Contract

Root fields are all required: `schema_version`, `title`, `base`, `actor_id`, `support_id`,
`corridor`, `start`, `camera`, `segments`. Unknown fields are rejected at every new level.
`base` embeds a complete accepted scene-0.1, environment-0.1 or composition-0.1. No reference
paths are followed. There must be exactly one character instance using the accepted
`rowan_01` asset. `actor_id` and `support_id` name its existing graph node and ground binding.
The base determines geometry, world scale, hierarchy, inherited visibility, layers and depth.
Its static character pose/position is a reference; this contract explicitly replaces that pose
and supplies the motion position. Base manifests still render unchanged with their own tools.

The blocking output is explicitly **90 frames, 720 × 1280, 30 FPS, H.264/yuv420p**, silent.
Scheduling uses contiguous half-open integer intervals [start_frame,end_frame); the end at
frame 90 is the mathematical endpoint, while the last rendered sample is frame 89 at 89/30 s.
The embedded base's frame count is not the blocking duration; its geometry/art direction are
reused in a separate immutable 90-frame compiled view. No input manifest is mutated.

| Field | Supported values |
| --- | --- |
| `schema_version` | Exactly `blocking-0.1` |
| `title` | Nonblank string, ≤120 characters |
| `actor_id`, `support_id`, segment `id` | Existing/snake_case identifiers, ≤48 characters |
| `corridor` | Exactly `level_field` |
| `start.position` | [world_x,world_y], finite numbers 0..640, inside trusted corridor |
| `start.facing` | `left`, `right` |
| `camera` | `base`, `locked`, `exit_right` |
| `segments` | 1..12 records, at most 13 route vertices including start |
| segment fields | `id`, `start_frame`, `end_frame`, `mode`, `destination`, `end_speed`, `facing`, `acting`, `expression` |
| frame fields | Strict integers 0..90, at least 6 frames/segment, exactly contiguous [0,90) |
| `mode` | `idle`, `walk`, `run`, `stop`, `turn` |
| `destination` | Finite [world_x,world_y]; all y equal the start floor height |
| `end_speed` | Scalar world units/s; walk 10..45, run 40..90, stop/idle/turn exactly 0 |
| `facing` | Left/right; changes only in a stationary turn of at least 12 frames |
| `acting` | `none` for travel; `idle`, `look_around`, `react`, or `none` while stationary |
| `expression` | Accepted calm/concerned/focused/surprised/frightened/determined presets |

The first speed is zero; subsequent entry speeds inherit the preceding exit speed. An idle
or turn cannot silently discard nonzero velocity. A turn must change facing, hold position,
and begin at rest. A later route can travel back after a stop and turn, demonstrated in tests.
Motion scale is inherited from the base and must be .35.. .75. No extra intensity, joint,
terrain or mathematical-expression parameters are accepted.

Each movement segment supplies one destination. Several segments form a short authored route;
this version supports **horizontal line travel only**, not curved paths through depth. Every
segment keeps the same world y. Moving direction must agree with facing. A `stop` travels
while decelerating, then holds its endpoint in the next stationary segment. Walking/running
may end the timeline still moving, as in the departure study.

For a simple linear speed ramp, choose distance = duration × (entry_speed + exit_speed)/2.
Other destinations produce a Hermite velocity curve; the validator checks its entire profile.
If it would reverse, exceed the mode's 45/90 speed ceiling, or exceed 240 world units/s²
acceleration, fix duration/destination/speed rather than inserting engine code.

## Example segment

The complete documents in `examples/blocking/` include all base geometry and placements.
An individual stop after entry speed 35, at x=180, y=550, is:

```json
{
  "id": "settle",
  "start_frame": 54,
  "end_frame": 66,
  "mode": "stop",
  "destination": [187, 550],
  "end_speed": 0,
  "facing": "right",
  "acting": "none",
  "expression": "concerned"
}
```

This is .4 s at average speed 17.5, so travels 7 world units. It is a segment inside a complete
90-frame document, not a standalone manifest. Copy a complete example, keep the base, and
edit supported fields. `inspect` reports the corridor bounds and inherited scale; `frame`
reports actual position, velocity, phase, pose, contact targets and camera projection.

## Trajectory, stride phase and contact

For duration T, endpoints x0/x1 and signed velocities v0/v1, with u=(t−t0)/T clamped to [0,1]:

```
p(u) = x0 + T*v0*u + [3*(x1-x0)-T*(2*v0+v1)]*u²
       + [-2*(x1-x0)+T*(v0+v1)]*u³
v(t) = dp/du / T
```

Position and velocity join exactly. Velocity is quadratic: endpoints and its possible interior
vertex establish its continuous min/max, not just sampled frame speeds. Acceleration is linear,
so endpoint extrema establish the whole 240-unit bound. These are C1 position trajectories,
not a claim of C2 acceleration continuity or general physics.

A movement bout consists of adjacent walk/run/stop segments of one direction. Let a be the
inherited actor world scale, D the positive travel distance in rig units, and r(u) the smooth
walk/run blend between segment endpoint weights. The accepted stride lengths are Lw=64 and
Lr=164 rig units. Define the harmonic stride density:

```
dD/dt = abs(v(t))/a
h(t) = (1-r(t))/64 + r(t)/164
raw_phase(t) = integral[(abs(v(t))/a) * h(t) dt]
phase(t) = q * raw_phase(t)
effective_stride(t) = 1 / (q*h(t))
```

Velocity is degree 2 and r is degree 3, so the phase density is degree 5 and its integral is
an exact degree-6 polynomial. There is no numerical frame-to-frame integration or phase reset
at a walk/run boundary. Running weights match at boundaries; phase and phase velocity remain
continuous. A final non-stopping bout has q=1 and bounded analytic continuation for swing targets.

A stopped bout ends at N+.56 cycles, with at least 1.56 cycles, chosen near its natural phase.
The factor q must be .7..1.3, otherwise the route is rejected as uncalibrated. This permits
both final feet to land in the accepted flat ±9 rig-unit idle footprint. Very short stop-start
moves are unsupported. At scale .47, an all-walk stopped bout needs approximately 36 world
units or more to meet this calibration; change the route, not the gait equations.

The accepted `contact_targets`, `foot_roll`, `transition_pose`, `plant_feet`, two-bone solver,
rig and secondary motion are reused. Only trusted clock/target parameters are generalized.
For each leg's integer/half-cycle start, bounded inverse phase lookup determines touchdown
travel D(t_hit), duty and anchor. The anchor stays fixed in rig travel coordinates during
stance; during swing, the existing C1 easing moves to the next anchor. The last two anchors
are D_end±9, with .62 duty, so phases .56/.06 are flat at the stop. No body animation is advanced
by mutable frame history. A small finite table stores step metadata, not rendered frames.

The returned pose is relative to D(t); the actor node travels as
`world_x = bout_origin + facing_sign*a*D(t)`. These terms cancel exactly at a planted contact.
The original solver adjusts torso/leg reach, arm swing and secondary motion come from the same
phase, and standing acting is blended in/out and re-planted. A brief bounded anticipation pulse
precedes travel. No new rig, independent leg solver, new artwork or frame cache is introduced.

## Ground support and painter order

Only trusted `orchard_ground_01` and the Phase 5B `generated_ground` plane expose `level_field`.
Authored Phase 5C assets have no support metadata and cannot become walkable. The corridor is
narrower than the existing stationary support envelope:

| Ground asset | Local center corridor [left,top,right,bottom] |
| --- | --- |
| `generated_ground` | [-115,-45,125,60] |
| `orchard_ground_01` | [-140,0,140,70] |

Positive ground transforms map these into the world bounds reported by `inspect`. Ground and
actor must be visible, unrotated and share parallax depth. Complete monotone root paths must
fit the corridor. Foot sweep is also certified against the full trusted support envelope:
stance x is constant, swing x is monotone C1 easing, and every branch endpoint/partial endpoint
is checked. A conservative ±40 rig-unit boot rotation bound covers intermediate sole geometry.
Thus the test is not merely whether destination centers fit. This certifies a planar staging
surface, **not obstacle-free terrain, the entire rendered ground, a heightfield or the drawn
curving path**. Route/object clearance remains authored and visually reviewed.

The actor retains its accepted node identity, world scale, parent visibility, layer and painter
order. Main scenery is still painted according to the accepted graph; foreground still occludes
the actor. There is no automatic obstacle avoidance, per-object interaction depth sorting,
walking behind arbitrary objects, slope/stair motion or depth navigation.

## Facing changes and camera

Turns are stationary and take at least .4 s. The current planar cutout has no front/back yaw
artwork. The bounded implementation uses accepted look/idle acting and a two-facing dissolve
over the central 30% of the turn, followed by a stable target-facing hold. It does not deform
the rig or teleport the root. At the midpoint, brief ghosting/transparency can still be seen;
it is an explicit artistic limitation, not full 3D turning.

The unordered ground-contact pair remains stable. Near/far depth labels exchange between
facing drawings: their per-label displacement is **18×actor_scale world units**, 16.92 output
pixels at scale .47 with a locked camera. This is not zero individual-foot identity tracking.
The report separates this turn role exchange from numerical stance drift in fixed-facing travel.
`frame` exposes source `facing`, `target_facing`, `dominant_facing`, and `turn_blend`; contact
coordinates refer to the source component during the dissolve.

`base` preserves its camera preset; `locked` uses the accepted locked camera. `exit_right` is
an additive **fixed framing crop**, not a moving follow camera: the locked scene is magnified
1.08× and translated (73.6,−44) logical units. The same transform applies to all layers, ground
and character. The actor remains visibly framed through the first 60 frames, then runs beyond
the right edge in the final third, while staying on supported world ground. Its final projected
center must exceed x=380 and its final mode must be run/right. Camera motion does not conceal
the character's travel. No existing camera preset or standalone scene output is changed.

## Limits, diagnostics and failures

The existing loader admits at most 1 MiB and 32 JSON container levels, rejects duplicate keys,
NaN/infinity/overflow, and never evaluates code. All numerical requests are bounded. A route
has at most 12 segments/13 vertices, 90 frames, 16 cycles/bout and a finite step table. The
compiler and inspector are native-free; rejected plans cannot create a render destination.

The global caps remain 64 graph nodes, 32 visual instances, 8 layers, 4096 DrawPaths and 80000
operations. The trusted turn reserves one additional Rowan envelope (256 paths/6000 operations)
in the blocking compiled view for at most two render passes of one actor. This is explicit
aggregate accounting, not a cap increase or extra character instance. Actual counts are checked
in the accepted graph evaluator. No output frame list is accumulated; one surface streams to
the existing supervised FFmpeg encoder. Strict 256 MiB process-tree / 64 MiB reserve policy,
workspace checks, no-clobber publication, cancellation and transaction ownership are unchanged.

| Error | Meaning / repair |
| --- | --- |
| JSON_* / INPUT_TOO_LARGE | Repair strict bounded UTF-8 JSON |
| BLOCKING_INVALID | Fix reported field/type/action/range |
| BLOCKING_TIMELINE | Make segments contiguous integer [0,90), each ≥6 frames |
| BLOCKING_REFERENCE | Select the single existing Rowan node |
| BLOCKING_SUPPORT | Use its trusted ground/corridor, one level y, and supported foot sweep |
| BLOCKING_TRAJECTORY | Adjust destination/time/end speed to avoid reversal, overspeed or excess acceleration |
| BLOCKING_GAIT | Increase/adjust route distance for a calibrated stopping phase or leg/contact feasibility |
| BLOCKING_CAMERA | Keep the actor framed, or meet explicit exit_right departure rules |
| BLOCKING_BUDGET | Reduce base complexity; no cap overrides |
| SCENE_* / ENVIRONMENT_* / GEOMETRY_* | Repair prefixed `/base/...` issue in the embedded contract |
| OUTPUT_EXISTS | Choose a new destination directory |
| TRANSACTION_CLEANUP | Retain evidence; do not sweep restored paths or suppress assertions |

Input errors return exit 2 with structured `issue.code/path/message`. Native/resource failures
return exit 1, interruption 130. Validation/inspection/render success returns 0. The underlying
scene render report describes the base graph as a reference; `blocking_job.json` and per-frame
motion diagnostics contain the actual moving position and pose.

Targeted tests run during implementation. One final full local-suite attempt is recorded;
known restoration failures are not repeatedly retried. Publication uses one standard full CI
run on the development branch. No separate diagnostic branch, push or deployment is performed
by this task. See PHASE6A_REPORT.md for actual measurements and visual limitations.
