# Phase 7B — integrated audio-synchronized reel workflow

Review candidate, 2026-11-02. **Acceptance remains blocked by persistent transaction-path
restoration after subsequent native work.** Four freshly generated jobs returned success
and passed full audiovisual verification at return, but their retired owned directories
later reappeared. Original per-job reports are preserved. This is not a clean reliability
approval or a target-VM deployment approval.

This report describes the replacement implementation recovered from approved Phase 7A
commit `763d8528a7526614703cec4ad1292d1b037bdfca`. Prior uncommitted Phase 7B implementation,
media and test evidence were unavailable after workspace rollback; none of the old measurements
or test outcomes are reused as evidence for this replacement. Two durable recovery checkpoints
were saved during this work. No GitHub push, CI, deployment, delegation or Phase 7C work ran.

## Implementation

`reel-0.1` embeds an actual accepted Storyboard and accepted AudioPlan. The four explicit
root fields are schema_version, title, storyboard, audio. Syntax, frame bounds, references,
trim, gain and overlap constraints use the accepted validators. At least one track is required.
No Story object is fabricated, no shot placeholders are introduced, and no audio timing is
inferred from prose. There is one 90-frame 30-FPS visual timeline and a 48 kHz sample clock:
frame F schedules sample F*1600; the effective audio interval is144000 samples per channel.

`tools/reel.py` exposes capabilities, schema, assets, validate, inspect, frame and render.
Planning reads registry metadata only and explicitly labels that limitation; it imports neither
Cairo nor native process tools. Render validates current WAV bytes, takes SHA-256-pinned
private copies, renders the visuals once via accepted direction evaluators and scene renderer,
then reuses mix_pcm, mux_audio, verify_audio and verify_video. H.264 is copied during muxing.
An additional narrow probe requires the exact stream configuration and rational PTS F/30.

One OwnedDirectory covers every native validation/render/mix/mux/decode stage. Plain internal
subdirectories are borrowed, never nested owned transactions. All native children are reaped
before owner cleanup. A candidate is fsynced and fully verified before atomic no-clobber
publication as reel.mp4. Primary, cleanup and resource failures remain separate. Already
published verified media is retained if cleanup fails, with overall failure status.

Three pre-existing implementation files changed, with existing defaults retained:

| File | Reason |
| --- | --- |
| src/reelforge/audio/registry.py | Native-free metadata resolution and owner-supplied validation staging |
| src/reelforge/media/encoder.py | Empty sibling staging borrowed from the outer owner; original standalone ownership/reaping retained |
| tools/scene.py | Shared cancellation Event and optional encoder staging; explicit deferred-cleanup report field |

No audio processing, video verification, resource policy, global transaction manager, rendering
backend, artwork, geometry, character, blocking, direction or storyboard compiler changed.
README and AGENTS document the new engineering workflow. `baseline_integrity.json` confirms
all 1,124 other accepted tracked files byte-identical, including all 22 accepted test files.
All 1,014 accepted tests remain present and unmodified. Production episode CLI stays not
render-ready; no contract meaning or dependency/native version pin changed.

## Delivered fresh proof media

| Reel | Manifest | Movie inside archive |
| --- | --- | --- |
| A — The Silent Signal | examples/reels/silent_signal.json | artifacts/phase7b/proofs/silent_signal/reel.mp4 |
| B — Abandoned Settlement | examples/reels/abandoned_settlement.json | artifacts/phase7b/proofs/abandoned_settlement/reel.mp4 |
| C — Shelter Entrance | examples/reels/shelter_entrance.json | artifacts/phase7b/proofs/shelter_entrance/reel.mp4 |
| Preplanned A repeat | Same A manifest | artifacts/phase7b/proofs/signal_repeat/reel.mp4 |

All three embedded storyboards are exactly the accepted Phase 7A examples. Their procedural
environments, authored objects, motion and cameras are reused. Every one of 270 freshly
rendered source frames matches the corresponding accepted Phase 7A source hash. All 90 source
and 90 decoded frames match between A and its independently preplanned repeat. Mixed PCM
and decoded AAC PCM hashes also match. Repeat execution was planned before the first job,
not triggered by a failed render. No native render was retried.

The first launcher invocation failed its parent-directory preflight: the harness had not
created artifacts/phase7b/proofs. No job transaction or native media work began. The four
errors are preserved in proof_preflight_failure.json. The launcher setup was corrected, then
the four native jobs above executed once each. A later collection-only invocation corrected
an empty review-directory setup conflict; it decoded the existing completed movies and did
not rerender them. Both collector logs are retained.

