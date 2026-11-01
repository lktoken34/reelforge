# Phase 5A — generalized declarative scene graph review

**Implementation and visual proofs delivered; local full-suite acceptance remains blocked.**
All 102 new scene cases pass. The preserved 488-case baseline encounters its known transaction
restoration failures on this execution host. No cleanup patch, skipped assertion, resource-policy
change, push, deployment or Phase 5B/5C work is included. Independent review is still required.

Approved baseline: `cdd56d1c183eaacb65b8ba1a11d4dd5f36bfef2e`.
Branch: `phase5a-generalized-scene-graph`. The published baseline tree matched the preserved local
source exactly; its exact canonical Git commit was imported only after SHA verification. This
phase does not invalidate the user's independent approval of Phase 4B.1 on GitHub-hosted Ubuntu.
Historical blocked-status files are retained as evidence of the original development host.

## Architecture delivered

Native-free scene-0.1 has strict versioned JSON validation, an immutable graph compiler and
absolute-frame evaluator. Typed root/group/layer/background/environment/asset/character nodes
have stable IDs and explicit parents. Compilation rejects cycles, missing/duplicate IDs, unsupported
transforms, disconnected/unlayered instances, bad ground references and excessive expansion.

The eight-entry registry exposes existing Rowan, tree variants, barn, fence, sky, hills, terrain
and foreground recipes through local-anchor adapters. No entire orchard composition is called by
any of the three new examples. No accepted artwork/rig is rewritten. Static local attachments,
uniform rotated groups, independent painter order/parallax and registered ground support are
implemented. Existing path/clip/gradient/alpha/stroke data survive transform composition.

See SCENE_GRAPH.md for exact schema, coordinate math, support envelopes, limits and weak-agent
commands. JSON Schema and capabilities snapshots are under artifacts/phase5a. The contract remains
separate from story-0.1/story-0.2; there is no new story compiler or production render command.

## Visual evidence and self-review

All three manifests author different object placements, groups, scales, character positions and
compositions using the same approved vocabulary. There are full-resolution start/middle/end PNGs,
transparent per-layer PNGs, compiled plans, SVG/PNG hierarchy diagrams and a labeled contact sheet.
The final barn-approach MP4 is 90 frames / 3 seconds, 720 × 1280 at 30 FPS, H.264/yuv420p, silent.
It is fully decoded by the accepted verifier. One streaming encode is used; there is no frame list
or default intermediate PNG sequence. Two complete movie renders have identical source and decoded
hashes for all 90 frames; final ground-support metadata does not change geometry or projection.

The three representative views and the barn start/middle/end were inspected visually:

- Rural outpost: a smaller building, sparse vegetation and a near-left actor establish an open
  location. Much of the upper frame remains common sky; this is component reuse, not a new sky asset.
- Tree path: two separately grouped groves, foreground trees and Rowan on the right remove the barn
  and materially alter the corridor. The composition is right-heavy; the reused field/fence pattern
  remains visibly agricultural rather than a newly generated woodland floor.
- Barn approach: a larger, nearer barn and dark foreground boughs frame Rowan and the doorway. The
  right roof/wall intentionally crop at the frame edge. The doorway and actor stay readable through
  the restrained camera drift; no accidental character clipping or floor penetration was observed.

This is an architectural/layout proof, not a claim of Stickocalypse parity. Local asset highlights
are preserved, but there is no automatic cross-object lighting, terrain reshaping, shadow casting
or relighting in response to rearrangement. The finite ground/sky patches and familiar procedural
crop details remain recognizable. Static attachments do not follow joints. These are stated limits,
not capabilities inferred from passing validation.

## Determinism, bounds and compatibility

| Scene | Nodes | Actual paths | Path+clip operations | Conservative allowance (paths / ops) |
| --- | ---: | ---: | ---: | ---: |
| rural_outpost | 17 | 810 | 5701 | 1280 / 24300 |
| tree_path | 19 | 782 | 7269 | 1216 / 26300 |
| barn_approach | 16 | 1006 | 6628 | 1536 / 26300 |

Limits are 64 nodes, 32 visual instances, 8 layers, depth 8, 4096 DrawPaths and 80000 path-plus-clip
operations. Hidden instances still count. Envelopes are checked at compile time and evaluation.
A repeated out-of-order sequence (89,0,45,0,89,45) gives exact geometry/pixel hashes for every
scene and matches independently produced stills. The transform/clip/material test also compares
against an independent native Cairo CTM oracle (at most one channel-intensity step for floating
CTM multiplication); repeated renders themselves are exact on the pinned build.

