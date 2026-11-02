# Experimental structured storyboards (`storyboard-0.1`)

A storyboard compiles one structured, silent, 90-frame visual story at 30 FPS into accepted
`blocking-0.1` and `direction-0.1` documents. The same scene evaluator, CPU renderer and
streaming encoder render the result. It does not read free-form screenplays or understand
emotional prose. The installed production episode CLI remains unchanged/not render-ready.

## Public workflow

Run in the project environment (`uv sync --frozen --extra renderer`):

```bash
python tools/storyboard.py capabilities
python tools/storyboard.py schema
python tools/storyboard.py validate examples/storyboards/silent_signal.json
python tools/storyboard.py beats examples/storyboards/silent_signal.json
python tools/storyboard.py compile examples/storyboards/silent_signal.json
python tools/storyboard.py frame examples/storyboards/silent_signal.json --frame 57
python tools/storyboard.py render examples/storyboards/silent_signal.json --output-dir outputs/new_stills --stills-only
python tools/storyboard.py render examples/storyboards/silent_signal.json --output-dir outputs/new_film
```

All commands emit JSON and meaningful exit status. `compile` exposes complete accepted
blocking/direction documents and the compiled scene reference, not a promise of a future
planner. Copy those documents from its JSON result into separate files when independently
validating them with the older tools. The compiled scene graph is a **static registration
reference**: use `frame` for the actual moving actor and direction camera. `beats` inspects
narrative intervals and their many-to-one shot allocation. `frame` reports the active beat,
actual global motion, contacts and camera. All planning commands work without Cairo or
FFmpeg and import neither subprocess nor a native renderer. Only rendering invokes them.

Copy one of the three examples, select a pattern, declare world/subjects/views once, then
edit explicit beat durations, actions, expressions and endpoints. Never edit engine source
for episode authoring. A validation failure cannot be repaired with a resource override,
script, external include or an invented action. Keep cleanup failures visible; do not retry
failed encodes merely to obtain a green status.

## Top-level data

| Field | Meaning |
| --- | --- |
| `schema_version` | Exactly `storyboard-0.1` |
| `title` | Nonblank text, <=120 characters |
| `description` | Optional metadata text, <=800 characters; never executed or spoken |
| `world` | One complete accepted scene-0.1, environment-0.1 or composition-0.1 |
| `rowan` | Explicit actor ID, existing trusted support ID and initial position/facing |
| `subjects` | 1..16 local symbolic focal definitions |
| `views` | 1..6 local reusable camera definitions, all allocated to beats |
| `pattern` | One documented narrative grammar |
| `beats` | 2..10 ordered beat entries with durations summing to exactly 90 |

The world is embedded **once**, including any Phase 5C geometry assets/placements. Reuse
that world's stable object IDs. The compiler never copies a separate world per beat or
asks for a nested direction/blocking document. Local subject/view aliases do not refer to
files or URLs; they cannot recursively reference other aliases. All three procedural world
families are supported. One visible accepted Rowan with valid level-field support is required.
No object becomes walkable or interactive by appearing in a subject definition.

```json
"rowan": {
  "actor_id": "rowan",
  "support_id": "ground",
  "start": {"position": [140, 550], "facing": "right"}
}
```

X/right and Y/down use the existing logical world/canvas coordinates (360×640). Output is
720×1280, so projected output pixels are twice logical screen coordinates. Actor scale and
all painter/depth/registration values come from the validated world, not inferred narration.
The actor keeps the supplied facing throughout storyboard-0.1; turning/reversal and depth
navigation are not exposed here. Existing blocking-0.1 turn support is unchanged.

A local subject is an ID plus one accepted target shape:

```json
{"id": "traveler", "target": {"kind": "actor", "id": "rowan"}}
{"id": "signal", "target": {"kind": "node", "id": "receiver"}}
{"id": "entrance", "target": {"kind": "point", "position": [230,415], "depth": 0.85}}
```

Actor aliases must reference this Rowan. Node IDs must resolve to visible visual instances,
not groups, roots or a second actor; depth must be >=0.18. All aliases are validated, even
if unused by a camera. A node target is the accepted compiled registration origin, **not**
an inferred attachment socket or a semantic center. Point components are 0..640 and depth
0.18..1.4. A point can explicitly represent an unseen/suspected location; declaring it does
not create a threat, object, sound, collision body or physical doorway. See the detailed
origin/depth semantics in `CINEMATIC_DIRECTION.md`.

