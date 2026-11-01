# Phase 4B.1 — transaction ownership investigation and safety hardening

**ACCEPTANCE STILL BLOCKED. This is not a completed reliability repair.**
The requested three zero-failure runs were not achieved. The commit is a reviewable safety
correction and diagnostic checkpoint; the archive contains the complete committed tree.
Do not publish it as an accepted milestone or begin Phase 4C.

Approved Phase 4A: `fd14320355f442f5fe9c59043b19a6009bd0f482`.
Parent Phase 4B: `a5672acc5b25df7073aac07697c51e3716d3ea4c`.
Repair branch: `phase4b-cleanup-fix`. No GitHub publishing, push or deployment occurred.

## Investigation and what is established

All retained Phase 4B logs were inspected before runtime changes: the complete 473-pass /
1-failure log, the 465-pass / 9-setup-error log, the partial rerun and isolated passing test.
The Phase 4B files remain unmodified as historical evidence. Python is the project's pinned
3.12.14, with Pycairo 1.29.2, pytest 8.4.2 and FFmpeg 6.1.1 on the development host.

The baseline diagnostic ran two one-second audio stories. It records each private transaction's
creation, exact path, entries/types, device/inode, ctime/mtime and size; directory removal
boundaries; native child creation and reaping; parent PID; relevant errors; and the overlay
mount type/device. Only this invocation's private paths are enumerated; no asset contents,
credentials or unrelated filesystem listings are logged. See baseline_lifecycle.jsonl and the
indexed diagnostic_summary.json under artifacts/phase4b1. The baseline JSONL capture lacks
a final complete marker; its recorded transitions are evidence, but it is not treated as a
complete child-lifecycle record. The hardened trace terminates at its explicit render error.

**Verified finding: private pathnames are restored after successful removal.** An encoder
directory was absent in an earlier snapshot and present again during a later native operation,
with a new directory inode. One restoration included `.rsync-tmp/pending.mp4`, with a stale
48-byte MP4 header. A previously removed outer audio directory also returned with new inodes
and old asset/PCM/video contents during the second job. These are new directory entries,
not an open handle keeping the original unlinked inode alive. The diagnostic's application
code does not recreate completed transactions, and the subsequent job uses new private names.

A fresh local checkout in the current workspace also reproduced encoder-directory restoration.
An experiment using an inherited output descriptor did not stop it and was reverted. Neither
experiment is shipped as an alleged fix. The minimal short WAV probe did not reproduce it,
which is evidence against assuming every native call necessarily causes restoration.

The hardened trace records cleanup-before/after boundaries explicitly. Eighteen native children
were reaped; no surviving process groups were observed. The application then detected a restored
encoder pathname and returned TRANSACTION_CLEANUP. Popen reaping/return codes are the lifecycle
evidence; raw `/proc/PID` presence is only ancillary because PID namespaces can differ.
No competing rendering jobs were started during suites or audiovisual verification.

The observed restoration mechanism explains both reported symptoms: an old outer audio path
can return after render success; a returned encoder path can contain a synchronization staging
directory that is outside the encoder's known content. The `.rsync-tmp` entry and inode changes
support a filesystem synchronization/restoration hypothesis. **The writer's identity, triggering
platform component and underlying implementation defect are not established.** No claim is
made that FFmpeg itself launches rsync. Syscall tracing was attempted but ptrace is denied on
this host (ptrace_limit.txt). No permission escalation or host configuration change was attempted.
A repository cleanup function cannot guarantee persistent absence against an independent writer
that subsequently recreates the same pathname. Adding retries, sweeps or waiting arbitrary
amounts of time would conceal the failure rather than establish ownership or reliability.

## Small safety correction

The previous encoder had a TemporaryDirectory finalizer plus an orchestration helper that could
reacquire a removed path by prefix/name alone. The audio wrapper similarly checked a pathname
without retaining inode identity. Neither pattern safely distinguishes a restored/replaced
transaction from the original owner.

A small standard-library OwnedDirectory now holds the original directory descriptor and
(device, inode) identity until explicit cleanup finishes. There is no GC finalizer, sleep,
retry or prior-job sweep. It rejects root replacement; removes audio subtrees through fd-safe,
non-symlink-following operations; and restricts encoder entries to the known pending.mp4 file.
Unexpected encoder content is preserved and reported. Failed removal raises a stable domain
error and cannot be converted into success by a second cleanup call. Rendering tools now verify
absence through their original encoder owner instead of deleting a recreated pathname. The old
reconciliation helper remains for compatibility with the original tests, but rendering no longer
uses it. Character/environment tool changes are only this cleanup call, not artwork or rendering.

These are verified ownership/safety corrections, **not a fix for the external restoration**.
No Cairo drawing, animation, audio filters, H.264/AAC options, manifest contract, timebase,
resource monitor, budget or reserve changed. In particular, no inherited-FD encoding experiment
is included. Stronger verification intentionally exposes restored silent-renderer directories
that the old path-based reconciliation could remove and mask.

## Publication and cleanup atomicity