## Audio provenance and editorial limits

No spoken narration was provided. Reused operator-registered original diagnostic fixtures
are unchanged: diag_opening (narration-role tone, mono24 kHz), diag_fence (stereo44.1 kHz
transient), diag_suspense (mono48 kHz tone). Existing generation definitions are in the
accepted tools/generate_audio_fixtures.py. No new audio was synthesized; no TTS/AI voice,
AI image or AI video was used. Example titles explicitly say diagnostic audio. A narration-role
tone is not speech, a professional voice performance, convincing radio static or final sound design.

All narration-role cues run 0..36 at gain 0.2. A transient runs 45..57 at gain 0.2, matching discovery.
B transient runs 45..57 at gain 0.2 and its atmospheric diagnostic tone 54..90 at gain 0.12, trimmed
from source 18..54; it crosses the one cut at 60/sample 96000 continuously. Those two SFX overlap
54..57; their mixed-window onset measurements are not isolated individual onset estimates.
C transient runs 72..84 at gain 0.18, marking reaction, followed by six quiet frames.

The audiovisual review used full decodes, exact timestamp/hash checks, scheduled beats/cues,
reference and decoded waveforms, and actual decoded frames 0/30/45/60/72/89. The contact sheet
and audiovisual_timeline.png were visually inspected. The radio/reveal is readable in A,
Rowan's escape is apparent after B's cut, and C's approach-to-pause/reaction is readable. Source
motion and camera continuity are unchanged; the new audio follows their absolute clock.

The diagnostic transient is aligned to each selected event, but this does not establish
professional suspense or naturalistic sound. Narration-to-words/action matching cannot be
assessed because there are no spoken words. B's trimmed tone can start abruptly; A/C include
intentional quiet endings. Original fixture envelopes are unchanged. The three-second duration
compresses establishment, discovery and response; meaningful spoken narration and more nuanced
pacing require a longer future approved timeline. Sound cannot prove an unseen threat exists.
Independent listening/playback and artistic review remain required. No Stickocalypse parity,
lip synchronization, multi-character capability or finished sound-design library is claimed.

## Audiovisual verification

Each movie has exactly one H.264/yuv420p video stream,720x1280,30 FPS,90 fully decoded frames,
video start0 and exact3.000-second video interval; every rational video timestamp is F/30.
The other stream is AAC-LC48 kHz stereo, encoded with the existing128000-bit/s target. The
observed bitrates for A/B/C are73112/119385/74128 bits/s; a quiet signal does not necessarily
fill its target bitrate. Reports distinguish target from observed bitrate.

H.264 bitstream hashes and all decoded video frame hashes are unchanged through muxing.
Audio fully decodes with a gapless compensated sample clock. Reference PCM has exactly 144000
samples per channel; raw AAC decode has 144384, with 384 terminal samples accepted by the
existing one-packet padding policy. No tolerance was relaxed:1024 samples/21.333ms remains
the accepted audible-boundary tolerance. No clipping or unintended all-silent mix was detected.

| Measurement | A | B | C |
| --- | ---: | ---: | ---: |
| Narration-role tone onset error, samples | -2 | -2 | -2 |
| Narration-role tone onset error, ms | -0.041667 | -0.041667 | -0.041667 |
| Transient onset error, samples | 0 | 0 (overlapping window) | 0 |
| Background tone onset error | — | 0 samples (overlapping window) | — |
| Audible activity-boundary drift, samples | -156 | +2 | +1 |
| Audible activity-boundary drift, ms | -3.250000 | +0.041667 | +0.020833 |
| Mixed PCM peak | 0.07200047 | 0.07200047 | 0.07200047 |
| Mixed PCM RMS | 0.02661622 | 0.03063445 | 0.02655776 |
| Decoded AAC peak | 0.07345587 | 0.07345587 | 0.07345587 |

Lossy audible threshold boundaries are not identical to scheduled sample boundaries. The
measured drift is not zero; it remains within the unchanged accepted policy and is distinct
from accumulated PTS/sample-clock drift. B's two SFX window readings cannot identify each
separate onset. Full raw metrics, probe metadata and commands are in each original report.json.
Private paths in command records are diagnostic locations whose owned data was cleaned; they
are not paths the reviewer is expected to replay directly.

## Performance and resources — development host only

