"""Small Linux lifecycle probe. Control mode imports no ReelForge and renders no movie.

The probe never removes a path after its recorded retirement. inotify timestamps are
userspace observation times, not kernel event times or evidence of writer PID.
"""

import argparse
import ctypes
import hashlib
import json
import os
import selectors
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


class Probe:
    def __init__(self, root: Path, *, fanotify=False):
        self.root = root.resolve()
        self.root.mkdir(exist_ok=False)
        self.events = []
        self.paths = {}
        self.deleted_names = set()
        self.phase = "initial"
        self.lock = threading.Lock()
        self.start_ns = time.monotonic_ns()
        self.parent_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.inotify_init1.argtypes = [ctypes.c_int]
        self.libc.inotify_init1.restype = ctypes.c_int
        self.libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self.libc.inotify_add_watch.restype = ctypes.c_int
        self.inotify = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.inotify < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1")
        mask = 0x100 | 0x200 | 0x40 | 0x80 | 0x400 | 0x800 | 0x20 | 0x8
        watch = self.libc.inotify_add_watch(self.inotify, os.fsencode(self.root), mask)
        if watch < 0:
            raise OSError(ctypes.get_errno(), "inotify_add_watch")
        self.fanotify = None
        if fanotify:
            self.libc.fanotify_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
            self.libc.fanotify_init.restype = ctypes.c_int
            self.libc.fanotify_mark.argtypes = [
                ctypes.c_int,
                ctypes.c_uint,
                ctypes.c_uint64,
                ctypes.c_int,
                ctypes.c_char_p,
            ]
            self.libc.fanotify_mark.restype = ctypes.c_int
            self.fanotify = self.libc.fanotify_init(1 | 2 | 0x400 | 0x800, os.O_RDONLY)
            if self.fanotify < 0:
                raise OSError(ctypes.get_errno(), "fanotify_init")
            self.fanotify_mark(self.root)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.watch, name="persistence-inotify", daemon=True)
        self.thread.start()
        sys.addaudithook(self.audit)
        self.emit("initial", identity=self.identity(), mounts=self.mounts())

    def emit(self, kind, **details):
        with self.lock:
            self.events.append(
                {
                    "event": kind,
                    "phase": self.phase,
                    "monotonic_ns": time.monotonic_ns(),
                    "wall_ns": time.time_ns(),
                    **details,
                }
            )

    def audit(self, event, args):
        if event in ("os.mkdir", "os.rmdir", "os.remove", "os.rename", "os.link", "os.symlink"):
            values = [str(a) for a in args if isinstance(a, (str, bytes, Path))]
            if any(str(self.root) in value for value in values):
                self.emit("python_mutation_audit", operation=event, arguments=values)
        elif event == "subprocess.Popen":
            self.emit("python_spawn_audit", executable=str(args[0]), argv=args[1])

    def watch(self):
        with selectors.DefaultSelector() as select:
            select.register(self.inotify, selectors.EVENT_READ)
            if self.fanotify is not None:
                select.register(self.fanotify, selectors.EVENT_READ)
            while not self.stop.is_set():
                for ready, _ in select.select(0.01):
                    if ready.fd == self.fanotify:
                        self.drain_fanotify()
                        continue
                    try:
                        raw = os.read(self.inotify, 65536)
                    except BlockingIOError:
                        continue
                    offset = 0
                    while offset + 16 <= len(raw):
                        wd, mask, cookie, size = struct.unpack_from("iIII", raw, offset)
                        name = (
                            raw[offset + 16 : offset + 16 + size]
                            .split(b"\0", 1)[0]
                            .decode(errors="replace")
                        )
                        self.emit(
                            "inotify",
                            watch=wd,
                            mask=mask,
                            cookie=cookie,
                            name=name,
                            timestamp_scope="Userspace drain time, writer PID unavailable",
                        )
                        identity = (wd, name)
                        if mask & 0x200:
                            self.deleted_names.add(identity)
                        if (
                            mask & 0x100
                            and identity in self.deleted_names
                            and any(
                                Path(key).name == name and record["retired"]
                                for key, record in tuple(self.paths.items())
                            )
                        ):
                            self.emit(
                                "recreation_process_census",
                                directory_name=name,
                                census=self.process_census(),
                            )
                        offset += 16 + size

    def fanotify_mark(self, path):
        if self.fanotify is not None:
            rc = self.libc.fanotify_mark(
                self.fanotify, 1, 0x100 | 0x200 | 0x40000000 | 0x08000000, -100, os.fsencode(path)
            )
            if rc:
                raise OSError(ctypes.get_errno(), "fanotify_mark")

    def drain_fanotify(self):
        try:
            raw = os.read(self.fanotify, 65536)
        except BlockingIOError:
            return
        offset = 0
        while offset + 24 <= len(raw):
            length, version, _, metadata_len, mask, fd, pid = struct.unpack_from(
                "=IBBHQii", raw, offset
            )
            if length < 24 or offset + length > len(raw):
                raise RuntimeError("Malformed fanotify metadata")
            names = []
            extra = offset + metadata_len
            while extra + 4 <= offset + length:
                kind, _, size = struct.unpack_from("=BBH", raw, extra)
                if size < 4 or extra + size > offset + length:
                    raise RuntimeError("Malformed fanotify info")
                if kind == 2 and size >= 20:
                    handle_bytes = struct.unpack_from("=I", raw, extra + 12)[0]
                    start = extra + 20 + handle_bytes
                    names.append(
                        raw[start : extra + size].split(b"\0", 1)[0].decode(errors="replace")
                    )
                extra += size
            self.emit(
                "fanotify",
                mask=mask,
                pid=pid,
                names=names,
                version=version,
                creator_pid_scope=(
                    "Unprivileged group: non-listener processes are redacted to 0; "
                    "calibration required"
                ),
            )
            if fd >= 0:
                os.close(fd)
            offset += length

    def process_census(self):
        result = []
        denied = 0
        for entry in list(Path("/proc").iterdir())[:4096]:
            if not entry.name.isdigit():
                continue
            try:
                comm = (entry / "comm").read_text().strip()
                status = (entry / "status").read_text().splitlines()
                record = {
                    "procfs_pid": int(entry.name),
                    "comm": comm,
                    "nspid": next((line for line in status if line.startswith("NSpid:")), None),
                    "ppid": next((line for line in status if line.startswith("PPid:")), None),
                    "mount_ns": os.readlink(entry / "ns/mnt"),
                    "pid_ns": os.readlink(entry / "ns/pid"),
                    "scope_fds": [],
                }
                try:
                    for fd in list((entry / "fd").iterdir())[:256]:
                        try:
                            target = os.readlink(fd)
                            if str(self.root) in target:
                                record["scope_fds"].append({"fd": fd.name, "target": target})
                        except OSError:
                            pass
                except OSError:
                    record["fd_inventory_unavailable"] = True
                result.append(record)
            except OSError:
                denied += 1
        return {
            "visible_processes": result,
            "unavailable_process_records": denied,
            "scope": (
                "No command lines or environment read. procfs visibility is namespace-limited; "
                "no writer attribution from inotify alone."
            ),
        }

    @staticmethod
    def stat(info):
        return {
            "dev": info.st_dev,
            "ino": info.st_ino,
            "mode": info.st_mode,
            "nlink": info.st_nlink,
            "size": info.st_size,
            "mtime_ns": info.st_mtime_ns,
            "ctime_ns": info.st_ctime_ns,
        }

    def identity(self):
        status = Path("/proc/self/status").read_text()
        return {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "pgid": os.getpgrp(),
            "procfs_self": os.readlink("/proc/self"),
            "nspid": next((s for s in status.splitlines() if s.startswith("NSpid:")), None),
            "pid_ns": os.readlink("/proc/self/ns/pid"),
            "mount_ns": os.readlink("/proc/self/ns/mnt"),
        }

    def mounts(self):
        raw = Path("/proc/self/mountinfo").read_bytes()
        applicable = []
        for line in raw.decode().splitlines():
            fields = line.split()
            mount = fields[4].replace("\\040", " ")
            if self.root == Path(mount) or self.root.is_relative_to(mount):
                sep = fields.index("-")
                applicable.append(
                    {
                        "mount_id": fields[0],
                        "parent_id": fields[1],
                        "device": fields[2],
                        "mount_root": fields[3],
                        "mount_point": mount,
                        "type": fields[sep + 1],
                        "source": fields[sep + 2],
                    }
                )
        return {
            "mountinfo_sha256": hashlib.sha256(raw).hexdigest(),
            "applicable_mounts": applicable,
            "parent_fdinfo": Path(f"/proc/self/fdinfo/{self.parent_fd}").read_text(),
        }

    def snapshot(self, label):
        self.phase = label
        states = {}
        for name, record in self.paths.items():
            item = {"original": record["original"], "retired": record["retired"]}
            try:
                current = os.stat(name, dir_fd=self.parent_fd, follow_symlinks=False)
                item["path"] = self.stat(current)
            except FileNotFoundError:
                item["path"] = None
            if record.get("observer_fd") is not None:
                item["original_fd"] = self.stat(os.fstat(record["observer_fd"]))
            states[name] = item
        self.emit(
            "snapshot",
            label=label,
            parent_fd=self.stat(os.fstat(self.parent_fd)),
            parent_path=self.stat(self.root.lstat()),
            paths=states,
            mounts=self.mounts(),
        )
        return states

    def canary(self, native=False, mp4=False, pipe=False, paced=False, decoded=False):
        path = Path(
            tempfile.mkdtemp(
                prefix=(
                    ".reelforge-encode-"
                    if pipe
                    else ".reelforge-audio-"
                    if mp4
                    else "retired-canary-"
                ),
                dir=self.root,
            )
        )
        name = path.name
        marker = path / "marker.txt"
        marker.write_text(
            "retired canary; child processes receive neither this path nor contents\n"
        )
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self.paths[name] = {
            "original": self.stat(os.fstat(fd)),
            "retired": False,
            "observer_fd": fd,
        }
        if native:
            wav = path / "native.wav"
            self.child(
                "native_named_output",
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-threads",
                    "1",
                    "-filter_threads",
                    "1",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:sample_rate=48000",
                    "-t",
                    "0.01",
                    "-c:a",
                    "pcm_s16le",
                    "-threads:a",
                    "1",
                    "-n",
                    str(wav),
                ],
            )
            self.child(
                "native_named_probe",
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(wav),
                ],
            )
        if mp4:
            source = (
                Path(__file__).resolve().parents[1]
                / "artifacts/phase7a/proofs/silent_signal_video/scene.mp4"
            )
            movie = path / "pending.mp4"
            if pipe:
                # Three bounded diagnostic color frames, no engine/render imports or artwork.
                pixels = b"".join(
                    bytes([b, g, r, 255]) * (360 * 640)
                    for b, g, r in [(20, 40, 60), (30, 70, 90), (80, 20, 100)]
                )
                self.child(
                    "native_raw_pipe",
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-nostdin",
                        "-max_alloc",
                        "67108864",
                        "-threads",
                        "1",
                        "-filter_threads",
                        "1",
                        "-filter_complex_threads",
                        "1",
                        "-f",
                        "rawvideo",
                        "-pixel_format",
                        "bgra",
                        "-video_size",
                        "720x1280" if paced or decoded else "360x640",
                        "-framerate",
                        "30",
                        "-i",
                        "pipe:0",
                        "-an",
                        "-sn",
                        "-dn",
                        "-frames:v",
                        "30" if paced or decoded else "3",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-tune",
                        "zerolatency",
                        "-threads:v",
                        "1",
                        "-x264-params",
                        "threads=1:lookahead_threads=1:sync-lookahead=0:rc-lookahead=0:bframes=0:ref=1",
                        "-profile:v",
                        "main",
                        "-level:v",
                        "3.1",
                        "-crf",
                        "20",
                        "-vf",
                        "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
                        "-pix_fmt",
                        "yuv420p",
                        "-colorspace",
                        "bt709",
                        "-color_primaries",
                        "bt709",
                        "-color_trc",
                        "bt709",
                        "-color_range",
                        "tv",
                        "-tag:v",
                        "avc1",
                        "-movflags",
                        "+faststart",
                        "-f",
                        "mp4",
                        "-n",
                        str(movie),
                    ],
                    payload=(
                        self.decoded_frames()
                        if decoded
                        else self.paced_frames()
                        if paced
                        else pixels
                    ),
                )
            else:
                self.child(
                    "native_mp4_copy",
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-v",
                        "error",
                        "-threads",
                        "1",
                        "-i",
                        str(source),
                        "-map",
                        "0:v:0",
                        "-c:v",
                        "copy",
                        "-an",
                        "-movflags",
                        "+faststart",
                        "-n",
                        str(movie),
                    ],
                )
            self.child(
                "native_mp4_probe",
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(movie),
                ],
            )
            os.link(movie, self.root / "published.mp4")
        self.snapshot("canary_before_cleanup")
        marker.unlink()
        if native:
            wav.unlink()
        if mp4:
            movie.unlink()
        path.rmdir()
        self.paths[name]["retired"] = True
        self.snapshot("canary_after_cleanup")
        return name

    @staticmethod
    def paced_frames():
        for index in range(30):
            yield bytes([20 + index, 40 + index, 60 + index, 255]) * (720 * 1280)
            time.sleep(0.03)

    def decoded_frames(self):
        source = Path(__file__).resolve().parents[1] / "artifacts/phase4a/story.mp4"
        args = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-threads",
            "1",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-an",
            "-frames:v",
            "30",
            "-threads:v",
            "1",
            "-filter_threads",
            "1",
            "-pix_fmt",
            "bgra",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
        proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            close_fds=True,
        )
        self.emit("decoder_start", pid=proc.pid, argv=args)
        os.set_blocking(proc.stdout.fileno(), False)
        deadline = time.monotonic() + 10
        try:
            with selectors.DefaultSelector() as ready:
                ready.register(proc.stdout, selectors.EVENT_READ)
                for _index in range(30):
                    frame = bytearray()
                    while len(frame) < 720 * 1280 * 4:
                        if time.monotonic() > deadline:
                            raise TimeoutError("Diagnostic decode deadline")
                        if ready.select(0.05):
                            try:
                                block = os.read(
                                    proc.stdout.fileno(), min(65536, 720 * 1280 * 4 - len(frame))
                                )
                            except BlockingIOError:
                                continue
                            if not block:
                                raise RuntimeError("Diagnostic source frame truncated")
                            frame.extend(block)
                    yield frame
            stdout, stderr = proc.communicate(timeout=max(0.1, deadline - time.monotonic()))
            if proc.returncode or stdout or stderr:
                raise RuntimeError("Diagnostic source decode failed")
            self.emit("decoder_reaped", pid=proc.pid, returncode=proc.returncode)
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, 9)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=2)
            proc.stdout.close()
            proc.stderr.close()

    def child(self, label, args, payload=None):
        self.phase = label
        self.snapshot(label + "_before_spawn")
        self.phase = label
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            close_fds=True,
        )
        pid = proc.pid
        self.emit(
            "popen_return",
            label=label,
            pid=pid,
            pgid=pid,
            parent_identity=self.identity(),
            command=args,
        )
        self.snapshot(label + "_after_popen_return")
        try:
            if payload is not None and not isinstance(payload, bytes):
                os.set_blocking(proc.stdin.fileno(), False)
                deadline = time.monotonic() + 10
                with selectors.DefaultSelector() as writer:
                    writer.register(proc.stdin, selectors.EVENT_WRITE)
                    for frame in payload:
                        view = memoryview(frame)
                        offset = 0
                        while offset < len(view):
                            if time.monotonic() > deadline:
                                raise TimeoutError("Diagnostic pipe deadline")
                            if writer.select(0.05):
                                try:
                                    offset += os.write(proc.stdin.fileno(), view[offset:])
                                except BlockingIOError:
                                    pass
                proc.stdin.close()
                proc.stdin = None
                stdout, stderr = proc.communicate(timeout=max(0.1, deadline - time.monotonic()))
            else:
                stdout, stderr = proc.communicate(input=payload, timeout=10)
        except BaseException:
            try:
                os.killpg(pid, 9)
            except ProcessLookupError:
                pass
            proc.wait(timeout=2)
            raise
        finally:
            proc.stdout.close()
            proc.stderr.close()
        if len(stdout) + len(stderr) > 65536:
            raise RuntimeError("Unexpected diagnostic output volume")
        try:
            os.waitpid(pid, os.WNOHANG)
            reaped = False
        except ChildProcessError:
            reaped = True
        try:
            os.killpg(pid, 0)
            group_absent = False
        except ProcessLookupError:
            group_absent = True
        except PermissionError:
            group_absent = None
        self.emit(
            "child_reaped",
            label=label,
            pid=pid,
            returncode=proc.returncode,
            waitpid_reports_no_child=reaped,
            process_group_absent=group_absent,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )
        self.snapshot(label + "_after_reaping")

    def finish(self):
        self.snapshot("final_before_observer_fd_close")
        for record in self.paths.values():
            if record.get("observer_fd") is not None:
                os.close(record["observer_fd"])
                record["observer_fd"] = None
        self.snapshot("final_after_observer_fd_close")
        time.sleep(0.03)
        self.stop.set()
        self.thread.join(timeout=2)
        os.close(self.inotify)
        if self.fanotify is not None:
            os.close(self.fanotify)
        os.close(self.parent_fd)
        value = {
            "probe_version": 1,
            "mode": (
                "instrumented engine"
                if any(n.startswith("reelforge") for n in sys.modules)
                else "engine-independent control"
            ),
            "reelforge_modules_loaded": [n for n in sys.modules if n.startswith("reelforge")],
            "identity": self.identity(),
            "probe_root": str(self.root),
            "events": self.events,
            "complete": True,
            "recreated_paths_never_removed": True,
        }
        (self.root / "trace.json").write_text(json.dumps(value, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "trace": str(self.root / "trace.json"),
                    "events": len(self.events),
                    "reelforge_modules_loaded": value["reelforge_modules_loaded"],
                }
            )
        )


