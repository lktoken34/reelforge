# ReelForge prompt-to-reel MVP — handoff

A supported natural-language prompt now produces a complete animated reel through one command,
and a genuine 60-second reel has been produced with the same machinery. This document covers both
deliverables. Branch `phase9c-snowy-mountain` in `D:\NikhilV\reelforge\outputs\reelforge-9b`, on
the approved baseline `19be6e4c2d904482a0ffd1211d55a9da0c94f2f7` plus the existing Phase 9C work
(all preserved). Nothing committed or pushed.

## Deliverables

- `outputs/YellowMellow_60s_MVP.mp4` — the 60-second reel (1,800 frames, 60.000 s, 720×1280,
  H.264/yuv420p, silent).
- `outputs/YellowMellow_60s_contact_sheet.png` — 20-panel contact sheet (one frame per segment).
- `tools/make_reel.py` — the prompt-to-reel CLI.
- `src/reelforge/mvp/` — the planning + shot-library package (`planner.py`, `storylib.py`).
- `outputs/example_A_manifest.json`, `outputs/example_B_manifest.json` — two example prompts'
  generated, validated production manifests (plus `example_A_plan.json`/`example_B_plan.json`
  summaries and `main_60s_manifest.json`).
- `MVP_VERIFICATION.json` — media verification, resource measurements and plan differences.

## Installation and dependencies

Use the existing environment; no new dependencies were added. Rendering needs the accepted native
stack (Python 3.12, pycairo 1.29.2, FFmpeg). On this machine that is the WSL Ubuntu 24.04
interpreter (`python3`), not the Windows `.venv` (which is blocked by Application Control).

```bash
cd /mnt/d/NikhilV/reelforge/outputs/reelforge-9b
export PYTHONPATH=$PWD/src
```

## One-command usage

```bash
# Render a 60-second reel from a prompt
python3 tools/make_reel.py \
  --prompt "Yellow Mellow travels across the snowy mountains, discovers a buried emergency beacon, activates it as a storm hits, then follows the signal down to the valley orchard where rescue answers" \
  --duration 60 --output outputs/my_reel.mp4

# Validate a plan without rendering (fast, no native work needed for planning)
python3 tools/make_reel.py --prompt "Yellow Mellow finds an emergency signal in the snowy mountains." \
  --duration 15 --plan-only --manifest-out outputs/example_A_manifest.json

# List the supported vocabulary
python3 tools/make_reel.py --list-support
```

Options: `--prompt` (required), `--duration {15,60}`, `--output <mp4>`, `--plan-only`,
`--manifest-out <json>`, `--work-dir <dir>`, `--title`, `--list-support`. Exit codes: 0 ok,
2 planning error (unsupported prompt/duration), 3 contract-validation error, 4/5 render error.

The 60-second reel above was produced by exactly this command. The two example prompts validate
with `--plan-only`; per the brief, the second prompt is not rendered as a second 60-second video.

## How a prompt becomes a plan

Pipeline (no hand-edited JSON between steps):

```
prompt --> planner.analyse (keywords) --> planner.plan_story (act skeleton + expansion)
       --> planner.build_production_manifest (production-0.1) --> compile_production (full
           scene/storyboard/direction/blocking validation) --> render_production (audited chunked
           episode-0.2 render + verified stream-copy concat) --> MP4 + verification
```

The planner is a small, explicit, **deterministic rule set** — not an AI model and no network
call. `planner.analyse` matches keyword patterns to supported signals: an environment
(snow/mountain → Frost Peak, orchard/valley → orchard), story actions (beacon, discover,
investigate, run, storm, rescue, lost), and a mood. `plan_story` builds a four-act skeleton
(discovery, storm/decision, journey, resolution) from those signals, then expands or trims it to
the exact segment count (5 for 15 s, 20 for 60 s) by lengthening each act from a per-act
continuation menu — extra time becomes distinct travel/observation beats in that act's single
environment, never a random location jump and never a duplicated set piece. Each beat is realised
by a named shot preset in `storylib` into a validated `storyboard-0.1` segment. Unsupported
prompts or durations return a clear error listing what is supported; the planner never silently
substitutes a default story.

## How an AI cloud agent can use the planner

An external LLM is optional and never required. Two integration points:

1. Call the CLI with a prompt; parse the JSON it prints (plan summary + `ok`/`stage`).
2. Or produce a `production-0.1` manifest directly (same shape as the example manifests) and feed
   it to `reelforge.productions.contract.compile_production` → `render_production`. The contract
   validates it strictly, so a model cannot smuggle unsupported assets, actions or paths.

