"""Standard-library bootstrap doctor; safe to run before installing project dependencies."""

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import sys
import tomllib
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    print(
        json.dumps(
            {
                "ok": False,
                "errors": [
                    {
                        "code": "PYTHON_VERSION",
                        "message": "Use CPython 3.12 on Ubuntu 24.04 x86_64.",
                    }
                ],
            }
        )
    )
    raise SystemExit(2)

# Only stdlib-backed resource/process helpers are loaded from the trusted checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reelforge.core.errors import OperationError
from reelforge.media.process import run_bounded
from reelforge.resources.deployment import (
    cgroup_capabilities,
    check_workspace,
    cpu_snapshot,
    memory_observability,
    pressure_snapshot,
)
from reelforge.resources.memory import add_memory_policy_argument
from reelforge.resources.monitor import memory_snapshot, preflight_memory


def inspect_deployment(workspace: Path, *, memory_policy: str = "strict") -> dict:
    errors, warnings = [], []
    snapshot = memory_snapshot(memory_policy=memory_policy)
    try:
        preflight_memory(snapshot=snapshot, memory_policy=memory_policy)
    except OperationError as error:
        return {
            "schema": "reelforge.deployment.v1",
            "ok": False,
            "errors": [{"code": error.code, "message": str(error)}],
            "memory": snapshot,
            "memory_observability": memory_observability(snapshot, snapshot),
            "target_vm_verified": False,
            "native_checks": "skipped_due_to_memory_refusal",
            "pressure": pressure_snapshot(),
        }
    cpu = cpu_snapshot(snapshot)
    try:
        distribution = platform.freedesktop_os_release()
    except OSError:
        distribution = {}
    project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    expected = (
        ("reelforge-v2", project["project"]["version"]),
        ("jsonschema", "4.25.1"),
        ("pycairo", "1.29.2"),
    )
    for distribution_name, wanted in expected:
        try:
            actual = importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        if actual != wanted:
            errors.append(
                {
                    "code": "DEPENDENCY_VERSION",
                    "dependency": distribution_name,
                    "found": actual,
                    "required": wanted,
                    "message": "Install the verified wheelhouse; do not compile on this VM.",
                }
            )
    native = None
    if importlib.util.find_spec("cairo") is not None:
        rc, out, err = run_bounded(
            [
                sys.executable,
                "-c",
                "import cairo,json;print(json.dumps(dict(pycairo=cairo.version,"
                "cairo=cairo.cairo_version_string())))",
            ],
            timeout=10,
            max_bytes=32768,
        )
        if rc:
            errors.append(
                {
                    "code": "CAIRO_RUNTIME",
                    "message": "Pycairo import failed; check libcairo2 runtime and Python ABI.",
                    "detail": err.decode(errors="replace")[-1024:],
                }
            )
        else:
            native = json.loads(out)
    else:
        errors.append(
            {
                "code": "PYCAIRO_MISSING",
                "message": "Install the prebuilt CPython 3.12/Linux x86_64 Pycairo wheel.",
            }
        )
    tools = {}
    for name in ("ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        tools[name] = {"path": executable}
        if executable is None:
            errors.append(
                {
                    "code": "MEDIA_TOOL_MISSING",
                    "message": f"Provision {name}; ordinary rendering must not need sudo.",
                }
            )
            continue
        rc, out, err = run_bounded([executable, "-version"], timeout=10, max_bytes=65536)
        tools[name]["version"] = out.decode(errors="replace").splitlines()[0] if out else None
        if rc:
            errors.append({"code": "MEDIA_TOOL_FAILED", "message": f"{name} -version failed"})
    if tools["ffmpeg"]["path"]:
        rc, out, err = run_bounded(
            [tools["ffmpeg"]["path"], "-hide_banner", "-encoders"], timeout=10, max_bytes=262144
        )
        supported = rc == 0 and any(
            len(row := line.split()) > 1 and row[1] == b"libx264" for line in out.splitlines()
        )
        tools["libx264"] = supported
        if not supported:
            errors.append(
                {
                    "code": "LIBX264_MISSING",
                    "message": "Provision an FFmpeg build with libx264; no fallback is allowed.",
                }
            )
    filesystem = None
    try:
        filesystem = check_workspace(workspace)
    except OperationError as error:
        errors.append({"code": error.code, "message": str(error)})
    try:
        preflight_memory(snapshot=snapshot, memory_policy=memory_policy)
    except OperationError as error:
        errors.append({"code": error.code, "message": str(error)})
    temporary = shutil.disk_usage("/tmp")
    identity = {
        "ubuntu_24_04": distribution.get("ID") == "ubuntu"
        and distribution.get("VERSION_ID") == "24.04",
        "x86_64": platform.machine() == "x86_64",
        "four_effective_cpus": abs(cpu["effective_cpu_upper_bound"] - 4) < 0.01,
        "no_host_swap": snapshot["host"].get("SwapTotal") == 0,
        "reported_ram_near_7_7_gib": 7.0 <= snapshot["host"].get("MemTotal", 0) / 1073741824 <= 8.5,
        "tmp_near_512_mib": 448 * 1048576 <= temporary.total <= 576 * 1048576,
    }
    if not all(identity.values()):
        warnings.append("Observed machine does not match every supplied target-VM characteristic.")
    if os.geteuid() == 0:
        warnings.append(
            "This run is root; unprivileged operation on the target remains unverified."
        )
    return {
        "schema": "reelforge.deployment.v1",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "python": platform.python_version(),
        "uid": os.getuid(),
        "distribution": distribution,
        "cpu": cpu,
        "memory": snapshot,
        "memory_observability": memory_observability(snapshot, snapshot),
        "pressure": pressure_snapshot(),
        "workspace": filesystem,
        "native": native,
        "media_tools": tools,
        "tmp": {"total_bytes": temporary.total, "free_bytes": temporary.free},
        "cgroup_capabilities": cgroup_capabilities(snapshot),
        "target_characteristics": identity,
        "target_identity_matches": all(identity.values()),
        "target_vm_verified": False,
        "note": "Host characteristics are diagnostics, not proof that this is the intended VM.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_memory_policy_argument(parser)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_deployment(args.workspace, memory_policy=args.memory_policy)
    except (OperationError, OSError) as error:
        result = {
            "ok": False,
            "errors": [{"code": getattr(error, "code", "HOST_INSPECTION"), "message": str(error)}],
            "target_vm_verified": False,
        }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()
