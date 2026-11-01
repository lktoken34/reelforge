# Experimental scene-0.1 graph authoring

This contract assembles registered components into new layouts. It is separate from story-0.1,
story-0.2 and the production episode contract. No legacy manifest meaning or CLI capability changes.
It does not support arbitrary objects, generated geometry, script interpretation or interactions.

## Weak-agent workflow

Use the pinned Python 3.12 checkout with the renderer extra installed:

```sh
uv sync --frozen --extra renderer
python tools/scene.py capabilities
python tools/scene.py schema
python tools/scene.py validate examples/scenes/rural_outpost.json
python tools/scene.py inspect examples/scenes/rural_outpost.json --frame 45
python tools/scene.py render examples/scenes/rural_outpost.json --output-dir outputs/outpost --stills-only
python tools/scene.py render examples/scenes/rural_outpost.json --output-dir outputs/outpost-video
```

Copy an example before changing it. Edit IDs, parents, order, visible, bounded transform fields,
registered variants and presets. Do not edit engine Python, geometry, filters or camera equations.
The destination directory itself must be new: creation reserves it atomically, protecting existing
files and concurrent jobs. Stills produce start/middle/end 720 × 1280 PNGs and transparent layer PNGs.
Video produces one silent H.264/yuv420p MP4, a detailed report and compact JSON CLI status.
Inspect output includes world transforms, deterministic painter IDs, character ground contacts
and conservative path/operation allowances. Validation/inspection/capabilities/schema need no Cairo
or FFmpeg. Rendering requires the existing Cairo/FFmpeg dependencies. The production episode CLI
still advertises render_available:false; this is explicitly experimental checkout tooling.

A failed validation returns code 2 with issue.code, issue.path (JSON Pointer) and issue.message.
An empty pointer identifies the root object. Repair the identified field; do not invent features.
SCENE_ASSET means select a registered asset/kind. SCENE_BUDGET means reduce instances, hierarchy
or transforms. SCENE_INVALID covers schema/topology/unsupported combinations. Rendering/native
and cleanup failures return code 1; interruption returns 130. A missing capability is not permission
to inject code or silently substitute geometry. Report it to the operator.

## Root object and strict fields

| Field | Required meaning |
| --- | --- |
| schema_version | `scene-0.1` |
| title | nonempty descriptive text, at most 120 characters; no on-screen caption |
| output | exactly width=720, height=1280, fps=30, frames=30..180, codec=h264, pixel_format=yuv420p |
| camera | `locked`, `gentle_drift`, `approach` |
| art_direction | exactly warmth, atmosphere, breeze; each finite 0..1 |
| nodes | flat array of 1..64 typed node records |

All node records require id, kind, parent, order, visible and transform. id and parent references
use snake_case `[a-z][a-z0-9_]{0,47}`. Only the one root has parent:null; its transform is identity.
Other parents reference an existing node ID, regardless of JSON array position. order is integer
0..127; visible is a boolean. transform is exactly x, y, scale, rotation_degrees. x is −720..720,
y −720..1280, scale is one positive scalar .25..2, rotation_degrees is clockwise −45..45.

| Kind | Additional required fields | Role |
| --- | --- | --- |
| root | none | exactly one root; identity coordinates |
| group | none | hierarchy, transform and visibility inheritance |
| layer | depth (finite 0..1.5) | one shared parallax projection; layers never nest |
| asset | asset_id, variant | tree/barn/fence instances |
| background | asset_id, variant | sky/hills components |
| environment | asset_id, variant | terrain/foreground components |
| character | asset_id, variant, character, ground_id | Rowan instance with explicit supporting terrain |

character is the existing six-field CharacterPreset: character=rowan_01, action=idle/look_around/react,
direction=left/right, speed=.5..1.5, expression=calm/concerned/focused/surprised/frightened/determined,
intensity=.5..1. Scene-0.1 deliberately rejects walk/run because it has no blocking/travel contract.
This restriction does not change the existing character, environment or story preset systems.

Unknown fields are errors at every level. No file/URL/image path, Python, SVG, FFmpeg fragments,
expressions, policy flags, raw matrices, nonuniform/negative scales or unregistered IDs are accepted.
Frames and order must be integer JSON tokens; booleans and floats are rejected even if numerically
integral. The strict loader preserves duplicate-key, nonfinite/overflow, UTF-8, 1 MiB input and
nesting-32 protections. JSON Schema is discoverable structural guidance; the Python validator is
mandatory for exact integer-token rules, finite values, topology, combinations and resource limits.

## Trusted visual registry and anchors

| Asset | Node kind | Variants | Local anchor |
| --- | --- | --- | --- |
| dusk_sky_01 | background | default | viewport origin (0,0) |
| distant_hills_01 | background | default | original horizon anchor (180,350), normalized to local (0,0) |
| orchard_ground_01 | environment | default | terrain anchor (180,500), normalized to local (0,0) |
| barn_01 | asset | default | existing barn foundation origin |
| orchard_tree_01 | asset | broad, lean, compact, windswept | trunk base |
| fence_01 | asset | default | first fence-post base; extends to local right |
| foreground_boughs_01 | environment | default | original framing anchor (180,640), normalized to local (0,0) |
| rowan_01 | character | default | sole-contact ground origin |

