# Phase 2C.1 — VM memory detection compatibility

Baseline: `5aa5958e7a9ddf525dde3bfe392c30d922932cdb`.
Branch: `phase2c-vm-memory-compat`. Package: 0.4.1, unchanged native/Python dependency graph.
Status: implemented and development-tested; **Muse Spark re-validation remains pending**.
No new target session was available. This change does not approve deployment or begin Phase 3.

## Target evidence and diagnosis

The supplied ZIP's readiness JSON and summary are preserved under `artifacts/phase2c1/target_baseline_*`.
The original VM attempt correctly stopped at MEMORY_PREFLIGHT without creating a runtime or video.
It reported Ubuntu 24.04.5, 4 vCPUs, 7.7 GiB total and 653–818 MiB guest available, no swap/GPU,
Python 3.12.3, native Cairo and FFmpeg 8.1.2/libx264. Null controller files alone cannot show
whether memory accounting is absent, masked, unmapped or inaccessible. Missing probes included
self membership, mountinfo, kernel controller inventory and guest/container identity evidence.

The old detector conflated that unknown capacity with zero effective available. Strict policy
retains refusal; the new opt-in policy can admit a screened, consistently observed controller-free
guest without pretending the missing controller was unlimited. It may still correctly block
this target if the newly collected evidence is ambiguous. No target compatibility is claimed.

## Architecture and changed sources

[MEMORY_OBSERVABILITY.md](MEMORY_OBSERVABILITY.md) is the full contract and risk explanation.

- New `src/reelforge/resources/memory.py`: bounded read-only probes, v2 mount/member resolution,
  visible ancestor accounting, narrowly supported hierarchical v1, strict guest memory parsing,
  explicit strict/guest fallback policy, guest screening, exact evidence/status/source reporting.
- `resources/monitor.py`: shared policy at admission and runtime, source/ancestor-loss cancellation,
  continuous-telemetry tracking, endpoint reserve checks; existing tree RSS/disk guards retained.
- `resources/deployment.py`: memory observability separate from rendering/approval, robust event
  parsing, unavailable mapped-cgroup reporting and policy-aware readiness.
- `media/process.py`: optional explicit child environment for bounded subprocesses; installer
  uses it for persistent TMPDIR without shell execution. Encoder/drawing backend unchanged.
- Tools updated: `wheelhouse.py`, `deployment_check.py`, `cloud_validate.py`, `render_video.py`,
  `recovery_check.py`, `benchmark_video.py`; new stdlib-only `memory_probe.py` works pre-install.
  Explicit policy flags propagate everywhere; no hidden env override or episode field exists.
- Installer gains cancellable monitored venv/pip execution, optional persistent JSON report;
  sealed CI manifests identify the exact source commit. Binary-only/hash-verified install retained.
- Worker independently enforces 384 MiB long admission; supervisor short-only mode gates first
  target tests. Separate rendering/observability/approval fields and exit 3 preserve OOM uncertainty.
- Tests, CI, package version/lock and scope/deployment documentation updated. No Cairo primitive,
  animation geometry, encoder codec/settings or agent manifest/CLI capability was added or changed.

The 256 MiB job envelope, 64 MiB reserve, 320 MiB ordinary admission and 384 MiB long admission
are unchanged. A valid cgroup capacity always limits available memory even when fallback is
explicitly enabled. Unreadable/partial/contradictory observations do not qualify as absence.

## Actual development verification

Development machine: Ubuntu 24.04.3 x86_64, Python 3.12.14, Cairo 1.18.0, Pycairo 1.29.2,
FFmpeg 6.1.1. Nine affinity CPUs with eight-CPU quota, 8 GiB cgroup cap and ample available RAM;
UID 0. It is **not the Muse target**; no naturally low-memory window was tested.

| Check | Actual result |
| --- | --- |
| Full Cairo suite | **188 passed**, including all 124 prior tests and 64 additional cases |
| Base installed wheel suite, Cairo absent | **129 passed, 7 skipped** |
| Ruff lint / format / diff whitespace | Passed |
| Wheel and source archive | Built 0.4.1 successfully |
| Installed wheel outside checkout | Base capabilities/schema/validate and renderer imports passed; package paths confirmed |
| Fresh sealed offline renderer installation | Passed; installer admission and whole-tree monitoring recorded |
| Existing two static Cairo diagnostics | Generated both sizes; hashes in machine-readable verification evidence |
| Existing Phase 2B benchmark | Four actual 150-frame encode/full-decode jobs, both sizes/repeats; decoded repeat content identical |
| Strict supervisor short matrix | Four 150-frame jobs passed, full decode/repeat checks and OOM telemetry qualified; deployment approval false |
| Actual handled SIGTERM recovery | Exit 130, no observed encoder left, no incomplete final, successful sentinel preserved |
| Fallback | Controlled fixtures including actual short encode/decode under mocked observations; **not actual VM evidence** |

