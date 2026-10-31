import pytest

from reelforge.core.errors import OperationError
from reelforge.resources.monitor import MIB, preflight_memory, process_rss, process_tree, procfs_pid


def test_conservative_memory_admission():
    with pytest.raises(OperationError) as caught:
        preflight_memory(snapshot={"effective_available_bytes": 319 * MIB})
    assert caught.value.code == "MEMORY_PREFLIGHT"
    assert preflight_memory(snapshot={"effective_available_bytes": 320 * MIB})
    with pytest.raises(OperationError):
        preflight_memory(snapshot={"effective_available_bytes": 0})


def test_process_metrics_are_available_on_linux():
    assert process_rss(procfs_pid()) > 0
    assert procfs_pid() in process_tree(procfs_pid())


def test_monitor_includes_a_live_child_despite_pid_namespaces():
    import subprocess
    import sys
    import time

    from reelforge.resources.monitor import JobMonitor

    with JobMonitor() as monitor:
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time;block=bytearray(8*1024*1024);time.sleep(3)"],
            start_new_session=True,
        )
        monitor.encoder_pid = proc.pid
        try:
            deadline = time.monotonic() + 2
            while monitor.encoder_peak == 0 and time.monotonic() < deadline:
                time.sleep(0.02)
            assert monitor.encoder_peak > 0
            assert monitor.tree_peak > monitor.renderer_peak
        finally:
            proc.terminate()
            proc.wait(timeout=2)
    assert monitor.report()["encoder_peak_rss_bytes"] > 0
