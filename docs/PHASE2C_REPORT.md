# Phase 2C — deployment gate evidence

Status: **tooling implemented; actual Muse Spark VM validation pending**.
Approved starting point: `7133f244`, Phase 2B. Branch: `phase2c-cloud-validation`.
No target session/remote execution access was available. Do not interpret this report as
successful target deployment or authorization for visual/character systems.

## Evidence by scope

| Scope | Result |
| --- | --- |
| Development host | Doctor, fresh offline installation, eight sequential encode/full-decode jobs, repeat determinism, handled SIGTERM recovery and automated tests passed |
| Actual target VM | **Not run**; exact commands in TARGET_VM_DEPLOYMENT.md |
| Natural 0.4–1.0 GiB available window | Not observed; unverified |
| Ordinary-user target operation | Unverified; development ran as UID 0, CI separately exercises ordinary runner operation |
| Dedicated hard memory enforcement | Unavailable here; read-only cgroup, no delegation assumed or changes made |
| Architectural deployment approval | Pending target evidence and external review |

Machine-readable evidence: [readiness](../artifacts/phase2c/development_readiness.json),
[measured results](../artifacts/phase2c/development_results.json),
[recovery](../artifacts/phase2c/development_recovery.json), and
[target status](../artifacts/phase2c/target_vm_status.json).
The compact committed report retains full resource/metadata records but replaces each long
frame-hash list with its count and SHA256 of newline-joined hashes. The complete raw lists
remain in local `outputs/phase2c-dev-600-final/`; the harness regenerates those full records.
No new videos or wheel binaries are required in Git; Phase 2B review videos remain available.

## Narrow changes

- `tools/deployment_check.py`: stdlib bootstrap, actionable Python/dependency/native/encoder,
  CPU/cgroup, memory, pressure/balloon hints, workspace and target-characteristic diagnostics.
- `tools/cloud_validate.py`: persistent directories, exclusive workspace lock, eight serial
  short/long/repeat jobs, full decode/metadata checks and supervisor-tree resource sampling.
- `tools/recovery_check.py`: real handled SIGTERM with observed child cleanup and output checks.
- `tools/wheelhouse.py`: streaming wheel hashes, exact metadata/pins, binary-only offline
  installation into a new venv using persistent temporary space. CI builds/distributes bundle.
- `resources/deployment.py` and small `monitor.py` extensions: disk/memory admission and
  runtime observations, pressure/cgroup readout, cancellation on failed guards.
- Existing engineering renderer script gains bounded frame counts, timeout, CPU/pressure/disk
  reporting and handled SIGTERM. Cairo backend, encoder, drawing contract, manifest and
  installed agent CLI remain unchanged. Package version 0.4.0; dependency graph unchanged.
- Tests, CI, README/AGENTS/roadmap and deployment documentation updated. Full changed-file
  list is the branch diff against `7133f244`.

## Development measurements

Ubuntu 24.04.3 x86_64, CPython 3.12.14, AMD EPYC processor, 9 affinity CPUs with cgroup quota
8 CPU equivalents. Host MemTotal 9.73 GiB, cgroup memory.max 8 GiB, no host swap.
This differs materially from the supplied 4-vCPU target. Native Cairo 1.18.0,
Pycairo 1.29.2 and FFmpeg 6.1.1/libx264; exact build string is in raw evidence.
Workspace free ~59.5 GiB; `/tmp` ~63 GiB, unlike the target's small temporary filesystem.

Fresh runtime was installed solely from the sealed eight-wheel bundle. Pycairo was built on
the development builder with X11 disabled; installation used no source compilation.
The following actual command ran using that fresh runtime:

```bash
/workspace/scratch/6ba0d4b7730a/phase2c-fresh/bin/python tools/cloud_validate.py --workspace . --run-directory outputs/phase2c-dev-600-final --scope development --long-frames 600 --timeout 180
```

Eight jobs, 3,000 total frames, ~51.57 seconds including supervisor/doctor/full verification.
All output codec/resolution/yuv420p/30-FPS/duration/frame-count checks passed. Each complete
MP4 decoded successfully. All four repeat pairs had identical decoded RGB SHA256 lists;
motion was present. Determinism is same native build, not a cross-build H.264 byte guarantee.

