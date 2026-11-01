# Last Light Orchard — Phase 3B.1 refinement contract

Approved parent: `ef27965967e78c025a2526def415a22975e3b5c1` (Phase 3B engineering accepted;
artistic refinement requested). This is a local review candidate, not production catalog or
deployment approval. No installed episode command, story scheduler or general light engine is added.

## Use by weaker agents

Keep the existing six-field preset. All existing examples and the three previous camera IDs
remain valid. Their camera equations, duration and framing are unchanged. Select
`examples/environments/orchard_suspense.json` for the recommended separate dramatic study:

```sh
python tools/validate_environment.py examples/environments/orchard_suspense.json
```

| Field | Published values / inclusive bounds |
| --- | --- |
| environment | `last_light_orchard_01` |
| shot | `locked`, `orchard_pan`, `orchard_push`, `orchard_suspense` |
| atmosphere | 0–1; valley haze and cool ambient contribution |
| warmth | 0–1; key-facing foliage/character accents and attached doorway/lantern light |
| breeze | 0–1; bounded foliage displacement, without moving roots or buildings |
| framing | −1–1; existing horizontal offset of up to eight logical units |

No new numeric fields. Unknown fields, unsupported IDs, booleans as numbers and nonfinite
values still fail explicitly. Frames remain 0–179 at 30 FPS, six seconds, 360 × 640 logical
units, output 720 × 1280. Preset validation remains native-free. Renderer tools are for trusted
engineering; production episode rendering remains unavailable.

`orchard_suspense` holds the initial composition for approximately .9 seconds, eases into a
23% push with 46-unit horizontal / 22-unit vertical travel, and settles for the last .6 seconds.
The barn entrance moves toward the frame center while Rowan retains the accepted concerned
look-around action. No reaction scheduler or character animation change is introduced. At depth
d the existing projection is used; hills move less than foreground branches. Ground, Rowan and
contact shapes share depth 1. The emitted light's upper footprint corners are mapped from the
barn's .85 depth into the ground plane, preventing the source from detaching during the push.

## Reusable visual methods and resource bounds

- `polish.variation`: fixed 32-bit integer mixing, independent of process hash seed, call order,
  wall time and mutable RNG state. Seeds come from the authored tree identities, never scene data.
- `polish.crown` / tree recipe: varied branch masses, connected cubic silhouettes, clipped
  upper-left accents, sparse detail and fruit. Seven boughs per tree; five authored trees.
  Entire bough details share a small analytic sway transform. Roots stay fixed.
- Terrain retains the original planted-bed directions and path. Missing plants, varied clumps,
  shallow ruts, scattered stones/leaves and restrained irregular ground marks break repetition.
- The accepted barn/fence recipes are retained. Added eave shade, cool side-wall fill, repairs,
  nails, roof wear and clipped vegetation shadows give those surfaces more construction cues.
- Wall lighting clips around an oppositely wound doorway hole. It never washes warm light over
  the dark open doorway. Threshold spill fades down the path; it has no blur buffer. The lantern
  halo stays in the barn's own transform. Ground and contact shadows point away from the key.
- Character paint grading changes material colors and local gradients, preserving every path,
  stroke width, alpha and rig transform. Cool exposure and a modest warm edge reduce the pasted-on
  appearance. This is an illustration convention, not pose-aware physical relighting.
- Four cloud-shelf shapes, one broken middle bank, thin high cloud, distant birds, valley haze
  and a balanced overhanging bough create an atmospheric frame. Horizontal cool edge grading
  protects the middle focal region. Sky remains screen-locked, as in the accepted shot.

The same ten named layers and painter order are preserved. Layer IDs are not configuration knobs.
No backend, media, rig or resource-policy source is changed. No new package dependency is added.

The five tree templates, one terrain template and original barn/fence templates are immutable
Python vector values, constructed once. They have no native surfaces and cannot grow with frames,
presets or requested times. Their measured retained Python object graph is recorded in
`artifacts/phase3b1/summary.json` against a 3 MiB design allowance. No LRU or frame cache is used. The smaller foreground fronds/boughs remain bounded
analytically evaluated vector paths.
Only bounded sway/color/footprint values change during evaluation; ground details and orchard canopy
contours are not regenerated per frame. All recipes have fixed loop ceilings.

The quality proof has fewer than 1,500 commands and 12,000 path/clip operations per frame under
all tested preset extremes. The unchanged backend limit remains 4,096 commands; these are lower
art-direction regression bounds, not changes to backend or memory policy. One 720p live ARGB32
surface is 3.516 MiB. High-resolution hero is 7.91 MiB; largest new proof sheet is 1620 × 2100,
12.98 MiB. Targets are sequentially owned, below the accepted 32 MiB surface allowance. Streaming
uses the existing one-thread FFmpeg settings, 256 MiB job budget, 64 MiB reserve and strict
preflight/monitoring. No cache of rendered frames, float image arrays, GPU or target deployment.

## Reproduce the review locally

Run sequentially from the checkout, in the pinned renderer environment:

```sh
uv sync --frozen --extra renderer
uv run pytest --basetemp outputs/pytest-phase3b1
uv run ruff check .
uv run ruff format --check .
uv run python -m build --no-isolation
uv run python tools/render_environment.py --output-dir outputs/polish --stills-only
uv run python tools/render_environment.py --output-dir outputs/polish
uv run python tools/environment_review.py --output-dir outputs/polish --repeat-dir outputs/polish-repeat
uv run python tools/render_environment.py --preset examples/environments/orchard_suspense.json --output-dir outputs/suspense
uv run python tools/review_environment_polish.py --output-dir outputs/polish
```

Use fresh output directories: comparison publication refuses to overwrite an existing video.
The A/B utility reads the unchanged committed Phase 3B MP4/still. It keeps both panels at native
720 × 1280, 30 FPS, 180 frames, producing a 1440 × 1280 comparison. The suspense camera is never
used in that A/B. The full 180-frame decoded hash lists and source checkpoints establish repeated
same-host consistency. They do not promise cross-platform or byte-identical codec output.

Proof sheets flatten each cell into its own bounded surface before tiling. This preserves
the intersection of the viewport and material clips and prevents cross-cell overscan.

The lighting sheet is explanatory: cool ambient with warmth/haze at zero; the normal final
composite; isolated wall/ground light components; isolated valley haze; original Rowan materials;
and shaded Rowan/contact. The ambient panel retains authored directional shading. It is not an
unlit physically based albedo pass. Isolated light components have no occluding barn and should
be interpreted alongside the actual depth sheet and composite.
