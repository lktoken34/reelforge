# Phase 8 — vertical reel MVP engineering report

Approved base: f5b689af1eb720303b3b819a3ec32a6b86818d50.
Development branch: phase8-vertical-reel-mvp. No main-branch publication or deployment.

## Delivered MVP

One command produces a complete vertical episode from structured scene data and registered
audio, without editing Python:

```bash
mkdir -p outputs
python tools/episode.py render examples/episodes/relay_to_shelter.json --output-dir outputs/new-reel
```

Capabilities, schema, assets, validate, inspect and frame commands are documented in
EPISODES.md. The episode tool advertises render_available=true; production readiness remains
false. The older foundation CLI is unchanged. Target-VM deployment is a separate mandatory
gate and has not been passed by this sprint.

## Scope and implementation

Additive episode-0.1 supports1..10 ordered, uniquely named accepted90-frame Storyboard segments,
3..30 seconds at30 FPS. The AudioPlan is the existing accepted structure with global episode
start frames. Narration remains at most one registered track, SFX at most four. Source duration,
trim, gain and overlap constraints are unchanged. No TTS, automatic screenplay interpretation,
sound selection, rig/backend changes or environment redesign was added.

One Cairo surface streams every segment into one FFmpegEncoder. Each storyboard evaluates
local frames0..89; video PTS and audio scheduling use global episode frames. Segment boundaries
are explicit editorial cuts with no seamless acting promise. There is no segment concatenation,
per-beat MP4 or uncompressed frame collection. Audio is mixed once over the full interval.

Two pre-existing modules changed: reels/contract.py adds a typed AudioRequest protocol and an
optional frame count to metadata resolution, defaulting to90. reels/workflow.py factors the
accepted owned AV transaction into render_av and parameterizes duration/stream checks; the
original render_reel wrapper remains exactly90 frames. Existing tests and all old contracts
remain unchanged. Audio processing, registry, encoder, scene/character/direction/storyboard
internals, global ownership and resource policy are untouched. The new episode video adapter
uses the accepted renderer/encoder primitives and a finite300-second encode ceiling.

One owned directory spans snapshots, silent encoding, one mix/mux and full verification.
Publication is no-clobber only after fsync and verification. Cancellation, child reaping,
separate primary/cleanup/resource errors, strict256 MiB budget and64 MiB reserve, storage
preflight and /tmp prohibition remain intact. Existing32 MiB MP4 stage limits are retained.

## Demonstration — Relay to Shelter

The actual movie is artifacts/phase8/demo/reel.mp4; its input is
examples/episodes/relay_to_shelter.json. The five segments show a damaged woodland relay,
an abandoned street, a further escape, shelter approach and threshold pause/reaction.
Segment-specific Rowan positions and camera views are explicit. The escape route deliberately
declares foreground overlap; a pole partly obscures Rowan near its end. That limits readability
and is preserved as an artistic limitation. Independent segment pose/velocity resets are
editorial cuts, not seamless motion. Existing environments and authored objects are reused.

The decoded15-frame contact sheet was inspected. It shows the radio reveal, readable street
reaction and escape, and approach/threshold progression. This is a small cinematic integration
MVP, not finished professional storytelling or a claim of Stickocalypse visual parity.

No spoken narration was supplied. Existing registered diagnostic fixtures are reused unchanged.
The narration-role asset is a tone, not voice acting. No AI voice/image/video was generated.
SFX starts are global45 (radio discovery),135 (street reaction),255 (tension carrying into the
shelter cut at270), and420 (threshold pause; reaction begins432). The255..309 tone is continuous
across the9-second cut. The soundtrack is sparse and includes intentional quiet intervals;
professional narration and final sound design are not claimed. Independent listening and
artistic review remain required.

## Technical verification

Exactly450 decoded frames,720x1280 (9:16),30 FPS; exact15.000-second video interval. One H.264
video stream and one AAC-LC48 kHz stereo stream. Video PTS are rational F/30 at every frame,
including cuts90/180/270/360. H.264 bitstream and all450 decoded video hashes are unchanged
through AAC muxing. Audio completely decodes on a gapless compensated sample clock.

The reference has720000 effective stereo samples per channel. Raw AAC decode has
720896 samples, including896 accepted tail samples.
The existing1024-sample/21.333ms tolerance and clipping policy are unchanged. Cue onset errors
are -2,0,0,0,+1 samples (-0.041667,0,0,0,+0.020833ms); all five windows are isolated. Measured
audible-threshold drift is1 sample (0.020833ms), not zero.
This is distinct from accumulated PTS/sample-clock drift. Mixed PCM peak is0.07200047
and RMS0.01472188; decoded peak0.07345587, with no clipping or silent fallback.
AAC targets128000 bits/s; sparse tones yield observed39397 bits/s.

One demo render attempt, no retries or repeat render. Pipeline wall time was
29.2756s (15.3712 FPS); outer monitored time including compilation
was32.5508s. Render/encode FPS was29.1456.
Sampled simultaneous process-tree peak was106.3828 MiB.
Sampled logical temporary peak was20,694,853 bytes, against
113,834,056 preflight-estimated bytes. Hard links are conservatively
counted twice; stage sampling can miss transient disk peaks. RSS sampling can miss peaks and
double-count shared pages. Encoder-specific PID attribution is not separately measured by the
new adapter; the whole-job tree observation covers its native children. These development-host
measurements do not certify the target VM.

## Validation and limitations

Targeted contract/shared-pipeline/regression coverage:86 cases passed across two executions.
The first run passed59 cases and had27 fixture setup errors because outputs did not yet exist;
those cases never reached native work. After creating the workspace parent, the27 affected
cases passed. Both original logs/JUnit results are preserved. All61 existing reel cases pass,
and25 new episode cases cover strict syntax, schema,1/5/10 segment bounds, global cues/cuts,
metadata-only operation, shared rendering/mixing count, cancellation and workspace refusal.
No complete local suite was run; one normal CI gate is required after publication.

Ruff lint/format and wheel/sdist build pass. Fresh installed-wheel planning is checked without
Cairo/FFmpeg. Initial frozen renderer setup lacked pkg-config; frozen base dependencies were
installed and the byte-identical approved pinned Pycairo binary reused locally. Pins were not
changed. The normal CI workflow provisions its native build dependencies as before.

The demo returned success=true, media_verified=true, published=true and transaction_clean=true.
Later contact-frame extraction observed retired_path_now_present=False.
The historical development-host persistent restoration blocker remains unresolved regardless
of this observation or CI success. Original Phase7B/7B.1 evidence is preserved. No directory
sweeps, reacquisition, alternate-filesystem workaround or weakened cleanup assertion was added.
No deployment or further feature phase is authorized. CI outcome will accompany the published
commit in the final delivery report; it is not invented in this pre-publication record.
