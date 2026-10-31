"""Seal or verify a flat, prebuilt wheelhouse; standard library only, no native compilation."""

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(65536):
            h.update(block)
    return h.hexdigest()


def wheel_details(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError(f"Expected one METADATA file in {path.name}")
        member = archive.getinfo(names[0])
        if member.file_size > 1048576:
            raise ValueError("Wheel metadata exceeds 1 MiB")
        metadata = BytesParser().parsebytes(archive.read(member))
    name = (metadata["Name"] or "").lower().replace("_", "-")
    version = metadata["Version"] or ""
    if not re.fullmatch(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", name) or not re.fullmatch(
        r"[0-9][a-zA-Z0-9.!+_-]*", version
    ):
        raise ValueError("Invalid wheel distribution/version")
    return {
        "file": path.name,
        "distribution": name,
        "version": version,
        "sha256": digest(path),
        "bytes": path.stat().st_size,
    }


def seal(directory: Path, *, source_commit: str | None = None) -> dict:
    if source_commit is not None and not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source_commit must be an exact lowercase Git commit SHA")
    directory = directory.resolve()
    wheels = sorted(directory.glob("*.whl"))
    if not wheels or any(p.is_symlink() for p in wheels):
        raise ValueError("Use a flat nonempty wheelhouse without symlinked wheels")
    entries = [wheel_details(path) for path in wheels]
    names = [entry["distribution"] for entry in entries]
    if len(names) != len(set(names)):
        raise ValueError(
            "Keep exactly one wheel per distribution/platform in a deployment wheelhouse"
        )
    for required in ("reelforge-v2", "pycairo", "jsonschema"):
        if required not in names:
            raise ValueError(f"Missing {required} wheel")
    requirements = "".join(
        f"{e['distribution']}=={e['version']} --hash=sha256:{e['sha256']}\n" for e in entries
    )
    lock = directory / "requirements.lock"
    lock.write_text(requirements)
    result = {
        "schema": "reelforge.wheelhouse.v1",
        "source_commit": source_commit,
        "files": entries,
        "requirements_sha256": digest(lock),
        "built_for": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "machine": platform.machine(),
            "libc": platform.libc_ver(),
        },
        "trust": "Checksums detect changes; obtain this manifest through a trusted channel.",
    }
    (directory / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def verify(directory: Path) -> dict:
    directory = directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema") != "reelforge.wheelhouse.v1":
        raise ValueError("Unsupported wheelhouse manifest")
    expected = set()
    for entry in manifest["files"]:
        name = entry["file"]
        if Path(name).name != name or not name.endswith(".whl") or name in expected:
            raise ValueError("Wheel manifest contains unsafe/duplicate paths")
        expected.add(name)
        path = directory / name
        if path.is_symlink() or not path.is_file() or digest(path) != entry["sha256"]:
            raise ValueError(f"Wheel missing or checksum mismatch: {name}")
        actual = wheel_details(path)
        if any(actual[key] != entry[key] for key in ("distribution", "version", "bytes")):
            raise ValueError("Wheel metadata differs from sealed requirements")
    if {p.name for p in directory.glob("*.whl")} != expected:
        raise ValueError("Wheelhouse contains unlisted wheels")
    lock = directory / "requirements.lock"
    if lock.is_symlink() or digest(lock) != manifest["requirements_sha256"]:
        raise ValueError("Wheel requirements checksum mismatch")
    expected_lock = "".join(
        f"{e['distribution']}=={e['version']} --hash=sha256:{e['sha256']}\n"
        for e in manifest["files"]
    )
    if lock.read_text() != expected_lock:
        raise ValueError("Wheel requirements must contain exactly the sealed pins/hashes")
    return manifest


def install(directory: Path, venv: Path, *, memory_policy: str = "strict") -> dict:
    verify(directory)
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Install with CPython 3.12 on the matching Linux architecture")
    if venv.exists():
        raise ValueError("Choose a new venv path; existing environments are never overwritten")
    venv = venv.resolve()
    venv.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from reelforge.resources.deployment import check_workspace
    from reelforge.resources.monitor import JobMonitor, preflight_memory

    admission = preflight_memory(memory_policy=memory_policy)
    check_workspace(venv.parent)
    with (
        JobMonitor(workspace=venv.parent, memory_policy=memory_policy) as guard,
        tempfile.TemporaryDirectory(
            prefix=".reelforge-wheel-install-", dir=venv.parent
        ) as temporary,
    ):
        environment = dict(os.environ, TMPDIR=temporary)
        from reelforge.media.process import run_bounded

        # Both bounded subprocesses share the monitor cancellation token.
        rc, out, err = run_bounded(
            [sys.executable, "-m", "venv", str(venv)],
            timeout=60,
            cancelled=guard.cancelled,
            env=environment,
        )
        if rc:
            raise RuntimeError(
                "venv creation failed; provision python3.12-venv: "
                + err.decode(errors="replace")[-2048:]
            )
        python = venv / "bin/python"
        rc, out, err = run_bounded(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--only-binary=:all:",
                "--find-links",
                str(directory.resolve()),
                "--require-hashes",
                "-r",
                str(directory.resolve() / "requirements.lock"),
            ],
            timeout=300,
            cancelled=guard.cancelled,
            env=environment,
        )

        if rc:
            raise RuntimeError(
                "Offline pip install failed: " + err.decode(errors="replace")[-2048:]
            )
    return {
        "installed": True,
        "venv": str(venv),
        "admission_memory": admission,
        "whole_install_memory": guard.report(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from reelforge.resources.memory import add_memory_policy_argument

    add_memory_policy_argument(parser)
    parser.add_argument("action", choices=("seal", "verify", "install"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--venv", type=Path)
    parser.add_argument("--report", type=Path, help="Persistent install/verification evidence")
    parser.add_argument("--source-commit", help="Builder commit provenance for seal")
    args = parser.parse_args()
    try:
        if args.action == "seal":
            result = seal(args.directory, source_commit=args.source_commit)
        elif args.action == "verify":
            result = verify(args.directory)
        else:
            if args.venv is None:
                parser.error("--venv is required for install")
            result = install(args.directory, args.venv, memory_policy=args.memory_policy)
    except (
        ValueError,
        OSError,
        KeyError,
        RuntimeError,
        zipfile.BadZipFile,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        KeyboardInterrupt,
    ) as error:
        from reelforge.resources.monitor import memory_snapshot

        report = {
            "ok": False,
            "code": getattr(
                error,
                "code",
                "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "INSTALL_FAILED",
            ),
            "message": str(error),
            "memory": memory_snapshot(memory_policy=args.memory_policy),
            "action": "Inspect memory evidence and wheelhouse platform/hashes; "
            "never lower thresholds.",
        }
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        raise SystemExit(2) from error
    report = {"ok": True, "result": result}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
