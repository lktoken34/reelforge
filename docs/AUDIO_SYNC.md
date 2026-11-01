# Experimental frame-grid audio — story-0.2

**Phase 4B review gate is blocked by a cleanup regression on this execution host.**
Audio/video timing and codec verification work, but a completed transaction's files can
reappear during a later native operation. The failing test is retained, not skipped or weakened.
Do not treat this candidate as an approved production or persistent-batch pipeline. See
PHASE4B_REPORT.md and artifacts/phase4b/test_results.txt before use.

## Weak-agent workflow

Existing story-0.1 manifests and all previous tools/presets remain unchanged. The production
episode CLI remains not render-ready. Copy examples/stories/last_farm_audio.json, select only
registered audio IDs and edit bounded JSON values:

```sh
python tools/validate_story.py examples/stories/last_farm_audio.json
python tools/render_story.py examples/stories/last_farm_audio.json --output-dir outputs/last-farm-audio
```

The validator performs strict story parsing and, for enabled audio, registry/file/codec/trim
validation before reporting valid. Audio-enabled validation needs FFmpeg/ffprobe, but not Cairo.
The underlying validate_story function is native-free structural validation; the CLI adds actual
asset verification. Invalid required narration is an error, never a silent-video fallback.
Audio render success alone does not clear the known post-repeat cleanup gate.

## Contract extension

story-0.1 still accepts exactly its original fields and has no audio key. story-0.2 adds one
required top-level `audio` field. Use `audio: null` to explicitly keep video-only output, or an
object with exactly these fields:

| Field | Supported value |
| --- | --- |
| sample_rate | integer 48000 |
| channels | integer 2 |
| codec | `aac`, native AAC-LC at encoding |
| bitrate | integer 128000 |
| narration | null, or one cue selecting an asset with registered narration role |
| cues | array of 0–4 cues selecting assets with registered sfx role |

An enabled object must contain at least one narration/cue. Cue fields are all required:

| Field | Meaning / bounds |
| --- | --- |
| asset_id | registered snake_case ID, at most 48 characters; never a path or URL |
| start_frame | integer global timeline frame, 0 through output.frames−1 |
| trim_start_frame | integer source-time frame, 0–899 |
| trim_end_frame | null for usable asset end, or integer greater than start, at most 900 |
| gain | finite linear multiplier 0.05–0.8 |

All original shot/output validation is retained: 30 FPS, 720 × 1280 H.264/yuv420p, 1–8 shots,
30–300 frames each, maximum 900 total frames, contiguous end-exclusive intervals and hard cuts.
Booleans/floats are not frame boundaries. Unknown fields, versions, duplicate keys, NaN/Infinity,
float overflow, excessive JSON nesting and input size are rejected by the existing strict loader.
No audio field supplies code, filter expressions, executables, paths, environment variables,
registry overrides, encoder flags, resource settings, captions or language-generation prompts.

Source trim coordinates are 30-FPS source-time units. Resample first, then trim at 48 kHz:
each frame is exactly **1600 samples per channel**. Usable asset end is the number of complete
source video-frame periods, floor(source_samples × 30 / source_rate); a fractional trailing
period is discarded. Cues extending beyond the video are hard-trimmed at output.frames × 1600.
An uncovered tail is zero-padded to that exact PCM length. There is no stretching, looping,
automatic speech fitting, ducking, music generation or inferred sync.

Cue starts are global and do not reset at shot cuts. The demonstration selects narration-role
`diag_opening` at frame 9 (0.3 s), `diag_fence` at frame 120 (4 s), and `diag_suspense` at frame
240 (8 s). These are original diagnostic signals, **not spoken narration or a musical score**.
The approved three-shot visual story is unchanged.

## Trusted registration

The operator-owned registry is assets/audio/registry.json, version audio-assets-0.1. Stories
select its IDs, not its location. Supported input is deliberately restricted to complete
uncompressed signed PCM16 RIFF/WAVE: mono/stereo, 16000/24000/44100/48000 Hz, at most 8 MiB/file,
at least one complete video frame, up to 30 seconds for narration and eight seconds for effects.
At most sixteen assets may be registered. Other formats/codecs are rejected, not guessed.

For a later user-supplied spoken take, an operator can run:

```sh
python tools/register_audio.py /trusted/local/narration.wav --id rowan_take1 --role narration
```

Then a weak agent changes the narration asset_id to rowan_take1. No Python editing or FFmpeg
command authoring is required. Existing IDs/files are not overwritten: register a new take ID.
A registry record pins ID, role, exact filename ID.wav, SHA-256, file size, source sample rate,
channel count and sample count. Byte or metadata changes require a fresh registration.
Registration/import is an explicit operator action; it is not performed by story rendering.
Assets are stored as local repository files, not embedded as base64 or loaded wholly into RAM.

