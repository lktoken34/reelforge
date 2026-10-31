# Target VM deployment and validation

**Phase 2C.1 update:** the original target attempt was blocked at admission; no render ran.
Use [the updated cloud prompt](TARGET_VM_PHASE2C1_PROMPT.md) and
[memory-observability contract](MEMORY_OBSERVABILITY.md) for the new explicit guest policy
and wheelhouse. Commands below document the original strict Phase 2C workflow.


Phase 2C is engineering tooling only. Phase 2B baseline: `7133f244`.
The Muse Spark VM has **not** been tested from this workspace. Development evidence is
supplementary. Neither matching host characteristics nor a zero exit code authenticates
VM identity or grants architectural approval.

## Prerequisites and installation

Target: Ubuntu 24.04 x86_64, CPython 3.12 with `venv`/pip, 4 vCPUs, no GPU or swap,
7.7 GiB reported RAM, often 0.4–1.0 GiB available, 512 MiB `/tmp`, persistent home disk.
Ask the provider/admin to provision native packages if absent:

```bash
# One-time administrative provisioning; ordinary installation/rendering needs no sudo.
sudo apt-get update
sudo apt-get install --no-install-recommends python3.12 python3.12-venv libcairo2 ffmpeg git unzip
```

FFmpeg must expose **libx264**, and ffprobe must be installed. There is no codec fallback.
The doctor checks exact Python distribution versions, native Cairo import, both media
tools, encoder availability, CPU affinity/quota, cgroup memory, swap, pressure indicators,
filesystem capacity and ordinary writes/fsync. Missing requirements produce JSON errors.
Native ABI compatibility is confirmed by import and the actual render, not wheel names alone.

Do not compile Pycairo on the constrained VM. On GitHub Actions, open the successful
`cairo-checks` job for this branch and download artifact
`reelforge-v2-py312-ubuntu24-x86_64-wheelhouse`. Its Ubuntu 24.04 x86_64/Python 3.12
builder compiles Pycairo with X11 disabled, downloads binary-only remaining dependencies,
seals exact versions/hashes, then tests a fresh offline installation and 450-frame render.
Artifacts expire after 30 days; rerun that workflow to rebuild. Obtain the archive from
the trusted repository/run and extract its **contents** into the directory below.
Checksums detect corruption, not malicious replacement of both wheels and manifest.

Run these commands as the VM's ordinary user, sequentially. The wheelhouse directory must
contain `manifest.json`, `requirements.lock` and the `.whl` files directly, not a nested folder.
Use new paths for a rerun; existing virtual environments and validation runs are protected.

```bash
mkdir -p "$HOME/reelforge-work" "$HOME/reelforge-wheelhouse"
cd "$HOME/reelforge-work"
git clone --branch phase2c-cloud-validation https://github.com/lktoken34/reelforge.git
cd reelforge
# Extract the trusted CI artifact into $HOME/reelforge-wheelhouse before continuing.
python3.12 tools/wheelhouse.py verify --directory "$HOME/reelforge-wheelhouse"
python3.12 tools/wheelhouse.py install --directory "$HOME/reelforge-wheelhouse" --venv "$HOME/reelforge-runtime"
mkdir -p outputs/target-evidence
"$HOME/reelforge-runtime/bin/python" tools/deployment_check.py --workspace "$PWD" --report outputs/target-evidence/readiness.json
"$HOME/reelforge-runtime/bin/python" tools/cloud_validate.py --workspace "$PWD" --run-directory outputs/target-evidence/run-600 --scope target_vm --long-frames 600 --timeout 180
"$HOME/reelforge-runtime/bin/python" tools/recovery_check.py --workspace "$PWD" --report outputs/target-evidence/recovery.json
```

Stop on any nonzero exit and inspect the JSON error. Do not lower limits or repeat a failing
job until its dependency/resource cause is resolved. No root is needed after native
provisioning. Installation uses local wheels, hash verification, binary-only pip and a
persistent temporary directory beside the requested venv, without package-network access.
A failed install can leave an incomplete venv: preserve diagnostics, remove only that known
failed environment manually, or choose a new path. Never overwrite an active/successful venv.

If native Cairo fails, check `libcairo2` and the bundle's OS/architecture/Python ABI;
if binary wheels do not match, rebuild on a compatible roomy builder. Do not enable
source installation on the VM. Base agent commands still work without the renderer extra.

## What the harness does

One workspace lock serializes harness/recovery invocations. Do not run standalone renderer,
install, or other heavy jobs alongside it; a lock cannot constrain unrelated processes.
The bootstrap doctor is stdlib-only and refuses native probes when memory admission fails.
Trusted checkout helpers bootstrap resource inspection; installed distribution versions and
native binding compatibility are checked separately. It is not a sandbox for untrusted code.

