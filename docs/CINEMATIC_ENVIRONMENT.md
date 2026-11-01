# Last Light Orchard — experimental environment contract

Phase 3B adds one original code-generated farm environment for external review. It is
not a world generator or a production episode compiler. The installed episode CLI still
advertises `render_available: false`; manifests remain `render_ready: false`.

## Weak-agent use

Copy `examples/environments/orchard_push.json`, edit only the six supported fields, then run:

```bash
python tools/validate_environment.py examples/environments/orchard_push.json
```

A zero exit and `valid: true` mean the preset is supported for this environment study.
Errors include the unsupported ID or numeric field; use the published choices below.
The strict loader rejects duplicate fields, nonfinite JSON, oversized input, excessive
nesting and unknown/missing keys. Do not supply paths, executable code or camera equations.

| Field | Supported value / inclusive range | Effect |
| --- | --- | --- |
| environment | `last_light_orchard_01` | One fixed, authored farm/orchard composition |
| shot | `orchard_push`, `orchard_pan`, `locked` | Smooth 8.5% push with 10-unit pan; 20-unit pan; fixed camera |
| atmosphere | 0–1 | Weather-independent horizon haze opacity |
| warmth | 0–1 | Warm sun halo and door light intensity |
| breeze | 0–1 | Bounded canopy and bracken motion |
| framing | −1–1 | Horizontal offset of up to 8 logical units |

Shots are fixed six-second studies, 180 frames at 30 FPS, in a 360 × 640 logical artboard.
The preset does not control duration, resolution, entities or geometry complexity. A trusted
engineer can render the quality proof with `tools/render_environment.py --preset PATH
--output-dir OUTPUT` in the renderer environment. This is not an installed episode command.
Only the default push has been fully encoded/repeated; pan/locked have camera/geometry tests.

## Boundaries

- `environments/presets.py`: native-free strict preset validation.
- `environments/artwork.py`: reusable barn, apple tree and fence recipes, plus sky, hills,
  cultivated ground and foreground silhouette artwork. Paths are code-authored, not raster imports.
- `environments/scene.py`: immutable named layers, explicit placement, stable painter order,
  depth-dependent camera sampling and uniform transform composition.
- `tools/render_environment.py`: existing Cairo/FFmpeg/JobMonitor orchestration pattern;
  one streaming surface and existing strict admission policy.
- `tools/environment_review.py`: independently clipped layer sheet, camera checkpoints,
  illustrative flat-background comparison, and sequential full decoded repeat comparison.

Painter order: sky → hills → ground → orchard → barn → fence/props → door light → Rowan
→ foreground → screen-space edge grade. Depth is a camera/parallax coefficient, not an
implicit sorting key. Placement order is explicit to prevent ambiguous depth ties. Ground,
Rowan and near props use depth 1. Hill depth is .18, orchard .72, barn .85, foreground 1.4.
The depth-1 contact plane and character share the exact transform. Uniform camera scale
composes with existing rotated/local character transforms; unsupported parent transforms fail.

Camera sample uses integer frame time and cubic smoothstep, not accumulated deltas. A depth
coefficient d produces scale `1 + (zoom−1)d`, translating around the (180, 400) ground anchor
and applying `−pan*d`. Distant hills move less than foreground foliage. All geometry is pure,
fixed-loop, out-of-order repeatable; there is no mutable RNG, image cache or native scene object.
The only character action is the unchanged approved `look_around` preset with concerned acting.

## Lighting, budget and limitations

Lighting uses a deliberately graded ochre/olive/teal palette, layered low-alpha sun shapes,
linear gradients, shaded barn planes, local siding highlights, fading cast-shadow shapes,
horizon haze and two screen-space edge gradients. These create soft-looking falloffs without
blur buffers, float arrays or shader logic. No weather, full-frame float passes or GPU is used.
Warmth is an artistic intensity control, not a physically based illumination simulation.

Default frame has 952 DrawPaths (backend maximum 4096); all loops and output sizes are fixed.
There is no persistent geometry cache. A 720 × 1280 live ARGB32 target is 3.516 MiB; the largest
review-sheet target is 1800 × 1400 / 9.613 MiB, sequentially owned and released. No frame list,
scene pool or extra render surface is introduced. Existing 256 MiB job budget and 64 MiB reserve,
encoder threading/backpressure, atomic publication and deployment restrictions are unchanged.
Check current measurements in `artifacts/phase3b/report.json`, not arithmetic alone.

Depth is deliberately layered 2.5D, not a unified perspective scene or 3D camera. The camera
is bounded to keep small contact discrepancies across depth planes visually minor. The sun
and distant sky are screen-locked. Leaves/bracken move; trunks and buildings remain rigid.
External review must assess whether the controlled push/parallax and quiet action are compelling.
