# Experimental cinematic direction (`direction-0.1`)

This engine capability films one accepted continuous world with a finite camera plan.
It does not interpret scripts or generate instructions from audio. The installed production
CLI remains unchanged and not render-ready. See `PHASE6B_REPORT.md` for measured evidence.

## Agent workflow

Copy one of `examples/direction/*.json`. Supply all fields explicitly; unknown fields,
paths/includes, expressions, arbitrary camera code and policy overrides are rejected.

```bash
python tools/direction.py capabilities
python tools/direction.py schema
python tools/direction.py validate examples/direction/woodland_suspense.json
python tools/direction.py inspect examples/direction/woodland_suspense.json
python tools/direction.py frame examples/direction/woodland_suspense.json --frame 60
python tools/direction.py render examples/direction/woodland_suspense.json --output-dir outputs/new_stills --stills-only
python tools/direction.py render examples/direction/woodland_suspense.json --output-dir outputs/new_movie
```

Use the installed project environment (`uv sync --frozen --extra renderer`). Commands emit
JSON and nonzero exit status on failure. Validation, schema, timeline and frame inspection
require neither Cairo nor FFmpeg. Only rendering imports the native backend/media modules.
Do not retry a failed cleanup job or reuse an output directory. Fix the manifest at the
structured issue's JSON Pointer path; never change engine code to admit episode data.

## Contract and units

Top-level fields are exactly `schema_version`, `title`, `base`, `shots`.
`schema_version` is `direction-0.1`; title is nonblank, at most 120 characters.
Embed one complete accepted `scene-0.1`, `environment-0.1`, `composition-0.1`, or
`blocking-0.1`. No external file references, recursive direction plans or multiple locations.
The nested contracts are validated by their original validators and remain unmodified.
Direction normalizes its compiled view to 90 frames and replaces its camera presentation.
In particular, a blocking plan's `exit_right` presentation crop is not applied a second time.
The embedded blocking contract must first pass its own original motion/support admission.

All distances and screen coordinates use the existing **360 × 640 logical canvas**;
720 × 1280 output pixels are twice those coordinates. X increases right, Y increases down.
Time is seconds or integer frames at 30 FPS as indicated. Zoom/depth are dimensionless.

| Shot field | Meaning and admission |
| --- | --- |
| `id` | Unique snake_case ID, 1–48 characters |
| `start_frame`, `end_frame` | Half-open interval; 1–6 contiguous shots covering [0,90), each >=8 frames |
| `behavior` | `establishing`, `follow`, `push_in`, `reaction`, `object_reveal`, `suspense_hold` |
| `target` | One explicit actor, visual node, or bounded world point; see below |
| `track` | Boolean; true requires the Phase 6A actor's actual trajectory |
| `look_ahead_seconds` | 0–0.35 s; nonzero requires actor tracking |
| `zoom` | Two endpoint zoom factors, each 0.9–1.7 |
| `offset_start`, `offset_end` | Two world/focal-coordinate offsets, each component −100..100 |
| `screen` | Desired focal screen coordinate; X 16..344, Y 16..624 |
| `hold_in_frames`, `hold_out_frames` | Nonnegative integers, leaving >=2 motion samples within the shot |
| `framing` | `full`, `feet_crop`, or explicit `offscreen` permission |
| `safe_margin` | 4–32 logical units; demos use 8 (=16 output pixels) |
| `foreground` | `clear` or `declared_overlap` |
| `continuity` | `matched` or `intentional_reframe` for the entering hard cut |

Targets have exactly one of these shapes:

```json
{"kind": "actor", "id": "rowan"}
{"kind": "node", "id": "receiver"}
{"kind": "point", "position": [230, 415], "depth": 0.85}
```