## Narrative grammars and expansion

These are planning grammars that constrain and compile explicit entries. They do not invent
missing beats, choose an object's identity, guess timings or auto-fill artistic decisions.
Selecting a pattern is observable validation/compilation behavior, not a descriptive tag.

| Pattern | Ordered stages | Required stages |
| --- | --- | --- |
| `discovery_reaction` | establish → approach → discover → react → hold | establish, discover, react |
| `approach_suspense` | establish → approach → hold → react | all four |
| `threat_escape` | establish → approach → discover → react → escape → hold | establish, react, escape |

Optional stages may be omitted. Stages cannot be reordered. Only approach and hold can
repeat; repetition still consumes the bounded beat count and total duration. For example,
an approach can expand into a travel beat followed by a stop beat, while both share a view.
All required stages must appear. Labels enforce observable supported actions:

| Beat type | Allowed actions | Specific meaning/constraint |
| --- | --- | --- |
| establish | idle, look_around, walk_to | Establish world/actor context, without inferred exposition |
| discover | idle, look_around, stop_at | Identify a valid non-actor subject; no automatic recognition |
| approach | walk_to, stop_at | Explicit supported horizontal travel/stop toward a declared non-actor subject |
| react | react, look_around | Stationary accepted visible performance, >=12 frames |
| escape | run_to | Explicit supported run destination/end speed, >=12 frames |
| hold | idle, look_around, react | Deliberate stationary pause; react action still requires >=12 frames |

Approach/discovery labels alone do not prove a 3D distance, visibility, eyeline or dramatic
motivation. The explicit world/action/view must make that intent read to the viewer. No
natural-language description supplies an expression or a command. Films are silent; the
legacy audio contracts/tools remain unchanged and separate from storyboard-0.1.

A beat has `id`, `type`, `frames`, `subject`, `action`, `view` and optional `description`
(<=400 metadata characters). IDs are snake_case, 1..48 characters, and unique per namespace.
Each duration is an integer >=6. Reaction/escape constraints above are stricter. Durations
are scheduled cumulatively into half-open intervals, so explicit start/end overrides are
forbidden. Sum must be 90 exactly. There are no gaps, overlaps or per-beat start positions.

```json
{
  "id": "investigate", "type": "approach", "frames": 36,
  "subject": "signal", "view": "signal_watch",
  "action": {"kind": "walk_to", "end_x": 180, "end_speed": 35, "expression": "concerned"}
}
```

Actions have exactly these fields:

| Action kind | Fields in addition to `kind` | Generated accepted segment |
| --- | --- | --- |
| idle, look_around, react | expression | idle at carried position, zero end speed, named accepted acting |
| walk_to | expression, end_x, end_speed | walk, explicit world destination and 10..45 world units/s |
| run_to | expression, end_x, end_speed | run, explicit world destination and 40..90 world units/s |
| stop_at | expression, end_x | stop at explicit world destination, end speed 0 |

`end_x` is 0..640. Y/facing carry from the initial actor declaration; position and velocity
carry from preceding accepted segments. No action can teleport or implicitly stop a moving
actor. `stop_at` must start moving; stationary performances must start at zero velocity.
Expressions come exclusively from the accepted character preset catalog. Travel uses the
unchanged Hermite, acceleration, stride-calibration and contact admission in Phase 6A.
Minimum duration alone is not sufficient: overspeed, reversal, too-short gait bouts, support
violations and uncalibrated stopping still fail. At least one admitted travel bout is required
because the reused blocking contract requires it; wholly stationary storyboards are explicitly
unsupported in this version, rather than fabricated with invisible movement.

## Views and shot allocation

A view has exactly `id`, `kind`, `subject`, `zoom`, `screen`, `offset_start`, `offset_end`,
`lead_seconds`, `hold`, `crop`, `foreground`, `cut`. Subject is a local focal alias; it can
be different from a beat's narrative subject when an intentional shared composition is wanted.

| Field | Units and constraints |
| --- | --- |
| kind | Accepted establishing, follow, push_in, reaction, object_reveal, suspense_hold |
| zoom | Explicit two endpoint factors, 0.9..1.7; establishing <=1.15 |
| screen | Desired focal location: logical X 16..344, Y 16..624 |
| offset_start/end | Focal/world offsets, components −100..100 logical units |
| lead_seconds | 0..0.35 s; follow uses actual signed world velocity |
| hold | [opening,closing] frame counts, each 0..88, leaving >=2 camera movement samples |
| crop | full, feet_crop, offscreen, with the exact Phase 6B semantics |
| foreground | clear or declared_overlap, with Phase 6B's conservative overlap policy |
| cut | matched or intentional_reframe; applies when this view occurrence begins |