The matrix is 360×640 and 720×1280, 30 FPS, 150 frames and 600 frames, **two runs of each**:
8 serial jobs, 3,000 frames. `--long-frames` also accepts 450 or 900; do not reduce the memory
policy to force a pass. Each worker renders/encodes sequentially using the unchanged Phase
2B pipe, probes metadata, decodes the complete MP4, counts frames, checks motion and compares
repeat decoded RGB hashes. Per-frame hashes are small strings, never stored frame images or
whole videos. Output MP4s, per-job reports and `results.json` stay in the persistent run directory.

The supervisor measures itself plus workers/tool descendants, while each worker reports
renderer/encoder RSS separately, CPU user/system time, encode and total wall time, effective
encoded FPS, bytes, exit status, initial/final/minimum available memory, disk and cgroup/pressure
observations. Sampled RSS is an estimate, not an OOM-proof cap; shared pages can be counted twice.
Cgroup peak/events cover the shared cgroup, not solely this job. No pressure is manufactured.

For development use the same command with `--scope development`. Target scope additionally
requires the supplied OS/CPU/RAM/swap/tmp characteristics; mismatches require investigation,
not relabeling a development machine. `target_vm_verified` and `deployment_gate_approved`
remain false until independent review. A target operator must attest where/how it was run.

## Resource policy and cgroups

- Keep the accepted 256 MiB job envelope plus 64 MiB available-memory reserve: admission
  needs at least **320 MiB effective available** (minimum of host MemAvailable and current
  cgroup headroom). Unknown cgroup capacity refuses admission under strict policy.
- Long jobs additionally require **384 MiB** at launch. If insufficient, report a skip and
  no overall technical pass. This is extra caution, not a reduced threshold.
- Sample tree RSS every ~10 ms; available memory/disk about every 100 ms plus endpoints.
  Cancel if tree exceeds 256 MiB, available memory drops below 64 MiB, disk below 64 MiB,
  or monitoring fails. Workspace admission requires 256 MiB free and successful writes.
- At 0.4 GiB available, admission may pass; safety on that VM is still unproven. A fast
  external memory loss can outrun cooperative monitoring. PSI/balloon counters are best effort;
  missing readings do not prove absence of host pressure/ballooning.

The doctor only reads cgroup v2 capabilities. The development mount was read-only, with no
delegation. Even a writable directory does not establish delegated controllers. Never create
subgroups, modify host memory/swap, or assume unprivileged `memory.max` permission.
If the provider offers a delegated job scope, investigate and review its accounting separately.
An exact 256 MiB cgroup cap conflicts with the current 320 MiB admission rule when the reserve
is counted inside that cap; do not bypass admission to make this experiment pass. Hard
per-job enforcement is **not implemented** in this milestone. OOM/kill counter changes or
unavailable OOM counters prevent a technical pass; Phase 2C.1 separately records successful
rendering with telemetry limitations (supervisor exit 3).

## Recovery and evidence handoff

SIGTERM/SIGINT handling unwinds worker/encoder contexts; the bounded subprocess utility
terminates/reaps children. Recovery waits for active encoding, sends real SIGTERM and checks
no surviving observed encoder, no published incomplete final, private transaction cleanup
and an existing success sentinel. Regression tests also protect existing destinations and
exercise write failure/cancellation/timeouts. Simulated low memory/disk tests never fill the VM.
The supervisor reconciles only its own fresh private job transaction after reaping that worker.
It refuses unexpected files/symlinks; there is no broad delete of stale transactions.

External SIGKILL, host loss or disk disappearing during cleanup are outside handled recovery.
Do not treat stale files as successes or automatically delete transactions belonging to a live job.
Encoder atomic publication certifies encoding completion; inspect the separate verification
report before treating an MP4 as a validated result. A later verification failure can leave a
fully encoded diagnostic MP4 for investigation, with no successful benchmark status.

Return readiness.json, complete run `results.json` and job reports, recovery.json, exit statuses,
checkout SHA, ordinary-user identity, and VM identity confirmation. Retain MP4s on persistent
disk for review. Record whether the natural 0.4–1.0 GiB window was observed; do not allocate
artificial pressure to reach it. If not observed, that condition remains unverified. Stop after
Phase 2C for architectural review.

## Rebuild bundle on a roomy matching Linux builder

Native build prerequisites belong on the builder, not the deployment VM. Use the checked-in
CI steps as the executable recipe: frozen lock export, `pip wheel --no-deps
--config-settings=setup-args=-Dno-x11=true pycairo==1.29.2`, binary-only wheel download for
runtime pins, project wheel build, `wheelhouse.py seal`, then fresh offline proof. Pinning
includes every transitive runtime distribution and its selected wheel hash in each bundle.
See [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/) and
[kernel cgroup v2 delegation](https://docs.kernel.org/admin-guide/cgroup-v2.html#delegation).