The implementation rejects traversal, unknown IDs, role mismatch, symlinks, missing/truncated
files, unsupported codecs/rates/channels, inconsistent metadata, out-of-range trims and wholly
silent trim selections. It streams headers, sample payload checks and hashes in bounded chunks.
Native decoders read hash-checked private copies, with fixed file-only protocol and WAV demuxer
selection, complete error-checked decoding, finite waits and bounded diagnostics. PCM16 sources
cannot contain executable scene/filter code. This is not a general sandbox for arbitrary codecs.

The original fixtures are generated by tools/generate_audio_fixtures.py. They are frozen in the
registry for CI and can be reproduced into a fresh directory:

```sh
python tools/generate_audio_fixtures.py --output-dir outputs/diagnostic-audio-registry
```

No TTS, paid API, external music or recording is used. The mono 24 kHz opening signal, stereo
44.1 kHz cut cue and mono 48 kHz suspense signal exercise resampling/channel conversion.

## Processing and verification

The accepted silent Cairo/FFmpeg renderer runs in a private transaction. One streaming video
encode covers all shots; no full video-frame list or PNG sequence is created. The accepted
renderer, encoder, character/environment art, camera math and memory policy are unchanged.

The sequential audio stage resamples with a fixed non-async 48 kHz clock. Mono is duplicated to
left/right at unity; stereo channels are retained. It applies frame-grid trims, explicit fixed
gain and sample-unit delay, sums without automatic normalization, pads/trims to exact video
length and writes float32 stereo reference PCM to disk. Overlapping gains must total at most
0.8. Actual mixed peak must stay at or below 0.90 full scale; decoded AAC must remain below
0.9995. Unsafe peaks cause a gain-reduction error rather than silent clipping/normalization.

A second bounded FFmpeg audio stage stream-copies H.264 and encodes AAC-LC 48 kHz/stereo at
128 kbps. It maps exactly one video and one audio stream, strips irrelevant metadata, and
retains faststart. There is no shortest-stream video truncation or video re-encode. The final
candidate is checked before a same-directory fsync/no-clobber hard-link publication. Existing
successful outputs, including a competing writer during processing, are protected.

Verification includes all video frame hashes and presentation timestamps before/after mux,
a compressed H.264 packet-data hash, stream metadata, full AAC decode, a gapless decoded
audio clock and PCM amplitude/activity comparisons. The declared audio interval must match
the video; decoded codec tail may contain up to 1024 extra samples and is excluded from the
logical interval. MP4 edit-list/priming handling must produce decoded audio beginning at PTS 0.
Cue-onset checks compare reference and decoded audible activity, including any source leading
silence. AAC is lossy: tolerance is **one AAC-LC frame, 1024 samples / 21.333 ms**, below one
video frame. This is not a claim of sample-perfect AAC packets. The supplied signals measure
much smaller errors. Overlapping cue windows are labeled mixed/attribution-limited; per-cue
isolation cannot be inferred reliably from a shared waveform.

All native stages use supervised bounded subprocesses and default strict JobMonitor admission:
256 MiB process-tree budget, 64 MiB reserve, CPU only. A master monitor spans asset validation,
snapshotting, video, mixing, muxing and verification; the accepted nested video monitor remains
unchanged. PCM is stored temporarily on disk, read in at most 64 KiB chunks, and bounded by the
30-second contract. Two full float32 stereo PCM files consume at most 23.04 MB. The temporary
storage estimate also covers asset copies, a validation copy, two 32 MiB video allowances and
report margin; existing minimum workspace headroom and disk reserve are not weakened.

Cancellation, native failure, bad inputs and workspace failures use owned transaction cleanup
and propagate explicit errors. **Persistent cleanup after later native work is currently
unverified/failing on this host**, despite absent files at each immediate render return. No
broad sweep of earlier/concurrent jobs is used to conceal this. No previous test was weakened.
See the retained failing end-to-end test and report for the review blocker.

## Review workflow

Use fresh output directories and run sequentially:

```sh
python tools/render_story.py examples/stories/last_farm_audio.json --output-dir outputs/audio-first
python tools/render_story.py examples/stories/last_farm_audio.json --output-dir outputs/audio-repeat
python tools/review_audio_story.py --output-dir outputs/audio-first --repeat-dir outputs/audio-repeat
```

The review compares exact expected/decoded PCM and all video frames on the same native build,
preserves the approved Phase 4A silent file, writes sync/compatibility/cleanup reports, and draws
a waveform/cue timeline. Its 50 ms plot bins are explanatory; timing checks operate on decoded
samples. Cross-build AAC byte identity is not required. Raw PCM/video frames are not retained
as deliverables. Native command templates in reports replace deleted private paths with
`<audio_transaction>`. Do not execute those diagnostic arrays as a weak-agent workflow.

Recommended next step is to reproduce and fix the retained cleanup test on ordinary Ubuntu,
then rerun all regressions and two complete audio renders before approving Phase 4B. No later
milestone or Muse Spark deployment is authorized by this candidate.