The compiler derives `track=true` only for follow and `false` otherwise. It fixes the safe
margin to 8 logical (=16 output) pixels and support corridor to trusted `level_field`.
All other accepted view-kind constraints remain mandatory; no silent defaults degrade a
rejected camera. View durations/shot frames are derived, never repeated in the input.

**Adjacent beats sharing the same view ID become one shot**, even when their narrative
subjects differ. Camera easing/holds span that merged shot, rather than restarting at each
beat. A different view ID creates a hard cut; a later nonadjacent reuse creates a new
occurrence. Generated bounded IDs are `shot_00`, etc.; source beat-to-shot mappings are
exposed. The direction validator enforces <=6 shots, >=8 frames per shot and every original
camera/framing constraint. Storyboards additionally reject cut pan jumps >60 logical units,
even when declared intentional. Matched cuts retain the stricter accepted 24-unit/0.15-zoom
limits. This encourages restrained editing without changing direction-0.1 semantics.

## Compiler and safety boundary

```
Story data -> bounded validation -> grammar + interval plan -> symbolic resolution
           -> blocking-0.1 + direction-0.1 -> original validators -> existing evaluation/render
```

Compilation carries actor state, maps action shorthand to accepted segments, schedules beats,
coalesces camera occurrences, resolves focal aliases, constructs accepted intermediate JSON,
and admits those plans through `compile_direction` (which invokes `compile_blocking`). It then
checks every subject reference and the stricter storyboard cut limit. There is one continuous
underlying world and absolute `frame/30` clock for actor, camera and breeze. It never stitches
independently rendered clips or resets motion at a beat/cut.

Input files use the original strict loader: duplicate keys, numeric overflow/nonfinite values,
>1 MiB input and >32 containers are rejected. Direct Python compilation also bounds nesting
and values (100000), finite JSON types and canonical ASCII serialized size (1 MiB). Unknown
fields, code, includes, URLs as references, audio paths, extra actors and budget overrides
are rejected. Descriptive strings can contain arbitrary text, but never become instructions.
Immutable compiled values and serialized intermediate documents prevent later caller-dict
mutations from changing evaluation. There is no frame-history dependency or per-frame cache.

Errors have JSON Pointer paths into the authored document. Native storyboard checks use
`STORYBOARD_INVALID`, `STORYBOARD_REFERENCE`, `STORYBOARD_PATTERN`, `STORYBOARD_TIMELINE`,
`STORYBOARD_BUDGET`, `STORYBOARD_UNSUPPORTED` or `STORYBOARD_EDITORIAL`. Underlying admission
errors retain their original code prefixed with `STORYBOARD_` and remap world, beat/action or
view paths (for example `/beats/1/action/end_x`). Structured schema discovery covers syntax;
semantic scheduling, references, gait and framing admission remain additionally mandatory.

No accepted runtime module or contract is modified. Renderer orchestration reuses
`tools.scene.render_scene` and the accepted direction evaluators. The outer strict monitor
spans compilation/admission and native work; the original inner monitor/encoder still own
surfaces, child processes, cancellation and no-clobber publication. Limits stay 256 MiB +
64 MiB reserve, 64 nodes, 32 instances, 8 layers, 4096 paths and 80000 path/clip operations.
A failed cleanup remains a failure even when a fully encoded/decoded MP4 is retained.

## Engineering review tools

`tools/review_storyboard.py` runs seven sequential public-CLI jobs (three stills, three films,
one selected repeat). It retains individual return codes. `--diagnostics-only` reads completed
media/reports and produces compiled plans, per-frame hashes, sheets, camera curves and narrative
timeline without retrying encodes. `tools/verify_storyboard_compatibility.py` checks 594 older
pixel checkpoints and the original audiovisual fixture, fully decodes all four new movies and
checks exact rational frame PTS. See `PHASE7A_REPORT.md` before reproducing expensive checks.
Use targeted tests during development and at most one final full-suite attempt. Preserve
known restoration failures, use one publishing CI run, and stop for independent review.