All 12 full-resolution legacy checkpoint hashes match a separate archived import tree of the
approved source: orchard 0/90/179, Rowan 0/74/149, story 0/119/120/239/240/359. Character, environment,
renderer, story, audio, encoder, ownership and resource modules, old tests, dependencies and lockfile
are unchanged. Original silent/AV files retain their SHA-256 values. Fresh decoding of the preserved
12-second audio reel passes: onset errors 0, −1, 0 samples, unchanged H.264 data/PTS and no audible
drift. The 1024-sample AAC tolerance and 512-sample terminal codec tail remain unchanged. No AAC
container byte identity across native builds is claimed.

Output destinations are reserved with atomic directory creation. Existing videos, still images,
reports and even empty existing directories are rejected, protecting partial jobs and concurrent
writers as well as final MP4 publication.

## Tests and validation limitation

Final full-suite run: **587 passed, 1 failed, 2 fixture errors**, 590 cases, 88.19 seconds.
All **102 new scene cases pass**; the retained 488 cases contribute 485 passed, 1 failed, 2 errors.
The failure is the existing repeated audio cleanup assertion. Two errors share the existing
silent-template cleanup failure. The original pre-audio 412 cases pass. See full_tests.txt, tests.xml,
scene_case_results.json and test_execution.json. Earlier complete and partial logs are labeled;
partial/truncated logs are not counted as successful completed runs. Final stdout/stderr was
captured through a bounded 2 MiB pipe and saved after pytest was reaped, rather than relying on
an open log file while native operations run.

No failure was excused or converted to a pass. All 488 baseline tests remain unchanged. No new
scene assertion was disabled. The known restoration remains an environment limitation requiring
a suitable independent run; it is not evidence of a newly proven renderer or audio defect.
Docker/Podman are unavailable, and creation of a private user/mount namespace was denied by the
kernel. No isolated remote runner is exposed for unpublished local source. Consequently a clean
full-suite result could not be obtained in the available environment. The user-approved baseline's
previous three independent 488-test passes are context, not new Phase 5A CI evidence.

The new MP4's immediate and post-subsequent-media cleanup checks pass, and its failure-injection
scene test reaps FFmpeg/releases surfaces. These limited successes do not override the full-suite
failures. Ownership safeguards and strict 256 MiB / 64 MiB policy were not changed.

## Actual movie workflow measurements

| Metric | Final 90-frame graph render |
| --- | ---: |
| Whole render/encode/decode wall time | 10.347 s |
| Geometry evaluation | 3.822 s |
| Cairo rasterization | 3.698 s |
| Stream writes | 0.524 s |
| Effective render/encode FPS | 10.579 |
| Parent CPU | 8.841 s |
| Child user + system CPU | 4.219 s |
| Sampled simultaneous process-tree peak RSS | 102703104 bytes (97.945 MiB) |
| Maximum geometry | 1006 paths / 6628 operations |
| Live surfaces / allocated surface bytes afterward | 0 / 0 |

Strict monitoring spans the native video workflow; there is no OOM delta or fallback. Sampling can
miss short spikes. Stills/contact-sheet/diagram jobs have their own bounded reports. Output video
size is recorded in quality_summary.json; no continuous temporary-disk high-water mark is claimed.
These development-host measurements do not certify deployment or performance on the target VM.

Ruff lint/format, sdist/wheel build and installed-wheel smoke checks pass. The final installed
wheel is checked outside the checkout without Cairo: all three JSON scenes validate, compile and
evaluate; schema discovery works, the title limit is enforced and the production CLI still reports
render_available:false. No dependency or build-policy change is required. Full tests use PYTHONPATH=src to exercise
the working tree. In this reused offline environment, frozen non-editable sync retained the old
0.6.0 package; explicitly reinstalling the newly built wheel made the direct checkout CLI smoke
pass as well. Fresh installs/the normal editable checkout workflow do not depend on that stale
local wheel. Installation and CLI logs are retained.

## Remaining review and follow-up

Run the unchanged full suite plus these 102 cases on ordinary Ubuntu 24.04 / Python 3.12 in an
isolated workspace, repeat the pixel/AV checks and review the three layouts. Obtain a clean gate
before approval; do not infer it from this host's passing new cases or previous baseline CI.
The next scene/story integration must use an explicit contract extension. Arbitrary novel geometry,
automatic scripts, object interactions, skeletal sockets, production deployment and Muse Spark
integration remain out of scope. No future milestone is started here.
