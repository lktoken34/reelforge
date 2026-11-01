# Phase 5B procedural environment review candidate

Base: `e9a38b12806c2bbaa396b9d3577f3342b379d364`.
Branch: `phase5b-procedural-environments`. Local export only; no push, deployment or Phase 5C.

## Outcome and acceptance boundary

The implementation provides native-free environment-0.1 validation/planning, stable per-object
seed streams, reusable bounded vector recipes, sealed static geometry integration with the
accepted graph, six seed examples, and three 90-frame silent cinematic proofs. It preserves
the existing scene/story/audio manifests and leaves the production episode CLI not render-ready.
See [the authoring guide](PROCEDURAL_ENVIRONMENTS.md) for the supported fields and limits.

Development-host transaction restoration continues to fail retained cleanup assertions.
This is a review candidate, **not a clean full-suite acceptance claim**. The assignment
explicitly requires retaining these failures and obtaining independent Ubuntu validation.
No transaction, resource, renderer, encoder, audio, legacy test or safety policy was changed.
The only accepted graph implementation change resolves immutable trusted generated assets;
its default empty catalog continues to use the original registered assets and recipes.

## Visual assessment

All six 720 × 1280 start/middle/end images, six layer sets, seed comparisons and decoded
movie contact sheets were inspected. The videos are restrained location studies, with existing
Rowan acting and deterministic camera movement; they are not completed survival-story scenes.

Woodland now reads as a conifer walking corridor rather than an orchard: tall trunks, varied
heights/leans, layered needle shapes, a curved dirt path, boulder, sparse ground plants and
closer dark foliage. Seeds change the path and tree silhouettes and placement. The paired
needle tiers are still recognizable as a shared recipe; vegetation is angular and the small
plants repeat a star-like silhouette. There is no wind animation in the generated static assets.

The settlement has varied rooflines, building heights, directional side planes, broken
windows/boards, scarred cladding, crate/barrel, regrowth and distant architecture. Its final road
is 1.8 times the trail width function and uses paving seams. A final review connected the
foreground overhead remnant to its post so the moving camera no longer isolates a floating
beam. The village is clearly a built environment; however, the road still has a stylized ribbon
shape, seams can cluster, window layouts repeat, distant buildings are flat silhouettes and
weathering consists of bounded marks rather than sophisticated material aging.

The rocky approach uses original layered angular ridges, shaded/faceted rock masses, sparse
dry vegetation, a constructed arch and an access path. Large cool foreground rocks separate
the camera from the entrance plane. The final framing branch extends off the left side so it
reduces isolated branch fragments under the approach camera; end-frame cropping can still
make the twig tips read as disconnected. Alternate seed 3 partially occludes the
entrance with a near rock, giving a materially different reveal, although the foreground/rock
recipe repetition and low-poly facets remain visible. The shelter is symbolic architecture,
not a modeled interior. Character ground is a standing anchor, not general terrain physics.

Across families the palette, haze and clear character silhouette support depth and category
readability. Lighting is painted face shading/gradients and contact ellipses, without cast-shadow
simulation or general light interaction. Camera choreography remains the accepted gentle drift
or approach preset. Framing and static environmental detail are less nuanced than the reference;
Stickocalypse visual or storytelling parity is not claimed. Independent artistic review remains
necessary; deterministic geometry is not evidence of professional art quality.

## Evidence map

- `examples/procedural/`: six strict requests; each family's pair differs only in title/seed.
- `artifacts/phase5b/*_trail_*`, `settlement_street_*`, `rocky_shelter_*`: frames 0/45/89,
  transparent layers, graph/asset inspection, per-frame source hashes and resource reports.
- `woodland_video`, `settlement_video`, `rocky_video`: final 90-frame MP4 and full decode reports.
- `seed_contact_sheet.png`, `camera_contact_sheet.png`, `decoded_camera_contact_sheet.png`:
  category, seed and camera visual review.
- `determinism_report.json`: all six requests evaluated 89,0,45,0,89,45, with matching repeated
  geometry and pixels. Every pair differs in layout and rendered geometry, not only color.
- `video_repeat_consistency.json`: controlled final-geometry repeats and explicit cleanup status.
- `legacy_compatibility.json`, `handoff_legacy_pixels.json`: 12 full-resolution Rowan/orchard/story
  checkpoints and unchanged original media hashes. Nine Phase 5A scene checkpoints also pass
  in the new regression suite. Existing audio/video timing is decoded again in handoff evidence.
- `capabilities.json`, `environment-0.1.schema.json`, `cli_validation.json`, `cli_inspection.json`:
  discoverability and machine-readable supported requests.
- `historical_*`, original/full/handoff/final test logs: failed runs retained as evidence.

## Engineering verification and resources

The final test, performance and packaging summary is recorded below and in the machine-readable
reports. All 590 previous tests remain unchanged. The 102 new cases cover strict field/type/bound
validation, loader limits, geometry envelopes across families/densities/detail/lighting and seeds,
independent seed channels and density stability, no global hash/RNG dependence, graph and
support/parallax invariants, out-of-order pixel equivalence, legacy scene checkpoints, rejection
before geometry, output protection, resource cancellation, surface/child cleanup and native
FFmpeg failure. Existing cleanup tests are retained without skips or weakened assertions.