An actor target is its world registration origin (Rowan's supporting-ground origin),
not the moving top of his head. Use an explicit negative Y offset to center the torso.
A node must be a visible non-character visual instance, at depth >=0.18. Its target is
its **compiled local registration origin**, including parent transforms, rather than an
inferred attachment point. In a JSON-authored instance, that origin may differ from the
chosen placement anchor because composition compiles the anchor offset into the node.
Inspect `target_world` before authoring focal offsets. Decorative artwork never creates
physical sockets, support planes or interactions. Point coordinates are 0..640 on both
axes, at an explicitly supplied depth 0.18..1.4. They represent artistic focal locations,
not inferred world geometry. At most one visible character is supported.

Behaviors reuse the same camera solve. Establishing limits zoom to <=1.15; follow requires
actual tracking; push-in requires increasing zoom; reaction requires an actor target;
object reveal requires a node or point; suspense hold requires no tracking, identical
offsets and equal zoom endpoints. Endpoint pan offsets, restrained zoom and opening/closing
holds compose the allowed behaviors. There are no arbitrary equations or smoothing scripts.

## Projection and interpolation

For integer global frame `f`, choose the single shot whose interval contains `f`.
Let `N=end-start`, and let opening/closing hold counts be `a,b`:

```
u = clamp((f-start-a) / (N-1-a-b), 0, 1)
e = u*u*(3-2*u)
zoom = lerp(zoom_start, zoom_end, e)
offset = lerp(offset_start, offset_end, e)
```

The smoothstep endpoint derivative is zero. A held target samples its world position at
`start/30`; tracking samples it at `f/30`. Actor look-ahead is signed instantaneous Phase 6A
velocity times `look_ahead_seconds`; it does not resample or approximate another route.
The focal point is `F=target+offset+(velocity*look_ahead,0)`.

Reuse the existing depth projection exactly. At depth `d`, `q=1+(zoom-1)*d`:

```
screen_x = 180*(1-q) - camera_x*d + q*world_x
screen_y = 400*(1-q) - camera_y*d + q*world_y
camera_x = (180*(1-q) + q*F.x - requested_screen.x) / d
camera_y = (400*(1-q) + q*F.y - requested_screen.y) / d
```

Depth zero remains fixed sky; other layers retain their existing painter order and
independent parallax. Actor and supporting ground share the same depth and transform.
The optional typed `camera_override` hook in `scenes.graph.evaluate_layers` is used only
by direction. The legacy default still calls exactly its previous `camera_at` function.
There is one camera projection per layer, no inverse/reprojection trick and no second crop.

Every recipe still receives **global `f/30`**, including Rowan's pose/secondary motion,
world trajectory and supported environmental breeze. A cut changes the camera, never the
source frame or an action clock. Shots do not reset locomotion, move objects, or change IDs.
Frame `end-1` belongs to the outgoing shot; frame `end` to the next. No crossfades are added.

Evaluation is a pure function of the immutable compiled plan and absolute frame index.
There is no previous camera state, integrator, history or per-frame cache. The finite
90-frame admission scan and reports are bounded, not a retained render-frame list.

## Framing and shot safety

Admission scans all 90 output frames, before native allocation, with fixed tolerances:

- Solved pan must stay within ±240 logical units per axis. Zoom stays 0.9–1.7.
- Within a shot, adjacent camera samples may move at most 240 logical units/s in
  Euclidean pan distance and 1.5 zoom units/s. These are output-frame step limits;
  they are not a formal bound on every subframe derivative of a tracked world trajectory.
- Analytical focal projection error must be <=`1e-7` logical units (2e-7 output pixels).
  This is a registration metric, not a measurement of perceived screen-space comfort.
- Conservative vector control-hull bounds include transforms and stroke envelopes.
  `full` protects actor head, width and feet inside the supplied margin. `feet_crop`
  explicitly permits a bottom crop while preserving head/width. `offscreen` explicitly
  permits a departure, a focus-away reveal or another artistic actor crop. It does not
  bypass pan, zoom, speed, object readability, resource or continuity constraints.
- A target node needs >=60% of its bounding-box area in the safe canvas and both box
  dimensions >=8 logical units. This is a silhouette-size proxy, not semantic recognition.
- `clear` rejects a conservative foreground bounding-box overlap upper estimate >15%
  of the actor box. `declared_overlap` requires explicit author permission and reports
  the estimate instead. The estimate sums path-box intersections and caps at 1; it can
  overestimate actual alpha coverage. It is not an automatic pixel-occlusion solver.
  Demonstrations have zero measured overlap even though permission is explicit.
- `matched` cuts limit pan displacement to 24 logical units and zoom delta to 0.15.
  Larger deliberate reframes require `intentional_reframe`. Every cut, regardless of
  declaration, limits camera zoom-factor ratio to 1.8. Hard-cut discontinuities are
  reported separately from within-shot motion. No automatic 180-degree/eyeline editing
  rules or narrative continuity inference are claimed.

Failures use `DIRECTION_INVALID`, `DIRECTION_REFERENCE`, `DIRECTION_TIMELINE`,
`DIRECTION_CAMERA`, `DIRECTION_FRAMING`, `DIRECTION_OCCLUSION`, `DIRECTION_SPEED`,
or `DIRECTION_CONTINUITY`. Nested base failures retain their original structured codes.
The discoverable JSON Schema covers structure; reference, timing and framing admission
remains mandatory and is deliberately stricter than structural schema validation alone.

## Resource boundary and exclusions

No renderer, encoder, rig, contact solver, locomotion mathematics, audio implementation,
transaction cleanup or memory policy is changed. Existing graph caps remain 64 nodes,
32 instances, 8 layers, 4096 DrawPaths and 80,000 path operations. Direction duplicates no
geometry and adds no render surface. One surface streams to the accepted FFmpeg encoder.
The strict JobMonitor spans compilation/admission, rendering, encode and full decode;
256 MiB process-tree budget and 64 MiB reserve remain unchanged. Memory is sampled RSS,
not a dedicated per-job cgroup measurement. Cancellation/error handling uses existing
ownership and no-clobber publication. A later restoration of a removed temporary directory
remains a visible failure; this module never sweeps somebody else's path to hide it.

Unsupported: full 3D cameras, perspective, rotations, focus blur, motion blur, arbitrary
camera expressions, automatic camera instructions, general multi-location editing,
multiple actors, object interactions, attachment physics and new audio features. Depth
planes may show graphic cardboard-like parallax at larger moves. Follow lead uses world
velocity and can inherit changes of acceleration at accepted route segment boundaries.
Artistic cropping and suspense still require human review.

## Engineering reproduction

`tools/review_direction.py` runs seven sequential monitored public-CLI proof jobs:
three still jobs, three films and one intentional repeat. `--diagnostics-only` rebuilds
reports/sheets from existing successful movies; it does not rerender or retry encodes.
`tools/verify_direction_compatibility.py` checks 324 legacy pixels, decodes all four new
movies with exact rational PTS, and verifies the accepted legacy audiovisual fixture.
Read the report and credit-saving policy before any rerun. Only one final local full
suite is permitted; the publishing agent uses one normal GitHub CI run.
