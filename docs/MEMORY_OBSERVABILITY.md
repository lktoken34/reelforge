# Memory observability — Phase 2C.1

This is an engineering admission/monitoring policy, not an agent episode capability or hard
resource sandbox. Defaults remain fail-closed. No resource numbers are exposed as CLI overrides.
Budget 256 MiB, reserve 64 MiB, admission 320 MiB, long-job admission 384 MiB remain unchanged.

## Evidence and detection

The target ZIP reports absent `memory.max/current/events`, empty `cgroup.controllers` and
653–818 MiB guest MemAvailable. It proves the previous refusal, but **does not establish why
the controller is unavailable**. It contains no mountinfo, hierarchy membership, kernel
controller inventory, container markers or virtualization probes. Preserve that evidence;
new admission is not authorized solely by those old null values.

`resources/memory.py` reads `/proc/self/cgroup`, `/proc/self/mountinfo`, `/proc/cgroups` and
strictly parsed `/proc/meminfo`. It records status (`present`, `missing`, `unreadable`, `invalid`)
for each attempted file. Observations are bounded to 128 KiB each. Permission errors never
become evidence of absence. It resolves mount roots and escaped mount paths, rejects
membership/mount contradictions, ambiguous multiple memory mounts, escaping paths, controller
overmounts and symlinks. It does not guess a process path underneath `/sys/fs/cgroup`.

For v2, it reads limit/usage at the leaf **and every visible ancestor through the mount root**.
Effective available is the minimum of guest MemAvailable and every finite limit minus its
corresponding usage. An explicit `max` is unlimited at that node, but still requires valid
usage and does not remove ancestor limits. Inconsistent, partial or over-limit observations
refuse admission. A genuine hierarchy root can lack memory accounting; that absence is not
interpreted as an unlimited node.

V1 support is intentionally narrow: one reliably mapped memory hierarchy, valid kernel
membership, readable `memory.limit_in_bytes`, `memory.usage_in_bytes` and
`memory.use_hierarchy=1` at visible ancestors; leaf `memory.stat` must expose
`hierarchical_memory_limit` without a smaller unseen inherited limit. Huge numeric v1 limits
remain finite numbers; no guessed unlimited sentinel is needed. Unsupported or incomplete
v1 topology fails closed. V1 OOM/fail counters are recorded when present but never fabricated
into v2 `memory.events` or a zero-OOM claim.

Kernel controller inventories vary across versions: a missing `memory` row alone does not
prove the kernel has no controller. Positive v2 accounting always takes precedence. Conversely,
an enabled/bound kernel memory controller with no accessible accounting, an advertised memory
controller without accounting, unreadable topology or masked/mismatched mounts blocks fallback.

## Explicit policies

Every relevant engineering entry point accepts the same documented flag:

```text
--memory-policy strict                 # default
--memory-policy guest_procfs_fallback  # explicit operator authorization/assertion of guest VM
```

`strict` uses validated cgroup accounting plus guest availability; unknown effective capacity
is zero/refused. Valid known-limit/unlimited cases retain their bounds. Some malformed or
partially readable cases are now more conservative than the earlier detector.

`guest_procfs_fallback` first attempts the **same controller discovery**. A real discoverable
limit always applies, regardless of the flag. Fallback is eligible only if the observed
controller inventory/membership/mount view consistently exposes no usable memory controller,
without unreadability or contradictory positive evidence. With no cgroup mounts, memberships
must also be absent and the inventory must not indicate an enabled/bound memory controller.

Additional checks restrict this opt-in to the supplied guest profile: Ubuntu 24.04 x86_64,
four affinity CPUs, 7–8.5 GiB MemTotal, no guest swap, ordinary ext4/xfs/btrfs root mount,
no known Docker/container marker files, and virtualization evidence from a hypervisor CPU
flag or recognized virtual DMI product. Missing/ineligible checks refuse fallback. These are
**necessary screening checks, not authenticated VM identity or proof of no hidden limits**.
The operator's explicit flag asserts this really is the intended guest; it is not appropriate
for an unidentified container. Unexpected root filesystems or DMI must be investigated rather
than worked around by editing checks. The pending target may still refuse if its new probes
show ambiguity. That is a legitimate blocked result, not grounds to lower thresholds.

