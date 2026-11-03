# Phase 9B — 60-Second Vertical Reel MVP: engineering report

Date: 2026-11-03. Host: WSL2 Ubuntu 24.04, Python 3.12, CPU-only, pycairo 1.29.2, FFmpeg/libx264.
Development-host result only. **Not** a target-VM or deployment certification. Technical decoding
success does not prove artistic quality.

## Result

A single, continuous, fully decodable 60.000-second silent Yellow Mellow reel is produced by one
documented command from a validated JSON production manifest, with no engine-source edits required
to author another story. The reel is assembled from two sequentially-rendered 30-second episode
chunks joined by FFmpeg stream-copy concat and independently verified end to end.

**Final video:** `outputs/yellow_mellow_60s/reel.mp4` (delivered as `YellowMellow_60s_Final.mp4`).

| Check | Result |
|---|---|
| Decoded frames | 1800 (full rgb24 framehash decode) |
| Duration | 60.000000 s |
| Resolution | 720×1280 |
| Frame rate | 30/1 (constant) |
| Codec / pixel format | H.264 / yuv420p, tag avc1 |
| Video streams | 1 |
| Audio streams | 0 |
| PTS | exact F/30, monotonic and continuous across all 1800 frames |
| Chunk assembly | assembled decoded hashes byte-identical to the two chunks concatenated (no dropped/duplicated/reordered frames) |
| Unique decoded frames | 1780 (20 repeats are intentional held/idle frames, not assembly artifacts) |
| MP4 layout | ftyp/moov before mdat (faststart) |
| File size | 9,900,287 bytes |
| Determinism | re-render produced a byte-identical reel |

## The one command

```
python tools/production.py render examples/productions/yellow_mellow_60s.json \
    --output-dir outputs/yellow_mellow_60s
```

Supporting commands: `capabilities`, `schema`, `validate MANIFEST`, `inspect MANIFEST`.
The 20-segment manifest is authored (no engine edits) by `tools/build_yellow_mellow_production.py`.

## Architecture — smallest safe extension

The existing episode system renders one continuous silent MP4 for up to ten 90-frame segments
(≤900 frames / 30 s) through the audited `render_episode` → `render_av` owned transaction. The
encoder already accepts up to 1800 frames and uses `bframes=0:ref=1` (every frame is I/P, no
B-frames), which makes its output concat-safe. The 60-second production reuses this exactly:

- **New `production-0.1` contract** (`src/reelforge/productions/contract.py`): an ordered list of
  2..20 ninety-frame segments (180..1800 frames; 6..60 s), silent only (`audio: null`). It splits
  the segments into contiguous chunks of at most 10 and compiles each as a silent `episode-0.2`,
  reusing the full accepted storyboard/blocking/direction/scene validation. Segment-error pointers
  are remapped from chunk-local to production-level indices.
- **New `production-0.1` workflow** (`src/reelforge/productions/workflow.py`): renders each chunk
  sequentially through the unchanged `render_episode` into its own owned output dir, so each chunk
  keeps the engine's memory admission, owned temp workspace, no-clobber publish, full decode
  verification and cleanup. No uncompressed frames are held across chunks. It then:
  1. probes each chunk MP4 and asserts identical codec parameters (H.264/yuv420p, 720×1280, 30/1,
     same time base and profile) — incompatible chunks are rejected, never silently joined;
  2. concatenates with the FFmpeg **concat demuxer `-c copy`** (no re-encode);
  3. verifies the assembled reel: metadata, full per-frame framehash decode, exact F/30 PTS, and a
     byte-exact assembly check (assembled hashes == concatenated chunk hashes).
- **New CLI** `tools/production.py` and advisory `src/reelforge/productions/schema.py`.

Nothing in the renderer, character rig, animation evaluator, FFmpeg encoder, resource monitor,
`render_av`, or the episode/reel/blocking/direction/scene contracts was modified. `episode-0.1`,
`episode-0.2` and every historical contract keep their exact bounds and meaning — the new
production-level bounds are separate and explicitly validated.

### Why chunked concat (the preferred approach)

Two 10-segment episode chunks are the natural unit: each stays within the audited ≤900-frame
`render_av` path and its 256+64 MiB budget, so no engine limit is weakened. The chunks share one
encoder command, so stream-copy concat is valid and introduces no re-encode and no quality loss.
The chunk boundary is placed exactly on an editorial cut (frame 900), never mid-segment.

## The story — "Yellow Mellow — The Last Signal"

Twenty 90-frame segments, four acts, on the registered orchard environment with the integrated
Yellow Mellow V2 rig/artwork/expressions/motions. Each segment has a distinct purpose; it is not a
looped walk cycle nor the Phase 9A story repeated four times.

- **Act 1 — Discovery (0–15 s, seg 1–5):** dusk arrival, a first glint, slowing, looking around,
  growing curiosity. Expressions neutral → curious → concerned.
- **Act 2 — Investigation (15–30 s, seg 6–10):** cautious step, closer look, reaching the spot,
  the unexpected, taking it in. curious/excited → surprised.
