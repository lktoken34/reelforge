"""Handled SIGTERM recovery on one private diagnostic job; no artificial memory pressure."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from cloud_validate import reconcile_case, workspace_lock

from reelforge.resources.deployment import check_workspace
from reelforge.resources.memory import add_memory_policy_argument
from reelforge.resources.monitor import (
    namespace_pid,
    preflight_memory,
    process_tree,
    procfs_pid,
)


def check_recovery(workspace: Path, *, memory_policy: str = "strict") -> dict:
    workspace = workspace.resolve()
    check_workspace(workspace)
    preflight_memory(memory_policy=memory_policy)
    with workspace_lock(workspace):
        case = workspace / f"recovery-{time.time_ns()}"
        case.mkdir()
        sentinel = case / "previous-success.mp4"
        sentinel.write_bytes(b"existing-success-must-not-change")
        output, report = case / "interrupted.mp4", case / "interrupted.json"
        stdout = (case / "worker.stdout").open("wb")
        stderr = (case / "worker.stderr").open("wb")
        proc = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).with_name("render_video.py")),
                "--memory-policy",
                memory_policy,
                "--width",
                "720",
                "--frames",
                "900",
                "--timeout",
                "180",
                "--output",
                str(output),
                "--report",
                str(report),
            ],
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        encoder_pids = set()
        try:
            deadline = time.monotonic() + 10
            ready = False
            while time.monotonic() < deadline and proc.poll() is None:
                candidates = [p for p in process_tree(procfs_pid()) if namespace_pid(p) == proc.pid]
                if candidates:
                    encoder_pids = process_tree(candidates[0]) - {candidates[0]}
                if encoder_pids and list(case.glob(".reelforge-encode-*/pending.mp4")):
                    ready = True
                    break
                time.sleep(0.02)
            if not ready:
                raise RuntimeError("Worker did not reach active encoding before recovery check")
            os.killpg(proc.pid, signal.SIGTERM)
            status = proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=2)
            stdout.close()
            stderr.close()
            reconciled = reconcile_case(case)
        live_encoder_pids = [pid for pid in encoder_pids if Path(f"/proc/{pid}").exists()]
        error_report = json.loads(report.read_text()) if report.is_file() else None
        result = {
            "memory_policy": memory_policy,
            "passed": (
                status != 0
                and not output.exists()
                and not live_encoder_pids
                and sentinel.read_bytes() == b"existing-success-must-not-change"
                and not list(case.glob(".reelforge-encode-*"))
            ),
            "case_directory": str(case),
            "worker_exit_status": status,
            "live_encoder_pids_after": live_encoder_pids,
            "incomplete_final_published": output.exists(),
            "existing_output_unchanged": sentinel.read_bytes()
            == b"existing-success-must-not-change",
            "supervisor_reconciled": reconciled,
            "worker_error_report": error_report,
            "scope": "Handled SIGTERM; external SIGKILL/host loss is not covered.",
        }
        (case / "recovery.json").write_text(json.dumps(result, indent=2) + "\n")
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_memory_policy_argument(parser)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check_recovery(args.workspace, memory_policy=args.memory_policy)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        result = {"passed": False, "message": str(error)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
