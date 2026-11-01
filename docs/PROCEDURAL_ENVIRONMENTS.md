# Experimental procedural environments — environment-0.1

Phase 5B provides three bounded environment families compiled into the accepted Phase 5A
scene graph. It does not make the production episode CLI render-ready. There is no
agent-authored vector program, story compiler, physics, collision system, terrain IK,
audio extension or deployment change.

## Agent workflow

Use the pinned Python 3.12 environment with `uv sync --frozen --extra renderer`.
From the repository root:

```bash
python tools/procedural_environment.py capabilities
python tools/procedural_environment.py schema
python tools/procedural_environment.py validate examples/procedural/woodland_trail_417.json
python tools/procedural_environment.py inspect examples/procedural/woodland_trail_417.json
python tools/procedural_environment.py render examples/procedural/woodland_trail_417.json --output-dir outputs/my-woodland
```

Choose a **new** destination for each render; even an existing empty directory is rejected.
Add `--stills-only` for frames 0, 45 and 89 and transparent depth-layer PNGs. Movie mode
streams one 90-frame silent H.264/yuv420p MP4 at 720 × 1280, 30 FPS, then fully decodes it.
Output dimensions, duration, camera and encoder settings are trusted implementation choices,
not free-form request fields. Copy one of the six JSON examples; every field is required.

| Field | Supported values | Meaning |
| --- | --- | --- |
| `schema_version` | `environment-0.1` | Isolated experimental contract |
| `title` | Nonblank string, ≤120 characters | Descriptive title only |
| `family` | `woodland_trail`, `settlement_street`, `rocky_shelter` | Trusted family rules |
| `seed` | Integer 0–4294967295, booleans rejected | Stable structural variation |
| `composition.density` | Integer 1–3 | Adds semantic object slots and bounded ground detail |
| `composition.path_alignment` | Finite number −1–1 | Path vanishing point and curvature bias |
| `composition.structure` | Finite number 0–1 | Tree lean/height, rock proportions, building wear |
| `composition.framing` | Finite number 0–1 | Foreground side framing; family-specific |
| `composition.detail` | `standard`, `rich` | Finite bark, scar, ground and crack detail |
| `art_direction.lighting` | `dusk`, `overcast` | Trusted palette/material shading |
| `art_direction.atmosphere` | Finite number 0–1 | Distance falloff and horizon haze |
| `rowan.enabled` | Boolean | Include the accepted Rowan rig |
| `rowan.action` | `idle`, `look_around`, `react` | Existing acting; no locomotion |
| `rowan.side` | `left`, `right` | Offset from the path center at the supported standing anchor |

Unexpected fields, unsupported values, duplicate JSON keys, nonfinite numbers, excessive
nesting and files over 1 MiB are rejected. CLI validation returns exit 2 and an `issue`
with `code`, JSON Pointer `path` and `message`. Semantic errors use `ENVIRONMENT_INVALID`
or `ENVIRONMENT_BUDGET`; strict loader errors retain their established loader codes.
Fix the reported field rather than adding code, paths or policy overrides. Schema discovery
is structural; run the semantic validator too. Schema integer validation alone does not
replace the stricter Python integer checks or nonblank-title check.

## Architecture and boundaries

1. `procedural.contract` parses and validates request data; it imports no native backend.
2. `procedural.planning` creates frozen `Plan`/`ObjectPlan` values: horizon, curved path,
   stable semantic IDs, positions/scales, actor anchor and conservative expansion allowances.
3. `procedural.drawing` supplies reusable polygon/curve, line, ellipse, gradient, palette,
   transform and budgeted `Pen` primitives. `procedural.recipes` constructs original static
   geometry for trees, rocks, buildings, doorways, ground, distant silhouettes and framing.
4. `procedural.compiler` seals immutable DrawPath tuples and Asset envelopes, then constructs
   root, layers and asset instances using the existing `Scene`/`Node` types. It calls the
   accepted graph compiler and frame evaluator. `scenes.geometry.GeneratedGeometry` is a
   trusted Python boundary, not a JSON asset-registration API. `scene-0.1` still only accepts
   its original registered assets and cannot name private `generated_` geometry.
