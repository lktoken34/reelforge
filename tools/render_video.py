"""One bounded engineering render/verify job; not an installed weak-agent command."""

import argparse
import json
import platform
import resource
import signal
import sys
import time
from pathlib import Path

from reelforge.core.errors import OperationError
from reelforge.media.encoder import FFmpegEncoder
from reelforge.media.process import run_bounded
from reelforge.media.verify import verify_video
from reelforge.rendering.backends.cairo import CairoRenderer, backend_versions
from reelforge.rendering.diagnostic import BACKGROUND, LOGICAL_SIZE
from reelforge.rendering.video_diagnostic import diagnostic_frame
from reelforge.resources.deployment import (
    check_workspace,
    event_delta,
    memory_observability,
    pressure_snapshot,
)
from reelforge.resources.memory import add_memory_policy_argument
from reelforge.resources.monitor import JobMonitor, preflight_memory


def confirm_transaction_cleanup(pending: Path, output: Path) -> None:
    """Reconcile only this reaped encoder's private path; never sweep another job's files."""
    directory = pending.parent
    if (
        pending.name != "pending.mp4"
        or directory.parent != output.parent
        or not directory.name.startswith(".reelforge-encode-")
    ):
        raise OperationError("TRANSACTION_PATH", "Encoder reported an unexpected transaction path")
    if directory.is_symlink() or pending.is_symlink():
        raise OperationError("TRANSACTION_PATH", "Refusing symlinked encoder transaction")
    if directory.exists():
        # Some checkpointed filesystems retain child-created paths after native cleanup.
        # The encoder has exited; reconcile only its known pending file, then an empty dir.
        if any(item != pending for item in directory.iterdir()):
            raise OperationError(
                "TRANSACTION_PATH", "Unexpected content in private encoder directory"
            )
        pending.unlink(missing_ok=True)
        directory.rmdir()
    if directory.exists():
        raise OperationError("TRANSACTION_CLEANUP", "Encoder transaction directory remains")


def render_job(
    output: Path,
    *,
    width: int,
    height: int,
    frames: int = 150,
    timeout: float = 60,
    memory_policy: str = "strict",
) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    workspace = check_workspace(output.parent)
    pressure_before = pressure_snapshot()
    own_cpu_start = time.process_time()
    child_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    renderer = CairoRenderer()
    source_samples = {}
    with JobMonitor(workspace=output.parent, memory_policy=memory_policy) as monitor:
        preflight_memory(snapshot=monitor.initial, memory_policy=memory_policy)
        if frames > 150 and monitor.initial["effective_available_bytes"] < 384 * 1024**2:
            raise OperationError("LONG_MEMORY_PREFLIGHT", "Long diagnostic needs 384 MiB headroom")
        started = time.perf_counter()
        with FFmpegEncoder(
            output,
            width=width,
            height=height,
            frames=frames,
            cancelled=monitor.cancelled,
            timeout=timeout,
        ) as encoder:
            monitor.encoder_pid = encoder.proc.pid
            with renderer.surface(width, height) as surface:
                for frame in range(frames):
                    renderer.draw(
                        surface,
                        diagnostic_frame(frame, frames),
                        background=BACKGROUND,
                        logical_size=LOGICAL_SIZE,
                    )
                    if frame in {0, frames // 2, frames - 1}:
                        source_samples[str(frame)] = surface.pixel_sha256()
                    encoder.write_surface(surface)
        render_seconds = time.perf_counter() - started
        if len(set(source_samples.values())) != 3:
            raise RuntimeError("Source geometry did not change at the three checkpoints")
        verification = verify_video(
            output,
            width=width,
            height=height,
            frames=frames,
            cancelled=monitor.cancelled,
        )
        if renderer.active_surfaces != 0 or renderer.allocated_bytes != 0:
            raise RuntimeError("Surface ownership was not released")
    rc, version, _ = run_bounded(["ffmpeg", "-version"], max_bytes=65536)
    events = event_delta(monitor.initial, monitor.final)
    if monitor.limit_reason:
        raise OperationError("RESOURCE_GUARD", monitor.limit_reason)
    if events is not None and any(
        events.get(k, 0) != 0 for k in ("oom", "oom_kill", "oom_group_kill")
    ):
        raise OperationError(
            "OOM_EVENTS", "Cgroup OOM counters changed during job; result is not a pass"
        )
    confirm_transaction_cleanup(Path(encoder.command[-1]), output)
    transaction_clean = not Path(encoder.command[-1]).parent.exists()
    if not transaction_clean:
        raise OperationError(
            "TRANSACTION_CLEANUP", "Encoder transaction directory remains; inspect before retry"
        )
    child_end = resource.getrusage(resource.RUSAGE_CHILDREN)
    observability = memory_observability(monitor.initial, monitor.final)
    if not monitor.oom_telemetry_continuous:
        observability["sufficient_for_technical_validation"] = False
        observability["limitations"].append("OOM telemetry was not continuous during sampling")
    return {
        "technical_rendering_success": True,
        "memory_observability": observability,
        "deployment_gate_approved": False,
        "cpu_seconds": {
            "renderer": time.process_time() - own_cpu_start,
            "children_user": child_end.ru_utime - child_start.ru_utime,
            "children_system": child_end.ru_stime - child_start.ru_stime,
        },
        "workspace_preflight": workspace,
        "pressure_before": pressure_before,
        "pressure_after": pressure_snapshot(),
        "cgroup_memory_event_delta": events,
        "transaction_clean": transaction_clean,
        "output": str(output),
        "width": width,
        "height": height,
        "fps": 30,
        "frames": frames,
        "render_encode_seconds": render_seconds,
        "effective_encoded_fps": frames / render_seconds,
        "file_size_bytes": output.stat().st_size,
        "encoder_exit_status": encoder.returncode,
        "encoder_command": encoder.command,
        "source_checkpoint_sha256": source_samples,
        "verification": verification,
        "whole_job_memory": monitor.report(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "distribution": platform.freedesktop_os_release()["PRETTY_NAME"],
            "ffmpeg_version": version.decode().splitlines()[0],
            **backend_versions(),
        },
        "resource_scope": "Renderer worker and child tools from preflight through full decode. "
        "CPU-only; host swap counters are recorded; not a target-VM certification.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_memory_policy_argument(parser)
    parser.add_argument("--width", type=int, choices=[360, 720], default=360)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--frames", type=int, choices=(150, 450, 600, 900), default=150)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()

    # Convert handled termination into the existing context-manager cancellation path.
    def terminate(signum, frame):
        raise KeyboardInterrupt("Diagnostic worker interrupted")

    signal.signal(signal.SIGTERM, terminate)
    try:
        report = render_job(
            args.output.resolve(),
            width=args.width,
            height=args.width * 16 // 9,
            frames=args.frames,
            timeout=args.timeout,
            memory_policy=args.memory_policy,
        )
    except (OperationError, OSError, KeyboardInterrupt) as error:
        report = {
            "ok": False,
            "technical_rendering_success": False,
            "memory_policy": args.memory_policy,
            "deployment_gate_approved": False,
            "error": {
                "code": getattr(
                    error,
                    "code",
                    "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "IO_ERROR",
                ),
                "message": str(error),
            },
            "render_ready": False,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), file=sys.stderr)
        raise SystemExit(130 if isinstance(error, KeyboardInterrupt) else 2) from error

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "peak_tree_mib": report["whole_job_memory"][
                    "estimated_simultaneous_tree_peak_rss_bytes"
                ]
                / 1048576,
                "seconds": report["render_encode_seconds"],
                "verified": True,
            }
        )
    )


if __name__ == "__main__":
    main()