def control(
    root, native=False, mp4=False, wav_followup=False, pipe=False, paced=False, decoded=False
):
    probe = Probe(root)
    probe.canary(native=native, mp4=mp4, pipe=pipe, paced=paced, decoded=decoded)
    time.sleep(0.10)
    probe.snapshot("no_child_time_control")
    probe.child("true_noop", ["/bin/true"])
    probe.child(
        "python_noop",
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            'import os,time;print("child_pid",os.getpid());time.sleep(.03)',
        ],
    )
    probe.child("ffmpeg_version", ["ffmpeg", "-version"])
    probe.child(
        "ffmpeg_null",
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-threads",
            "1",
            "-filter_threads",
            "1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            "0.01",
            "-threads:a",
            "1",
            "-f",
            "null",
            "-",
        ],
    )
    if native:
        movie = (
            Path(__file__).resolve().parents[1] / "artifacts/phase7b/proofs/silent_signal/reel.mp4"
        )
        probe.child(
            "existing_movie_probe",
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(movie),
            ],
        )
        probe.child(
            "existing_movie_decode",
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
                "-t",
                "0.01",
                "-f",
                "null",
                "-",
            ],
        )
    if mp4:
        probe.child(
            "published_mp4_decode",
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-threads",
                "1",
                "-i",
                str(probe.root / "published.mp4"),
                "-map",
                "0:v:0",
                "-an",
                "-threads:v",
                "1",
                "-f",
                "null",
                "-",
            ],
        )
    if wav_followup:
        stage = Path(tempfile.mkdtemp(prefix=".register-", dir=probe.root))
        source = Path(__file__).resolve().parents[1] / "assets/audio/diag_opening.wav"
        target = stage / "input.wav"
        shutil.copyfile(source, target)
        probe.child(
            "next_registered_wav_probe",
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file",
                "-f",
                "wav",
                "-show_entries",
                "stream=codec_type,codec_name,sample_rate,channels:format=format_name",
                "-of",
                "json",
                str(target),
            ],
        )
        probe.child(
            "next_registered_wav_decode",
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-xerror",
                "-err_detect",
                "explode",
                "-threads",
                "1",
                "-protocol_whitelist",
                "file",
                "-f",
                "wav",
                "-i",
                str(target),
                "-map",
                "0:a:0",
                "-vn",
                "-sn",
                "-dn",
                "-threads:a",
                "1",
                "-f",
                "null",
                "-",
            ],
        )
    probe.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--native-canary", action="store_true")
    parser.add_argument("--mp4-canary", action="store_true")
    parser.add_argument("--wav-followup", action="store_true")
    parser.add_argument("--pipe-canary", action="store_true")
    parser.add_argument("--paced-pipe", action="store_true")
    parser.add_argument("--decoded-pipe", action="store_true")
    args = parser.parse_args()
    control(
        args.output_dir,
        native=args.native_canary,
        mp4=args.mp4_canary or args.pipe_canary or args.paced_pipe or args.decoded_pipe,
        pipe=args.pipe_canary or args.paced_pipe or args.decoded_pipe,
        decoded=args.decoded_pipe,
        paced=args.paced_pipe,
        wav_followup=args.wav_followup,
    )
