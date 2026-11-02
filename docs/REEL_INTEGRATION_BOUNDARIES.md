# Phase 7B integration boundary inspection

Inspected before replacement implementation: storyboard compiler/schema and public tool;
AudioPlan/Cue/audio_from_data; AudioRegistry/inspect_wav; mix_pcm/mux_audio/verify_audio;
audio transaction wrapper; render_audio_story/register_audio; scene renderer; FFmpegEncoder;
verify_video; JobMonitor/check_workspace and OwnedDirectory; existing cleanup tests.

Reuse the actual Storyboard and AudioPlan values. No fabricated Story or shot data.
The storyboard compiles to accepted direction/blocking/scene values; render_scene accepts
its frame and layer evaluators. Audio processing already accepts resolved cues + frame count,
so no audio processing changes are needed. Shared clock: frame F -> sample F*1600.

The legacy orchestration owns nested registration/encoder transactions. The new workflow
requires one owner, so introduce only three additive adapters: registry metadata-only resolution
and borrowed validation directories; encoder borrowed staging; scene borrowed staging/shared
cancellation. All existing defaults remain unchanged. One OwnedDirectory spans every native
stage, snapshots and both decodes; child processes are reaped before cleanup. Final publication
is a no-clobber hard link only after complete verification. Cleanup failure retains failure
status and any verified published MP4. Never reacquire or sweep restored paths.

Recovery note: prior uncommitted Phase 7B work and evidence were absent after workspace
rollback. This is a replacement implementation from exact approved commit
763d8528a7526614703cec4ad1292d1b037bdfca. Prior claimed test/render measurements are not evidence
for this implementation. One new final full-suite attempt is permitted for this replacement.
