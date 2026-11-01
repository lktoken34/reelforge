# Phase 3B.1 — cinematic environment artistic review candidate

Approved base: `ef27965967e78c025a2526def415a22975e3b5c1`.
Local branch: `phase3b1-environment-polish`. Stop for independent visual/architectural review.
This assignment does not approve production catalog promotion, Phase 4 or target deployment.

## Reference observations and changes

Before editing, the actual supplied 87.07-second reference MP4 was decoded at 2.61, 10.45,
20.90, 33.09, 45.28, 56.60, 67.92 and 80.11 seconds. The original orchard MP4 was decoded at
0, 1, 2, 3, 4 and 5.9 seconds. The reference's dusk exterior and barn/interior samples emphasize
large cool/dark framing masses, restricted warm light, strong figure readability and depth
from intervening vegetation. Its dramatic cuts and sound also contribute, beyond this shot's
scope. These are visual observations, not claims about the creator's implementation.
No reference footage, traced shapes, stock art, generated imagery or external textures enter
the runtime or this export. The original ochre/olive/teal identity and Rowan are retained.

| Review concern | Observation in original orchard | Implemented response / review evidence |
| --- | --- | --- |
| Repeated trees | Similar round lobes and uniformly distributed highlights | Stable per-tree branch height/lean/width; seven irregular cubic bough masses, clipped directional accents and sparse details; compare orchard layer and A/B |
| Uniform crop rows | Even V-shaped marks and solid regular bed edges | Missing plants, offset spacing, varied clump scale/value, subtle soil marks and path wear; farm layout retained for recognizability |
| Disconnected lighting | Broad ambient tone; entrance spill not attached through depth | Clipped warm siding/lantern accents, eave/side-plane shade, authored branch shadows, projected threshold footprint, cool character materials and directional contact shadow |
| Empty upper scene | Broad repeated cloud ribbons with little scale or framing | Broken diagonal cloud bank, restrained high cloud, small distant birds and connected overhead/right bough framing; same main camera preserved |
| Restrained camera | Short push had little narrative emphasis | Separate `orchard_suspense`: opening hold, larger easing push/drift toward entrance, closing settle; existing concerned look-around retained |
| Character cohesion | Jacket/face read brighter and warmer than surroundings | Dusk paint grading, modest warm material edge and stronger near-foot/cast shadow; all rig paths, transforms and stroke widths preserved |
| Game-background feeling | Similar visual emphasis across farm details | Cool edges and foreground, warm focal path/threshold, more layered atmosphere and quieter scattered detail; separate suspense shot demonstrates the intended focus |

Reusable code lives in `environments/polish.py` and existing scene composition. It emits only
the accepted drawing vocabulary. The six preset fields and every previous camera equation
remain compatible; the new shot is an additive named preset. See ENVIRONMENT_POLISH.md.
No renderer, encoder, media process/verification, rig, resource policy, dependency or lockfile
source changed. No GPU, full lighting engine, narration, timeline or extra environment.

## Controlled deliverables

All current proofs are in `artifacts/phase3b1/`:

| File | Meaning |
| --- | --- |
| `original_phase3b.mp4` | Byte-for-byte copy of the approved committed Phase 3B film |
| `orchard_cinematic.mp4` | Refined main shot: 720 × 1280, 30 FPS, 180 frames / six seconds |
| `before_after.mp4`, `before_after.png` | Original on left, refined on right; native 720 × 1280 per panel, same original camera/action/timing; still at frame 90 |
| `orchard_suspense.mp4` | Separate new camera demonstration with the same six-second format |
| `hero_1080x1920.png` | Independently rasterized full-resolution vector hero at frame 90 |
| `frame_000.png`, `frame_090.png`, `frame_179.png` | Full 720p main-camera checkpoints |
| `camera_contact_sheet.png`, `suspense_contact_sheet.png` | Start/middle/end, left to right; main and separate camera |
| `layer_*.png`, `depth_breakdown.png` | Same ten layers; nine transparent isolated layers and an opaque RGB sky; clipped labeled depth sheet |
| `lighting_atmosphere_breakdown.png` | Six labeled panels explaining ambient, final composite, surface/ground light, haze and Rowan's material grading |
| `report.json`, `suspense_report.json`, `comparison_report.json` | Full format/decode, timing and whole-job resource evidence |
| `repeat_consistency.json`, `suspense_repeat_consistency.json` | Repeated full decoded/source consistency checks |
| `summary.json`, `artifact_manifest.json`, check logs | Compact measurements, integrity metadata and local verification |

A fresh unchanged baseline render on this host matched all 180 decoded frames of the committed
original. The delivered A film is the committed original itself, not a substituted recreation.
Main A/B camera equality is checked numerically for the existing preset equations. The comparison
utility stacks the two inputs without panel scaling, exposure adjustment or differing frame time.
It is a comparison transcode; consult the original inputs for compression-sensitive detail.

