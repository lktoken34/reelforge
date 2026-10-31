# V1 source audit

Audited attachment: `agent_reel_pipeline.zip`, SHA-256
`a7ce25e398ca106ba97ea482be86794749ee14a9135e23c24fe740742d4b68ab`.
Read its Python modules, tests, sample project, wrapper, requirements, Makefile and documentation.
All paths below refer to that archive, not V2. No V1 runtime code was copied.

## Evidence and scope

Ran `python3 -m unittest discover -s tests -v` inside the extracted V1 directory: all **5 tests
passed** on CPython 3.12.14. They test the sample, duplicate scene IDs, bad captions, one
interpolation midpoint and an image size of 180×320. That is basic prototype evidence; there
is no memory/throughput benchmark, image golden comparison or production video verification.

Additional isolated validation probes using deep copies of the provided project:

| Mutation | Observed V1 result |
| --- | --- |
| Add unknown root property `render_magic` | Accepted |
| Set first scene duration to float NaN | Accepted |
| Set output to 720×720 | Accepted by validation; rendering separately rejects aspect ratio |
| Replace first scene with an empty list | Unhandled AttributeError |

V1 numeric checks use `isinstance(value, (int, float))`; booleans can satisfy those checks.
A short boolean duration may still fail a separate caption bound check. Validation should
reject it by type before any downstream checks. These probes did not invoke video rendering.

Independently probed the supplied reference using ffprobe: H.264 video, AAC audio,
720×1280, 30/1 fps, container duration 87.074830 seconds. Inspected one downscaled frame at
10s: consistent cutout figures/dog, barn geometry, selective light cones, layered depth and
outlined white captions. This narrow sample is not a fresh shot-by-shot review. V1's
`docs/REFERENCE_ANALYSIS.md` describes 25 frames, but that historical claim was not repeated
in this audit. No inference is made about the original creator's tools or rights. No reference
frame/video is bundled with V2.

## Reuse and rewrite decisions

| V1 component | Reusable idea | Recommendation |
| --- | --- | --- |
| `spec.py` | Validate before expensive work, stable scene IDs, project-root path confinement | Rewrite with strict versioned schema, staged semantic checks and bounded diagnostics |
| `render.py:16` `motion` | Explicit keyframes and pure easing/interpolation | Re-specify later as pure frame-index evaluation; test endpoint/partial-key behavior |
| `render.py:136` `render` | Stream raw frames to FFmpeg rather than keep a video in memory | Retain pattern later; rewrite lifecycle, budgets, flags, error handling and atomic output |
| `art.py:30` `Painter` | Logical coordinate space and procedural primitives | Use as design inspiration for backend-neutral commands; do not port hard-coded figures |
| `art.py` backgrounds/actors | Consistent palettes and deterministic local Random(seed) in map | Reference examples only; rebuild as reusable versioned code recipes and rigs in later phases |
| `render.py` captions | Text wrapping, mobile contrast, highlighted words | Preserve requirements; rewrite around pinned fonts, shaping, safe-area and overflow contracts later |
| `qa.py` | Distinguish technical output checks from human art review | Retain distinction and review dimensions; rewrite robust technical probing later |
| CLI, Makefile, `pipeline.py` | Small repeatable command interface and fail-fast orchestration | Replace with packaged CLI, machine-readable errors and capability discovery; no full pipeline now |
| AGENTS, character/world bible concepts | Persistent identity and continuity; honest quality claims | Retain principles; reduce agent task complexity through approved catalog/templates |
| `tests/test_spec.py` | Baseline validation and frame smoke concept | Rewrite contract/CLI tests now; defer frame tests until a backend exists |
| PNG layer path and asset-pack instructions | Stable identity references can be useful | Reject external raster-art dependency; future visuals originate in trusted code recipes |

No missing production component is disguised as reusable finished functionality. V1's
placeholder art is not evidence that the reference quality has been reached. There is no
license file in the uploaded prototype; review ownership/licensing before copying any code.

## Main weaknesses

1. **Contract robustness:** `spec.py:27–62` checks a subset of fields, accepts unknown keys,
   NaN and non-portrait output, and assumes nested shapes. Actor positions are numeric but
   unbounded; camera, lighting, color and transform fields are largely unchecked. Keyframe
   time ordering/duplicates and parameter completeness are not enforced. Audio path checks
   are unnecessarily repeated inside the scene loop. JSON loading has no byte bound and
   ordinary parsing accepts duplicate keys/non-finite literals.
2. **False capabilities:** `SUPPORTED_POSES` lists look/crouch, but drawing mostly handles
   walk/point/scared/idle behavior. Dog facing is ignored. Direction does not consistently
   transform whole characters. A weaker agent can request a validated effect that never occurs.
3. **Coupling:** art, character identity, posing, effects and world geometry live together in
   `art.py`; camera/captions/composition/FFmpeg/audio share `render.py`. CLI eagerly imports
   raster dependencies even for validation. There are no replaceable backend/IR boundaries.
4. **Memory risk:** background cache holds up to 24 images and external asset cache 48 decoded
   RGBA images, bounded by count rather than bytes. At 720×1280, 24 RGB backgrounds alone are
   ~63.3 MiB and 48 full-size RGBA images ~168.8 MiB, before frame copies, masks and encoder.
   Actual occupancy depends on keys and source dimensions. `spotlight`/`vignette` allocate
   full-frame NumPy intermediates; zoom/resize/rotation create additional buffers. Layer size
   checking happens after the source is decoded/copied and does not bound rotation expansion.
5. **Scheduling:** `round(scene_duration * fps)` per shot can accumulate timeline discrepancy.
   Whole-image zoom scales all composition; no articulated hierarchy, depth-aware parallax,
   stable identity catalog or semantic acting template system exists.
6. **Process safety:** FFmpeg uses default thread behavior, no memory preflight, cancellation
   policy or timeout; output is written directly to its final name. Audio remux renames the
   source before success. Failures can leave partial files and need clearer recovery.
7. **Reproducibility:** broad Pillow/NumPy ranges, no transitive lock, system-dependent font
   fallbacks, no dependency fingerprint or deterministic pixel/video tests. FFmpeg version,
   flags, metadata and fonts are not pinned as a render environment.
8. **QA and operations:** `qa.py:5` probes before checking existence, assumes a usable stream,
   and does not check corruption/black frames/audio. CLI QA exits unsuccessfully only on
   errors even if warnings make `passed_technical_checks` false. `pipeline.py` runs all stages
   without an enforced creative approval stop. Tests check dimensions, not image quality.
9. **Agent workload:** V1 asks the driver to invent art assets/bibles, stage shots, repair rigs
   and judge quality. That is too much variability for the intended weaker agents. V2 should
   concentrate complexity in trusted libraries and expose a narrow, discoverable vocabulary.

## Migration policy

Keep V1 separate for reference. Do not support V1 JSON via implicit fallback. Any later importer
must explicitly translate seconds into integer frames with a declared rounding policy, report
unsupported art/poses/PNG dependencies, and produce a versioned V2 draft for review. Phase 1
contains no importer, rendered demo or compatibility layer.
