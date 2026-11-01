# Experimental shot timeline — story-0.1

This is the smallest bounded multi-shot study interface, separate from the foundation episode
manifest. Existing production `reelforge capabilities` still says `render_available: false` and
foundation validation remains `render_ready: false`. The story validator also reports
`render_ready: false` to avoid implying production readiness; `valid: true` authorizes only the
experimental render tool described here. No story interpreter, general animation timeline,
new environment, backend, scheduler or asset upload mechanism is introduced.

## Minimal weak-agent workflow

Copy the supplied example and edit JSON only:

```sh
python tools/validate_story.py examples/stories/last_farm.json
python tools/render_story.py examples/stories/last_farm.json --output-dir outputs/last-farm
```

Validation prints one JSON result and exits 0 on success, 2 on invalid input/I/O. Errors contain
`issue.code`, JSON Pointer `issue.path` and a repair message. Fix that field using the choices
below, validate again, then render. Never edit engine Python to make a story validate.
The render tool validates before creating output directories or importing Cairo/FFmpeg code.
It returns structured JSON and a nonzero exit for validation, runtime failure or cancellation.
Use a fresh output directory: the accepted encoder refuses to clobber an existing `story.mp4`.
The JSON never chooses filenames, paths, render commands or memory policy.

The ordinary render writes **one `story.mp4` and one `report.json`**, with no intermediate PNG
sequence. In the sample, cut boundaries are frames 120 and 240. Frame 359 is the last rendered
image; the interval ends exactly at frame 360 / 12.0 seconds. The first image is frame zero,
without a lead-in black frame. Output is silent H.264/yuv420p, 720 × 1280 at 30 FPS.

## Exact contract

Top-level keys must be exactly `schema_version`, `title`, `output`, `shots`.
`schema_version` is `story-0.1`; `title` is nonempty metadata, at most 120 characters, and never
appears as a video caption. Fields are required; unknown/missing fields fail explicitly.
Input reuses the accepted UTF-8 JSON loader: bounded 1 MiB read, maximum 32 container nesting,
no duplicate keys, NaN, Infinity or float overflow. Nothing is evaluated or dynamically imported.

`output` has exactly these fields:

| Field | Supported value / inclusive bound |
| --- | --- |
| width | integer 720 |
| height | integer 1280 |
| fps | integer 30 |
| frames | integer 30–900, equal to final shot end_frame |
| codec | `h264` |
| pixel_format | `yuv420p` |

`shots` contains 1–8 shot objects. Each shot has exactly:

| Field | Supported value / semantics |
| --- | --- |
| id | unique snake_case ID, starts with a letter, maximum 48 characters |
| start_frame | integer, inclusive; first must be zero; later starts equal preceding end |
| end_frame | integer, exclusive; shot duration 30–300 frames (1–10 seconds) |
| environment | `last_light_orchard_01` |
| camera | one of the three trusted composition IDs below |
| transition | `cut` only; no blend, gap, inserted frame or transition duration |
| character | exact existing six-field CharacterPreset object, stationary actions only |
| art_direction | exact `atmosphere`, `warmth`, `breeze`, `framing` object |

Timeline frames are true integers: booleans, fractional/numeric-string boundaries, unsorted
shots, overlaps, gaps and nonpositive/oversized durations fail. No silent sorting or repair.
End-exclusive ranges partition every output frame once. Shot IDs are labels, independent of
camera selection. All shot timing and supported behavior come from the JSON; no manual Python
editing or external selection is needed.

`character` uses existing fields `character`, `action`, `direction`, `speed`, `expression`,
`intensity`. Character is `rowan_01`; action is `idle`, `look_around` or `react`; direction is
`left` or `right`; speed is 0.5–1.5 and intensity 0.5–1.0. All existing expressions are supported:
`calm`, `concerned`, `focused`, `surprised`, `frightened`, `determined`. Actions `walk`/`run`
remain valid in the existing character preset API but are **explicitly unsupported here**:
this milestone has no character travel/blocking contract. No fallback to idle is permitted.

The art fields reuse EnvironmentPreset bounds: atmosphere/warmth/breeze 0–1, framing −1–1.
Framing offsets the trusted camera horizontally by up to eight logical units. There are no
exposed camera coordinates, geometry seeds, paths, arbitrary entity lists or lighting equations.
The existing environment preset JSON/shot IDs remain valid in their own tools, unchanged.

## Three compositions and timing

