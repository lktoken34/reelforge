# Phase 9C — Frost Peak visual correction

Branch `phase9c-snowy-mountain` in `D:\NikhilV\reelforge\outputs\reelforge-9b`, on top of the
approved baseline `19be6e4c2d904482a0ffd1211d55a9da0c94f2f7` plus the earlier uncommitted Phase 9C
work. Nothing is committed or pushed. No video was rendered.

All five stills still go through `compile_storyboard` → `direction_frame` → `CairoRenderer`, the
same per-frame call the episode renderer makes. Each still is one key frame chosen at the shot's
story beat (frames 45, 80, 82, 76 and 80), rather than the fixed midpoint used before.

## What changed, per requirement

**1. Shot 2 close-up.** I added a `close_up` camera behavior. It is the only behavior allowed to
zoom past 1.7, up to 5.0. It must not use `full` framing, and a close-up on the actor must track
the actor. The other six behaviors keep the original 0.9–1.7 bound. The blocking scale limit
(0.35–0.75) and every per-frame safety check are unchanged; shot 2 passes the same margin,
pan-speed and zoom-speed checks as every other shot. Shot 2 now runs at zoom 4.6–4.8, and the head
spans roughly a quarter of the frame width. A test confirms that `reaction` at the same zoom is
still rejected.

**2. Foreground slab and pale bottom strip.** The cause was layering geometry, not cropping:
- The foreground node was placed at y=560, but the asset's anchor is 640. That shifted an opaque
  navy bank 80 units up, and the depth-1.4 parallax enlarged it further.
- The bank ended at y=680, which exposed the flat base of the ridge underneath as the pale strip.

The node now sits at its anchor. The opaque bank is replaced by two shaded corner drifts and a
translucent bottom gradient, and all of it extends past the frame edge. The ridge now reaches
further down, with a deeper colour gradient, downslope drift crests and a footprint trail. I did
not crop anything after rendering.

**3. Buried beacon.** I redesigned the device:
- a canted steel housing with a hazard-orange band;
- a recessed control panel with one large red button, with its asset-local position published as
  `BEACON_SOCKET`;
- a lamp dome and antenna;
- a snow drift over its lower body and dome, with the panel left clear. The drift's base fades into
  the ground, so it no longer reads as a flat block.

In the `active` variant the snow is blown off, the lamp and beam are lit, and the button glows.

**4. Interaction.** I implemented this end to end, with one limitation (below):
- New V2 motion preset `activate`. Mellow turns three-quarter, crouches, leans and looks down, then
  reaches and presses. A bounded, deterministic two-angle arm solve places the pointing fingertip
  on a fixed target 34 units forward and 34 units up, within the rig's joint limits. The solve
  reports its residual, and the preset rejects any target it can't reach within 0.5 units.
- `activate` is a new acting mode in the storyboard beats (react/hold), in blocking and in the V2
  episode adapter. Blocking accepts it only for characters whose registry lists `activate`, so
  Rowan manifests are rejected rather than silently idling. It also requires at least 18 frames.
- In shot 3 the beacon is sized and placed so that its button sits on that target, in the same
  depth layer as Mellow, so there is no parallax between hand and button.
- The contact is measured with a new `fingertip_world()`, which uses the exact placement chain the
  renderer uses. Over the press hold (frames 78–89) the fingertip is at most **0.33 output pixels**
  from the button centre. At frame 60 it is more than 5 world units away, so the hand travels to
  the button rather than starting on it. Both facts are asserted in tests.

**5. Continuity.**
- Shot 3 ends on the press.
- In shot 4 the beacon is lit and blowing snow intensifies (a new `storm` variant of the
  foreground). The lit beacon looms in the lower-left foreground, and Mellow is jolted two steps
  back, stops, and reacts with surprise. Nobody runs off.
- In shot 5 the beacon burns steadily behind him and a new `answer_light_01` asset pulses on the
  far peaks. His expression moves from concern to happy.

## Remaining limitations and blockers

- **The rig does not know about the prop.** `activate` reaches one registered fixed target, and
  the storyboard places the beacon to meet it. The contact is real and measured, but only because
  it was staged. Reaching an arbitrary prop would need: a beat-level `target` node id; a
  per-asset socket registry (the beacon's socket is the first entry); and blocking that converts
  the socket's offset from the actor into the preset's `reach`/`height` and checks it against the
  reach envelope at compile time. I didn't build this, because it is a contract design decision.
- **The beacon can't change state within a shot.** scene-0.1 variants are static per segment, so
  the beacon goes from buried to active across the cut between shots 3 and 4. A light-up on the
  press frame would need time-varying prop states.
- **Shot 4's recoil is a short forward walk.** Storyboard beats can only travel in the facing
  direction and have no turn action. So "jolted back" is two steps away from the beacon followed by
  a stop, and he faces away from it while reacting.
- **Shot 3 skips the actor margin check.** It uses `offscreen` framing because Mellow walks in from
  the left edge of the close object shot. The beacon's readability check still applies.
- **Cost and fixed pose.** The arm solve costs about 0.4 s, run twice, each time an activate drawer
  is built; this is bounded and needs no cache. `activate` always uses the three-quarter facing.

## Verification

- Ruff check and format pass on all 14 modified or new Python files.
- Focused tests, run with `--basetemp` under `outputs/`:
  - snowy + Yellow Mellow V2 + blocking + direction + storyboards: **281 passed**;
  - scenes + environments + environment polish: **160 passed**.
- The new tests in `tests/test_snowy_mountain.py` cover:
  - the `activate` residual, and rejection of an unreachable target and a too-short duration;
  - measured fingertip-to-button contact;
  - all five corrected shots passing production safety;
  - the close-up zoom being scoped to `close_up`;
  - the per-character `activate` gate.
- I did not run the full historical suite or CI. These stills are not evidence of final animation
  quality.

## Files

- **New:** `src/reelforge/environments/snowy.py`, `tools/phase9c_snowy_storyboard.py`,
  `tests/test_snowy_mountain.py`.
- **Modified:** `scenes/assets.py`; `blocking/{contract,sampling,schema}.py`;
  `characters/yellow_mellow_v2/{motions,episode}.py`; `direction/{contract,schema}.py`;
  `storyboards/{compiler,patterns,schema}.py`.

The JSON schemas only state the 5.0 ceiling. The per-behavior zoom limit is enforced by the
compilers.