| Measurement | A | B | C |
| --- | ---: | ---: | ---: |
| Pipeline wall seconds (registry through cleanup) | 8.5353 | 7.2621 | 7.3603 |
| Outer monitored seconds (includes compilation) | 9.2113 | 7.9129 | 7.9302 |
| Pipeline FPS | 10.5444 | 12.3931 | 12.2278 |
| Render/encode FPS | 19.4956 | 25.9910 | 26.0658 |
| Sampled simultaneous tree peak MiB | 99.7070 | 98.7383 | 98.0156 |
| Sampled logical temporary bytes | 5,042,992 | 4,343,000 | 4,443,167 |

The four preplanned jobs took 36.2298 seconds under the review supervisor, whose sampled tree
peak was 125.5156 MiB including itself and child CLI processes. The repeat pipeline took 9.6891s,
with 99.4609 MiB peak and 5,043,010 logical temporary bytes. Timing scopes are different:
encoded FPS excludes audio/verification, pipeline FPS excludes compilation, outer observation
includes compilation and all native stages. Import/startup overhead is not wholly represented
by the CLI monitor. No performance extrapolation to the target cloud VM is justified.

Strict 256 MiB process budget, 64 MiB reserve, existing cgroup admission, telemetry, cancellation,
bounded logs/timeouts, geometry limits and storage policy remain intact. Maximum observed
scene complexity was 846 paths and 6224 operations, below accepted caps. Assets and bounded
PCM are streamed/staged in the persistent workspace, no full video-frame list or /tmp movie.
Logical storage samples overcount hard-linked inodes and can miss transient high-water marks.
Process-tree RSS is sampled, can miss peaks and double-count shared pages; these measurements
are not OS enforcement or target-VM deployment certification.

## Cleanup reliability — unresolved review blocker

All four per-job reports retain success=true, media_verified=true, published=true and
transaction_clean=true at return, with no primary/cleanup/resource error. Later native
work was followed by reappearance of every retired private root; cleanup_followup.json records
exact paths. These later observations are a separate failure of persistent cleanup reliability;
they must not be dismissed or turned into a clean overall acceptance. The final post-suite
observation records any still-visible roots without changing original job outcomes.

Fault-injection tests establish that detected cleanup failure produces failure, retains an
already verified published MP4, preserves primary errors, and never deletes/reacquires the
restored foreign path. Real borrowed-encoder failure/cancellation tests check process reaping.
The root cause of this host's later restoration is not established by these observations.
No global transaction rewrite, filesystem workaround, broad sweep or failure retry was attempted.
The user-requested final reliability criterion therefore remains unproven on this host.

## Validation and evidence

- Initial targeted run: 57 passed, 1 failed in 22.20s. The failure was a wrong accepted-video
  fixture directory in the new test, before native media work; it was corrected.
- Focused follow-up: 4 passed, 57 deselected in 5.95s. This covers the corrected real audio
  pipeline check and three additional publication/borrowed-encoder checks. Across the two
  runs all 61 new test cases were exercised successfully after that correction.
- Exactly one final complete local suite: **1,073 passed, 2 failed**, 161.50s pytest time
  (162.0556s driver wall time), 1,075 cases total. All 61 new integration tests passed;
  the 1,014 accepted cases yielded 1,012 passed and 2 failed, with no fixture errors.
  Failures: tests/test_audio.py::test_real_pcm_mix_aac_mux_repeat_and_clock and
  tests/test_transaction_cleanup.py::test_two_audio_jobs_persistently_clean_after_native_work.
  Both detect restored private audio directories after later native work. Original assertions
  remain intact; full_tests.txt and tests.xml preserve failures. No suite or failed render retry.
- Ruff lint/format checks pass. Wheel and sdist build succeeded without dependency changes.
- Fresh installed-wheel native-free smoke check and compatibility evidence are recorded
  separately. Original12-second audio/video re-verification passed, with cleanup at return.
- Historical 594 visual checkpoint evidence is reused explicitly, not represented as a new
 594-frame render. Its original evidence hash and all accepted file identities are retained.

The archive includes three manifests/movies, repeat movie, complete compiled plans,90-frame
inspection/cue schedules per study, full FFprobe/decode/hash evidence, onset/drift/peak/RMS
reports, waveform/beat/cut diagram, decoded contact sheets, memory/storage/timing observations,
original failure logs, cleanup follow-up, exact test transcript/JUnit, build/smoke evidence,
compatibility record and SHA-256 artifact manifest. Complete commit and archive integrity
identities are provided alongside the exported ZIP. Independent engineering and artistic
review, normal publishing CI and target deployment validation remain separate future gates.
