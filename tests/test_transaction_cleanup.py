"""Cleanup fault injection stays within explicit fixture-owned directories."""

import gc
import os
from pathlib import Path

import pytest
from test_audio import audio_data as audio_data_fixture
from test_audio import template as audio_template
from test_audio import workflow as audio_workflow
from test_video_pipeline import fake_tool as video_fake_tool
from test_video_pipeline import opaque_surface as video_surface

from reelforge.audio.transaction import private_directory
from reelforge.core.errors import OperationError
from reelforge.core.transaction import OwnedDirectory
from reelforge.media.encoder import FFmpegEncoder
from reelforge.media.process import run_bounded

audio_data = audio_data_fixture
template = audio_template
workflow = audio_workflow
fake_tool = video_fake_tool
opaque_surface = video_surface


def test_nested_audio_cleanup_and_no_gc_finalizer(tmp_path):
    with private_directory(tmp_path) as outer:
        with private_directory(outer, ".register-") as inner:
            (inner / "input.wav").write_bytes(b"owned")
        assert not inner.exists()
        (outer / "asset").write_bytes(b"owned")
    gc.collect()
    assert not inner.exists() and not outer.exists()


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_interrupted_nested_cleanup(tmp_path, failure):
    with pytest.raises(failure):
        with private_directory(tmp_path) as outer:
            with private_directory(outer) as inner:
                (inner / "partial").write_bytes(b"owned")
                raise failure("injected")
    assert not outer.exists() and not inner.exists()


def test_symlink_is_unlinked_without_touching_other_job(tmp_path):
    with private_directory(tmp_path) as other:
        target = other / "success"
        target.write_bytes(b"other job")
        with private_directory(tmp_path) as own:
            (own / "linked-job").symlink_to(other, target_is_directory=True)
        assert target.read_bytes() == b"other job"
        assert not own.exists()


def test_replaced_root_is_never_reacquired(tmp_path):
    owner = OwnedDirectory(tmp_path, ".reelforge-audio-")
    moved = tmp_path / "original-owned-inode"
    owner.path.rename(moved)
    owner.path.mkdir()
    foreign = owner.path / "do-not-delete"
    foreign.write_bytes(b"replacement owner")
    with pytest.raises(OperationError) as caught:
        owner.cleanup()
    assert caught.value.code == "TRANSACTION_IDENTITY"
    assert foreign.read_bytes() == b"replacement owner" and moved.exists()
    # Test owns both fixture paths; no runtime reacquisition/retry occurs.
    foreign.unlink()
    owner.path.rmdir()
    moved.rmdir()


def test_successful_owner_does_not_delete_reappeared_path(tmp_path):
    owner = OwnedDirectory(tmp_path, ".reelforge-audio-")
    owner.cleanup()
    owner.path.mkdir()
    foreign = owner.path / "replacement"
    foreign.write_bytes(b"leave")
    with pytest.raises(OperationError, match="reappeared"):
        owner.cleanup()
    assert foreign.read_bytes() == b"leave"


def test_unexpected_video_content_is_preserved_and_fails(tmp_path):
    owner = OwnedDirectory(tmp_path, ".reelforge-encode-", files=frozenset({"pending.mp4"}))
    (owner.path / "pending.mp4").write_bytes(b"partial")
    unexpected = owner.path / ".rsync-tmp"
    unexpected.mkdir()
    (unexpected / "pending.mp4").write_bytes(b"foreign copy")
    with pytest.raises(OperationError) as caught:
        owner.cleanup()
    assert caught.value.code == "TRANSACTION_CONTENT"
    assert (unexpected / "pending.mp4").read_bytes() == b"foreign copy"
    assert (owner.path / "pending.mp4").exists()


def test_failed_directory_removal_propagates_once(tmp_path, monkeypatch):
    owner = OwnedDirectory(tmp_path, ".reelforge-audio-")
    original = os.rmdir
    calls = []

    def denied(path, *args, **kwargs):
        if Path(path) == owner.path:
            calls.append(path)
            raise PermissionError("safe injected removal failure")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(os, "rmdir", denied)
        for _ in range(2):
            with pytest.raises(OperationError) as caught:
                owner.cleanup()
            assert caught.value.code == "TRANSACTION_CLEANUP"
    assert len(calls) == 1 and owner.path.is_dir()
    original(owner.path)


