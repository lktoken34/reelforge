# Phase 9C — Final 15-second render

One complete animated reel of the approved Frost Peak story. No new features, no visual
corrections, no video variations. Branch `phase9c-snowy-mountain` in
`D:\NikhilV\reelforge\outputs\reelforge-9b`, on the approved baseline
`19be6e4c2d904482a0ffd1211d55a9da0c94f2f7` plus the existing Phase 9C local work (preserved,
not reset). Nothing committed or pushed.

## Deliverable video

| Property | Value |
|---|---|
| File | `outputs/YellowMellow_FrostPeak_15s_Final.mp4` |
| Frames | 450 (decoded 450) |
| Duration | 15.000 s |
| Resolution | 720 × 1280 (9:16) |
| Frame rate | 30/1 FPS |
| Codec / pixel format | H.264 (High) / yuv420p |
| Audio | none (zero audio streams) |
| Size | 3,131,961 bytes (~2.99 MiB) |
| Editorial cuts | frames 90, 180, 270, 360 |

## How it was rendered

The five corrected Phase 9C storyboards (from `tools/phase9c_snowy_storyboard.py`, the
visually-reviewed versions) were assembled unchanged into one silent `episode-0.2` and rendered
through the existing audited episode workflow — no new renderer, no slideshow of PNGs:

`tools/phase9c_final_render.py` → `episodes.contract.compile_episode` →
`episodes.workflow.render_episode` → the shared bounded `reels.workflow.render_av`.

`render_av` streams all 450 frames through one continuous `FFmpegEncoder`, drawing each frame with
`direction.sampling.direction_frame(segment.storyboard.direction, local_frame)` — the identical
per-frame call the stills used — on a single reused Cairo surface. Frames are never buffered as a
list or written to disk as PNGs. Segment boundaries at 90/180/270/360 are explicit editorial cuts
(independent storyboards); no seamless cross-cut continuity is claimed.

The job ran inside the normal owned transaction: memory admission preflight, a private owned
workspace, full decode + exact rational-PTS verification, no-clobber publish-by-link, and cleanup.
The workflow reported `success=true, published=true, media_verified=true, transaction_clean=true`
with `error/cleanup_error/resource_error = null`. `outputs/frost_peak_final/report.json` is the
full workflow report; the final MP4 is a copy of the published `reel.mp4`.

## Story as rendered (sampled frames in `frost_peak_sampled_frames.png`)

- **Shot 1 (0–89):** Mellow walks the snowy ridge (real walk cycle — feet/legs change across
  f30/f75) toward the half-buried beacon and reacts.
- **Shot 2 (90–179):** corrected close-up; his face is large and readable and the expression moves
  from neutral (f90) to concern (f170), with a shifting stance rather than a frozen pose.
- **Shot 3 (180–269):** he reaches the beacon, crouches (f215) and presses the red button
  (f262); the measured fingertip/button contact holds (≤0.33 output px over the press).
- **Shot 4 (270–359):** immediately after the press the beacon is active (amber lamp + beam),
  wind/snow intensify; he recoils two steps (f300) and stares (f345). Not a long escape.
- **Shot 5 (360–449):** the beacon keeps transmitting, the distant answering light appears on the
  peaks (visible from f360), and he settles into a readable closing composition with a relieved
  expression.

## Verification (independent pass, `frost_peak_video_verification.json`)

`tools/verify_frost_peak.py` ran ffprobe/ffmpeg against the one finished MP4 and sampled 15
decoded frames around the key events. All checks pass:

- 450 frames (header and decoded), 15.000 s, 720×1280, 30/1 fps, one H.264/yuv420p stream;
- zero audio streams; `ffmpeg -xerror` full decode with no errors;
- continuous timestamps at exactly 1/30 s; cuts present at 90/180/270/360;
- no near-black sampled frames; all 15 sampled frames are distinct (the picture genuinely changes).

This is in addition to the workflow's own internal `verify_video` (per-frame rgb24 framehash) and
`stream_check` (exact rational PTS), which also passed inside the transaction.

## Resource use (development host; from the workflow report)

- Estimated simultaneous process-tree peak RSS ≈ 130.97 MiB, within the 256 MiB job budget
  (64 MiB reserve); strict memory policy, continuous OOM telemetry, zero OOM events.
- Render/workflow throughput ≈ 10.79 fps; total wall ≈ 41.7 s for the full 450-frame job.
- Max 465 draw paths / 1,856 path-ops per frame. Silent MP4 well under the 32 MiB stage limit.
- No safety threshold was lowered. These are development-host figures and do not certify a target
  VM.

## Files changed

- New (tools only, no engine source changed in this task):
  `tools/phase9c_final_render.py`, `tools/verify_frost_peak.py`.
- The Phase 9C engine/source changes it relies on were made earlier and are unchanged here.

## Known issues / honest limitations

- Editorial cuts are hard cuts; there is intentionally no seamless motion across shots.
- The beacon's buried→active change happens at the 3→4 cut (scene props are static within a shot),
  staged to read as the consequence of the press.
- Shot 4's "jolted back" is two steps away from the beacon (storyboard travel is in the facing
  direction only), so he faces away from the device while reacting.
- The answering light is a distant static asset, not a separately animated rescue craft.
- Development-host render only; no CI, no GitHub publish, no target-VM certification.