`planner.supported()` (also `make_reel.py --list-support`) returns the machine-readable vocabulary
an agent should plan within: durations, environments, shot presets, beat keywords and the
character id.

## Supported scope

- Character: `yellow_mellow_v2` (rig, expressions, motions, including the `activate` interaction).
- Environments: `frost_peak` (snowy mountain + emergency beacon + answering light) and `orchard`
  (Last Light dusk orchard). Both place the actor on an existing walkable registered ground.
- Shot presets: `establish` (wide), `reaction` (readable close-up), `investigate` (approach +
  crouch + measured beacon button press), `threat` (low beacon flare + storm), `travel`,
  `travel_run` (escape), `resolve` (hero/outcome). The beacon presets require Frost Peak.
- Durations: 15 s (5 segments) and 60 s (20 segments). Output is silent 720×1280 H.264 at 30 fps.

## Audio: the one-command MVP is silent

**The one-command prompt-to-reel output (`make_reel.py`, both 15 s and 60 s) is silent: the MP4
has zero audio streams.** This is deliberate. The long reel is compiled as a silent
`production-0.1` (`audio: null`), so the deliverable is a video-only H.264 file. `make_reel.py`
has no audio option, does not mix or schedule audio, and never generates audio (no AI speech,
music or sound effects).

### Adding audio separately (existing, unchanged workflow)

Audio is supported by a *separate* existing path that this MVP does not wrap or modify: the
registered-audio `episode-0.1` workflow. To produce a reel with sound you work outside
`make_reel.py`:

1. Register real operator-supplied PCM16 WAV assets with `tools/register_audio.py` (its `--help`
   documents the import workflow); assets live under `assets/audio`.
2. Author an `episode-0.1` manifest whose `audio` block is an accepted `AudioPlan` (48 kHz
   stereo, AAC 128 kbps target, ≤1 registered narration cue and ≤4 registered SFX cues, with
   absolute episode start frames).
3. Render it with `tools/episode.py render <manifest> --output-dir <dir> --registry-root
   assets/audio`. That path runs `render_episode` with the existing registration, sample-accurate
   alignment and audio verification rules.

Constraints are enforced by the existing contracts, not bypassed: unsupported audio
configurations (unregistered files, too many cues, bad timestamps) are rejected with a clear
error rather than silently coerced. This MVP task did not rebuild or expand the audio engine; the
`episode-0.1` audio path is exactly as it already was.

## Known limitations

- The planner understands the supported MVP vocabulary only (two environments, a fixed beat set).
  It is keyword/rule based; it does not claim open natural-language understanding and rejects
  prompts outside scope.
- Editorial cuts between segments (and the chunk boundary at frame 900) are hard cuts; no seamless
  motion continuity is promised across them.
- Location changes happen at an act boundary (the journey hands Frost Peak off to the orchard);
  the engine cannot morph one environment into another within a shot.
- Longer acts reuse legitimate walk/run cycles with varied framing; they are distinct segments,
  not duplicated staged shots, but they are still traversal beats rather than new set pieces.
- 15 s and 60 s only; other durations are rejected.
- Development-host render and resource figures only; no CI, no GitHub publish, no target-VM
  certification.

## Files changed in this sprint (additive only; no engine source modified)

New:
- `src/reelforge/mvp/__init__.py`, `src/reelforge/mvp/storylib.py`, `src/reelforge/mvp/planner.py`
- `tools/make_reel.py` (prompt-to-reel CLI), `tools/verify_60s.py` (60s verification + sheet)
- `tests/test_mvp_prompt_to_reel.py`

The engine contracts, renderer, character, environments and production workflow are unchanged this
sprint; the MVP layer only assembles validated manifests and calls the existing pipeline.

## Verification summary

- 60-second MP4: 1,800 decoded frames, 60.000 s, 720×1280, H.264/yuv420p, zero audio streams,
  `ffmpeg -xerror` decode clean, continuous 1/30 s timestamps, 19 editorial cuts, 19/20 sampled
  segment frames distinct, no black frames. Production reported `success=true`,
  `assembly_frame_hash_match=true` (concat dropped/duplicated no frames), exact rational PTS.
- Resources: max per-chunk process-tree peak ≈ 135.6 MiB against the 256 MiB budget.
- Planner: prompt A (snowy beacon) vs prompt B (orchard discovery + run) differ in environment,
  presets, actions and scene assets (A uses `beacon_01`; B uses `orchard_ground_01` and a
  `travel_run` escape).
- Focused tests: 14 MVP tests pass; 118 production/snowy/storyboard contract tests pass (no
  regression). Ruff check and format pass on all new files.
