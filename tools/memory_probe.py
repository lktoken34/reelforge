"""Stdlib-only pre-install memory evidence; performs no native probes or renders."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reelforge.core.errors import OperationError
from reelforge.resources.deployment import pressure_snapshot
from reelforge.resources.memory import add_memory_policy_argument
from reelforge.resources.monitor import memory_snapshot, preflight_memory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_memory_policy_argument(parser)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    snapshot = memory_snapshot(memory_policy=args.memory_policy)
    report = {
        "memory": snapshot,
        "pressure": pressure_snapshot(),
        "admission_allowed": False,
        "target_vm_verified": False,
        "deployment_gate_approved": False,
        "scope": "Memory admission only; dependencies/rendering not tested",
    }
    try:
        preflight_memory(snapshot=snapshot, memory_policy=args.memory_policy)
        report["admission_allowed"] = True
    except OperationError as error:
        report["error"] = {"code": error.code, "message": str(error)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    raise SystemExit(0 if report["admission_allowed"] else 2)


if __name__ == "__main__":
    main()
