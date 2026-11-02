# Phase 7B.1 — persistent cleanup investigation

2026-11-02. Started from existing unpublished Phase 7B commit
`a2587e7f42a4260aa2b5ed2941b15b05c6370d81`, whose parent is the accepted Phase 7A
`763d8528a7526614703cec4ad1292d1b037bdfca`. No reimplementation or diagnostic branch was created.

**Finding: the reproduced retired paths are newly created filesystem objects. The final
controlled reproduction isolates their creation outside the traced engine Python process
and its 55 supervised native children.** It does not identify the external service or writer
PID. Persistent cleanup on this development host still fails; this is an external-blocker
investigation result, not a cleanup fix, deployment approval or permission to suppress failures.

No production runtime correction is justified by this evidence. All engine source, schemas,
contracts, test assertions and original Phase 7B reports/media remain byte-identical. New work
is trusted diagnostic tooling, scoped evidence and documentation. No GitHub push, CI,
production deployment, Muse Spark work or next milestone ran. GitHub was used read-only to
confirm the accepted baseline; remote_baseline.json records its identity.

## What the original evidence established

Read cleanup_followup.json, post_suite_transaction_observation.json, original JUnit failures
and all four per-job reports before reproducing anything. Original jobs returned verified,
published media with immediate cleanup, followed by later observations of retired private
roots. Those records alone lack the original inode identities and creation-event timing.
They establish the failure but cannot attribute a writer or distinguish every proposed cause.

Historical Phase 4B.1 lifecycle evidence already recorded new inodes and a .rsync-tmp entry.
The extracted historical_restoration_windows.json preserves the relevant observation windows.
That filename is a clue to copying/synchronization, not proof of rsync, FFmpeg or a particular
platform component being responsible. This investigation does not assign such an identity.

## Inspection of engine boundaries

OwnedDirectory retains an original directory descriptor and (device,inode), checks identity,
removes only its owned subtree with fd-safe operations, closes its descriptor, and subsequently
asserts absence without reacquiring a retired name. There is no finalizer or previous-job sweep.
Native run_bounded and FFmpegEncoder use new sessions, finite waits, termination on failure,
reaping and bounded diagnostics. No code path was found that intentionally recreates retired
root names. Registry validation defaults own fresh staging; Phase 7B borrows validation stages.
The borrowed encoder leaves its stage for the single outer owner. Scene and reel orchestration
share cancellation, retain strict resource guards and verify media before no-clobber publication.

The investigation adds no retry, sleep-based cleanup fix, renamed transaction, directory
reconciliation, alternate storage location, changed ownership rule or relaxed assertion.
Observation-only duplicate descriptors are deliberately retained in diagnostic runs to compare
the original unlinked inode with a later pathname. They are non-inheritable, are closed at the
end, and never grant ownership of a recreated path. Production ownership code is unchanged.

## Hypothesis-driven experiments

The complete execution transcripts and traces are in artifacts/phase7b1. Eight small engine-
independent controls imported no reelforge modules. They exercised: elapsed-time/no-child and
/bin/true controls; normal versus isolated Python startup; a small native WAV; an MP4 stream
copy and hard-link publication; later registered-WAV probing; a three-frame rawvideo pipe;
a paced 30-frame pipe; and a 30-frame decode-to-encode pipe using existing farm media.
Their retired canaries stayed absent. These negative results reject a universal claim that
any native child or any FFmpeg command restores a path. They do not certify persistent cleanup.
Small controls are bounded diagnostics, not target-VM resource/deployment measurements.

One actual Phase 7B audio job reused an accepted rendered silent video, performed current
registry validation, snapshot/mix/mux/full AV verification and cleanup, then decoded audio
again after job return. All 18 children were reaped, groups absent and pipes closed. Its path
stayed absent in the observed interval. This took 5.0883 monitored seconds and sampled
100.5234 MiB process-tree RSS. No storyboard frames or original proof movies were regenerated.
A single limited clean observation cannot override the original failures.

The positive reproducer is exactly the unchanged test:
`tests/test_transaction_cleanup.py::test_two_audio_jobs_persistently_clean_after_native_work`.
It uses a short legacy fixture, not the three completed 90-frame Phase 7B proof movies.
Four targeted executions gathered different information; every one retained the failure:

| Capture | New question / instrumentation | Result | Pytest seconds |
| --- | --- | --- | ---: |
| legacy-trace | Inode/descriptor, mount, inotify and process chronology | 1 failed | 9.04 |
| writer-trace | Process/fd census at kernel create notifications | 1 failed | 8.08 |
| confined-trace | Fanotify plus initial seven-syscall native restriction | 1 failed | 7.98 |
| final-confined-trace | Close the io_uring path as well; ten denial self-checks per child | 1 failed | 8.40 |

These were instrumented executions of one test, not complete suites or retries to obtain a
pass. The initial confinement is preserved as provisional evidence: its narrower restriction
is not the final isolation proof. No final full local suite ran because no runtime fix was made.
No previous assertion was weakened, replaced or silently skipped.

## Decisive final capture

The listener Python process was namespace PID11 / procfs PID recorded in the trace. The
unprivileged fanotify calibration reports the listener's own creations with its PID and a
known child creation with PID0. Thus PID0 is a redacted non-listener identity, not "process 0"
and not a usable creator PID. The real capture similarly reports engine cleanup deletions
with PID11 and the later directory creations with PID0.

Before executing each native command, a small diagnostic C wrapper installs an inherited
seccomp filter after setting no_new_privs. It denies mkdir/mkdirat; rename/renameat/renameat2;
link/linkat; io_uring setup/enter/register; mount/reconfiguration and namespace-transition
syscalls. It rejects x32 syscall numbering and unexpected architectures. Normal file reads,
file writes, codec work and parent-side publication remain unchanged. The filter cannot be
removed by exec or inherited children. It is applied only to this diagnostic run, not added
to production rendering, the transaction manager or host policy.

