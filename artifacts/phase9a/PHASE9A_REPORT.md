# Phase 9A: Yellow Mellow Episode Integration — engineering report

Date: 2026-11-03. Host: WSL2 Ubuntu 24.04, Python 3.12.3, pycairo 1.29.2, FFmpeg 6.1.1, CPU only.
Development-host result only. Not a target-VM or deployment certification. Technical success does
not prove artistic quality.

## Mission result

Yellow Mellow V2 is integrated into ReelForge's normal episode-generation workflow. A new,
complete, verified 15-second silent Yellow Mellow story was generated from a validated JSON
manifest through the standard `tools/episode.py` interface, without editing the engine for that
story. Character registration alone was not relied upon: the episode animates Yellow Mellow's
real rig, IK, expressions and motion presets through the pipeline.

Deliverable video: `outputs/yellow_mellow_episode/scene/reel.mp4` — 720×1280, 30 fps, 450 decoded
frames (all unique), 15.000 s, one H.264/yuv420p video stream, zero audio streams, continuous
rational PTS at F/30.

## Git provenance (honest status)

There is no Git repository in the workspace (`git rev-parse` fails; no `.git`). As authorized, I
did not run `git init`. I cannot establish any commit hash, and the baseline `f5b689a…` and the
Phase 8 ZIP are not present as git objects. Provenance is instead recorded as source-file SHA-256:

- `outputs/phase9a/source_snapshot_sha256.txt` — hashes of all 290 tracked `src/tools/tests/docs/
  examples` files captured before any Phase 9A edit.
- `outputs/phase9a/changed_files.txt` — the diff: 6 files added, 11 modified, 279 unchanged.

No pre-existing uncommitted modifications were identifiable (no VCS to compare against); the
snapshot is the authoritative "before" state. The Phase 8 engine and the Yellow Mellow V2 package
were already present and intact in the working tree and were reconciled by working against them
directly, not by restoring an archive.

## Architecture (smallest backward-compatible, versioned extension)

The pipeline was hardwired to Rowan in several places and the episode contract required audio.
The integration adds one indirection layer and two versioned contract bumps; it does not rebuild
the engine or add a character-specific render script.

1. **Character registry** (`src/reelforge/characters/registry.py`, new): the single place
   episode-side code resolves a character id to its scene-asset id, scene actions, expression
   vocabulary and standing height. Registers `rowan_01` and `yellow_mellow_v2`. Lazy imports avoid
   cycles and keep the renderer-heavy packages off the import path until needed.

2. **Character dispatch at the drawer level, not the route math.** The blocking `RouteClock` and
   contact solver compute a character-agnostic world root trajectory and a left/right facing per
   90-frame segment — this drives camera tracking and contact validation for *both* characters and
   is unchanged. Only the per-frame *drawing* is dispatched: `blocking.sampling.commands` now
   builds the Rowan vector character as before, or, for a non-Rowan plan, a Yellow Mellow V2
   `Performance` whose action timeline is derived from the same blocking segments
   (`characters/yellow_mellow_v2/episode.py`, new). The V2 drawer returns ground-origin commands in
   the exact shape of `rowan.draw_character(position=(0,0), scale=1)`, so the camera, scene graph,
   compositing order, framing-safety checks and the owned/verified/no-clobber transaction are all
   untouched.

3. **Character selection in the contracts, versioned and optional.** The storyboard `rowan` block
   accepts an optional `character` field (default `rowan_01`), and the compiled blocking document
   stays `blocking-0.1` for Rowan or becomes `blocking-0.2` when a non-Rowan character is selected.
   `blocking-0.1` manifests are byte-identical in behaviour; the `character` field is refused under
   `blocking-0.1`. The beat `expression` is validated against the selected character's own
   vocabulary (Rowan's 6 or Yellow Mellow's 8). `direction` accepts `blocking-0.2` as a base.

4. **Registered character scene node.** `yellow_mellow_v2` is registered as a `character` asset
   (`scenes/assets.py`). A non-Rowan character scene node uses a minimal `{character, action,
   expression}` descriptor (`scenes/contract.py`, `CharacterRef`) instead of Rowan's six-field
   `CharacterPreset`. A static scene-recipe fallback draws a neutral standing Yellow Mellow; the
   episode path always supplies the animated per-frame override instead.

