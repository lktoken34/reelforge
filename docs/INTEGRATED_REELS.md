# Integrated reels — reel-0.1

Experimental engineering workflow: one real Storyboard plus the accepted AudioPlan,
compiled and rendered on one absolute 90-frame timeline. The installed production episode
CLI is unchanged and remains not render-ready. No script interpreter, TTS, automatic sound
selection, longer storyboard timeline or deployment is added.

## Authoring

Run from the checkout with its Python 3.12 environment:

```bash
python tools/reel.py capabilities
python tools/reel.py schema
python tools/reel.py assets
python tools/reel.py validate examples/reels/silent_signal.json
python tools/reel.py inspect examples/reels/silent_signal.json
python tools/reel.py frame examples/reels/abandoned_settlement.json --frame 60
python tools/reel.py render examples/reels/silent_signal.json --output-dir outputs/my-new-reel
```

`--registry-root DIR` is a trusted operator option before the command. It never appears in
untrusted reel JSON. Register operator-supplied PCM16 WAVs with the existing register_audio.py
workflow; discover exact usage with its `--help`. Agents only choose registered IDs.

The manifest contains exactly `schema_version`, `title`, `storyboard`, `audio`. Version is
`reel-0.1`; title is nonblank text <=120 characters. Embed a complete accepted storyboard-0.1
JSON document and the existing Phase 4B audio object. No includes, filenames, URLs, expressions,
FFmpeg fragments or shell commands are accepted. At least one narration or SFX track is required.
Audio is fixed to sample_rate 48000, channels 2, codec aac, bitrate 128000; narration is one cue
or null, cues is a list of at most four SFX. Every cue requires asset_id, start_frame,
trim_start_frame, trim_end_frame (null means asset end), and gain. The accepted validator
preserves frame, gain, trim, role and conservative overlap headroom constraints. Tracks ending
past frame 90 are truncated to the shared output interval under the accepted AudioPlan semantics.

Schema discovery is structural; semantic compilation and registry resolution remain required.
Errors expose a code and JSON Pointer; nested storyboard errors are prefixed `/storyboard`.
Unknown IDs, wrong roles, invalid trims and overlap gain errors use `/audio` and asset details.

`assets`, `validate`, `inspect`, `frame` are native-free. They read only the trusted registry
index, never WAV bytes, never import Cairo or launch FFmpeg. Their output explicitly says
metadata-only; successful validation does not promise the registered bytes still exist.
Rendering always revalidates original WAV bytes, hash, format, complete decode, audible trim
and registry metadata, then takes immutable private snapshots with matching SHA-256.

## Shared timeline

30 FPS, 90 video frames, 3.000 seconds. Sample F starts at F*1600 in the 48 kHz audio clock.
The effective interval is exactly 144000 samples per channel. Beat and shot boundaries are
half-open; a hard camera cut never resets character motion or audio sample position.
Inspection returns complete accepted plans and scheduled cue intervals. Selected-frame
inspection includes actual direction/motion evaluation and active/starting audio cues.
It never infers timing from descriptive text.

## Ownership and native work

The workflow has exactly one OwnedDirectory with a fresh `.reelforge-audio-` root. Its plain
validation, assets, encode and video subdirectories are borrowed stages, not nested owners.
The native validation snapshots, two bounded PCM files and MP4 candidates stay in that root.
The existing scene renderer streams one reused Cairo surface to one FFmpegEncoder across
all 90 frames; no beat movies, concatenation or uncompressed frame collection is introduced.
The accepted renderer performs its full silent-video decode, then existing mix_pcm/mux_audio/
verify_audio and verify_video perform the final full audio/video verification. H.264 is copied.

Only three pre-existing runtime/tool modules changed:

| Module | Additive adapter | Existing behavior |
| --- | --- | --- |
| audio/registry.py | Explicit metadata-only resolution; optional borrowed WAV validation staging | Full validation and private-directory defaults retained |
| media/encoder.py | Optional empty sibling staging directory supplied by an owner | Original standalone OwnedDirectory, pipe, process reaping and publication retained |
| tools/scene.py | Shared cancellation Event and optional encoder staging; reports deferred cleanup | Existing standalone rendering and cleanup retained |

