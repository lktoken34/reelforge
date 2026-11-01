# Phase 4A — declarative cinematic sequencing review candidate

Approved base: `b8aa300b06e1123eeafd300f87fa553d34b58e3d`.
Local branch: `phase4a-shot-sequencing`. This milestone stops for independent architectural
and visual review. No GitHub push, individual asset upload or deployment was attempted.
The repository's remote baseline was read/fetched only; its tree matched the accepted local
Phase 3B.1 implementation. No new environment or character was authored.

## Result and weak-agent path

`examples/stories/last_farm.json` fully determines the title, output, shot timing, compositions,
existing environment/character IDs, actions/expressions and art-direction values. The
`story-0.1` validator constructs immutable Story/Shot values and rejects missing/unknown fields,
overlap/gaps/order errors, invalid ranges, nonfinite values, unknown IDs, unsupported walking/
running combinations, transitions other than cut and requests outside the single output profile.
It does not evaluate strings, follow asset paths, dynamically import code or infer a narrative.

```sh
python tools/validate_story.py examples/stories/last_farm.json
python tools/render_story.py examples/stories/last_farm.json --output-dir outputs/last-farm
```

The first tool is native/media independent. The second validates before output creation or
optional rendering imports, then streams a continuous silent film and report. No manual Python
editing is necessary. The installed production episode CLI remains not render-ready; these are
experimental study tools. See SHOT_TIMELINE.md for exact fields, bounds and clock semantics.

| Sample shot | Exact interval / seconds | Composition and acting |
| --- | --- | --- |
| quiet_orchard | [0, 120) / 0.0–4.0 | Establishing wide, idle/calm Rowan, dusk orchard geography |
| rowan_notices | [120, 240) / 4.0–8.0 | Tighter left-side Rowan, look_around/concerned, doorway retained right |
| dark_entrance | [240, 360) / 8.0–12.0 | Larger doorway-focused push, react/frightened, cropped Rowan at left |

Frames 119/120 and 239/240 are the two actual cut pairs. There is no rendered frame 360:
frame 359 is shown until the exact 12.0-second endpoint. Every output frame belongs to one shot.
There is no transition padding, intermediate encoded clip or encoder restart.

## Narrow implementation and compatibility

- `stories/contract.py`: native-free versioned validation, existing strict JSON loader and
  preset validation, 1–8 shots, 30–300 frames per shot, at most 900 total frames, 30 FPS.
- `stories/sampling.py`: bounded direct lookup by global integer frame, normalized shot
  progress, real-time shot-local acting, global atmosphere time and three composition recipes.
  No accumulated state, frame-index table or generic animation framework.
- Existing `environments/scene.py`: extract `compose_layers`, accepting an explicit camera and
  the two clocks. The original layers_at/environment_frame wrappers still supply their exact
  old camera/time/actor. No drawing recipe or old camera equation changed. An explicit existing
  direction parameter enables the validated left/right character preset without rig edits.
- `tools/render_story.py`: one accepted Cairo surface and one accepted FFmpegEncoder across
  the full schedule, strict preflight/JobMonitor, decode/probe/stream checks and measured reports.
- `tools/review_story.py`: bounded representative/cut frames, isolated-panel storyboard, SVG
  timeline, same-host compatibility check and complete repeat comparison. The SVG was also
  rasterized as timeline.png for convenience. Proof labels are not video captions.

Renderer/backend, media/encoder/process/verification modules, character rig/acting source,
resource/security/deployment policies, production episode contracts/CLI, dependencies and lockfile
are unchanged. A future CI step was added for the validator, full story render and repeat proof;
no remote CI run is claimed for this local assignment.

Before editing, 16 full-resolution Cairo hashes were captured on the approved parent: frames
0, 60, 120 and 179 for all four existing environment camera presets. After the refactor,
**all 16 match exactly**. Existing committed films/proofs were preserved. This is same-host/native
pixel evidence, not a promise that different Cairo/FFmpeg builds produce identical pixels.

## Evidence delivered

`artifacts/phase4a/` contains:

- `story.mp4`: final 720 × 1280, H.264/avc1, yuv420p, 30 FPS, 360 frames, 12.000 seconds;
  one video stream, no audio/subtitle stream, faststart layout and complete strict decoding.
- `storyboard.png`: representative frames 60, 180 and 300, ordered left to right and labeled
  by composition. Each panel is rendered separately before tiling to preserve material clips.
- `frame_060.png`, `frame_180.png`, `frame_300.png`: full-resolution representative frames.
  `frame_000`, `119`, `120`, `239`, `240`, `359`: first/last and exact cut-adjacent proofs.
- `timeline.svg`, `timeline.png`: code-generated diagram with exact [0,120), [120,240),
  [240,360) intervals and 0/120/240/360 frame / 0/4/8/12 second labels.
- `report.json`, `repeat_report.json`: complete first/repeat source and decoded hash lists,
  canonical story, format, timing, CPU, memory/OOM and cleanup evidence.