Strict supervisor-plus-descendants sampled peak was **109.34 MiB**. Existing video benchmark
worker peaks were ~58.2 MiB at 360p and up to ~89.8 MiB at 720p. Sampled RSS is not a hard cap and
can miss transients/double-count shared pages. Full raw reports remain under ignored `outputs/`;
committed compact reports retain metadata/resources and replace per-frame hash lists with digests.

Regressions cover valid/finite/unlimited v2, ancestors/mount roots, hierarchical v1, disabled/
absent controllers, enabled-but-unseen controllers, unreadable files, partial telemetry, malformed
paths/topology, invalid guest values, thresholds, explicit authorization, container screening,
reserve loss and controller disappearance during jobs, OOM gaps/missing counters, policy mismatch,
installer/doctor/worker/supervisor/recovery propagation, failed workers, private cleanup and
existing output preservation. Scarcity is mocked; no memory/disk pressure was generated.

One expanded failure fixture exposed a supervisor exception on a missing worker report; fixed
and covered. Development runs also detected retained private transaction paths after native
cleanup on this checkpointed workspace. The workflow refused success. The engineering worker
now confirms/reconciles only its reaped encoder's known private pending path, rejects unexpected
content/symlinks, and confirms removal before success. This mirrors the accepted supervisor
ownership restriction; no broad scavenging or encoder redesign was introduced. Subsequent tests
passed. Historical failed attempts remain under ignored outputs and are not counted as passes.

## Evidence, artifacts and target steps

- [Development verification](../artifacts/phase2c1/development_verification.json)
- [Strict short matrix](../artifacts/phase2c1/development_short_results.json)
- [Fresh install](../artifacts/phase2c1/development_install.json) and [doctor](../artifacts/phase2c1/development_readiness.json)
- [Handled recovery](../artifacts/phase2c1/development_recovery.json)
- [Explicitly simulated fallback evidence](../artifacts/phase2c1/fixture_evidence.json)
- [Cloud-agent prompt and exact commands](TARGET_VM_PHASE2C1_PROMPT.md)

CI built and verified a new `reelforge-v2-phase2c1-py312-ubuntu24-x86_64-wheelhouse` from code commit
`3aeb449aacde8313e19292fe0a263a025f70f3ce`. Both jobs in
[CI run 41229189609](https://github.com/lktoken34/reelforge/actions/runs/41229189609) passed:
188 Cairo tests, fresh offline install, 450-frame encode/full decode, strict probe and handled
recovery under UID 1001. [Artifact 13053051936](https://github.com/lktoken34/reelforge/actions/runs/41229189609/artifacts/13053051936)
is 778,056 bytes; its manifest identifies that exact source commit. Exact archive hash and
provenance are in [ci_evidence.json](../artifacts/phase2c1/ci_evidence.json). Use that bundle,
not the old 0.4.0 wheels. Follow-up commits update evidence/documentation only; runtime code
and artifact source stay at the SHA above.

The target sequence is: verify exact checkout/artifact; strict and explicitly authorized memory
probes; offline install; doctor; short-only matrix; longer matrix only after short encoding,
decoding/repeat and cleanup succeed; recovery; return reports. Exit 3 permits preserving/
continuing diagnostic evidence only when rendering succeeded with empty errors; it never means
qualified OOM telemetry or external deployment approval. A skipped/refused/failed job stops work.

## Remaining risks and review recommendation

No actual fallback render or new installation has run on Muse Spark. The supplied target may
fail further eligibility/topology probes, and FFmpeg 8.1.2/native ABI compatibility still needs
actual import/encode/decode checks. Guest/hypervisor identity cannot be authenticated by procfs
or DMI; hidden ancestor constraints can remain outside the namespace. Ballooning and external
contention can consume available memory faster than sampling/cancellation. No hard cgroup
sandbox is installed, no host settings were changed, and SIGKILL/host loss can bypass cleanup.

Missing OOM counters remain null/unavailable, never zero events. `technical_rendering_success`
may be true while `technical_run_passed` is false and deployment_gate_approved stays false.
Recommend review of this narrow compatibility change, then execute the supplied target prompt
and review its real reports. Stop after Phase 2C.1; do not begin Phase 3.
