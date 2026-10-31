# First character rig — Phase 3A

Approved development baseline: `84eee4af27a38644e1a7461b4fb0a699eee4bfbb`.
Scope: one original character, an articulated cutout rig and three bounded locomotion presets.
No deployed-resource policy or episode contract is changed. Native Cairo objects remain inside
its accepted backend; this module emits the existing immutable DrawPath vocabulary.

## Reference study and original design

Read REFERENCE_STYLE.md and re-inspected the supplied video at 14, 21, 35 and 49 seconds.
The 14s figure uses a pale oversized head, tiny face, narrow clothing silhouette and segmented
limbs; bent elbows/head angle convey alertness. The 21s and 49s hat-wearing figure retains
identity through clothing color/accessories across standing and bent poses. At 35s the side-on
run uses opposition of limbs and a compact upper body against elongated legs. These are
observations about visual language; no claim about the creator's tools or exact rig mechanics.
No reference frames or traced proprietary shapes enter the runtime or distributed proof assets.

**Rowan Vale**, `rowan_01`, is an original young orchard keeper: short ochre field hat with a
creased crown and teal keeper pin, rust utility jacket, ochre neck cloth, patched blue-grey
trousers, leather gloves/boots and a small side satchel. Rounded, asymmetrical jaw/cheek curves,
sparse eyes, freckles and raised inner brows give a worried, watchful expression. The wide hat,
side bag and exposed narrow limbs provide a recognizable silhouette. The existing reference's
green cap/long coat character is not reproduced.

Head plus hat occupy roughly one third of the full standing silhouette. Local outlined path
widths are mostly 0.6–1.1 design units; interior seams are thinner. Cream face/ochre accents
separate from rust/blue-grey mid-values and a dark olive stage. Restrained local gradients,
flat shadow panels, hems, patch stitches and boot soles provide volume and material separation.
These are hand-authored paths, not placeholder primitives; ellipses remain appropriate for
small eyes/freckles and contact shadows. No AI images/video, stock character art or raster
textures are used. This is an artistic candidate, not a certified reference-quality match.

## Skeleton, geometry and ownership

`characters/rig.py` contains reusable frozen `Joint`, `Skeleton`, `Pose` and `Rigid` values.
Parents precede children; exactly one root and unique joint names are required. At most 64
joints are accepted. This rig has 17: root/torso/neck/head/scarf and three joints per leg/arm.

A joint maps its local artwork into world coordinates as:

`parent_world × translate(attachment) × rotate(rest + pose) × translate(-artwork_pivot)`.

Angles are radians, clockwise in Y-down coordinates. `attachment` is in the parent's artwork
coordinates; `pivot` is in the child's artwork coordinates. Tests exercise nonzero pivots and
rotated parents. Child pivot world positions coincide with parent attachments. Bone segments
are 42/45 units for thighs/shins and 31/29 units for upper/lower arms. Feet/hands attach at the
segment endpoints; overlapping rounded artwork covers the hinge without disconnecting it.

`rowan.py` binds local artwork to named joints with explicit painter order: far legs, near
legs, far arm, bag/neck/scarf, torso, near arm, head, face, hat. Back limbs use darker materials.
The same fixed 18 artwork parts and separate face overlay are transformed in every pose.
Artwork can be replaced without changing the hierarchy or pose evaluator. New proportions
would require a validated skeleton/profile and motion reach calibration; this is not yet a
retargeting system. There is one original character, not a cast or general catalog resolver.

Art transforms use the accepted backend's translation/rotation/uniform-scale contract.
Left facing is a horizontal reflection of this three-quarter cutout; it is **not a new side,
back view or a genuine 3D turnaround**. No shear, native object, image surface or borrowed
pixel buffer escapes the renderer. Static immutable artwork is the only fixed asset cache.

## Deterministic movement and contact

`sample_pose(preset, seconds, travel=True)` is a pure time-to-pose function. No frame history,
randomness, simulation timestep or wall clock enters it. Time is finite and bounded 0–600s.
Calling out of sequence produces the same pose. `travel=False` leaves the root in place for
pose sheets/tracking-camera composition, while retaining the same articulation.