No character, geometry, environment, blocking, direction, storyboard, audio processing,
verification, resource policy or global transaction manager code changes. No legacy tests
are modified. The encoder only borrows an empty non-symlink sibling under the same job root;
it never claims ownership or removes the borrowed root. Its abort/finish still terminate,
reap and close native processes/pipes. The job owner cleans after every native stage ends.

Cancellation propagates through validation, streaming, mix, mux, decodes and publication
checks. CLI SIGINT/SIGTERM set the same Event used by all monitors and native operations.
A snapshot copy checks cancellation every <=64 KiB. No external FFmpeg code is accepted.

## Publication and failures

A new output directory is required. The only public movie is `reel.mp4`. A pending candidate
must pass full decode, original audio tolerances, matching decoded video hashes, unchanged
H.264 bitstream, exactly two expected streams, exact rational PTS F/30 and 3.000-second video
interval. It is fsynced, resource state checked, then published with an atomic no-clobber
hard link. A concurrent destination cannot be overwritten.

Cleanup is explicit after native children finish. Assert the original owner's absence again
after whole-job monitoring. Cleanup or monitoring failure makes success false even if verified
media was already published. Such media is retained with its failure report; it is never
relabelled as a successful job. Primary and cleanup/resource errors have separate fields.
Later restored paths are recorded in read-only follow-up evidence. No sweep, path reacquisition,
retry, renamed transaction or global cleanup workaround is used to obtain success.

The report contains published/media_verified/transaction_clean/success independently, native
commands, hashes, full probe metadata, decoded frame hashes, cue schedules/onsets, PCM peak/RMS,
terminal padding, memory observation, CPU/wall timings and stage storage sizes.

## Audio interpretation

Mixing produces exactly 144000 stereo samples. AAC is lossy; the accepted one-packet tail
allowance and 1024-sample audible-boundary tolerance are unchanged. Priming compensation and
the decoded sample clock must be gapless. Report onset errors in samples and milliseconds;
mixed windows containing overlapping cues cannot establish each individual onset. Audible
threshold drift is a measurement of lossy activity boundaries, not proof of accumulating
sample-clock drift. Do not claim zero audible drift unless measured.

The encoder targets AAC-LC 128 kbps. A quiet diagnostic signal can yield a lower observed
stream bitrate; reports show both the configured target and observed metadata. No silent
normalization, gain relaxation or tolerance substitution is allowed.

## Resources and review

Strict admission requires 256 MiB process budget +64 MiB reserve. Existing cgroup discovery,
OOM telemetry and 10ms sampled process-tree monitoring apply without override. Native stage
logs/timeouts and one-frame streaming stay bounded. Workspace preflight requires at least
256 MiB free or the larger stage estimate plus 64 MiB. The estimate includes two sets of asset
snapshots, two 144000*8-byte PCM files, three 32 MiB MP4 allowances and 1 MiB overhead.
Logical stage samples conservatively count hard links twice, can miss transient peaks, and
are not an exact allocated-disk high-water mark. Memory sampling is not a hard OS cap or
certification of the intended constrained cloud VM. No large temporary files are staged in /tmp.

The three examples reuse byte-identical accepted Phase 7A storyboards. Existing diagnostic
assets are reused without generating new audio: diag_opening is a tone registered in the
narration role, NOT spoken narration; diag_fence is a diagnostic transient; diag_suspense a
diagnostic tone. Every example title identifies diagnostic audio. No actual narration was
provided and no AI voice was generated. The workflow supports registered spoken PCM16 input,
but these proofs cannot establish professional narration, voice/action matching or sound design.

Proof A schedules the transient at discover frame 45. Proof B schedules it at reaction 45;
a second tone from 54 through 90 crosses the camera cut at 60 without restart. SFX overlap 54..57
is explicitly nonisolated. Proof C transient at 72 marks reaction, followed by a short quiet
ending. Original accepted fades/trims are unchanged. Longer pacing and independent listening
are needed for artistic approval. Sound does not prove a visually unseen threat exists.
