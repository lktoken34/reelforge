# Safe vector authoring: geometry-0.1 and composition-0.1

These experimental contracts describe original vector objects as data, not renderer presets
or executable drawing programs. They reuse immutable DrawPath values, sealed GeneratedGeometry,
Phase 5A composition and Phase 5B environments. The production episode CLI remains not
render-ready. They do not parse prose or turn a story into geometry automatically.

## Discover, author, validate, preview, place

Use Python 3.12 and `uv sync --frozen --extra renderer`. Run from the checkout root:

```bash
python tools/geometry.py capabilities
python tools/geometry.py schema
python tools/geometry.py schema --composition
python tools/geometry.py validate examples/geometry/survival_objects.json
python tools/geometry.py inspect examples/geometry/survival_objects.json
python tools/geometry.py preview examples/geometry/survival_objects.json --asset water_cart --output-dir outputs/cart-preview
python tools/geometry.py validate-composition examples/compositions/woodland_relay.json
python tools/geometry.py inspect-composition examples/compositions/woodland_relay.json
python tools/geometry.py render examples/compositions/woodland_relay.json --stills-only --output-dir outputs/relay-stills
python tools/geometry.py render examples/compositions/woodland_relay.json --output-dir outputs/relay-video
```

Every destination must be new, including for separate still/video calls. Validation and
inspection do not import Cairo or run native programs. Rendering needs the optional Cairo
backend and FFmpeg. A malformed input never reaches native rendering or creates its requested
output. File paths on the command line are operator-selected input/output locations; **no
path, include, URL or executable is accepted inside either JSON contract**.

Preview produces 720 × 1280 frames 0/45/89 using a locked camera and transparent layer
breakdown. Scene movies stream exactly 90 frames for environment bases (scene bases retain
30..180 frames). The proof examples all use 90 frames, 30 FPS, H.264/yuv420p. No sound is added.
Existing story/audio contracts and timing are untouched.

## A complete small object

This is valid geometry-0.1, independent of all named object examples:

```json
{
  "schema_version": "geometry-0.1",
  "palette": {"steel": "#647c82", "dark": "#142c32", "lamp": "#e5b56a"},
  "assets": [{
    "id": "signal_box",
    "size": [100, 120],
    "anchors": {"origin": [50, 115], "center": [50, 60]},
    "shapes": [
      {"type": "rect", "rect": [10, 20, 80, 90], "fill": "steel"},
      {"type": "polygon", "points": [[10,20],[25,8],[90,8],[90,20]], "fill": "dark"},
      {"type": "ellipse", "ellipse": [50, 48, 12, 12], "fill": "lamp"},
      {"type": "path", "path": [["M",25,85],["L",75,85]],
       "stroke": {"paint": "dark", "width": 3}}
    ]
  }]
}
```

Complete compound objects, with no Python artwork recipes, are in
`examples/geometry/survival_objects.json`: a damaged communications mast, survival water cart,
checkpoint watchtower and field radio. `heldout_wash_station.json` is an additional object
created after the compiler/tool source snapshot, from `heldout_description.txt`.

## Grammar and numerical bounds

All objects reject unknown fields. Arrays preserve order. Optional fields have only the
fixed defaults below; the engine does not guess unsupported geometry. JSON input is bounded
to 1 MiB and 32 container levels; duplicate keys, invalid UTF-8, nonfinite constants and float
overflow are rejected by the accepted loader. JSON integers beyond Python's safe parsing
limit are rejected too. Boolean values never count as geometry numbers or instance orders.

Identifiers are snake_case ASCII, 1..24 characters. Trusted registered IDs and names beginning
`generated_` or `agent_` cannot be asset definitions. The compiler maps local `name` to private
`generated_agent_name`; it never replaces a registered or procedural asset. No asset-reference
recursion or definition inheritance is supported. Independently authored subparts can be
pasted into local groups or placed as separate reusable assets; duplication is explicit.