These are adapters to accepted vector recipes, not newly invented asset classes. Tree variants
select four trusted authored seeds; manifests cannot choose an unbounded seed or texture program.
Sky/ground/framing are finite existing component patches, not full procedural terrain generators.
Anchor normalization composes transforms; it never discards per-command sway, clips or material data.
The component registry exposes declared type, variants, anchors, upright requirement, support
metadata and complexity envelopes through capabilities. Adding a trusted asset requires engine
review and an envelope, but placement of approved assets needs only JSON changes.

## Coordinate and painter semantics

The logical viewport remains 360 × 640, rasterized at 720 × 1280. X points right, Y down.
A node maps a point as `translation * clockwise_rotation * positive_uniform_scale`. World placement
is the ordered product of all ancestors and that node. Local translation therefore rotates and
scales with its parent; translations are not simply added. Composed placement must stay within
±2048 in X/Y, scale .1..3 and rotation ±90 degrees. Upright assets (sky, hills, terrain, Rowan)
require zero effective rotation, allowing an explicitly counter-rotated parent/child combination.

Uniform ancestor scale is intentional: its composition with existing locally rotated/reflected
character parts is exact without shear. Each final DrawPath retains its local path, clip, fill,
gradient, alpha and stroke; only its trusted Transform changes. No geometry baking loses gradient
or stroke semantics. Nonuniform ancestor scale, shear and arbitrary matrices are rejected rather
than approximated. Per-command nonuniform/reflected transforms already authored in trusted assets
remain intact. There is no general affine or 3D camera advertised by this version.

Every visual instance must descend from exactly one layer. Groups above layers may transform
several layers; groups/instances within a layer share its camera projection. Camera projection
occurs after world composition, once, using accepted Camera.transform(depth). Depth zero is fixed;
near layers move/zoom more. Named graph camera recipes evaluate absolute normalized frame progress
with bounded accepted camera mathematics; no state is accumulated between samples.

Painter order is independent of parallax depth. Layers sort globally by (order,id). Within a layer,
children sort by (order,id) and traverse depth-first, emitting a parent's geometry before its children.
This permits ground (depth 1) to paint behind a barn (depth .85), as in the accepted 2.5D pipeline.
JSON array reordering has no visual effect; explicitly changing order or hierarchy does. IDs are
stable tie breakers. Visibility is inherited with logical AND. Hidden nodes still consume their
compiled complexity allowance, so visibility cannot bypass admission.

Visual instances can parent other components: this attaches them in the parent's local frame and
paints the child afterward. These are static root attachments, not skeletal sockets, joint following,
interaction solving or interleaved limb occlusion. No unsupported joint binding is silently inferred.

## Character ground binding

A character's transform origin is its planted-sole ground coordinate. ground_id must reference a
registered component with support-envelope metadata; graph code does not hard-code a farm asset ID.
Both must share parallax depth, and visible Rowan requires visible supporting ground. The current
terrain's conservative local support rectangle is X −250..250, Y −80..250; the actor origin must lie
inside it after inverse floor placement. Parent scale and camera projection apply identically to
Rowan and the declared ground point. Existing pose/contact solving is reused unchanged and a small
existing-style contact shadow is anchored to the same local origin.

This is a bounded support-plane contract, not terrain collision, slope adaptation or physics.
It does not sample the exact painted terrain outline. Different artwork scales/layouts still need
visual inspection. Ground support metadata allows a future approved terrain adapter without changing
compiler logic. It does not authorize arbitrary new terrain geometry in JSON.

## Compilation and resource limits

Nodes/instances are frozen data values. Compilation checks duplicate IDs, missing parents, cycles,
reachability, hierarchy depth <=8 edges, <=8 layers and <=32 visual instances. It computes immutable
world placements and a deterministic painter plan, with no native surface construction or frame
index table. All frames evaluate from absolute frame/30 and the named action/camera presets.

Admission sums trusted asset envelopes, including hidden instances: at most 4096 DrawPaths and
80000 path-plus-clip operations. 4096 also respects the existing Cairo draw-call cap. Per-asset
and total envelopes are checked again during evaluation; a changed trusted recipe that overruns
its envelope fails. A small manifest cannot request arbitrary expansion. Output is limited to six
seconds, one bounded surface at a time, CPU only. Default video rendering streams to the accepted
FFmpegEncoder; no frame list or intermediate PNG sequence is generated. Explicit still proofs are
separate. The strict 256 MiB process-tree budget, 64 MiB reserve, timeouts, cancellation, no-clobber
publication and inode ownership safeguards are reused without modification.

A published MP4 can remain valid when a later cleanup check fails; file presence is not whole-job
success. Failed post-decode ownership checks produce success:false in the detailed report and a
nonzero CLI exit. No restored private pathname is swept or silently accepted. This development
host still exhibits restoration in full legacy suites; see PHASE5A_REPORT.md before claiming a pass.

## Integration boundary

scene-0.1 is an independent authoring/evaluation contract. Story-0.1/story-0.2 still select their
original trusted orchard/shot IDs and retain audio timing semantics. No scene reference is smuggled
into those manifests, and no story-0.3 or production compiler is added. A future explicit version
may bind a compiled scene into shots, after this graph passes architectural/visual review.
