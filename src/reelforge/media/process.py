"""Small POSIX process utilities with finite waits and bounded collected output."""

import os
import selectors
import signal
import subprocess
import time
from threading import Event

from reelforge.core.errors import OperationError
from reelforge.core.streams import check_interrupt


class VideoError(OperationError):
    """Encoding or verification failed."""


def stop_process(proc: subprocess.Popen) -> None:
    """Reap our session leader and terminate its process group; never an unbounded wait."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass
    # Also stop inherited-pipe descendants if the session leader exited first.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired as error:
        raise VideoError("PROCESS_CLEANUP", "Child did not exit after kill") from error


def run_bounded(
    args: list[str],
    *,
    timeout: float = 15,
    max_bytes: int = 1_048_576,
    cancelled: Event | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, bytes, bytes]:
    """Drain both pipes while bounding combined output; no shell and no input stream."""
    try:
        proc = subprocess.Popen(
            args,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
    except OSError as error:
        raise VideoError("TOOL_UNAVAILABLE", f"Cannot start {args[0]}") from error
    buffers = [bytearray(), bytearray()]
    deadline = time.monotonic() + timeout
    completed = False
    try:
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate((proc.stdout, proc.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, index)
            while selector.get_map():
                check_interrupt(deadline, cancelled)
                for key, _ in selector.select(0.05):
                    data = os.read(key.fileobj.fileno(), 8192)
                    if not data:
                        selector.unregister(key.fileobj)
                    else:
                        buffers[key.data].extend(data)
                        if sum(map(len, buffers)) > max_bytes:
                            raise VideoError(
                                "TOOL_OUTPUT_LIMIT", "Subprocess output exceeded limit"
                            )
            while proc.poll() is None:
                check_interrupt(deadline, cancelled)
                time.sleep(0.01)
        completed = True
        return proc.returncode, bytes(buffers[0]), bytes(buffers[1])
    finally:
        if proc.poll() is None or not completed:
            stop_process(proc)
        proc.stdout.close()
        proc.stderr.close()