| Action | Speed-1 cycle | Root travel / cycle at intensity 1 | Motion |
| --- | --- | --- | --- |
| idle | Breathing period 3s | 0 | Small breathing height/torso change, head drift, relaxed arms |
| walk | 0.95s | 64 units | 62% stance, opposed arms/legs, eased swing with 19-unit lift |
| run | 0.60s | 164 units | 38% stance, flight intervals, stronger lean/elbow bend, 31-unit lift |

Each leg uses a two-bone analytical solve toward bounded ankle targets. Stance X moves
backward at the root's forward velocity; stance Y cancels root bob. Feet remain horizontal
in stance. Swing X uses Hermite easing with matching contact velocities, Y uses squared sine,
and toe rotation eases from/to zero. Tests establish zero geometric sole-point sliding during
steady right-facing world-space stance, across speed/intensity bounds. Reflection preserves
this property. This is not a terrain, collision or full-body IK system.

The five-second review composition is deliberately fixed: idle 0–0.85s; idle/walk blend
0.85–1.15s; walk 1.15–2.85s; walk/run blend 2.85–3.15s; run thereafter. Smoothstep angle/root
blends and an analytical integral of ground travel avoid instantaneous pose resets. The
character stays framed while a ground marking layer scrolls. During those short blends,
contact is approximate: measured sole overshoot is 0.726 design units (<2 pixels at the proof
scale), and transient foot drift is possible. This is explicitly not a general timeline or
contact-constrained action-transition solver.

## Experimental weak-agent contract

Example: `examples/characters/rowan_walk.json`. All six fields are required; unknown fields,
unknown IDs, booleans as numbers, nonfinite/overflow values and unsupported bounds are rejected.
The bundled `characters/preset.schema.json` identifies `urn:reelforge:character-preset:0.1`.

| Field | Accepted values |
| --- | --- |
| character | `rowan_01` |
| action | `idle`, `walk`, `run` |
| direction | `left`, `right` |
| speed | 0.5–1.5; multiplies preset time/frequency, not an arbitrary joint velocity |
| intensity | 0.5–1.0; stride/arm amplitude, or idle breathing amplitude |
| expression | `calm`, `concerned`, `focused` |

Use `uv run --frozen python tools/validate_character.py PATH`. Exit 0 returns normalized preset
data; exit 2 returns a clear error. The existing bounded JSON loader handles duplicates,
nonfinite values, byte/nesting limits; the separate preset validator does not interpret the
file as an episode manifest. It makes no native rendering calls.

A trusted future compositor can call `rowan.preset_commands(data, frame_index)` to select
these animation functions and artwork without agent-written joint math. Frames are fixed 30 FPS,
integer 0–17999, and root travel is world-space. Camera/framing remains that trusted composer's
responsibility; long travel can leave a fixed viewport. No Python, graphics commands, paths,
URLs or plugins are accepted in the preset. `tools/render_character.py` deliberately renders
the fixed three-action engineering proof, not arbitrary episodes from this data.

The production CLI remains capabilities/schema/validate, episode schema 2.0-draft1, and
render_available/render_ready false. Experimental preset validity does not imply an episode
is renderable or that a weak agent can orchestrate a production reel.

## Reproduction and boundaries

```bash
uv sync --frozen --extra renderer
uv run --frozen python tools/validate_character.py examples/characters/rowan_walk.json
mkdir -p outputs/rowan-new-review
uv run --frozen --extra renderer python tools/render_character.py --output-dir outputs/rowan-new-review --stills-only
uv run --frozen --extra renderer python tools/render_character.py --output-dir outputs/rowan-new-review
```

Use a fresh output directory for each video. Accepted FFmpeg no-clobber/atomic publication,
opaque native BGRA streaming, single encoder thread, timeouts, cancellation, cleanup and
strict 256 MiB/64 MiB admission/monitoring remain in effect. One 720p surface is reused for
150 frames; no PNG intermediate or frame list feeds FFmpeg. The pose sheet uses one separate
1440×1280 surface and releases it before still frames. There are 169 commands per demo frame.
Reports include full decode/metadata/hash checks, RSS/CPU/wall timings and released surfaces.

Proof headings are a small hand-authored monoline uppercase alphabet for fixed engineering
labels; no font dependency, shaping, subtitle or dialogue system is introduced. The layered
stage consists only of fixed vector color planes and a contact shadow, not an environment
catalog, lighting or atmosphere system. No target VM work is authorized here. Stop for review.
