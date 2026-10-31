# Cloud operator handoff — Phase 2C.1

Run only on the intended Muse Spark guest VM, sequentially as an ordinary user. Do not edit
engine source, lower thresholds, add swap, change cgroups or manufacture memory pressure.
Rendering is still diagnostic only; deployment approval remains false. Use the exact source
commit/artifact in `artifacts/phase2c1/ci_evidence.json` (from successful CI), not the old
0.4.0 wheelhouse. Record `id` and `git rev-parse HEAD`. If the current shell is root, arrange
an existing ordinary-user session without changing host policy, or report unprivileged testing
blocked. Stop on refusal or failed checks; return the evidence instead of applying workarounds.

The following flag is explicit authorization to use guest procfs **only if the detector's
eligibility checks pass**. It asserts the operator has identified this as the intended VM.
It does not ignore discoverable limits or authorize an arbitrary container fallback.

Verified bundle: [artifact 13053051936](https://github.com/lktoken34/reelforge/actions/runs/41229189609/artifacts/13053051936)
from exact source commit `3aeb449aacde8313e19292fe0a263a025f70f3ce`.
Archive SHA256: `26f958e494912d88e001e40f1f7c3fcd91c0066d2399df5ee974dc2b4488c092`.
The wheelhouse manifest must identify that source commit. Artifact retention is 30 days.
If it has expired, request a new CI artifact and provenance; do not substitute older wheels.

## 1. Prepare source and pre-install probes

```bash
cd "$HOME/reelforge-work/reelforge"
git fetch origin phase2c-vm-memory-compat
git switch phase2c-vm-memory-compat
git pull --ff-only
git rev-parse HEAD
id
mkdir -p outputs/target-2c1
python3.12 -S tools/memory_probe.py --memory-policy strict --report outputs/target-2c1/memory-strict.json
# A strict MEMORY_PREFLIGHT with absent controllers is expected; retain this report.
python3.12 -S tools/memory_probe.py --memory-policy guest_procfs_fallback --report outputs/target-2c1/memory-authorized.json
```

If the second probe exits 2, **stop**. Return both JSONs and SUMMARY describing failed checks.
The old ZIP is insufficient to establish eligibility; the new target run may still be blocked.
Do not modify markers/topology, impersonate a guest, or alter internal checks to pass.

## 2. Install verified prebuilt wheels, then doctor

Download the CI artifact identified in `artifacts/phase2c1/ci_evidence.json`, from the trusted
repository/run. Extract the ZIP contents to a **new** `$HOME/reelforge-wheelhouse-2c1` directory.
Confirm manifest `source_commit` exactly matches that evidence's source commit. It can differ
from a later documentation-only branch tip; compare the documented source commit and wheel
version 0.4.1. Manifest hashes detect corruption, not authenticity of an untrusted bundle.

```bash
python3.12 tools/wheelhouse.py verify --directory "$HOME/reelforge-wheelhouse-2c1"
python3.12 tools/wheelhouse.py install --directory "$HOME/reelforge-wheelhouse-2c1" --venv "$HOME/reelforge-runtime-2c1" --memory-policy guest_procfs_fallback --report outputs/target-2c1/install.json
"$HOME/reelforge-runtime-2c1/bin/python" tools/deployment_check.py --workspace "$PWD" --memory-policy guest_procfs_fallback --report outputs/target-2c1/readiness.json
```

Stop on nonzero install/doctor exit. These need Python 3.12 venv/pip, native Cairo,
FFmpeg/libx264 and ffprobe already provisioned. No ordinary step needs sudo or native
compilation. Keep all working files under persistent home/project paths. A prior failed
venv/run is never overwritten: choose a new path for reruns, preserving old evidence.

## 3. Short tests first

```bash
"$HOME/reelforge-runtime-2c1/bin/python" tools/cloud_validate.py --workspace "$PWD" --run-directory outputs/target-2c1/short --scope target_vm --short-only --memory-policy guest_procfs_fallback --timeout 180
```

Record exit status. Inspect `short/results.json`:

- Exit **2** or `technical_rendering_success=false`: stop. Do not run longer tests.
- Exit **3**, `technical_rendering_success=true`, empty `errors`, and
  `validation_status=rendered_with_observability_limitations`: short encode/decode/repeat/
  cleanup succeeded; OOM telemetry remains unknown. This is expected for eligible fallback,
  and permits continuing the diagnostic sequence without claiming a deployment pass.
- Exit **0** with `technical_run_passed=true`: short technical checks passed; still no independent
  deployment approval. Verify all four jobs passed, each report has `transaction_clean=true`,
  encoder exit 0, expected 150 decoded frames and repeat match before continuing.

## 4. Longer matrix and recovery, only after successful short checks

```bash
"$HOME/reelforge-runtime-2c1/bin/python" tools/cloud_validate.py --workspace "$PWD" --run-directory outputs/target-2c1/matrix-600 --scope target_vm --long-frames 600 --memory-policy guest_procfs_fallback --timeout 180
"$HOME/reelforge-runtime-2c1/bin/python" tools/recovery_check.py --workspace "$PWD" --memory-policy guest_procfs_fallback --report outputs/target-2c1/recovery.json
```

The matrix deliberately rechecks short profiles and runs everything serially. Record exit 0/3/2
separately from rendering/observability/approval fields. Long launch needs 384 MiB headroom;
a skipped/refused long job is incomplete, not a pass. Stop on matrix failure before recovery;
exit 3 with successful rendering and no errors is an observability-limited result, not failure
of rendering. Do not lower thresholds to finish the matrix.

Return all JSON evidence and a summary of checkout SHA, artifact source SHA/ID, VM identity,
ordinary-user execution, exit statuses, actual min/initial/final available RAM, renderer/encoder/
supervisor tree RSS, CPU/wall times, files/frame counts/metadata, decoded-repeat match,
cleanup and pressure/balloon readings. Preserve diagnostic MP4s for review. Missing OOM counters
must be reported as unavailable, never zero events. Do not claim actual low-memory-window
coverage unless naturally observed. Stop after Phase 2C.1 for external review.
