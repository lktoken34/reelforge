# Phase 4B review candidate — frame-grid audio

**ENGINEERING GATE BLOCKED: intermittent persistent-transaction cleanup regression.**
This archive contains the implementation, audiovisual proofs and the failing regression.
It is a complete committed repository export, not a claim that Phase 4B is accepted.
Approved parent: `fd14320355f442f5fe9c59043b19a6009bd0f482`.
Local branch: `phase4b-audio-sync`. No push, deployment or later milestone was attempted.

## Implemented behavior

`story-0.2` adds explicit registered narration/effect cues to the existing frame timeline;
`story-0.1` serialization, presets and video-only behavior are preserved. See AUDIO_SYNC.md
for the exact contract, bounds, operator WAV registration and two-command weak-agent workflow.
The example selects original diagnostic sounds rather than spoken narration. PCM16 WAV only,
fixed IDs/roles, pinned hashes/metadata and bounded full decoding keep this deliberately small.
No executable/filter fragments or media paths are accepted from story JSON.

The accepted silent renderer produces the same three shots. Supervised sequential stages create
bounded disk PCM, stream-copy H.264 into AAC MP4, verify all frames/timestamps and decoded audio,
then publish with no-clobber atomic hard linking. No full video or long PCM list is held in RAM.
Existing media, rendering, character/environment, resource-policy and production CLI modules,
dependencies and lockfile are unchanged. The production episode CLI remains not render-ready.

## Blocking finding and honest scope

An earlier complete regression run reports **473 passed, 1 failed (474 cases)**. The latest
exclusive full-suite rerun reports **465 passed, 9 fixture-setup errors**; the original 412 cases
pass in both. There are 62 added cases. The latest errors share one failure in the unchanged
silent-template renderer: unexpected content in its private encoder directory. See
`test_results_exclusive.txt`. This broadens the cleanup concern beyond the audio transaction;
it does not establish the cause or justify changing the accepted renderer. The retained failure is
`tests/test_audio.py::test_real_pcm_mix_aac_mux_repeat_and_clock` at its final check that both
completed jobs have no `.reelforge-audio-*` directories. Immediate transaction exit checks pass,
but a prior completed job's temporary files have reappeared after later native work. This has
been observed with independent CLI processes as well as repeated work in one process. No broad
previous-job sweep, skipped assertion or changed resource threshold conceals it.

The isolated rerun passes, as do the two final full-story renders' post-repeat/post-visualization
cleanup checks (`cleanup_report.json`). Full-suite runs nevertheless encounter cleanup failures.
This is an intermittent observation, not an established attribution to the execution host or
FFmpeg. Its root cause is unresolved. Immediate `transaction_clean` fields and a passing latest
artifact cleanup check do not establish the persistence guarantee. Review all test logs together.
Cancellation, missing/invalid assets, malformed timing, native failure, low disk, late resource
cancellation, competing output and interruption tests pass; they do not override this blocker.
The candidate is unsuitable for approval as a persistent batch/production workflow until repaired.

## Audiovisual evidence

`artifacts/phase4b/story.mp4` contains exactly 360 decoded video frames at 30 FPS,
720 × 1280 H.264/yuv420p, and one AAC-LC stereo 48 kHz audio stream. Declared duration is
12 seconds. The silent compatibility reference remains `artifacts/phase4a/story.mp4`, unchanged.
All 360 source and decoded video frames match that approved reference; all presentation times
remain frame/30. H.264 packet data is unchanged by audio muxing. Cuts remain at 120 and 240.

| Selection | Scheduled frame / sample | Measured AAC onset error |
| --- | --- | --- |
| diag_opening (narration-role test tone) | 9 / 14400 | 0 samples |
| diag_fence | 120 / 192000 | −1 sample (−0.020833 ms) |
| diag_suspense | 240 / 384000 | 0 samples |

Activity onset includes each source's own envelope, rather than assuming audible onset at the
first scheduled sample. Global first/last audible error and measured drift are zero samples.
Reference PCM is exactly 576000 samples/channel. AAC decode returns 576512: the final 512 samples
(10.667 ms) are codec tail outside the logical declared interval. The audio clock begins at zero
and is gapless. Source overhang is trimmed and uncovered intervals padded to the video length.
AAC-LC tolerance is 1024 samples (21.333 ms), below one video frame; packet/sample perfection
across codec builds is not promised. Reference-versus-decoded SNR is 42.7393 dB; clipping checks pass.

Two independent CLI renders on FFmpeg 6.1.1 produced identical reference PCM hashes, decoded PCM
hashes, all source/video frame hashes and cue measurements. This does not require AAC MP4 byte
identity across FFmpeg builds. The three WAV fixtures were independently regenerated byte-for-byte.
`audio_timeline.png`/`.svg` show planned frame boundaries and reference/decoded peak envelopes;
50 ms visualization bins are explanatory, while onset checks use individual samples.
The waveform was visually inspected. Visual continuity is unchanged from the accepted silent reel:
establishing orchard, Rowan's reaction, barn reveal. Tones demonstrate synchronization, not a
finished survival-story soundtrack or Stickocalypse-level storytelling.

## Measured complete workflow (development host)

| Metric | First full render | Repeat |
| --- | ---: | ---: |
| Complete wall time, including validation and verification | 51.714 s | 54.507 s |
| Silent video stage, including its verification | 41.565 s | 42.704 s |
| Video render/encode | 35.460 s | 36.420 s |
| Encoded video FPS | 10.152 | 9.885 |
| PCM mix | 0.266 s | 0.258 s |
| Audio mux | 0.287 s | 0.369 s |
| Final audiovisual verification | 8.693 s | 10.445 s |
| Parent CPU seconds | 40.365 | 42.185 |
| Child user + system CPU seconds | 24.145 | 28.476 |
| Sampled simultaneous process-tree peak RSS | 100.066 MiB | 100.262 MiB |
| Sampled temporary storage peak | 17127730 bytes | 17127737 bytes |

The strict 256 MiB job budget and 64 MiB reserve remain unchanged. All child stages are monitored;
OOM telemetry was continuous, with no detected OOM delta and no fallback. The 77,847,376-byte
preflight temporary estimate is conservative; stage samples are not a continuous filesystem
high-water mark. RSS sampling can miss short native spikes and is not target-VM certification.
CPU time can exceed wall time because children and parent execute concurrently. Both renders
finish with zero live Cairo surfaces. Detailed native versions, commands, all timestamps/hashes,
resource samples and stage sizes are in report.json/repeat_report.json. Private command paths
are redacted to `<audio_transaction>`; these are diagnostic templates, not agent commands.

## Validation and next action

Ruff lint/format and wheel/sdist build pass. The installed wheel validates both versions from
outside the checkout without Cairo; capabilities still report `render_available: false`.
The earlier complete failure log, latest exclusive-suite error log, isolated passing log and
partial/interrupted rerun log are retained. The partial log is not counted as a completed run.
No original tests or cleanup guarantees were weakened.

First reproduce and repair the retained cleanup failure on ordinary Ubuntu and this host,
then rerun all tests and two complete audiovisual jobs with post-job persistence checks.
Only after that should independent review consider approval or a later milestone. User-supplied
spoken WAV registration is supported but real speech, dense overlapping mixes, broader codecs,
audio aesthetics, cross-build AAC equivalence and target deployment have not been certified.
No TTS, cloning, lip-sync, subtitles, music generation or production episode compiler was added.