- `repeat_consistency.json`: all 360 source and all 360 decoded frames matched.
- `compatibility_report.json`: all 16 legacy before/after checkpoints and native versions.
- `proof_report.json`, `boundary_audit.json`, `pts_audit.json`, `summary.json`, integrity manifest and local
  test/lint/build/installed-wheel smoke logs.

Source surface hashes use the native Cairo ARGB32 layout header; decoded hashes are RGB24.
The first and repeat films are not asserted to be byte-identical codec containers. Timing,
acting and all source pixels are evaluated independently for every requested frame. Metadata
and source diagnostics found no blank frame, no adjacent source duplicates and 360 distinct
decoded frames in the delivered film. All 360 presentation timestamps also match frame/30
within ffprobe's six-decimal display precision. Static holds remain allowed in other valid stories;
repeated-image diagnostics alone do not reject intentional stillness.

## Local verification and measured cost

**412 tests passed: all 325 previous cases plus 87 new cases.** New coverage includes strict
field/JSON/resource validation; frame-exact end-exclusive ranges and cut membership; minimum,
maximum and eight-shot schedules; independent durations/clocks; hash-seed/order independence;
three composition targets and a consistent screen axis; existing character direction/action
presets and depth-1 ground contact; legacy wrapper compatibility; native-free validation and
invalid-CLI behavior; real continuous two-shot encode/full decode/repeat; and injected geometry,
encoder-write and cancellation failures with child reaping and surface/transaction cleanup.

Ruff lint/format, wheel/sdist build and installed base-wheel smoke outside the checkout passed.
The wheel smoke checked validation, shot lookup and pure scene geometry with Cairo explicitly
absent, and confirmed the production CLI still advertises render_available false. No new runtime
or development dependency is required.

| Development-host measurement | First full film | Full repeat |
| --- | ---: | ---: |
| Render + encode wall time | 28.825 s | 26.256 s |
| Observed encoded FPS | 12.49 | 13.71 |
| Main-process CPU, including verification/report preparation | 28.812 s | 26.797 s |
| Waited child user / system CPU | 14.183 / 1.423 s | 16.256 / 1.401 s |
| Sampled simultaneous process-tree peak RSS | 98.51 MiB | 106.94 MiB |

First-film geometry generation took **11.399 s**, Cairo rasterization **13.153 s** and stream
writes **2.988 s**. The wall total additionally includes hash/metadata/bookkeeping overhead.
Per-shot timings and all repeat details are in the reports. The proof-sheet job peaked at
84.02 MiB. Rendering is CPU-only and slower than real time; a separate exploratory run measured
15.86 FPS, illustrating normal host-load/allocator variation rather than a throughput guarantee.

Peak emitted complexity was **1,259 DrawPaths / 9,704 path+clip operations**, comparable to the
accepted scene. No frame cache, floating-point image pass, extra runtime surface, process pool
or per-shot encoder was introduced. The existing immutable art templates are unchanged. The
story retains at most eight preset pairs and 900 text hashes, not full video frames. The default
render writes no PNG sequence; nine specific sample proof frames are generated separately.

Both full jobs used the unchanged **256 MiB process-tree budget / 64 MiB reserve**, strict memory
policy and continuous OOM telemetry with unchanged counters. They finished with zero live
surfaces/allocated surface bytes and no private encoder transaction. Failure/cancellation tests
also verify cleanup. RSS is sampled every 10 ms and can miss short peaks or double-count shared
pages; cgroup counters have shared scope, not a dedicated job cap. This development host has
more available memory than the target VM. No Muse Spark run or constrained-target certification.

## Visual assessment and limitations

I inspected the representative full-resolution frames, both sides of each cut, the final
storyboard/timeline and 24 decoded animation samples spaced at half-second intervals. The
three shots communicate an understandable beginning, reaction and focus on a suspect location:
the orchard's quiet geography is established; Rowan's concern becomes readable at larger scale;
then the doorway takes over the composition while he remains on its left. Ground contact and
warm/cool identity are maintained. All shots stay on the same viewing side. The cuts are
intentional compositional/acting edits, rather than accidental camera interpolation jumps.

The reveal shows **the dark entrance**, not an animated antagonist or an explained threat.
Existing acting is restrained, and the finite react action settles before the four-second shot
ends. There is no pose blending/state carry between shots; action clocks restart at cuts.
Arbitrary valid shot/action/expression combinations can still be artistically weak. This
validator checks executable support and resource bounds, not dramatic coherence.

The accepted art remains an illustrated 2.5D setting with approximate lighting/shadows and a
screen-locked sky, not a unified perspective or physically lit environment. Close compositions
make those limitations and the hand-authored material detail more visible. There is deliberately
no narration, captions, sound, music, lip-sync, autonomous story interpretation or production
compiler. **Full Stickocalypse storytelling quality is not claimed.** Reviewers should evaluate
both the small subsystem boundary and the actual film before authorizing any later milestone.