| Size | Frames per run | Encode time, two runs (s) | Encoded FPS | Peak renderer RSS (MiB) | Peak encoder RSS (MiB) | Peak worker tree RSS (MiB) | MP4 bytes each |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| 360×640 | 150 | 1.294 / 1.103 | 115.9 / 136.0 | 16.88 | 41.74 | 58.62 | 536,332 |
| 360×640 | 600 | 3.998 / 4.336 | 150.1 / 138.4 | 17.09 | 41.05 | 58.05 | 1,302,089 |
| 720×1280 | 150 | 2.243 / 2.316 | 66.9 / 64.8 | 19.74 | 66.31 | 86.03 | 1,415,235 |
| 720×1280 | 600 | 8.387 / 8.199 | 71.5 / 73.2 | 19.75 | 66.41 | 86.14 | 3,534,995 |

The **supervisor plus all descendants** sampled simultaneous peak was **102.87 MiB**
(107,864,064 bytes), below the provisional 256 MiB envelope on this host. Worker tree figures
include renderer plus encoder/verification, not supervisor. Adding independent peak columns
would not yield a measured simultaneous peak. CPU user/system times and full decode wall times
are retained per job in the machine-readable report.

Effective available memory: initial supervisor sample **7,786.47 MiB**, observed minimum **7,709.89 MiB**,
final **7,771.88 MiB**. No low-available-memory window was tested. Cgroup memory.peak was
~789 MiB before and after (shared, historical, not this job's peak); all memory.events deltas
including OOM/OOM-kill were zero. RSS sampling can miss short peaks and double-count shared
pages; these results are estimates, not hard enforcement. PSI was unavailable; exposed
balloon counters were zero, which cannot exclude pressure outside the guest.

## Resource policy decision

Retain **256 MiB job + 64 MiB reserve**, 320 MiB admission; add 384 MiB long-job admission.
The measurements leave headroom for the diagnostic on the development host but cannot establish
safety with the target's ballooning/competing processes. No limits were lowered to pass.
Monitor available memory during jobs, refuse unknown capacity, stop below reserve or over tree
budget, enforce disk admission/reserve, and record OOM counters. No host memory/swap settings
were changed, and no artificial memory/disk pressure was created.

Dedicated cgroup enforcement is not available here. The existing admission rule counts cgroup
headroom, so an exact 256 MiB dedicated cap would conflict with 320 MiB admission. That requires
a reviewed accounting design and actual delegated scope; no untested enforcement is installed.

## Tests and recovery

124 automated tests passed with the Cairo extra, preserving the 103 baseline tests. Added
coverage exercises corrupt/malicious wheel manifests, exact pins, duplicate/unlisted wheels,
existing-environment protection, mocked low-memory/disk refusal, monitor cancellation,
workspace locks, transaction reconciliation and an actual 450-frame CLI render/full decode.
Existing regressions cover missing encoder/tools, early exit, broken pipe, timeout, cancellation,
write failures, surface cleanup, deterministic geometry, dimensions/stride/byte counts, output
protection and metadata. Ruff lint/format and package/base-install checks are recorded in CI.

Actual recovery: SIGTERM during active 720p encoding returned worker exit **130**,
no observed live encoder remained, no incomplete final MP4 was published, private transactions
were cleaned and the existing-output sentinel was unchanged. Mocked scarcity tests do not
claim real low-memory/low-disk target validation. A first development harness attempt exposed
an erroneous tool timeout argument passed to verification; it was corrected and the actual
long CLI regression now covers that path. Only the subsequent complete successful run is evidence.

## Remaining risks and next milestone

Target hardware, ordinary-user native installation and naturally low available memory remain
unverified. Cooperative monitoring cannot prevent sudden external OOM or survive host loss;
SIGKILL can bypass Python cleanup. Cgroup counters are shared; container ancestors/ballooning
may impose limits not fully visible inside the guest. Wheelhouse compatibility and artifact
trust/expiry require operator care. Encoder atomic output completion is separate from later
verification status. Larger future scenes can consume more memory than this diagnostic.

**Recommendation:** retain the accepted renderer/pipeline and conservative policy. Have the
cloud agent run the documented target checks sequentially and submit reports/MP4s for review.
If resources refuse admission, fix provisioning/headroom rather than lowering thresholds.
Do not advance to the next engine milestone until the actual deployment gate is accepted.