| Camera ID | Composition and purpose | Bounded camera recipe |
| --- | --- | --- |
| establishing_wide | Orchard/barn geography, foreground frame and full Rowan silhouette | Zoom .95→1.03; slow five-unit drift |
| character_reaction | Rowan enlarged on the left, doorway retained to his right for attention/eyeline | Zoom 1.72→1.88; x 25→29, y 28→32 |
| suspense_reveal | Barn doorway dominates; cropped Rowan remains at left to maintain identity and direction | Zoom 2.05→2.30; x 70→94, y 35→42; first/last 10% held |

These are three compositions of the same accepted art, not a general 3D camera. They preserve
uniform transform composition and the same ten layers/painter order. Character, near props,
contact shadows and ground all use depth 1. Door spill remains attached to the barn's depth .85
through the accepted depth-to-ground projection. Hills and foreground retain their existing
parallax coefficients. Mirroring direction is an explicit user choice, not automatic eye tracking.

For global frame f in shot [a,b): local frame is f−a, action seconds are (f−a)/30, atmosphere
seconds are f/30, camera progress is (f−a)/(b−a−1). Integer-derived values never accumulate deltas.
Camera interpolation uses the existing smoothstep; endpoints occur on the first and last
included frames. Changing duration stretches camera motion while preserving real-time action
cadence. Existing speed/intensity still govern acting, and `react` retains its anticipation,
recoil and settle. There is no reinterpretation of a four-second action as a six-second clip.

**Action clocks restart at each cut**, as declared by the shot selection. Atmosphere/breeze
continue on global time, preserving background phase. No pose blending is promised between
hard cuts: selecting a new action/expression makes an intentional edit. Reusing the same
art-direction values and direction preserves location/lighting/screen axis in the sample;
the validator does not judge the artistic continuity of arbitrary combinations. There is no
general story scheduler, state transfer, narrative inference or threat simulation.

The old environment `layers_at`/`environment_frame` wrappers still supply their original
six-second camera, concerned look-around actor and time to `compose_layers`. All 16 captured
before/after checkpoints across the four old camera IDs match exactly on the local native build.
See `artifacts/phase4a/compatibility_report.json` for that evidence, not a cross-platform guarantee.

## Resource and process boundaries

Story/Shot values are immutable and hold at most eight preset pairs. Scheduling is a bounded
linear lookup; there is no global frame table or mutable playback cursor. Only the current
frame's DrawPath tuple and one 720p ARGB32 target (3.516 MiB) are used by the render loop.
The existing fixed vector-template allowance is unchanged. No native frame is retained in
Python. Up to 900 source SHA-256 text hashes (57.6 KiB of digest characters, plus bounded Python
container overhead) support verification; these are metadata, not image buffers.

One accepted FFmpegEncoder context consumes the entire timeline. Hard cuts change the next
draw list, without restarting the encoder or inserting padding. Existing BGRA streaming,
backpressure, one-thread encoding, max allocation flag, finite waits, atomic no-clobber video
publication, cancellation and child cleanup remain unchanged. JobMonitor uses the existing
256 MiB process-tree budget, 64 MiB reserve and strict preflight; JSON cannot override these.
Total encoder timeout is bounded at max(120, frames/2) seconds (maximum 450 seconds); the accepted
per-frame write timeout remains five seconds. This changes no encoder or deployment policy.

Full verification counts/decodes every requested frame, checks H.264/yuv420p/30 FPS/duration and
faststart, and confirms one video stream with no audio/subtitles. Source hashes include the native Cairo ARGB32 layout header; decoded hashes are RGB24.
Reports include every source and decoded hash, boundary hashes, per-shot counts/timings, source blank/duplicate diagnostics,
whole-job RSS, CPU, OOM observability and cleanup counters. Static holds can legitimately produce
identical neighboring images; duplicate diagnostics alone do not reject a valid hold.

Review tooling is separate and bounded: at most eight representative frames, two sides of each
cut, and first/last frames are written as proof PNGs, never a default frame sequence. Storyboard
cells use the accepted isolated-panel procedure to preserve material clipping. A small SVG
diagram shows exact sample boundaries. No audio/captions are composited into the movie.

## Review and reproduction

Run sequentially, in the pinned renderer environment:

```sh
uv sync --frozen --extra renderer
uv run ruff check .
uv run ruff format --check .
uv run pytest --basetemp outputs/pytest-phase4a
uv run python -m build --no-isolation
uv run python tools/validate_story.py examples/stories/last_farm.json
uv run python tools/render_story.py examples/stories/last_farm.json --output-dir outputs/last-farm
uv run python tools/review_story.py examples/stories/last_farm.json --output-dir outputs/last-farm --repeat-dir outputs/last-farm-repeat
```

Render/report success certifies only this experimental technical path. It does not approve the
production episode contract, artistic storytelling parity or constrained-target deployment.
Stop after Phase 4A for independent architectural and visual review.