Strict limits remain 256 MiB for the process tree with a 64 MiB reserve, CPU-only operation,
64 nodes, 32 instances, 8 layers, 4096 paths and 80000 path/clip operations. No caps were raised.
Sampled process-tree RSS is not a kernel-enforced per-job peak and may miss short-lived peaks;
cgroup readings are shared-host observations, not dedicated job attribution. These measurements
are development evidence, not deployment certification. Temporary media and frames are streamed;
only a few explicitly requested proof images are written, without PNG sequences during encoding.

The fresh audio verification retained all 360 frames and exact presentation timestamps, including
cut frames 120 and 240. H.264 stream-copy hashes are unchanged. Decoded effective audio is 576000
samples/channel at 48 kHz with a documented 512-sample AAC tail; cue onset errors remain 0,−1,0
samples and measured audible drift is zero. Immediate private-directory cleanup passed, but that
path reappeared after a subsequent native decode. The report therefore marks the **overall cleanup
gate failed** separately from passing media synchronization. No speculative cleanup repair was made.

## Remaining review

Run the complete suite on independent Ubuntu 24.04 / pinned Python 3.12 with Cairo/FFmpeg,
using a fresh workspace-based pytest directory. Review the six full-resolution examples and
three moving-camera proofs. No independent Phase 5B CI or clean-host pass is claimed here.
Extend primitives, support metadata and any broader geometry language only under a future
reviewed assignment. Do not start Phase 5C from this candidate.

## Final visual-proof measurements

| Final 90-frame proof | Encoded FPS | Render + decode wall | Paths / operations | Sampled render tree RSS | Job cleanup |
| --- | ---: | ---: | ---: | ---: | --- |
| woodland_trail | 13.08 | 9.06 s | 755 / 5866 | 97.79 MiB | passed |
| settlement_street | 34.96 | 3.53 s | 616 / 3439 | 96.53 MiB | failed: path reappeared |
| rocky_shelter | 38.54 | 3.32 s | 438 / 3960 | 96.16 MiB | passed |

FPS measures the accepted encode loop, not full-job throughput. Static geometry construction
takes approximately 10–28 ms in the six-example determinism run; frame geometry sampling,
rasterization, CPU and stream times are separately recorded in the JSON reports. Woodland
whole-job wall time is 9.10 s. Final settlement and shelter controlled repeats monitor the
complete workflow, including generation, native children and decode; their wall/RSS and
cleanup errors are in `*_repeat_job.json`. These final repeats both preserve all 90 source
and decoded frame hashes; both reported path-restoration cleanup failures. They are not
successful end-to-end acceptance runs. The earlier successful rocky repeat belongs to the
pre-framing artwork and is historical evidence only.

Final proof render peaks are below 98 MiB; including controlled repeats the sampled whole-job
maximum is 99.72 MiB. Across earlier and final recorded Phase 5B jobs the highest sample is
100.02 MiB. The strict 256 MiB cap and 64 MiB reserve remain unchanged. Individual encoder
PID samples can be zero for short jobs; `all_children` and simultaneous tree samples include
native verification/encoding children. RSS sampling has the limitations stated above.

Six-example complexity is 438–755 paths and 3429–5866 operations. The final rocky framing
adds one path operation relative to the first checkpoint (3960 instead of 3959). Example
graphs use 24–25 nodes and 16–17 instances, seven layers, within the unchanged accepted caps.
The maximum declared family allowances in the authoring guide cover density 3 and rich detail.

## Final verification record

Pinned environment: CPython 3.12.14, Pycairo 1.29.2, Cairo 1.18.0; system FFmpeg
build/commands are recorded in per-job reports. `uv sync --frozen --extra renderer` passed.

| Completed suite | Passed | Failed | Fixture errors |
| --- | ---: | ---: | ---: |
| Saved pre-framing final run (`full_tests.txt`) | 690 | 2 | 0 |
| Fresh handoff run (`handoff_full_tests.txt`) | 690 | 2 | 0 |
| Final connected-framing source (`final_full_tests.txt`) | 689 | 3 | 0 |

All **102 new procedural cases pass** in the final 692-case suite. The remaining 590 are
the unchanged baseline cases; 587 passed and three failed. The exact final failures are:

- `test_audio.py::test_real_pcm_mix_aac_mux_repeat_and_clock`
- `test_transaction_cleanup.py::test_two_audio_jobs_persistently_clean_after_native_work`
- `test_video_integration.py::test_engineering_worker_accepts_long_render_arguments`

All three report reappearing private transaction paths, rather than generator assertion,
geometry bound, rendering, media-timing or resource-budget failures. The logs and final
JUnit XML are included intact. This classification does not make them passes. Earlier
pre-road-refinement logs, including fixture errors, are retained too. No tests were deleted,
skipped, weakened or selectively excluded to produce these results.

Ruff lint and format checks pass. Wheel/sdist build and installed-wheel smoke verification
are performed on the final source and recorded in `build.txt`, `handoff_lint.txt` and
`installed_wheel_smoke.json`. The installed CLI capabilities/schema/validation and all six
request compilations run outside the checkout with no Cairo installed. The no-network cache
lacked jsonschema, so a fresh smoke venv reused the already installed pinned runtime dependency
distributions, installed the new wheel separately and passed `uv pip check`. This is an
installed-wheel runtime test, not a fresh online dependency-resolution claim.

The final decode confirms all three 3-second, 90-frame, 720 × 1280, 30 FPS H.264/yuv420p
MP4s, all 270 hashes matching their final render reports, and representative stills matching
source frames. A successful decode does not override a render job's cleanup error.
