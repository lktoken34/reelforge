"""Trusted, bounded lifecycle probe; observes only directories created in this invocation."""

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

PREFIXES = (".reelforge-audio-", ".reelforge-encode-", ".register-")


def metadata(path):
    try:
        s = path.lstat()
        kind = "symlink" if stat.S_ISLNK(s.st_mode) else "dir" if path.is_dir() else "file"
        return {
            "type": kind,
            "inode": s.st_ino,
            "device": s.st_dev,
            "mode": s.st_mode,
            "bytes": s.st_size,
            "mtime_ns": s.st_mtime_ns,
            "ctime_ns": s.st_ctime_ns,
        }
    except FileNotFoundError:
        return None


def diagnose(output: Path, cycles: int):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    roots = []
    processes = {}
    events = 0
    with (output / "lifecycle.jsonl").open("x") as log:

        def snapshot(root):
            root_metadata = metadata(root)
            return {
                "root": str(root),
                "metadata": root_metadata,
                "entries": {str(p.relative_to(root)): metadata(p) for p in sorted(root.rglob("*"))}
                if root_metadata and root_metadata["type"] == "dir"
                else {},
            }

        def emit(event, **data):
            nonlocal events
            events += 1
            if events > 20000:
                raise RuntimeError("Diagnostic event limit")
            log.write(
                json.dumps(
                    {
                        "event": event,
                        "pid": os.getpid(),
                        "ppid": os.getppid(),
                        "monotonic_ns": time.monotonic_ns(),
                        **data,
                    }
                )
                + "\n"
            )
            log.flush()

        def owned(path):
            p = Path(path).absolute()
            return any(p == r or r in p.parents for r in roots)

        mkdtemp = tempfile.mkdtemp
        unlink, rmdir = Path.unlink, Path.rmdir
        init, poll = subprocess.Popen.__init__, subprocess.Popen._internal_poll

        def create(*a, **kw):
            name = mkdtemp(*a, **kw)
            if Path(name).name.startswith(PREFIXES):
                root = Path(name).absolute()
                roots.append(root)
                emit("create", transaction=snapshot(root))
            return name

        def removal(fn, path, *a, **kw):
            if not owned(path):
                return fn(path, *a, **kw)
            emit(fn.__name__ + "_before", path=str(path), metadata=metadata(path))
            try:
                result = fn(path, *a, **kw)
            except BaseException as e:
                emit(
                    fn.__name__ + "_error",
                    path=str(path),
                    error=type(e).__name__,
                    errno=getattr(e, "errno", None),
                )
                raise
            emit(fn.__name__ + "_after", path=str(path), metadata=metadata(path))
            return result

        def start(proc, args, *a, **kw):
            emit(
                "native_before",
                executable=Path(args[0]).name,
                transactions=[snapshot(r) for r in roots],
            )
            init(proc, args, *a, **kw)
            processes[proc.pid] = {"pid": proc.pid, "returncode": None}
            emit("child_started", child_pid=proc.pid)

        def reaped(proc, *a, **kw):
            result = poll(proc, *a, **kw)
            if result is not None and processes.get(proc.pid, {}).get("returncode") is None:
                processes[proc.pid] = {"pid": proc.pid, "returncode": result}
                try:
                    os.killpg(proc.pid, 0)
                    group_exists = True
                except ProcessLookupError:
                    group_exists = False
                emit(
                    "child_reaped",
                    process_group_present=group_exists,
                    child_pid=proc.pid,
                    returncode=result,
                    proc_entry_present=Path(f"/proc/{proc.pid}").exists(),
                    transactions=[snapshot(r) for r in roots],
                )
            return result

        mounts = []
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            fields = line.split()
            if output.is_relative_to(fields[4]):
                mounts.append(
                    {"mountpoint": fields[4], "filesystem": fields[fields.index("-") + 1]}
                )
        emit(
            "host",
            python=sys.version,
            filesystem=max(mounts, key=lambda x: len(x["mountpoint"])),
            device=output.stat().st_dev,
        )
        from reelforge.core.transaction import OwnedDirectory

        cleanup = OwnedDirectory.cleanup

        def clean(owner):
            emit(
                "cleanup_before",
                transaction=snapshot(owner.path),
                processes=list(processes.values()),
            )
            try:
                result = cleanup(owner)
            except BaseException as error:
                emit(
                    "cleanup_error",
                    transaction=snapshot(owner.path),
                    error=type(error).__name__,
                    code=getattr(error, "code", None),
                )
                raise
            emit(
                "cleanup_after",
                transaction=snapshot(owner.path),
                processes=list(processes.values()),
            )
            return result

        with (
            patch.object(OwnedDirectory, "cleanup", clean),
            patch("tempfile.mkdtemp", create),
            patch.object(Path, "unlink", lambda p, *a, **k: removal(unlink, p, *a, **k)),
            patch.object(Path, "rmdir", lambda p, *a, **k: removal(rmdir, p, *a, **k)),
            patch.object(subprocess.Popen, "__init__", start),
            patch.object(subprocess.Popen, "_internal_poll", reaped),
        ):
            from render_story import render

            from reelforge.media.process import run_bounded
            from reelforge.stories.contract import load_story, validate_story

            root = Path(__file__).resolve().parents[1]
            data = load_story(root / "examples/stories/last_farm_audio.json").to_data()
            data["shots"] = data["shots"][:1]
            data["shots"][0]["end_frame"] = data["output"]["frames"] = 30
            data["audio"]["narration"].update(start_frame=1, gain=0.3)
            data["audio"]["cues"][0]["start_frame"] = 15
            data["audio"]["cues"][1]["start_frame"] = 24
            data["audio"]["cues"][1]["gain"] = 0.1
            for cycle in range(cycles):
                try:
                    render(validate_story(data), output / f"render-{cycle}")
                    emit("render_return", cycle=cycle, transactions=[snapshot(r) for r in roots])
                except BaseException as e:
                    emit(
                        "render_error",
                        cycle=cycle,
                        error=type(e).__name__,
                        code=getattr(e, "code", None),
                        transactions=[snapshot(r) for r in roots],
                    )
                    raise
                rc, _, _ = run_bounded(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(root / "assets/audio/diag_opening.wav"),
                        "-f",
                        "null",
                        "-",
                    ]
                )
                assert rc == 0
                emit(
                    "after_subsequent_native",
                    cycle=cycle,
                    transactions=[snapshot(r) for r in roots],
                )
            emit(
                "complete",
                processes=list(processes.values()),
                transactions=[snapshot(r) for r in roots],
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cycles", type=int, choices=range(1, 5), default=2)
    args = parser.parse_args()
    diagnose(args.output_dir, args.cycles)