- **Act 3 — Escape (30–45 s, seg 11–15):** sensing danger, the decision, the run, pause and check,
  a safe way. concerned/determined, with the run (run_to) in a follow shot.
- **Act 4 — Resolution (45–60 s, seg 16–20):** reaching safety, catching breath, the meaning, a
  small smile, a confident closing pose. determined → happy/tired → happy.

Supported movements only: idle, walk_to, run_to, stop_at, look_around, react. Facial expressions
from the registered V2 set (neutral, curious, concerned, surprised, excited, determined, happy,
tired). Camera: establishing (zoom ≤1.15), medium push-ins (~1.30–1.40) and a follow shot for the
run; multiple distinct compositions with per-act reframes and deliberate holds.

### Readability improvement over Phase 9A

Phase 9A framed the character small. Here the character is kept more readable by using higher zoom
through the existing validated storyboard `zoom` range (medium ~1.30–1.40 vs 9A's ~1.08–1.26), with
screen positions that keep him centred, and by respecting the engine's framing-safety checks (which
rejected over-tight zooms during authoring). The rig, scale band and camera semantics were not
changed. Honest limitation: he is more readable than 9A but still modest in frame; a substantially
larger figure would require re-tuned blocking magnitudes beyond this milestone's scope.

### Documented compromises

- The "mysterious signal", "shadow/danger" and "signal's meaning" are conveyed through camera
  framing, expression and the character's reactions toward registered point/node subjects (e.g. the
  orchard tree), not through new prop assets or VFX — the registered library has no signal/creature
  prop. This is a truthful visual alternative, not a misleading substitution.
- The faint tree-line silhouette near the top of some frames is the registered `distant_hills_01`
  background asset, present in Rowan renders too; it is not character geometry.

## Resource and transaction safety

- Each chunk ran through the unchanged `render_av` owned transaction: memory admission, owned temp
  workspace, no-clobber publish, full decode verification, cleanup — all preserved. Both chunk
  transactions reported `transaction_clean=True`.
- Per-chunk estimated simultaneous process-tree peak RSS: 137.3 MB and 141.5 MB — within the
  256 MiB budget + 64 MiB reserve. `/usr/bin/time` peak maximum resident set for the whole job:
  ~90 MB parent. No safeguard was disabled to pass.
- No uncompressed frames accumulate across chunks: chunk 2 renders only after chunk 1 is published
  and its surfaces released (the episode workflow asserts no surface leak per chunk).
- The production workflow adds its own no-clobber output dir, a compatibility gate before concat,
  bounded FFmpeg subprocess output and timeouts, and cancellation checks between chunks.
- Render + encode + assembly + full verification wall time: ~9m38s (render/encode ~8m33s).

## Tests

`tests/test_production.py` (15 focused tests, all passing): 60-second manifest compiles; 20
segments split into two ordered 900-frame chunks with preserved order; editorial cuts at every 90
frames and the chunk join coincides with an editorial cut; frame total = segments×90; `audio` must
be null; too-few/too-many segments rejected; wrong schema version rejected; duplicate IDs rejected;
segment-error pointer remapped to the production index; bounds constants; episode-0.1/0.2 unchanged
(still require/allow audio, still capped at 10 segments); each chunk is a valid silent episode;
chunk compatibility gate accepts matching params and rejects differing codec/size/fps; loader
round-trip. Directly affected regressions re-run green: `test_episodes.py` (25) and
`test_yellow_mellow_integration.py`. Ruff lint and format pass on all new files. The full historical
suite was not re-run (instructed to use focused tests; the full CI gate is for later publication).

## Visual evidence

- `outputs/evidence/YellowMellow_60s_Contact_Sheet.png` — 17 frames decoded from the FINAL
  assembled reel across all four acts, with the chunk join (F899→F900→F901) highlighted.
- `outputs/evidence/frames/` — the individual decoded PNGs, including the boundary frames.
- Inspection confirms: Yellow Mellow present and grounded every frame; distinct poses (walk,
  arms-out reactions, idle holds); per-act camera reframes; and a seamless chunk join (no black
  frame, no geometry tear, continuous position/framing across frame 900).

## Technical evidence files

- `outputs/yellow_mellow_60s/report.json` — the production run report (success, per-chunk reports,
  verification, PTS, assembly match).
- `outputs/final_verification.json` — independent re-verification of the assembled reel.
- `outputs/yellow_mellow_60s/chunks/chunk_0{0,1}/report.json` — per-chunk episode reports.

## Git and publication

Worked on a fresh clone of the approved branch `mvp-yellow-mellow-integration` at
`fb8716ea6d9341e39d4abdc18004b179871428d1`, on a local development branch `phase9b-60second-reel`.
No push, no merge, no `main` change, no GitHub CI triggered. The approved Phase 9A baseline is
unchanged. Local commits and the export ZIP are provided for independent review.

## Remaining blockers / honest notes

- None blocking acceptance. The only issue found during development was a verification output-buffer
  limit too small for 1800 framehash lines; it was fixed (one constant) and the full run then wrote
  a complete report. The reel content itself was correct before and after the fix (byte-identical).
- Character on-screen size is improved but still modest (see above).
- Artistic quality is my own frame inspection only; it needs independent review.
