# Phase 9C — "Yellow Mellow: The Last Light of Frost Peak"

Snowy-mountain cinematic storyboard (Stage 1 preview) and production integration.

## 1. Verified repository and baseline

- **Working git checkout:** `D:\NikhilV\reelforge\outputs\reelforge-9b` (toplevel confirmed with
  `git rev-parse --show-toplevel`). The parent `D:\NikhilV\reelforge` is **not** a git repo; the
  previous Stage-1 agent worked there, which is why its work was never on the approved baseline.
- **Approved branch/commit:** `phase9b-60second-reel` @
  `19be6e4c2d904482a0ffd1211d55a9da0c94f2f7`. Confirmed this commit is the baseline in history
  (`git merge-base --is-ancestor … HEAD` → ancestor). The working tree started clean.
- **Work branch:** `phase9c-snowy-mountain` (created from the approved baseline; no reset,
  nothing overwritten). **Nothing pushed to GitHub.**
- **Tested baseline:** all work and tests below were run against this checkout at that baseline
  plus the local changes listed in §5.

## 2. Existing Yellow Mellow integration (verified first)

The previous report's claim that Yellow Mellow V2 is *not* episode-integrated is **out of date
for this repo**. In this checkout it is fully wired into the production pipeline:

- `characters/yellow_mellow_v2/episode.py` turns accepted **blocking** segments (a
  character-agnostic route + per-segment facing) into a real V2 `Performance` and a Rowan-shaped
  per-frame drawer.
- `characters/registry.py` registers `yellow_mellow_v2` (asset id, expressions, standing height);
  `scenes/assets.py` registers it as a `character` asset; `blocking/sampling.py` builds and caches
  the V2 drawer and injects it as the scene **character override**.
- Rendering chain: `storyboard-0.1` → `blocking`/`direction` → `scenes.graph.evaluate_layers`
  (with the character override and camera) → `direction.sampling.direction_frame(plan, frame)` →
  `CairoRenderer.draw(..., logical_size=(360, 640))`. This is exactly what the audited
  `episodes/workflow.py` calls per frame, and what `examples/productions/yellow_mellow_60s.json`
  uses. The 60-second production chains these storyboard segments.
- **Environment selection** is by scene-graph node `asset_id` + `variant`, resolved to trusted
  code recipes in `scenes/assets.py::recipe(...)` which receive art direction (`warmth`,
  `atmosphere`, `breeze`) and `seconds`. **Camera/composition** come from scene camera presets
  (`locked`/`gentle_drift`/`approach`) plus storyboard `views` (behavior, zoom, screen, offsets)
  compiled into `direction` shots; `validate_safety` enforces framing/occlusion/readability.
- **Expressions/motions:** V2's eight expressions and its idle/look/surprise/walk/run/stop/turn
  vocabulary are reachable from blocking acting modes.
- **Props/interaction:** scene asset nodes can be placed at specific ground positions and used as
  camera `node` subjects (`object_reveal`), which the safety validator keeps readable. There is
  **no** rig capability for a character's hand to physically grip/clear an object — see §7.

The preview reuses this pipeline; it does **not** introduce a separate renderer.

## 3. The new environment — `snowy_mountain` (Frost Peak)

New module `src/reelforge/environments/snowy.py`, authored in the same trusted, code-only vector
style as `environments/artwork.py`/`polish.py` (pure `DrawPath` values, bounded fixed loops, a
stateless integer mixer for variation, deterministic, no raster/AI/native/random/cache). Palette:
deep navy shadow, cold cyan/blue snow light, desaturated distant peaks, and one controlled warm
amber reserved for the beacon. Registered assets (in `scenes/assets.py::ASSETS` + `recipe`):

| Asset id | Kind | Variants | Role |
|---|---|---|---|
| `frost_sky_01` | background | default | Cold twilight gradient, aurora veil, moon glow, stars |
| `frost_peaks_01` | background | far, mid | Layered snow peaks, lit caps, crevasse strokes, atmospheric haze |
| `frost_ridge_01` | environment | default | **Walkable** snow ridge/path: lit crust, blue drift ridges, sastrugi, packed path |
| `pine_snow_01` | asset | tall, short, cluster | Snow-laden conifers |
| `frost_rocks_01` | asset | cliff, drift | Exposed stone cliff / foreground snow bank |
| `beacon_01` | asset | buried, active | Emergency signal device; `buried` = dark/standby, `active` = warm lamp + beam + glow |
| `frost_foreground_01` | environment | default | Foreground snow-bank silhouette + blowing-snow streaks |

Each recipe stays within a declared path/op budget (verified by tests). Art direction drives the
warm-vs-cold balance and the beacon pulse; `breeze` drives blowing-snow drift. Because the assets
are registered, any future scene-0.1/storyboard can reuse them by `asset_id` with no renderer
changes.

## 4. The five-shot story

"Yellow Mellow is crossing a snowy ridge, finds a half-buried emergency beacon, investigates and
activates it as the weather turns." All five stills are the midpoint (frame 45) of a 90-frame
(3-second) storyboard segment, rendered through `direction_frame`. **Stills only — no 15s/60s
video was rendered.**

| Shot | Composition (behavior) | Story beat | Viewer reads |
|---|---|---|---|
| 1 Lonely Mountain | WIDE establishing | Small lone Mellow crosses the ridge; towering peaks; a faint buried beacon ahead | Place + danger; he notices something |
| 2 Something in the Snow | MEDIUM-CLOSE reaction | Closer; his **concerned** face is readable | The emotional beat — restrained, not arms-out |
| 3 The Buried Beacon | OBJECT reveal | The beacon fills the frame; Mellow low and close beside it | Investigation — a readable focal object |
| 4 The Mountain Answers | THREAT (follow, beacon flare) | Beacon flares **warm** with a beam; wind rises; Mellow breaks into a run | Escalation — warm active signal + blowing snow + flee, unlike shot 2 |
| 5 A Signal of Hope | MEDIUM hero / outcome | The beacon now burns **steadily** beside him; **determined** face | Outcome — the device changed state; resolve |