## Engineering evidence

**325 tests passed: all 301 existing cases plus 24 targeted cases.** Coverage includes stable
integer variation across hash seeds/order; distinct tree identities; bounded zero/full breeze;
unchanged old camera equations and preset loading; extreme lighting values; deterministic
suspense composition/parallax; attached threshold origins across depth planes; material-only
character grading; layer order; doorway light exclusion in actual pixels; out-of-order pixel
hashes; injected encoder failure cleanup; and proof-cell clipping with an existing material clip.
Ruff lint/format, wheel/sdist build and an installed base-wheel geometry/CLI smoke test outside
the checkout passed. That wheel check explicitly confirmed Cairo was absent.

The initial full-test attempt used pytest's `/tmp` default and correctly hit the unchanged
persistent-workspace restriction in one existing media integration test. Its log is retained as
`initial_test_attempt.txt`. Final full verification used `--basetemp outputs/pytest-phase3b1-final`;
no resource policy or old test was relaxed.

| Same development host | Render/encode wall | Geometry | Rasterization | Observed encoded FPS | Sampled simultaneous process-tree RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unchanged Phase 3B rerender | 14.453 s | 7.492 s | 5.477 s | 12.45 | 90.85 MiB |
| Refined main | 12.812 s | 5.330 s | 6.305 s | 14.05 | 91.78 MiB |
| Separate suspense shot | 14.452 s | 6.075 s | 7.089 s | 12.45 | 98.12 MiB |

The refined main repeat peaked at 106.23 MiB after proof-sheet work. Full-resolution A/B
assembly peaked at 143.83 MiB; corrected proof-sheet assembly peaked at 153.58 MiB. Final
repeat metrics, including the suspense repeat, are preserved in their JSON reports. Host load,
allocator state and monitoring overhead affect these few observations; they are not a statistical
speedup claim. Rasterization is costlier, while immutable templates reduce geometry work enough
to avoid an observed end-to-end regression in this run.

An early uncached art pass took 26.68 s. It was replaced before delivery: the fixed five-tree,
one-terrain, barn/fence object graph is now 2,253,848 bytes (2.15 MiB), below the documented
3 MiB design allowance. It cannot grow with frame count. Current frame complexity is 1,258
commands versus 952 before; sampled path/clip operation count is 9,698. Targeted extremes keep
both below 1,500 commands / 12,000 operations. There are no rendered-frame caches or new buffers.

Every video was fully decoded with strict FFmpeg error handling and ffprobe frame counting;
all main and suspense repeats matched all 180 decoded RGB hashes and source checkpoints.
The A/B is verified at 1440 × 1280, H.264/yuv420p, 30 FPS, six seconds; individual films are
720 × 1280 in the same format. No native surfaces, allocated surface bytes or private encoder
transactions remain after each render. The injected-failure test also reaps its child and
removes the partial transaction. Comparison/PNG utilities report whole-tree RSS; they do not
claim a separately registered encoder-only peak.

All measured jobs retained the unchanged **256 MiB budget / 64 MiB reserve**, strict policy,
continuous OOM telemetry and unchanged OOM counters. The 10 ms RSS sampler can miss brief peaks;
summing RSS can count shared pages more than once. Host/cgroup counters are shared-scope and
not a dedicated per-job hard cap. This development machine has much more headroom than the
target VM. None of this certifies constrained-target deployment; Muse Spark was not used.

Visual QA caught an existing proof-layout assumption: a command with its own material clip
could overscan an adjacent sheet cell. The new review utility renders each cell to a separate
bounded surface before tiling. A native pixel regression test covers that case. Final sheets
were regenerated and inspected; scene/video pixels required no change for this correction.

## Artistic self-review

The candidate has clearer dusk cohesion, more varied orchard silhouettes and planting, a
more anchored warm entrance and a better foreground frame. The separate camera draws attention
toward the doorway more deliberately. These are useful, reusable improvements at bounded cost.

This remains a stylized illustrated environment. Tree masses still share one recipe; crop beds
retain their regular farm perspective; siding and terrain lack the richness of painted material.
Sky negative space remains generous in the controlled shot. Local shadows/penumbrae and light
shafts are authored approximations, not volumetric transport or a physically lit scene. Rowan's
local-space material edge is not full pose-aware relighting. Tree/terrain shadow relationships
across different parallax planes remain approximate. The quiet six-second look-around does not
match the reference's cuts, sound design or narrative escalation. The foreground bough is a
strong graphic gesture that reviewers may want softened.

**No reference-quality parity or artistic acceptance is claimed.** Independent reviewers should
judge the matched A/B and separate suspense shot, then accept, request focused polish or reject
the gate before any later milestone. Work stops here with a local committed ZIP; no push,
individual GitHub uploads or deployment was attempted.