5. **Silent episode (`episode-0.2`).** The episode contract accepts `audio: null` under
   `episode-0.2` (the underlying `audio_from_data` already supported `None`; only the episode layer
   forbade it). `episode-0.1` still requires audio. `render_av` gained a `silent` flag that skips
   the registry-snapshot, PCM mix, AAC mux and audio-verify stages, verifies the silent `scene.mp4`
   directly and publishes it; `stream_check(silent=True)` asserts exactly one video stream and zero
   audio streams. The owned private transaction, no-clobber publish-by-link, resource monitoring,
   full-decode verification and cleanup are identical to the audio path. No dummy or muted track is
   attached.

### Coordinate reconciliation

Yellow Mellow (standing height 142.5 character units) is drawn at `draw_scale = 95/142.5 ≈ 0.667`
so that under the shared blocking plan scale it occupies a frame fraction comparable to Rowan. The
story's character node uses world scale 0.47 (inside the blocking 0.35–0.75 band) — the value the
accepted example worlds resolve to — so the proven walk/run trajectory magnitudes settle in the
calibrated stride phase. The blocking route owns absolute world X; the drawer draws at the local
ground origin and drops V2's baked locomotion travel to avoid double-counting horizontal motion.
V2's vertical pelvis motion (bob, crouch) and planted-foot contacts are preserved.

## The new story — "Yellow Mellow: The Orchard Trail"

Manifest: `examples/episodes/yellow_mellow_orchard.json`. Five 90-frame storyboard segments on the
registered orchard scene (`dusk_sky_01`, `distant_hills_01`, `orchard_ground_01`, `orchard_tree_01`,
`fence_01`), with a five-beat arc and intentional per-segment camera framing:

| Seg | Frames | Beat arc | Expressions | Camera |
|---|---|---|---|---|
| 1 Something in the orchard | 0–89 | enter → curious walk → discover → wonder → hold | neutral → curious | push_in with offset |
| 2 Closer to the glimmer | 90–179 | ready → creep → arrive → pause → startle | curious → excited → surprised | push_in |
| 3 Down the trail | 180–269 | brace → wary walk → decide → scan → run | concerned → determined | establishing + follow (editorial cut inside) |
| 4 Catching breath | 270–359 | slow → ease in → stand → breathe → relief | determined → happy | push_in |
| 5 A good find | 360–449 | glance → step up → realize → cheer → end pose | happy → excited → determined | push_in with offset |

Beginning (arrival), discovery (the glimmer), reaction (startle), meaningful action (the run), and
resolution (relief, then a confident end). It is not the V2 showcase and does not reuse the Phase 8
Rowan sample. Editorial cuts at frames 90/180/270/360, plus an in-segment cut in segment 3.

## Verification (independent)

`outputs/yellow_mellow_episode/video_verification.json` (ffprobe + full `ffmpeg -xerror` decode):

| Check | Result |
|---|---|
| Decoded frames | 450 (engine `verify_video` framehash + independent ffprobe frame list) |
| Unique decoded frames | 450 / 450 (genuine motion) |
| Duration | 15.000 s |
| Resolution / fps | 720×1280, 30/1 |
| Streams | 1 H.264 video, 0 audio |
| Pixel format | yuv420p |
| Timestamps | 0.000 → 14.967 s, every step 1/30 s; engine `stream_check` confirms exact rational PTS F/30 |
| Decode errors | none (exit 0, empty stderr) |
| File size | 2,563,070 bytes |

Representative frames: `outputs/yellow_mellow_episode/frames/` (two per segment plus each editorial
cut boundary). Contact sheet: `YellowMellow_Episode_Contact_Sheet.png`.

**Frame inspection.** I pixel-differenced the composed frame against an environment-only render:
the character contributes pixels in exactly one compact grounded region per frame — Yellow Mellow
is drawn once, grounded on the path, correctly framed by the tracking camera, with visible pose
changes (walk cycle, arms-out reactions at the startle and relief beats) and visible expression
changes (eyes widen at the surprise). The faint tree-line silhouette on the distant ridge is the
accepted `distant_hills_01` asset, present in Rowan renders too, not a character artifact.

## Resources and safety

