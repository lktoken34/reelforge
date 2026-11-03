# Vertical reel MVP — episode-0.1

One episode JSON plus registered audio produces one 720x1280 (9:16) H.264/AAC MP4.
Use Python3.12 and the accepted Cairo/FFmpeg environment. From the checkout:

```bash
mkdir -p outputs
python tools/episode.py capabilities
python tools/episode.py schema
python tools/episode.py assets
python tools/episode.py validate examples/episodes/relay_to_shelter.json
python tools/episode.py inspect examples/episodes/relay_to_shelter.json
python tools/episode.py frame examples/episodes/relay_to_shelter.json --frame 270
python tools/episode.py render examples/episodes/relay_to_shelter.json --output-dir outputs/my-new-episode
```

Select a fresh output directory under an existing persistent workspace parent. The result
is reel.mp4 plus report.json. Exit0 means the job verified, published and established cleanup
at return; nonzero means failure. Check success, media_verified, published, transaction_clean,
error, cleanup_error and resource_error separately. Valid published media can coexist with a
later cleanup/resource failure. File presence does not establish job success.

The manifest has exactly schema_version (episode-0.1), title, segments, audio. Segments is an
ordered list of1..10 objects with unique snake_case id and a complete accepted storyboard-0.1
under storyboard. Every segment is90 frames. Its global interval is[i*90,(i+1)*90); total
length is3..30 seconds at30 FPS. All dimensions, codecs and safety budgets stay fixed.
No filenames, external includes, Python, FFmpeg fragments, URLs or policy overrides are
accepted in scene/audio data. Agents edit JSON only. Copy the supplied complete example;
reduce or extend its ordered segments using supported storyboards and valid audio timestamps.

Audio is exactly the accepted AudioPlan structure:48 kHz stereo, AAC target128000 bits/s,
<=1 registered narration cue and<=4 registered SFX cues. At least one track is required.
Use existing trusted tools/register_audio.py to register operator-supplied PCM16 WAV assets;
its --help describes the operator import workflow. The --registry-root operator option on
this tool, before the subcommand, selects a trusted registry; manifests cannot select paths.

Every audio start_frame is an ABSOLUTE episode frame. Sample start is frame*1600 at48 kHz.
For15 seconds there are450 frames and720000 effective samples per channel. Cues do not reset
at segment cuts. Accepted source trims, duration limits, gain and overlap headroom remain
unchanged. A cue extending beyond the output is clipped under existing AudioPlan semantics.
Planning/schema/inspection are native-free and read registry metadata only; rendering always
revalidates current WAV bytes and media, then takes pinned private copies. Metadata validation
cannot promise a file still exists or contains valid audio.

The renderer streams all segment frames into one accepted FFmpegEncoder, sequentially using
one Cairo surface. There are no separate beat/segment movies or concatenation. Direction
sampling uses local frame0..89 inside each accepted storyboard; the encoder PTS and audio
use global frameF. Every segment boundary is an explicit EDITORIAL CUT. Independent storyboards
can change pose, location, velocity, lighting or camera. No seamless acting/locomotion continuity
is promised across those cuts. Within each segment the accepted continuous timeline is retained.

The shared Phase7B audiovisual orchestration now accepts a trusted bounded frame count and
visual-plan callback. render_reel remains the original90-frame wrapper. stream_check and
metadata_plan retain their90-frame defaults. No existing contract changed. Audio mixing,
AAC/H.264 verification, global ownership, resource policy, registry staging and encoder code
are unchanged. New episode orchestration still has one owned transaction, bounded internal
stages, child reaping, cancellation and no-clobber publication only after full verification.
The fixed32 MiB allowance for each silent/final MP4 is retained. Episode encode has a finite
300-second ceiling, covering at most900 frames; native verification keeps existing deadlines.

Strict256 MiB process-tree budget,64 MiB reserve, cgroup/OOM telemetry and the /tmp workspace
prohibition remain intact. Two bounded PCM files cover the complete interval; frames are never
buffered as a list. Storage preflight includes both snapshots, full-episode PCM and bounded
MP4 stages. Sampled RSS/storage can miss transient peaks and do not certify target deployment.
The production foundation CLI remains unchanged; tools/episode.py is the working MVP interface.

The15-second example, Relay to Shelter, moves from a damaged woodland radio through an empty
settlement and escape to a shelter approach and threshold reaction. Segment-specific Rowan
positions and framing are explicit. A foreground overlap is declared in the escape shot.
All audio is existing registered DIAGNOSTIC TONES, including a tone in the narration slot.
There is no spoken narration, TTS or professional sound design. A tone at global255..309
crosses the cut at270 without reset. The final transient is420..432. Independent artistic
review and licensed/supplied recorded audio are needed for finished production work.

The known development-host reappearance of retired paths remains a blocker. Read
PHASE7B1_REPORT.md; no sweep, fallback filesystem or speculative cleanup fix is introduced.
A target-VM deployment gate remains mandatory and separate from this MVP and normal CI.