Final MP4 publication remains a no-clobber hard link after successful encoding/verification and
fsync. Existing outputs and competing writers are protected. Cleanup is a separate fallible
step after publication: if it fails, the operation raises and no overall-success report is
written by the audio driver. An already published valid MP4 is retained; it is not rolled back
or replaced. A retry in the same directory is rejected as OUTPUT_EXISTS. Inspect the failure
and use a fresh destination after resolving it. File presence alone is not whole-job success.

Fault-injection tests exercise both audio and video post-publication removal failures and
preservation of unrelated outputs. Additional tests cover successful/nested cleanup, interruption,
actual FFmpeg failure, denied rmdir, unexpected content, root replacement, no GC finalizer,
symlinks to other jobs, successive real encodes, repeated audio jobs and persistence after
later native work. No existing test or assertion was removed or weakened.

## Full-suite results

All 488 cases (412 original + 62 Phase 4B + 14 new cleanup cases) were run three times,
sequentially, with fresh workspace-based pytest directories. The implementation was unchanged
between these runs. Diagnostic-only tooling was refined between runs; no resource policy changed.

| Run | Passed | Failed | Fixture errors | Wall time |
| --- | ---: | ---: | ---: | ---: |
| 1 | 485 | 3 | 0 | 94.30 s |
| 2 | 483 | 3 | 2 | 73.21 s |
| 3 | 476 | 3 | 9 | 61.63 s |

Logs and the third run's JUnit XML are committed. These are **failed gates**, not three successful
runs. In run 1 the original 412 cases pass; runs 2 and 3 also fail the original continuous-story
cleanup assertion (411/412 original cases pass). Third-run breakdown: Phase 4B 52 passed, 1 failed,
9 fixture errors; new cleanup cases 13 passed, 1 failed. Shared silent-template restoration causes
fixture errors; the persistence test remains deliberately strict and failing.

All observed failures in these runs are transaction cleanup/content/restoration failures, not
RESOURCE_GUARD failures. The independently reported Python 3.13 resource rejection is distinct
and was not recreated by changing memory pressure or limits. Python 3.13 is outside the pinned
project requirement. The 256 MiB process-tree budget and 64 MiB reserve remain unchanged.

## Updated audiovisual and resource evidence

To avoid rebuilding approved artwork, tools/verify_cleanup_story.py reuses the original silent
12-second Phase 4A file, then runs fresh trusted-asset validation, PCM mixing, AAC muxing and full
AV verification twice. These are successive jobs in one Python process, not independent complete
video rerenders. The old Phase 4B independent-render evidence is preserved separately.

Both new jobs pass; their post-repeat/post-waveform cleanup checks also pass. This limited success
does not override failing suites or prove persistence indefinitely. The new MP4 and detailed reports
are in artifacts/phase4b1/av-first; the repeat job's report and consistency evidence are included.

- Exactly 360 fully decoded H.264/yuv420p frames, 720 × 1280 at 30 FPS; cuts at 120 and 240.
- One AAC-LC 48 kHz stereo stream; declared duration 12 seconds. All video PTS and compressed
  H.264 data preserved. All 360 decoded/source frame hashes match the approved silent reference.
- Cue onset errors: 0, −1, 0 samples at scheduled frames 9, 120, 240. Global audible drift 0.
- Logical PCM 576000 samples/channel; decoded 576512, with 512 codec-tail samples outside the
  declared interval. AAC tolerance remains 1024 samples / 21.333 ms; no sample-perfect packet claim.
- Exact repeated reference/decoded PCM hashes and video hashes; SNR 42.7393 dB; clipping checks pass.

| Measurement (audio reprocessing + full verification only) | First | Repeat |
| --- | ---: | ---: |
| Total wall time | 11.219 s | 10.446 s |
| Silent reference copy | 0.0167 s | 0.0023 s |
| PCM mix | 0.2656 s | 0.2919 s |
| AAC mux | 0.2741 s | 0.2629 s |
| Full final verification | 9.6192 s | 8.9171 s |
| Parent CPU | 2.230 s | 2.053 s |
| Child user + system CPU | 11.265 s | 10.576 s |
| Sampled process-tree peak RSS | 97099776 bytes | 97611776 bytes |
| Sampled temporary storage peak | 17127656 bytes | 17127656 bytes |

Strict monitoring spans these stages and all children. There was no OOM delta or fallback.
There is no new video-render FPS measurement: encoded_fps/render_encode_seconds are zero in
this proof to explicitly mark reuse; archived per-shot measurements inside the reference report
belong to the prior milestone. RSS and storage sampling can miss short peaks; this is not target
VM certification. The WAV fixtures remain diagnostic tones, not spoken narration or music.

## Packaging and remaining work

Ruff lint/format, sdist/wheel build and installed-wheel smoke checks pass. The wheel was tested
outside the checkout without Cairo: both manifests validate, an owned-directory cleanup works,
and production capabilities remain render_available:false. Frozen renderer environment sync
succeeds using --no-editable; normal editable offline sync lacks the cached editables dependency
and its failed logs are retained. Project dependencies/lockfile are unchanged.

Required unresolved work: identify/stop the pathname-restoring writer in a controlled environment,
reproduce the same diagnostic there and obtain three truly clean full-suite runs, then repeat AV
persistence checks. Ordinary Ubuntu and this execution host should be distinguished in that
report. Do not approve Phase 4B.1, publish it as accepted, or proceed to Phase 4C from this checkpoint.