| Structure | Required / optional fields | Limits / semantics |
| --- | --- | --- |
| Document | `schema_version`, `palette`, `assets` | Version exactly geometry-0.1 |
| Palette | Named color strings | 1..32 colors, #RRGGBB or #RRGGBBAA |
| Asset | `id`, `size`, `anchors`, `shapes` | 1..8 assets/document; size is [width,height], each 1..512 |
| Anchors | Named [x,y] | 1..8, including `origin`; every anchor lies inside size |
| Rectangle | `type: rect`, `rect: [x,y,width,height]` | Width/height ≥.01 |
| Ellipse | `type: ellipse`, `ellipse: [cx,cy,rx,ry]` | Radii ≥.01; expands to four cubic segments |
| Polygon | `type: polygon`, `points` | 3..64 [x,y] vertices; closes explicitly during compilation |
| Path | `type: path`, `path` | 2..128 M/L/C/Z operations |
| Leaf options | `fill`, `stroke`, `clip`, `transform` | Default null fill/stroke/clip, identity transform; fill or stroke required |
| Group | `type: group`, `shapes`; optional `transform` | Ordered children; four group levels; no material/clip/opacity inheritance |
| Transform | `x`, `y`, `scale`, `rotation_degrees` | Translation ±512, positive uniform scale .25..2, rotation ±45° |
| Composed local transform | Derived, never supplied | Scale .1..4, rotation ±90°; otherwise rejected |
| Stroke | `paint`, `width` | Width .25..12; accepted renderer's round join/cap |
| Linear gradient | `linear: [x0,y0,x1,y1]`, `stops: [[offset,color_id],...]` | Distinct endpoints; 2..8 strictly increasing stops including 0 and 1 |

Colors in stops are palette names, not nested gradients. A paint is a palette name or this
linear-gradient object. Null fill/stroke/clip disables that component. Coordinates and gradient
endpoints must be finite and within ±512. All transformed path/control points, primitive
bounds and clipping control points must fit the declared [0,width] × [0,height] reference
box. Stroke width can extend outside by half its transformed width. The reference box is a
conservative geometric bound, not an automatic clip. Preview fits this box in the viewport.

Paths use arrays `["M",x,y]`, `["L",x,y]`, `["C",x1,y1,x2,y2,x3,y3]`, `["Z"]`.
Every contour starts with M. L/C require an active contour; after Z a new M is required.
Open paths are supported for stroke-only shapes. Filled and clipping contours must explicitly
close with Z and have nonzero signed area; every contour must have nonzero extent. Polygon
and clip degeneracy use a conservative area threshold .0001 in local units; cubic area is
checked with 16 fixed samples per segment. Contours with extent below .001 are rejected.
Self-intersections that cancel signed area are intentionally unsupported, rather than inferred.
Cairo's existing nonzero winding fill rule is retained. This is not general SVG path support.

A leaf can contain one **local** closed path in `clip`, using the same operation grammar.
That clip transforms with the leaf, including inherited group transforms. There are no global
clip references, clip programs, filters, raster imports, SVG imports, arbitrary shaders,
nonuniform scale, skew, reflection or executable expressions.

Example gradient/clip/group structure:

```json
{
  "type": "group",
  "transform": {"x": 20, "y": 10, "scale": 1, "rotation_degrees": 0},
  "shapes": [{
    "type": "rect", "rect": [0,0,40,40],
    "fill": {"linear": [0,0,0,40], "stops": [[0,"steel"],[1,"dark"]]},
    "clip": [["M",0,0],["L",40,0],["L",0,40],["Z"]]
  }]
}
```

This group is a subshape, to be placed inside an asset with a sufficiently large reference
box and the referenced palette materials. It is not a complete document by itself.

## Expansion admission and resource boundaries

Each asset permits **128 total shape/group entries**, at most 128 DrawPaths and 4096 path/clip
operations. The whole document permits 512 DrawPaths and 16000 operations. A primitive is
one DrawPath: rect=5 operations, ellipse=6, N-vertex polygon=N+1; a path keeps its supplied
operations. Clip operations count again. Groups do not draw; their transforms are flattened
into immutable leaf IR in painter order, without multiplying geometry. All document costs
are admitted before any DrawPath compilation, and actual counts are checked after expansion.

composition-0.1 adds the base's conservative allowances and each placement's authored counts
**once for every instance**, even invisible instances. It rejects excess before compiling
procedural recipes or authored DrawPaths. The accepted graph compiler then checks final
transforms, hierarchy, references and aggregate counts again. The unchanged limits remain
64 nodes, 32 visual instances, 8 layers, 4096 DrawPaths and 80000 path/clip operations.

Strict whole-job monitoring covers composition compilation, geometry construction, rendering,
encoder children and full decode: 256 MiB budget and 64 MiB reserve. One scene frame surface
is used with bounded streaming/backpressure; there is no accumulated frame list or general
cache. Proof contact sheets are separate bounded artifact-composition work. Resource
observability, no-clobber directory reservation, atomic media publication, cancellation and
child reaping remain the accepted implementations. Cleanup failure is reported as failure,
even when a valid published MP4 is preserved for review. No broad filesystem sweeps or retries
are introduced. Independent Ubuntu/Python 3.12 validation remains required.