All 55 native PIDs have matching wrapper records. Every record confirms ten denied direct
syscall probes, no_new_privs=1 and seccomp mode2 before exec. The offline summary verifies
this one-to-one PID coverage; native_restrictions.jsonl retains every original record. The
source and compiler/binary hashes are in guard_build.json. The wrapper closes its log before
exec and emits no native stdout/stderr that could alter the accepted media checks.

| Retired object | Original inode | New inode | Last-absent to first-present window |
| --- | ---: | ---: | ---: |
| Encoder .reelforge-encode-nwtd9lax | 2228466 | 2228484 | 70.965920 ms |
| First audio .reelforge-audio-gilqbpok | 2228472 | 2228503 | 70.382249 ms |

Both objects were on device27. Observation descriptors still referenced the original inodes
with link count0 while the restored names referenced different inodes. Parent path/fd identity,
mount namespace and mount information stayed stable across each window. Kernel inotify and
fanotify emitted directory-create events, ruling out mere continued access to the original
unlinked inode or an observed mount/parent swap. No old pathname was reopened for deletion.

The first window occurred during a later ffmpeg WAV-validation decode (PID55), and the second
during ffprobe validation of a different job's WAV (PID169). Their complete argument lists
are recorded. "During" establishes correlation, not that those executables caused creation.
In this controlled run their directory-changing syscalls were denied. Fanotify excludes the
Python listener as the creator, including writes performed in that process through native
extensions. Together those observations isolate the restoring actor outside the traced engine
parent and its supervised native children/descendants. This conclusion is scoped to the
captured execution; it does not name a platform service or retrospectively identify every
historical failure's exact writer.

All 55 children returned, waitpid subsequently reported no such child, their process groups
were absent, and stdout/stderr handles were closed. The observer kept watching through test
return, final child checks, and observation-descriptor closure. Recreated paths were left
untouched. The final targeted test remains exit1. Its monitored wall time was8.5142 seconds,
with120.4844 MiB sampled process-tree RSS under the unchanged256 MiB budget/64 MiB reserve.
There was no OOM-counter change, telemetry relaxation or guest fallback. Sampling is not a
hard resource sandbox and does not certify the constrained target cloud VM.

## Attribution limits and deployment implications

The creator's actual PID and executable remain unavailable. The census captured namespace-
visible processes and only scoped fd targets, with no command lines, environment or credentials.
It did not identify the writer. strace/ptrace is denied; its failure is preserved. Fanotify
cannot disclose other processes' PIDs at these privileges, as the calibration demonstrates.
The result is isolation of an external actor, not a diagnosis of a specific filesystem daemon,
rsync binary, FFmpeg defect or vendor implementation.

An external actor that recreates retired directory entries defeats a persistent-absence
promise regardless of engine cleanup. The engine must continue failing on detected restoration.
A production sweep or repeated deletion would cross ownership boundaries and hide this problem.
No filesystem workaround or new production confinement policy is shipped.

For host support or an independently controlled Ubuntu environment, reproduce the same focused
case with the diagnostic guard and inspect the provider-side writer/mount/synchronization
activity at the recorded windows. The restricted local PID view cannot supply that last
attribution step. After independent review, the publishing agent's single standard CI gate
can establish behavior on that separate supported runner. Normal CI success would not prove
this development host has been repaired. Production/Muse Spark deployment remains unauthorized.

## Reproduction

Use the existing Python3.12 renderer environment and Linux x86_64 development host. This is
operator-only investigation tooling; it adds no untrusted manifest commands or policy flags.
Choose fresh output directories and preserve failed traces. The source guard requires a local
C compiler and Linux seccomp headers; the probe requires working inotify/fanotify support.
If the kernel facilities or restriction self-checks fail, report the reproduction as inconclusive.

```bash
cc -std=c11 -O2 -Wall -Wextra -Werror tools/native_directory_guard.c \
  -o outputs/phase7b1-native-directory-guard
.venv/bin/python tools/trace_reel_cleanup.py --legacy-test --confine-native \
  --output-dir outputs/my-fresh-persistence-investigation
```

The expected result on the affected host is a failing persistence assertion with trace.json,
JUnit XML and native_restrictions.jsonl. Observe the final fanotify/create events, original
inode nlink0, new pathname inode, stable parent/mount and complete restriction/reaping records.
Do not interpret a clean small control or missing events as proof that the problem was fixed.
The checked-in offline summary contains the archived capture, not a live deployment check.

The early trace mode label was hardcoded "engine-independent control" even for instrumented
engine runs; the explicit loaded-module inventory is authoritative. This labeling defect was
corrected in the diagnostic tool; raw evidence was preserved. Event timestamps are userspace
drain/observation times, not exact kernel event times. Reported windows bound sampled absence
and presence; they do not identify the first filesystem operation's exact nanosecond.

## Deliverables and integrity

The full committed repository includes all original Phase 7B media/reports/failures, new
read-only summaries, raw lifecycle traces, four focused JUnit results, guard source and denial
records, capability failures/calibration and reproduction instructions. Original Phase 7B
FILE_HASHES entries remain unchanged and are reverified. All baseline source/test/media blob
identities are checked; only README/AGENTS gain documentation for this investigation. Lint,
format and C compilation checks pass. No new wheel or full-suite claim is made for unchanged
runtime code. The complete Git archive, file/blob/manifest verification and commit identity
are supplied for independent review. The host's persistent cleanup gate remains blocked.