**Compositional variety (not just scale/X):** shot size (wide→close), subject position (lower-left,
centred, beside object, running, offset), foreground emphasis (snow bank, drift), landmark use
(peaks, pines, cliff, beacon), beacon state and placement (buried-right → object-centre →
active-left-flare → active-right-steady), lighting/mood (cold establishing → cold intimate →
cold reveal → warm threat → warm-in-cold resolution), and camera behavior (establishing, reaction,
object_reveal, follow). Expressions: curious → concerned → curious/determined → surprised →
determined.

## 5. Files changed

New:
- `src/reelforge/environments/snowy.py` — the Frost Peak vector recipes (reusable).
- `tools/phase9c_snowy_storyboard.py` — Stage-1 preview tool (authors the five storyboard-0.1
  segments and renders midpoint stills + sheets via `compile_storyboard` → `direction_frame`).
- `tests/test_snowy_mountain.py` — 18 focused tests (see §6).

Modified (small, additive, backward-compatible):
- `src/reelforge/scenes/assets.py` — registered the seven Frost Peak assets and their recipes;
  no existing asset or recipe changed.
- `src/reelforge/blocking/contract.py` — added `frost_ridge_01` to the walkable-ground allowlist
  and gave it a `level_field` corridor. Orchard (`orchard_ground_01`) and `generated_ground` keep
  byte-identical behavior; this only *adds* a new trusted level support plane.

No renderer, encoder, FFmpeg, rig, character, or unrelated phase was modified. The 60-second
production system is untouched.

## 6. Verification

Run in WSL Ubuntu 24.04, Python 3.12.3, pycairo 1.29.2, FFmpeg 6.1.1 (CPU-only Cairo).

- **Ruff:** `ruff check` and `ruff format --check` pass on all four changed/new Python files.
- **Targeted tests (persistent `--basetemp outputs/pytest-phase9c`):**
  - `test_scenes.py` + `test_blocking.py` → **177 passed**.
  - `test_storyboards.py` + `test_direction.py` + `test_environments.py` +
    `test_environment_polish.py` → **201 passed**.
  - new `test_snowy_mountain.py` → **18 passed** (asset registration, per-variant path/op budgets,
    buried-vs-active beacon differ, ridge is walkable support, a snowy storyboard compiles and
    renders a frame through the real pipeline, orchard ground still walkable).
- **Note on `/tmp`:** running the scene/blocking suites with pytest's default temp dir triggers
  the engine's `WORKSPACE_TMP` guard (3 cases). Re-running with `--basetemp` under the persistent
  `outputs/` workspace, as the engine's resource policy requires, all pass. This is the known
  development-host workspace policy, not a regression from these changes.
- **No GitHub CI was run; no CI approval is claimed.** The full historical suite was not run.
- These are development-host results; they do not certify target-VM deployment, and a passing
  storyboard does not prove final animation quality.

## 7. Known limitations (honest)

- **Hand-to-object contact is not representable.** The blocking→V2 acting adapter supports
  idle / look / surprise / walk / run / stop / turn, with the character drawn at a ground origin;
  there is no rig/contract path for the hand to grip, clear snow from, or press a control on a
  prop. Shot 3 therefore stages investigation by making the beacon the readable `object_reveal`
  subject and placing Mellow low and immediately beside it, facing it — a convincing spatial
  relationship, **not** a literal grab. Adding true hand/prop contact would require a new acting
  mode threaded through the storyboard→blocking→episode contracts (an interaction socket on the
  rig and a reach solve) — deliberately out of this preview's small scope. It is flagged here
  rather than faked.
- **Character on-screen size is capped.** Blocking requires the actor's composed scale in
  `0.35..0.75` and camera zoom `<=1.7`, so the largest readable framing here is a medium-close.
  Faces are readable in shots 2, 3 and 5; there is no extreme close-up.
- **"Threat" is a lighting/signal event**, not a physical hazard entity — the strongest honest
  option the engine supports (active beacon + blowing snow + flee), consistent with the brief.
- **Shot 5 "answer"** is the beacon's own visible state change (buried-dark → steadily-lit), not a
  separately rendered rescue light; the still and labels were worded to match what actually renders.
- A faint beacon-beam apex and aurora detail sit near the top edge of shot 4; a frame-bounds
  diagnostic confirmed no stray character/geometry — the actor is well within safe margins.

## 8. Unfinished animation requirements (for the full 15s)

If the storyboard is approved, the full reel would: assemble the five storyboard-0.1 segments into
one `production-0.1` (or a 5-segment `episode-0.1`), render through the audited
`render_production`/`render_episode` (memory admission, owned workspace, no-clobber publish, full
decode + PTS verification, cleanup), and add an `AudioPlan` if sound is wanted. Known
development-host workspace-restoration caveats from earlier phases still apply and a target-VM
gate remains separate. No video was rendered in this stage.

## 9. Deliverables

In `outputs/phase9c_snowy/`: `snowy_shot_01..05.png`, `snowy_mountain_contact_sheet.png`,
`snowy_mountain_labelled_storyboard.png`, `snowy_preview_report.json`, and this report. Packaged
as `ReelForge_Phase9C_SnowyMountain_Review.zip` (new/modified source, the preview tool, the new
test, five PNGs, two sheets, the report, and the preview JSON — no full repo, no video).
