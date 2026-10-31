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


def seal(directory: Path) -> dict:
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


def install(directory: Path, venv: Path) -> None:
    verify(directory)
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Install with CPython 3.12 on the matching Linux architecture")
    if venv.exists():
        raise ValueError("Choose a new venv path; existing environments are never overwritten")
    venv = venv.resolve()
    venv.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from reelforge.resources.deployment import check_workspace
    from reelforge.resources.monitor import preflight_memory

    preflight_memory()
    check_workspace(venv.parent)
    with tempfile.TemporaryDirectory(
        prefix=".reelforge-wheel-install-", dir=venv.parent
    ) as temporary:
        environment = dict(os.environ, TMPDIR=temporary)
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, env=environment)
        python = venv / "bin/python"
        subprocess.run(
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
            check=True,
            env=environment,
            timeout=300,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "verify", "install"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--venv", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "seal":
            result = seal(args.directory)
        elif args.action == "verify":
            result = verify(args.directory)
        else:
            if args.venv is None:
                parser.error("--venv is required for install")
            install(args.directory, args.venv)
            result = {"installed": True, "venv": str(args.venv)}
    except (
        ValueError,
        OSError,
        KeyError,
        RuntimeError,
        zipfile.BadZipFile,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "message": str(error),
                    "action": "Check wheelhouse hashes/platform and python3.12-venv availability.",
                }
            )
        )
        raise SystemExit(2) from error
    print(json.dumps({"ok": True, "result": result}))


if __name__ == "__main__":
    main()
