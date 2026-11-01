# Phase 3B — first cinematic environment review candidate

Approved parent: `705694a4f5d6b583c5583d44a577544cc1a78344`.
Branch: `phase3b-cinematic-environment`. Stop here for external architectural/artistic review.
No Muse Spark deployment was attempted. No rig, backend, encoder or monitor source changed.

## Delivered visual proofs

All files are under `artifacts/phase3b/`:

- `orchard_cinematic.mp4`: silent H.264/yuv420p, 720 × 1280, 30 FPS, 180 frames / 6 seconds.
- `frame_090.png`: full-resolution concept/hero composition with Rowan; frame 0 and 179 are
  full-resolution camera checkpoints.
- `layer_*.png`: ten full-resolution isolated layers, transparent outside authored artwork.
- `depth_breakdown.png`: labeled, clipped ten-layer sheet, 1800 × 1400.
- `camera_contact_sheet.png`: start/middle/end, 1080 × 640.
- `flat_vs_environment.png`: approved character-study background beside the new environment,
  1440 × 1280. This illustrates staging/depth differences; character scale/action are not matched,
  so it is not a controlled animation A/B or a character improvement claim.
- `report.json`, `repeat_consistency.json`, `test_results.txt`, `build_results.txt`: raw evidence.

The supplied Stickocalypse MP4 was sampled into a contact sheet for visual study. The new
artwork is original code-generated geometry; no footage, raster background, generated imagery,
stock assets, fonts or Blender models were imported into the environment.

## Technical evidence on the development host

301 automated tests passed, including all 276 pre-existing tests and 25 new cases. New coverage
includes strict bounds/IDs/fields, deterministic frame sampling, depth/parallax math, transform
composition with rotated character parts, explicit painter order, parameter effects, out-of-order
pixel consistency, repeated native rendering and exception cleanup. Ruff lint/format and
wheel/sdist builds passed. A fresh base wheel installation is checked without Cairo.

The first render encoded 180 frames in **11.475 seconds / 15.69 FPS**. Geometry took 6.253s,
drawing 4.150s and streaming 0.928s. Main-process CPU over render + verification/report preparation
was 11.606s; child user/system CPU 6.785s / .552s includes encoding and full decode verification.
These are observed development-host results, not a real-time throughput promise.

Full ffprobe frame counting and strict FFmpeg complete RGB decoding passed at the requested
resolution/FPS/duration. All 180 decoded frames were changing. The second complete render took
11.484s and matched **every decoded frame hash and every source checkpoint** on the same native
build. Byte-identical MP4s and cross-platform pixel identity are not implied.

Sampled simultaneous whole-job RSS peaked at **89.75 MiB**, with **99.36 MiB** on the repeat
process after review-sheet work. Both used the existing **256 MiB budget / 64 MiB reserve** and
strict memory policy, without fallback. Sampling interval was 10 ms; transient peaks can be
missed and shared RSS can be double-counted. Cgroup counters are shared with the host scope,
not an exclusive per-job cap. OOM telemetry was available continuously and counters did not
change. No retained surfaces or allocated surface bytes remained after rendering.

The host has much more available memory than the target VM. These measurements do not certify
constrained-target deployment, and no target gate or safety threshold was changed. Native build
prerequisites were absent; development-only Ubuntu headers/pkgconf were extracted outside the
repository to build pinned Pycairo against the existing shared Cairo. CI uses its normal
Ubuntu development packages. Dependencies and lockfile are unchanged.

## Honest artistic assessment

This is a coherent, restrained illustrated orchard, with a legible barn silhouette, siding/roof
construction, a path into the doorway, cultivation, apple trees, fence and trough, cool atmospheric
hills, warm focal accents and a dark foreground frame. Rowan reads at a plausible near-ground
scale. The push and stronger foreground parallax improve depth over the flat character-proof field.

It is a review candidate, **not a claim of professional/reference parity**. The canopy lobes,
cloud ribbons and crop rows remain visibly procedural and repetitive. Surfaces have selective
material marks rather than rich painted texture. Cast shadows are authored approximations;
there is no volumetric scattering or physically based light transport. The quiet look-around is
less dramatic than the reference's staging and edits. The upper sky is intentionally spacious,
but reviewers may find the pacing/framing too restrained. The character is an approved rig,
not newly lit with environment-specific relighting. Technical success cannot resolve those
artistic questions. External reviewers should accept, request targeted polish, or reject the
visual gate before any further milestone is started.

CI now runs the new preset validator, default stills/video and full repeated decode proof,
and uploads the environment review artifact alongside all existing CI checks. The exact remote
commit and live GitHub status are reported in the handoff rather than predicted here.
