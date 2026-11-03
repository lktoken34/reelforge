# Phase 9B.1 — Scene Repetition Correction

Scope: artistic/storyboard correction only. The production engine (production-0.1 contract,
chunked rendering, FFmpeg stream-copy assembly, resource safeguards, verification) is unchanged.
No engine source was edited. Same 20 segments, 1,800 frames, 60.000 s.

## What was wrong

The Phase 9B manifest embedded the *same* `tree_path` orchard scene in all 20 segments and cycled
four beat kits, so every 3-second segment was the same composition (same path, sunset, trees,
fence). Only camera zoom and pose varied — not enough for visual storytelling.

## What changed (composition only)

A new author tool, `tools/build_yellow_mellow_production_v2.py`, builds four **distinct scene
palettes**, one per act, from the existing registered catalog (`dusk_sky_01`, `distant_hills_01`,
`orchard_ground_01`, `barn_01`, `orchard_tree_01` in its four variants, `fence_01`,
`foreground_boughs_01`). Yellow Mellow still binds to the single supporting ground
`orchard_ground_01`; nothing about the rig, scale band or camera semantics changed.

| Act | Location feel | Barn | Hills | Foreground | Light (warmth/atmos/breeze) | Camera |
|---|---|---|---|---|---|---|
| 1 Discovery | open orchard, airy | — | yes | left tree | 0.80 / 0.62 / 0.35 (warm dusk) | drift/approach/locked |
| 2 Investigation | by the old barn, enclosed | right, large | no | both sides | 0.52 / 0.80 / 0.25 (cool, hazy) | approach |
| 3 Escape | bare clearing, open | — | yes | none | 0.40 / 0.55 / 0.90 (cool twilight, windy) | drift/locked |
| 4 Resolution | sheltered corner, settled | left | no | right tree | 0.72 / 0.68 / 0.20 (warm, calm) | drift/locked |

Within each act the five segments vary camera mode, tree variant/positions, shot scale
(establishing/medium/closer), start side and expressions, so no more than two consecutive
segments share a composition. Act 2 and Act 4 both use the barn but on **opposite sides** with
different light and framing, so they do not read as the same shot.

Differences are driven by: barn landmark present/absent and placed left vs right; hills on/off
(skyline and depth); foreground framing trees (both/left/right/none, varied scale); tree
count/variant/position/rotation/scale; fence position or removal; ground placement/scale; scene
camera mode; and per-segment art_direction (lighting, haze, motion). All validated under scene-0.1.

## Preview-first process

A cheap 20-panel storyboard preview (`outputs/preview_20panel.png`, one engine-generated still at
each segment midpoint, no encoding) was produced and inspected **before** the full render. It
confirmed the four acts look visibly different; only then was one full 60-second render performed.

## Final render — technical acceptance preserved

Independent ffprobe + full framehash decode of `outputs/yellow_mellow_60s/reel.mp4`:

| Check | Result |
|---|---|
| Decoded frames | 1800 |
| Unique decoded frames | 1800 |
| Duration | 60.000000 s |
| Resolution / fps | 720×1280 / 30-1 |
| Codec / pixel format | H.264 / yuv420p / avc1 |
| Video / audio streams | 1 / 0 |
| PTS | exact F/30, continuous |
| Chunk assembly | assembled hashes == concatenated chunks (no dup/drop/reorder); join at frame 900 |
| File size | 10,919,012 bytes |
| Per-chunk peak RSS | 138 MB, 142 MB (within 256+64 MiB) |

Evidence: `outputs/evidence/YellowMellow_60s_Contact_Sheet.png` (17 frames decoded from the FINAL
MP4 across all four acts, chunk join highlighted) and `outputs/final_verification.json`.

## Honest limitations

- The registered catalog has one character-supporting ground (orchard), so all acts are variations
  of the orchard rather than genuinely separate biomes (woodland/settlement/shelter exist only as
  non-character environment/composition worlds, incompatible with the Yellow Mellow blocking path).
  Variety is achieved through landmark, depth, lighting and framing changes, which the preview and
  final contact sheet show is sufficient to make the four acts distinct.
- The Act 2 barn reads large/close; it is within the registered asset envelope and intentionally a
  strong landmark.
- Artistic quality is my own inspection; it needs independent visual review.
