"""Trace one real audio integration job using accepted silent media; never render visuals."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

from investigate_persistence import Probe

from reelforge.audio.processing import command
from reelforge.core.transaction import OwnedDirectory
from reelforge.reels import workflow
from reelforge.reels.contract import load_reel
from reelforge.resources.monitor import JobMonitor

ROOT = Path(__file__).resolve().parents[1]


def instrumentation(probe, confined=False):
    original_popen = subprocess.Popen
    processes = []

    class ObservedProcess(original_popen):
        def __init__(self, args, **kwargs):
            probe.snapshot("native_before_constructor")
            probe.emit("native_enter", argv=args)
            if confined:
                args = [
                    str(ROOT / "outputs/phase7b1-native-directory-guard"),
                    str(probe.root / "native_restrictions.jsonl"),
                    str(probe.root / "must-not-be-created"),
                    "--",
                    *args,
                ]
            super().__init__(args, **kwargs)
            self.reported = False
            processes.append(self)
            probe.emit(
                "native_constructor_return",
                pid=self.pid,
                argv=args,
                process_group=os.getpgid(self.pid) if self.returncode is None else None,
            )
            probe.snapshot("native_after_constructor")

        def poll(self):
            result = super().poll()
            if result is not None and not getattr(self, "reported", False):
                self.reported = True
                probe.emit("native_reaped_by_poll", pid=self.pid, returncode=result)
                probe.snapshot("native_after_reap")
            return result

    class ObservedOwner(OwnedDirectory):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            key = str(self.path.relative_to(probe.root))
            self.probe_key = key
            probe.paths[key] = {
                "original": probe.stat(os.fstat(self._fd)),
                "retired": False,
                "observer_fd": os.dup(self._fd),
            }
            probe.emit(
                "owned_create",
                path=str(self.path),
                fd=self._fd,
                identity=list(self._identity),
                observer_fd=probe.paths[key]["observer_fd"],
            )
            parent = self.path.parent
            mask = 0x100 | 0x200 | 0x40 | 0x80 | 0x400 | 0x800 | 0x20 | 0x8
            probe.libc.inotify_add_watch(probe.inotify, os.fsencode(parent), mask)
            probe.libc.inotify_add_watch(probe.inotify, os.fsencode(self.path), mask)
            probe.fanotify_mark(parent)
            probe.snapshot("owned_created")

        def cleanup(self):
            probe.snapshot("owned_cleanup_before")
            probe.emit(
                "owned_cleanup_enter",
                path=str(self.path),
                identity=list(self._identity),
                children=[{"pid": p.pid, "returncode": p.poll()} for p in processes],
            )
            try:
                result = super().cleanup()
            except BaseException as error:
                probe.emit(
                    "owned_cleanup_failure", code=getattr(error, "code", None), message=str(error)
                )
                probe.snapshot("owned_cleanup_failed")
                raise
            probe.paths[self.probe_key]["retired"] = True
            probe.snapshot("owned_cleanup_return_absent")
            return result

    return ObservedProcess, ObservedOwner, processes


def trace(root):
    probe = Probe(root)
    ObservedProcess, ObservedOwner, processes = instrumentation(probe)

    def reuse_silent(plan, output, **kwargs):
        output.mkdir()
        source = ROOT / "artifacts/phase7a/proofs/silent_signal_video"
        shutil.copyfile(source / "scene.mp4", output / "scene.mp4")
        report = json.loads((source / "render_report.json").read_text())
        return report

    with JobMonitor(workspace=probe.root) as monitor:
        with (
            patch.object(subprocess, "Popen", ObservedProcess),
            patch.object(workflow, "OwnedDirectory", ObservedOwner),
        ):
            result = workflow.render_reel(
                load_reel(ROOT / "examples/reels/silent_signal.json"),
                probe.root / "job",
                registry_root=ROOT / "assets/audio",
                render_silent=reuse_silent,
            )
            probe.emit(
                "job_return",
                success=result["success"],
                published=result["published"],
                transaction_clean=result["transaction_clean"],
                error=result["error"],
                cleanup_error=result["cleanup_error"],
            )
            probe.snapshot("after_job_return")
            movie = probe.root / "job/reel.mp4"
            if movie.exists():
                command(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-v",
                        "error",
                        "-threads",
                        "1",
                        "-i",
                        str(movie),
                        "-map",
                        "0:a:0",
                        "-vn",
                        "-threads:a",
                        "1",
                        "-f",
                        "null",
                        "-",
                    ]
                )
            probe.snapshot("after_post_job_native_decode")
            reaped = []
            for proc in processes:
                rc = proc.poll()
                try:
                    os.waitpid(proc.pid, os.WNOHANG)
                    no_child = False
                except ChildProcessError:
                    no_child = True
                try:
                    os.killpg(proc.pid, 0)
                    group_absent = False
                except ProcessLookupError:
                    group_absent = True
                except PermissionError:
                    group_absent = None
                reaped.append(
                    {
                        "pid": proc.pid,
                        "returncode": rc,
                        "waitpid_reports_no_child": no_child,
                        "process_group_absent": group_absent,
                        "stdout_closed": proc.stdout is None or proc.stdout.closed,
                        "stderr_closed": proc.stderr is None or proc.stderr.closed,
                    }
                )
            probe.emit("all_children_final", processes=reaped)
    probe.emit("resource_report", report=monitor.report())
    probe.finish()
    return 0


def legacy_test(root, confined=False):
    """Run exactly the archived failing persistence test, with all ownership assertions intact."""
    import pytest

    import reelforge.audio.transaction as audio_transaction
    import reelforge.core.transaction as core_transaction
    import reelforge.media.encoder as media_encoder

    probe = Probe(root, fanotify=confined)
    ObservedProcess, ObservedOwner, processes = instrumentation(probe, confined=confined)
    with JobMonitor(workspace=probe.root) as monitor:
        with (
            patch.object(subprocess, "Popen", ObservedProcess),
            patch.object(audio_transaction, "OwnedDirectory", ObservedOwner),
            patch.object(media_encoder, "OwnedDirectory", ObservedOwner),
            patch.object(core_transaction, "OwnedDirectory", ObservedOwner),
        ):
            code = pytest.main(
                [
                    "-q",
                    "tests/test_transaction_cleanup.py::test_two_audio_jobs_persistently_clean_after_native_work",
                    "--basetemp",
                    str(probe.root / "pytest"),
                    "--junitxml=" + str(probe.root / "targeted.xml"),
                ]
            )
            probe.emit("targeted_test_return", exit_code=int(code))
            probe.snapshot("after_targeted_test_return")
            reaped = []
            for proc in processes:
                rc = proc.poll()
                try:
                    os.waitpid(proc.pid, os.WNOHANG)
                    no_child = False
                except ChildProcessError:
                    no_child = True
                try:
                    os.killpg(proc.pid, 0)
                    group_absent = False
                except ProcessLookupError:
                    group_absent = True
                except PermissionError:
                    group_absent = None
                reaped.append(
                    {
                        "pid": proc.pid,
                        "returncode": rc,
                        "waitpid_reports_no_child": no_child,
                        "process_group_absent": group_absent,
                        "stdout_closed": proc.stdout is None or proc.stdout.closed,
                        "stderr_closed": proc.stderr is None or proc.stderr.closed,
                    }
                )
            probe.emit("all_children_final", processes=reaped)
    probe.emit("resource_report", report=monitor.report())
    probe.finish()
    return int(code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--legacy-test", action="store_true")
    parser.add_argument("--confine-native", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        legacy_test(args.output_dir, confined=args.confine_native)
        if args.legacy_test
        else trace(args.output_dir)
    )
