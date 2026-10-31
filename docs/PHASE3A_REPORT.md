# Phase 3A — first reusable character review

Branch: `phase3a-character-rig`, based on approved `84eee4af27a38644e1a7461b4fb0a699eee4bfbb`.
Package version 0.5.0; dependency graph unchanged. Status: implemented on development hardware,
**awaiting independent artistic/architectural review**. Muse Spark remains blocked; it was not
used and its memory/deployment policy has not been changed.

## Visual deliverables

- [Six-pose sheet](../artifacts/phase3a/rowan_pose_sheet.png), 1440×1280.
- [Idle / walk / run MP4](../artifacts/phase3a/rowan_idle_walk_run.mp4), 720×1280, 30 FPS, 5 seconds, silent.
- Full-resolution source frames: [idle](../artifacts/phase3a/frame_000.png),
  [walk](../artifacts/phase3a/frame_060.png), [run](../artifacts/phase3a/frame_120.png).
- [Machine-readable render/decode/repeat/memory evidence](../artifacts/phase3a/report.json).
- [Development host/native dependency context](../artifacts/phase3a/development_host.json).
- [Design, skeleton mathematics, action parameters and experimental contract](CHARACTER_RIG.md).
- [Agent preset example](../examples/characters/rowan_walk.json).

**Rowan Vale** is an original orchard keeper with a pale oversized head, small worried face,
creased ochre hat, rust jacket, neck cloth, patched blue-grey trousers, work gloves/boots and
satchel. All artwork is manually authored cubic paths and restrained local shading. It is the
same artwork/hierarchy in every pose. No AI images/video, tracing or stock character packs.
The supplied reference was re-inspected at 14/21/35/49s alongside REFERENCE_STYLE.md; observed
silhouette/pose principles guide this original design without inferring production tools.

Reviewed the six-pose sheet, full-resolution idle/run images, eight decoded chapter samples
and six closely spaced running samples across a cycle. Corrected a visible jaw/neck gap,
concerned brow direction, toe-off rotation and an initially too-small run stride. The final
poses retain identity, articulating sleeves/boots and a clear hat/bag silhouette. This visual
inspection is not an independent artistic acceptance or a claim of reference-level quality.

## Architecture and files

New `src/reelforge/characters/` contains `rig.py` (immutable hierarchy/pivots/pose transforms,
two-bone solve), `presets.py` (bounded parameters and deterministic idle/walk/run), `rowan.py`
(original layered artwork and data-to-trusted-preset entry point), `study.py` (fixed review
composition/pose sheet), `preset.schema.json` and the package marker. Cairo-specific objects
remain inside the existing backend. Art, skeleton, motion and proof scene are separate.

Added `tools/render_character.py`, `tools/validate_character.py`, `tests/test_characters.py`,
the example, docs and review assets. Updated README/AGENTS/architecture/roadmap/catalog status,
project version/lock metadata and added a development CI proof/artifact step. Existing Cairo,
FFmpeg, surfaces, process utilities, resource/memory policies, foundation schema and CLI
implementation are unchanged. No catalog, general timeline, story compiler or deployment work.

## Actual technical verification

All **232 tests passed**: previous 188 preserved plus 44 new character cases. Tests cover
hierarchy/order/pivots, attachment coincidence, IK endpoint reach, bounded parameter extremes,
frame-order determinism, stance contact, toe-off/wrap continuity, stronger run envelope,
small idle motion, mirrored artwork, replaceable artwork, preset schema/JSON failure cases,
chapter transitions and real repeated pixels/expression changes. Ruff lint/format passed;
wheel and source archive built. Base installed wheel without Cairo: **172 passed, 8 skipped**;
rig/schema work outside the checkout and the foundation CLI still reports no render capability.

Two sequential full MP4 encodes passed ffprobe and entire-file decoding. Both contain exactly
150 changing H.264/avc1 yuv420p frames at 30/1 FPS and duration 5.000000s, faststart MP4. All
150 decoded RGB frame hashes matched between repeats on the same FFmpeg build. Raw checkpoint
hashes, artifact hashes, full decode command and metadata are committed in report.json. No
byte-identical H.264 guarantee across native builds is asserted.

| Measurement | First / repeat |
| --- | --- |
| Render + encode wall time | 2.646 / 2.686 s |
| Effective encoded FPS | 56.68 / 55.85 |
| First geometry / draw / stream-write time | 0.361 / 1.807 / 0.387 s |
| First whole-job wall time including decode | 4.213 s |
| Renderer CPU / child user / child system | 2.776 / 3.409 / 0.273 s |
| First renderer peak RSS | 20.74 MiB |
| First encoder peak RSS | 66.30 MiB |
| First sampled simultaneous whole-job tree peak | **87.02 MiB** |
| MP4 bytes | 842,969 |
| Live surfaces / allocated surface bytes after | 0 / 0 |

Geometry/draw/pipe durations are measured inside a concurrently encoding job, not an isolated
renderer throughput promise. Whole-job RSS includes the renderer and encoder/verification
children. Individual peak columns must not be added to invent a simultaneous peak. Sampling
can miss transients and double-count shared pages; this is not a hard enforced cap.

Host: Ubuntu 24.04.3 x86_64, Python 3.12.14, Pycairo 1.29.2, Cairo 1.18.0 and FFmpeg 6.1.1;
9 affinity CPUs with quota equivalent to 8, 8 GiB cgroup memory cap, ample available memory,
UID 0. Native/software renderer and CPU encoder only. This is not target-VM evidence or a
low-available-memory benchmark. The accepted 256 MiB job/64 MiB reserve policy remains strict.
No resource-security source file was changed; no controller/swap/host setting was modified.

## Visual limitations and review request

The pose sheet is not a 3D turnaround: left is a mirrored three-quarter cutout. Limbs are rigid
segments; jacket shoulders/elbows use overlap rather than deforming cloth. Hat/bag remain rigid,
scarf motion is limited, hands are a small mitten design, and the face has only three simple
expressions plus fixed proof blinks. Current outline weight/detail is somewhat fuller than
the sparsest reference shots. No independent perspective, texture or sophisticated lighting.

World-space steady stance contact is tested geometrically. The fixed short action blends are
approximate: small transient foot drift and <=0.726 logical units of sole overshoot (under
2 screen pixels at this proof scale) remain. It is not a general contact/collision solver.
The run is a stylized cycle, not motion-capture biomechanics. Artistic timing, acting and
cinematic storytelling are not certified by passing tests.

Request review of silhouette/readability, proportions, pose/identity continuity, limb layering,
stride/weight and expression before expanding the library. Keep the current infrastructure;
address concrete artistic notes on this one character before any later cast/environment or
production-animation milestone. **Stop after Phase 3A.**