Eligible fallback uses validated guest MemAvailable, never total/free RAM or an invented
capacity. Reports name `memory_source=guest_procfs`, `fallback_enabled`, `fallback_used`,
`guest_checks`, exact observations and limitations. Supplying the flag on a controller-capable
host reports enabled=true, used=false and continues respecting limits.

## Consistent lifecycle

The offline installer, doctor, validation supervisor, worker, runtime JobMonitor, recovery
check and legacy video benchmark propagate the selected policy explicitly. No hidden env
switch or manifest field selects it. Supervisor verifies the policy reported by its worker.
Installer runs venv/pip through bounded cancellable subprocesses under the same monitor;
its temporary directory is on persistent storage. Optional installer `--report` records
admission/whole-install memory or the refusal snapshot. No native compilation is allowed.

Monitor samples tree RSS ~10 ms and re-observes availability/topology ~100 ms plus endpoints.
It cancels below reserve, above budget, or when observation fails. A previously visible
controller/ancestor cannot disappear into fallback during a job. Losing OOM telemetry records
an observation gap even if it returns by the end. Long workers independently recheck 384 MiB
admission; the supervisor also checks before launch. No complete video or float frame buffer
is collected. Job matrices remain small and serial.

## Success, telemetry and approval are independent

Worker `technical_rendering_success=true` means encoding/full decode/metadata/motion and
surface cleanup completed. Its exit 0 is rendering success, not deployment certification.
The supervisor additionally compares repeat decoded content and separates these fields:

| Field/status | Meaning |
| --- | --- |
| `technical_rendering_success` | All requested profiles/repeats rendered and decoded; false for failed/incomplete/skipped jobs |
| `memory_observability` | Source/policy/fallback use, OOM counters available, nullable event delta/change and limitations |
| `technical_run_passed` | Rendering success with sufficient continuous OOM telemetry, no observed OOM changes and no errors |
| `validation_status=validated`, exit 0 | Technical checks met; still no deployment approval |
| `rendered_with_observability_limitations`, exit 3 | Rendering succeeded, but OOM telemetry was unavailable/incomplete; review required |
| `failed_or_incomplete`, exit 2 | Refused, failed, interrupted or incomplete matrix; do not proceed |
| `deployment_gate_approved` | Always false; only independent external review can accept the deployment gate |

Unknown `memory.events` produces null event deltas, not zero OOMs. A fallback render therefore
normally exits 3 from the supervisor, preserving successful video evidence without pretending
technical certification. A short-only run certifies only its explicitly requested short scope;
it is not the long matrix. `target_vm_verified` also remains false pending independent review.

## Remaining limits and read-only probes

The mount namespace may hide host/container ancestors, and procfs/DMI are not cryptographically
authenticated. Guest MemAvailable cannot reveal all hypervisor reservations or enforcement.
Ballooning and other jobs can reduce memory suddenly, faster than cooperative monitoring.
A read-only observation is not a dedicated cgroup cap. No cgroups, swap, memory limits or
host-wide settings are modified; no artificial pressure is generated. SIGKILL/host loss can
bypass Python cleanup, as documented in Phase 2C.

`python3.12 -S tools/memory_probe.py --report PATH` works before package installation and saves
the probes/pressure evidence. For provider investigation also return read-only outputs of
`cat /proc/1/cgroup`, `readlink /proc/self/ns/cgroup`, `readlink /proc/1/ns/cgroup`,
`cat /proc/cmdline` and the mount/kernel probes in that report if the topology is rejected.
These establish more context but cannot authenticate the intended VM. Do not mount controllers
or change provider settings as part of this task.

Semantics consulted: [kernel cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)
and [v1 memory controller](https://docs.kernel.org/admin-guide/cgroup-v1/memory.html).