5. `tools/procedural_environment.py` imports media/rendering only when rendering begins.
   It wraps planning, geometry generation, rendering and decode in the existing strict job
   monitor and calls the accepted scene rendering tool. No renderer or encoder was rebuilt.

Scene planning owns arrangement and layer assignment. An individual recipe owns only its
bounded local shape and material detail. Trees are reused for woodland, settlement regrowth,
dry shelter vegetation and foreground framing; rocks are reused as trail props, shelter
masses and foreground framing. Doorway, material, ground/path and backdrop primitives are shared.
The original orchard ground, barn and scenery recipes are never called by these families.

## Determinism and complexity

Each sample hashes `environment-0.1/family/seed/semantic-ID/channel` with SHA-256. No global
RNG, Python `hash()`, wall clock or previous frame state is used. Explicit slot order
`0,2,4,1,3,5` lets increasing density add objects without moving existing slots. Separate
channels control height, lean, roof type, damage, material and placement. Pixels are only
promised reproducible on matching Python/Cairo/FFmpeg builds; codec bytes across builds are
not an acceptance criterion. Generated static geometry is compiled once per request;
Rowan and camera evaluate from absolute frame time, including out-of-order requests.

All accepted caps remain **64 nodes, 32 instances, 8 layers, 4096 DrawPaths, 80000 path/clip
operations**. A recipe's `Pen` rejects its next command before retaining an over-budget draw
list. Planning sums recipe envelopes and the existing Rowan envelope before invoking recipes.
Each sealed asset checks its actual count again, and the accepted graph compiler checks the
whole scene. The hard limits are not raised.

Conservative family maxima at density 3 with Rowan (rich included) are:

| Family | Nodes | Instances | DrawPath allowance | Operation allowance |
| --- | ---: | ---: | ---: | ---: |
| Woodland | 27 | 19 | 2036 | 43700 |
| Settlement | 27 | 19 | 2392 | 40000 |
| Rocky shelter | 26 | 18 | 1828 | 31400 |

These follow directly from four base objects, two banks of at most six woodland or five
building/rock slots, bounded family props, one foreground and optional Rowan. Every recipe
has a finite loop count independent of frame history; per-recipe envelopes in capabilities
are enforced in addition to these aggregate bounds. Static geometry, not a frame cache, is
retained. Rendering uses one owned surface and a bounded streaming encoder pipe.

## Graph, ground and depth semantics

Seven layers use depths `0, .18, 1, .48, 1, 1, 1.4` in explicit painter order: sky,
backdrop, ground, distant silhouettes, main objects, people, foreground. The ground underlay
paints before the distant objects; the ordering is deliberate and separate from parallax.
Main objects sort by base y and stable ID. Existing world transforms, inherited visibility,
parent hierarchy, camera transforms and per-layer parallax remain in the graph evaluator.
Woodland/settlement use `gentle_drift`; shelter uses `approach`.

Each generated ground uses its own terrain/path geometry and a local support anchor at
world `(180,510)`, with envelope `[-175,-75,175,130]`. Rowan stands at world y=525,
path-center x ±17, scale .47, with the **same parallax depth as ground**. The ground reference
passes the accepted support checks. This is a supported standing region, not a sampled
heightfield: the interface does not support arbitrary terrain walking, cliff contact,
changing elevation, interactions, or dynamic actor occlusion behind every main-plane object.
Do not infer a walkable route from the rendered path. Cameras and poses retain existing semantics.

## Art direction and extension limits

Materials use authored silhouettes, finite local damage marks, directional face colors,
contact ellipses, gradients and alpha haze. This is stylized 2D lighting, without a general
light solver or unrestricted shader language. Foreground is cooler and darker; distant
shapes blend toward haze. Recipes have deliberate negative space around the path and Rowan.
These families are broader than named orchard presets but still bounded family generators.

Unsupported requests include arbitrary cities, arbitrary SVG or generated Python, file paths,
new characters, cloud assets, perspective meshes, general audio, variable-duration stories,
terrain IK or automatic script interpretation. Future Phase 5C can add reviewed primitives,
explicit geometry validation and stronger support metadata behind a separately versioned
contract. That compiler is not implemented here.

See `PHASE5B_REPORT.md` and `artifacts/phase5b/` for measured costs, proofs, regression results
and the independent-validation requirement.