def test_child_failure_reaped_before_owned_cleanup(tmp_path):
    with pytest.raises(RuntimeError):
        with private_directory(tmp_path) as root:
            rc, _, _ = run_bounded(["ffmpeg", "-v", "error", "-invalid-reelforge-option"])
            assert rc != 0
            (root / "partial").write_bytes(b"partial")
            raise RuntimeError("propagate child failure")
    assert not root.exists()


@pytest.mark.parametrize("fail_cleanup", [False, True])
def test_video_publication_cleanup_failure_is_reported_and_output_preserved(
    tmp_path, fake_tool, opaque_surface, monkeypatch, fail_cleanup
):
    output = tmp_path / "result.mp4"
    other = tmp_path / "unrelated.mp4"
    other.write_bytes(b"existing success")
    encoder = FFmpegEncoder(output, width=360, height=640, frames=1, ffmpeg=fake_tool())
    original = os.rmdir

    def removal(path, *args, **kwargs):
        if fail_cleanup and encoder._transaction and Path(path) == encoder._transaction.path:
            assert encoder.proc.poll() == 0 and output.read_bytes() == b"fake-encoded-output"
            raise PermissionError("cleanup after publication")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(os, "rmdir", removal)
        if fail_cleanup:
            with pytest.raises(OperationError, match="Cannot remove"):
                with encoder:
                    encoder.write_surface(opaque_surface[1])
        else:
            with encoder:
                encoder.write_surface(opaque_surface[1])
    assert encoder.proc.returncode == 0
    assert output.read_bytes() == b"fake-encoded-output"
    assert other.read_bytes() == b"existing success"
    assert encoder._transaction.path.exists() is fail_cleanup
    if fail_cleanup:
        original(encoder._transaction.path)
    encoder.confirm_cleanup()


def test_audio_cleanup_failure_after_publication_is_not_success(tmp_path, workflow, monkeypatch):
    _, _, run, _ = workflow
    out = tmp_path / "cleanup-failed"
    original = os.rmdir
    retained = []

    def removal(path, *args, **kwargs):
        path = Path(path)
        if path.parent == out and path.name.startswith(".reelforge-audio-"):
            assert (out / "story.mp4").exists()
            retained.append(path)
            raise PermissionError("audio cleanup after publication")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(os, "rmdir", removal)
        with pytest.raises(OperationError) as caught:
            run(out)
    assert caught.value.code == "TRANSACTION_CLEANUP" and len(retained) == 1
    assert (out / "story.mp4").stat().st_size > 0
    assert not (out / "report.json").exists()  # No overall-success report.
    with pytest.raises(OperationError) as existing:
        run(out)
    assert existing.value.code == "OUTPUT_EXISTS"
    original(retained[0])


def test_successive_real_video_cleanup_persists_after_native_operation(tmp_path, opaque_surface):
    prior = []
    for i in range(3):
        encoder = FFmpegEncoder(tmp_path / f"video-{i}.mp4", width=360, height=640, frames=1)
        with encoder:
            encoder.write_surface(opaque_surface[1])
        encoder.confirm_cleanup()
        assert encoder.proc.returncode == 0
        prior.append(encoder)
        rc, _, _ = run_bounded(
            ["ffmpeg", "-v", "error", "-i", str(encoder.output), "-f", "null", "-"]
        )
        assert rc == 0
        for previous in prior:
            previous.confirm_cleanup()


def test_two_audio_jobs_persistently_clean_after_native_work(tmp_path, workflow):
    _, _, run, _ = workflow
    outputs = []
    for i in range(2):
        out = tmp_path / f"audio-{i}"
        report = run(out)
        assert report["transaction_clean"]
        outputs.append(out)
        rc, _, _ = run_bounded(
            ["ffmpeg", "-v", "error", "-i", str(out / "story.mp4"), "-f", "null", "-"]
        )
        assert rc == 0
        for previous in outputs:
            assert not list(previous.glob(".reelforge-audio-*"))
            assert not list(previous.glob(".reelforge-encode-*"))