- Render + encode + full verification: 52.2 s render/encode; whole-job wall 71.2 s.
- Memory budget 256 MiB + 64 MiB reserve preserved and enforced. Renderer peak RSS 43 MB; estimated
  simultaneous process-tree peak 131 MB; all-children peak 92 MB. OOM telemetry continuous;
  `limit_reason` null.
- At most 847 draw paths / 7,479 ops per frame (caps 4096 / 80000). One reused 720×1280 surface; 0
  live surfaces and 0 surface bytes after render (no leak). Owned transaction cleaned and absent.
- Cancellation (SIGTERM/SIGINT) wired in `tools/episode.py`; child cleanup and temporary-workspace
  handling inherited unchanged from `render_av`.

## Tests

`tests/test_yellow_mellow_integration.py` (new, 24 tests) plus the full regression set all pass:
`551 passed` across `test_yellow_mellow_integration`, `test_yellow_mellow_v2`, `test_episodes`,
`test_reels`, `test_storyboards`, `test_blocking`, `test_scenes`, `test_characters`,
`test_direction`, `test_character_polish` (run with `--basetemp outputs/pytest-phase9a-full`).

New tests prove: the registry lists both characters; expression mapping; blocking-segment → V2
action mapping including the terminal-run stop; a JSON-selected Yellow Mellow actually changes pose
between idle and walk and travels along the route; the face changes across a segment (eyes widen on
surprise); every segment frame renders ≤4096 valid DrawPath commands; feet stay grounded; invalid
instructions are rejected (unknown character, dict/`eval` injection, character field under
blocking-0.1, V2-invalid expression, too-short sub-segment); the silent episode-0.2 contract
accepts `audio: null` while episode-0.1 still rejects it and episode-0.2 still accepts audio; and
Rowan storyboards/episodes are unchanged (still blocking-0.1, still rowan_01, still render).

Ruff lint and format pass on all changed and new files. The full historical suite, wheel/sdist
build and no-Cairo base install were not re-run (no packaging or dependency change; instructed to
use focused tests).

## Authoring without Python (for a weaker agent)

`examples/episodes/yellow_mellow_quickstart.json` is a second, different 6-second (2×90) episode
authored entirely in JSON — no Python edited. To make another episode: copy a segment, set
`rowan.character: "yellow_mellow_v2"`, set the scene character node `asset_id` and `character` to
`yellow_mellow_v2`, choose beats/actions and a V2 expression per beat, keep the character node
world scale in 0.35–0.75, and set `audio: null` for silence. Validate with
`python tools/episode.py validate PATH`, render with `--output-dir`. The route magnitudes must
settle the stride phase; reuse the orchard numbers (walk ~40 units over 36 f at speed ~30–35, run
~40 units over 30 f at speed ~80) as a safe starting point.

## Known limitations and uncertainty

- **Character on-screen size.** At world scale 0.47 Yellow Mellow reads fairly small in frame. This
  satisfies the blocking support/scale band and keeps the proven trajectories valid, but a larger
  figure would need re-tuned route magnitudes. Documented, not hidden.
- **Terminal run stops internally.** When a segment's locomotion is still moving at frame 90 (the
  escape), the V2 clip is asked to stop so it resolves to planted feet rather than being cut
  mid-stride; the body still follows the blocking route via the per-frame placement, so no sliding
  beyond V2's small residual is introduced. The camera route itself continues per the blocking
  segment.
- **Expression aliasing.** A storyboard authored with Rowan's expression names maps onto the
  nearest V2 expression (e.g. `calm→neutral`, `frightened→surprised`); the orchard story uses V2
  names directly.
- **Scene recipe fallback** for a non-Rowan character draws a neutral standing pose only; it is a
  static-inspection path and is never used during episode rendering (the per-frame override always
  wins).
- **No Git / no deployment claim.** No repository, no commit hash, no push/CI. This is a
  development-host integration gate for independent review, not a deployment certification.
- Artistic quality is my own frame inspection only; it needs independent review.

## Toward the 60-second MVP

The integration keeps the one-pass continuous encode, the owned transaction and the 90-frame
segment model intact, and adds silent rendering and character selection as versioned, additive
contract fields. A 1,800-frame / 20-segment reel reuses the same `render_av` path (its frame bound
already allows up to 900 frames; extending to 1,800 is a bound change, not a redesign) and the same
character dispatch, so this gate is a direct stepping stone to the 60-second one-command workflow.