## Composition and anchors

`composition-0.1` requires exactly `schema_version`, `title`, `geometry`, `base`, `instances`.
`geometry` embeds one complete geometry-0.1 document. `base` embeds one unchanged scene-0.1
or environment-0.1 document. No paths/includes are followed. Complete examples are in
`examples/compositions/`; they cover all three procedural families and the accepted orchard
layout. Existing manifests continue to validate and render with their original tools.

Each of 1..16 instances requires:

```json
{
  "id": "supply",
  "asset": "water_cart",
  "anchor": "origin",
  "parent": "layer_objects",
  "order": 20,
  "visible": true,
  "transform": {"x": 120, "y": 543, "scale": 0.7, "rotation_degrees": 0}
}
```

`asset` names a local definition, `anchor` a declared anchor, and `parent` an existing base
layer/group (1..24-character identifier). `id` cannot collide with a base node or another
placement. Orders are integers 0..127; ties follow the accepted graph's stable ID ordering.
Instance translations are x±720/y±1280, scale .25..2, rotation ±45°. Existing composed-world
bounds (.1..3 scale, ±2048 position, ±90° rotation) apply unchanged. Translation positions the
chosen anchor: node placement = requested transform × translation(-anchor). Local dimensions
are reusable across placements; no manually edited renderer mathematics is needed.

Instances inherit parent visibility/transforms and their layer's parallax, painter order and
camera projection. Local group hierarchy does not create new scene layers. Split an object
into multiple assets/placements if independent parallax planes are needed. There is no new
camera system or general perspective projection.

Authored assets are always ordinary visual assets with **no supporting-ground metadata**.
They cannot be referenced as character support, cannot override Rowan or generated terrain,
and do not acquire collision, locomotion, IK or interaction behavior. Putting a drawn surface
under a character does not prove contact or walkability. Those capabilities are unsupported.

## Actionable errors

CLI exit 0 means successful validation/inspection/render; malformed input exits 2 with
`{"ok":false,"issue":{"code":"...","path":"...","message":"..."}}`.
Runtime/resource/cleanup failures exit 1 with an error object; interruption exits 130.
Messages are bounded to 240 characters. Schema discovery is structural; semantic validation
is mandatory for finite values, topology, transformed bounds, contour degeneracy and costs.

| Error | Trigger | Repair |
| --- | --- | --- |
| JSON_DUPLICATE_KEY / JSON_NONFINITE | Duplicate keys, NaN, overflow | Supply strict finite JSON |
| GEOMETRY_INVALID | Missing/unknown field, bad type/range | Fix the reported JSON Pointer |
| GEOMETRY_PATH | Unknown command, bad arity, open filled contour | Use M/L/C/Z and close each filled contour |
| GEOMETRY_DEGENERATE | Zero radii, zero contour area/extent | Give it visible geometric extent |
| GEOMETRY_BOUNDS | Transformed controls leave reference size | Adjust reference size/coordinates/group placement |
| GEOMETRY_MATERIAL | Unknown palette name | Define or select a named material |
| GEOMETRY_NAMESPACE | Reserved/duplicate asset or instance ID | Choose a new local snake_case name |
| GEOMETRY_REFERENCE | Unknown asset/anchor/parent | Select a declared definition and base layer/group |
| GEOMETRY_BUDGET | Too much geometry or placement expansion | Simplify or reduce instances within published caps |
| SCENE_* / ENVIRONMENT_* | Invalid embedded legacy base | Fix its prefixed `/base/...` issue |
| OUTPUT_EXISTS | Destination already exists | Choose a new destination |
| TRANSACTION_CLEANUP | Owned temporary path restoration/failure | Retain evidence; do not weaken assertions or sweep paths |

`examples/geometry/invalid/` includes complete intentionally invalid requests and expected
codes/pointers. These files are for validator/error handling exercises and are never rendered.

## What an author still does

An author chooses proportions, connected silhouettes, perspective hints, palette, anchors,
layer assignments and scene positions. A language model or person may translate a textual
brief into that JSON; the engine only checks and executes the explicit supported data.
Recognizability, material cohesion and visual hierarchy still need rendered-pixel review.
The held-out example is a documented authoring exercise, not a blinded benchmark, automated
natural-language understanding or proof of unlimited creative coverage.
