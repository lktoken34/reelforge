"""Sequential deployment gate harness. Development evidence never certifies the Muse target."""

import argparse
import fcntl
import json
import signal
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from deployment_check import inspect_deployment

from reelforge.core.errors import OperationError
from reelforge.media.process import run_bounded
from reelforge.resources.deployment import check_workspace, event_delta, memory_observability
from reelforge.resources.memory import add_memory_policy_argument
from reelforge.resources.monitor import MIB, JobMonitor, memory_snapshot, preflight_memory


@contextmanager
def workspace_lock(workspace: Path):
    with (workspace / ".reelforge-validation.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise OperationError(
                "VALIDATION_BUSY", "Another validation owns this workspace"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def reconcile_case(directory: Path) -> list[str]:
    """Only call after the sole worker in this fresh private case directory has been reaped."""
    removed = []
    for transaction in directory.glob(".reelforge-encode-*"):
        if transaction.is_symlink():
            raise OperationError("TRANSACTION_PATH", "Refusing a symlink transaction directory")
        for item in transaction.iterdir():
            if item.name != "pending.mp4" or item.is_symlink():
                raise OperationError(
                    "TRANSACTION_PATH", f"Unexpected transaction content: {item.name!r}"
                )
            item.unlink()
            removed.append(str(item))
        transaction.rmdir()
    return removed


def validate(
    workspace: Path,
    run_directory: Path,
    *,
    scope: str,
    long_frames: int,
    timeout: float,
    memory_policy: str = "strict",
    short_only: bool = False,
) -> dict:
    workspace = workspace.resolve()
    run_directory = run_directory.resolve()
    if workspace != run_directory and workspace not in run_directory.parents:
        raise OperationError(
            "RUN_PATH", "Run directory must remain inside the persistent workspace"
        )
    check_workspace(workspace)
    result = {
        "schema": "reelforge.cloud-validation.v1",
        "scope": scope,
        "target_vm_verified": False,
        "target_vm_status": "pending_no_target_vm_access"
        if scope == "development"
        else "operator_reported_target_requires_review",
        "technical_run_passed": False,
        "technical_rendering_success": False,
        "validation_status": "not_completed",
        "memory_policy": memory_policy,
        "short_only": short_only,
        "deployment_gate_approved": False,
        "jobs": [],
        "errors": [],
        "policy": {"job_budget_mib": 256, "reserve_mib": 64, "long_launch_minimum_mib": 384},
        "run_directory": str(run_directory),
    }
    monitor = None
    before = memory_snapshot(memory_policy=memory_policy)
    started = time.perf_counter()
    with workspace_lock(workspace):
        run_directory.mkdir(parents=True, exist_ok=False)
        try:
            doctor = inspect_deployment(workspace, memory_policy=memory_policy)
            result["readiness"] = doctor
            if not doctor["ok"]:
                raise OperationError(
                    "DEPLOYMENT_NOT_READY", "Resolve readiness report errors before rendering"
                )
            if scope == "target_vm" and not doctor["target_identity_matches"]:
                raise OperationError(
                    "TARGET_IDENTITY", "Observed host differs from supplied target characteristics"
                )
            with JobMonitor(workspace=workspace, memory_policy=memory_policy) as monitor:
                for width in (360, 720):
                    for frames in (150,) if short_only else (150, long_frames):
                        reference_hashes = None
                        for repeat in (1, 2):
                            snapshot = memory_snapshot(memory_policy=memory_policy)
                            preflight_memory(snapshot=snapshot, memory_policy=memory_policy)
                            if frames > 150 and snapshot["effective_available_bytes"] < 384 * MIB:
                                result["jobs"].append(
                                    {
                                        "width": width,
                                        "frames": frames,
                                        "status": "skipped_insufficient_long_headroom",
                                        "available_bytes": snapshot["effective_available_bytes"],
                                    }
                                )
                                break
                            check_workspace(workspace)
                            case = run_directory / f"{width}_{frames}_{repeat}"
                            case.mkdir()
                            output, report = case / "diagnostic.mp4", case / "job.json"
                            command = [
                                sys.executable,
                                str(Path(__file__).with_name("render_video.py").resolve()),
                                "--memory-policy",
                                memory_policy,
                                "--width",
                                str(width),
                                "--frames",
                                str(frames),
                                "--timeout",
                                str(timeout),
                                "--output",
                                str(output),
                                "--report",
                                str(report),
                            ]
                            try:
                                rc, out, err = run_bounded(
                                    command,
                                    timeout=timeout + 120,
                                    max_bytes=65536,
                                    cancelled=monitor.cancelled,
                                )
                            finally:
                                reconciled = reconcile_case(case)
                            data = json.loads(report.read_text()) if report.is_file() else None
                            entry = {
                                "width": width,
                                "frames": frames,
                                "repeat": repeat,
                                "admission_memory": snapshot,
                                "exit_status": rc,
                                "supervisor_reconciled": reconciled,
                                "report": data,
                                "status": "passed" if rc == 0 else "failed",
                            }
                            result["jobs"].append(entry)
                            if rc or data is None or data.get("ok") is False:
                                entry["stderr_tail"] = err.decode(errors="replace")[-4096:]
                                raise OperationError(
                                    "WORKER_FAILED",
                                    "Worker failed; inspect its bounded error report",
                                )
                            if data.get("transaction_clean") is not True:
                                raise OperationError(
                                    "TRANSACTION_CLEANUP", "Worker cleanup was not confirmed"
                                )
                            if data["memory_observability"]["policy"] != memory_policy:
                                raise OperationError(
                                    "MEMORY_POLICY", "Worker policy differs from supervisor"
                                )
                            if data["whole_job_memory"]["encoder_peak_rss_bytes"] <= 0:
                                raise OperationError(
                                    "METRICS_MISSING", "Encoder RSS was not observed"
                                )
                            hashes = data["verification"]["decoded_rgb_sha256"]
                            if reference_hashes is not None and hashes != reference_hashes:
                                raise OperationError(
                                    "DECODE_MISMATCH", "Repeated decoded visual content differs"
                                )
                            reference_hashes = hashes
                            entry["repeat_content_matches"] = True
                            print(
                                json.dumps(
                                    {
                                        "completed": case.name,
                                        "tree_peak_mib": data["whole_job_memory"][
                                            "estimated_simultaneous_tree_peak_rss_bytes"
                                        ]
                                        / MIB,
                                    }
                                ),
                                flush=True,
                            )
            completed = [j for j in result["jobs"] if j["status"] == "passed"]
            result["technical_rendering_success"] = len(completed) == (4 if short_only else 8)
            result["technical_run_passed"] = result["technical_rendering_success"]
            result["low_available_window_observed"] = any(
                j["admission_memory"]["effective_available_bytes"] <= 1024 * MIB for j in completed
            )
            result["target_vm_status"] = (
                "pending_no_target_vm_access"
                if scope == "development"
                else "operator_target_evidence_pending_architect_review"
            )
        except (
            OperationError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            KeyboardInterrupt,
        ) as error:
            result["errors"].append(
                {
                    "code": getattr(
                        error,
                        "code",
                        "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "VALIDATION_IO",
                    ),
                    "message": str(error),
                }
            )
        finally:
            after = memory_snapshot(memory_policy=memory_policy)
            result["memory_before"], result["memory_after"] = before, after
            result["cgroup_memory_event_delta"] = event_delta(before, after)
            observability = memory_observability(before, after)
            if monitor is not None and not monitor.oom_telemetry_continuous:
                observability["sufficient_for_technical_validation"] = False
                observability["limitations"].append(
                    "OOM telemetry was not continuous during sampling"
                )
            if any(
                not (j.get("report") or {})
                .get("memory_observability", {})
                .get("sufficient_for_technical_validation", False)
                for j in result["jobs"]
            ):
                observability["sufficient_for_technical_validation"] = False
                observability["limitations"].append(
                    "At least one worker lacks complete OOM observability"
                )
            result["memory_observability"] = observability
            # Retain uncertainty without conflating completed video with missing OOM telemetry.
            result["technical_run_passed"] = (
                result["technical_rendering_success"]
                and observability["sufficient_for_technical_validation"]
                and not result["errors"]
            )
            result["validation_status"] = (
                "validated"
                if result["technical_run_passed"]
                else "rendered_with_observability_limitations"
                if result["technical_rendering_success"] and not result["errors"]
                else "failed_or_incomplete"
            )
            if monitor is not None and hasattr(monitor, "final"):
                metrics = monitor.report()
                metrics["root_role"] = (
                    "validation_supervisor; per-job renderer/encoder are in job reports"
                )
                result["supervisor_and_descendants_memory"] = metrics
            result["wall_seconds"] = time.perf_counter() - started
            (run_directory / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_memory_policy_argument(parser)
    parser.add_argument(
        "--short-only",
        action="store_true",
        help="Run both 150-frame profiles before authorizing long jobs",
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--scope", choices=("development", "target_vm"), required=True)
    parser.add_argument("--long-frames", type=int, choices=(450, 600, 900), default=600)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()

    def interrupt(signum, frame):
        raise KeyboardInterrupt("Validation interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    try:
        result = validate(
            args.workspace,
            args.run_directory,
            scope=args.scope,
            long_frames=args.long_frames,
            timeout=args.timeout,
            memory_policy=args.memory_policy,
            short_only=args.short_only,
        )
    except (OperationError, OSError) as error:
        print(
            json.dumps(
                {
                    "technical_run_passed": False,
                    "technical_rendering_success": False,
                    "validation_status": "not_completed",
                    "memory_policy": args.memory_policy,
                    "short_only": args.short_only,
                    "target_vm_verified": False,
                    "error": {
                        "code": getattr(error, "code", "VALIDATION_IO"),
                        "message": str(error),
                    },
                }
            )
        )
        raise SystemExit(2) from error
    print(
        json.dumps(
            {
                "technical_run_passed": result["technical_run_passed"],
                "technical_rendering_success": result["technical_rendering_success"],
                "validation_status": result["validation_status"],
                "target_vm_status": result["target_vm_status"],
                "results": str(args.run_directory / "results.json"),
            }
        )
    )
    raise SystemExit(
        0
        if result["technical_run_passed"]
        else 3
        if result["technical_rendering_success"] and not result["errors"]
        else 2
    )


if __name__ == "__main__":
    main()
