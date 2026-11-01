"""Explicit ownership for a single private directory; never reacquire a removed pathname."""

import os
import shutil
import stat
import tempfile
from pathlib import Path

from .errors import OperationError


class OwnedDirectory:
    """Own one inode through cleanup, with no GC finalizer or previous-job reconciliation."""

    def __init__(self, parent: Path, prefix: str, *, files: frozenset[str] | None = None):
        self.path = Path(tempfile.mkdtemp(dir=parent.resolve(), prefix=prefix))
        self._fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self._identity = self._key(os.fstat(self._fd))
        self._files = files
        self._attempted = False
        self._error: OperationError | None = None

    @staticmethod
    def _key(info: os.stat_result) -> tuple[int, int]:
        return info.st_dev, info.st_ino

    def assert_absent(self) -> None:
        if self.path.exists() or self.path.is_symlink():
            raise OperationError(
                "TRANSACTION_CLEANUP", f"Completed transaction path reappeared: {self.path}"
            )

    def cleanup(self) -> None:
        if self._attempted:
            if self._error is not None:
                raise self._error
            self.assert_absent()
            return
        self._attempted = True
        try:
            # Hold the original directory fd until removal completes. A new inode at the
            # same pathname is a different owner, even if its name has our private prefix.
            if self._key(self.path.lstat()) != self._identity or self.path.is_symlink():
                raise OperationError(
                    "TRANSACTION_IDENTITY", f"Private directory identity changed: {self.path}"
                )
            if self._files is not None:
                entries = tuple(self.path.iterdir())
                if any(
                    p.name not in self._files or not p.is_file() or p.is_symlink() for p in entries
                ):
                    raise OperationError(
                        "TRANSACTION_CONTENT", f"Unexpected private directory content: {self.path}"
                    )
                for entry in entries:
                    os.unlink(entry.name, dir_fd=self._fd)
            else:
                # Python's fd-based rmtree does not traverse directory symlinks. It removes
                # only this invocation's owned subtree, after supervised children are reaped.
                if not shutil.rmtree.avoids_symlink_attacks:
                    raise OperationError("TRANSACTION_PLATFORM", "FD-safe cleanup is required")
                for name in os.listdir(self._fd):
                    info = os.stat(name, dir_fd=self._fd, follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        shutil.rmtree(name, dir_fd=self._fd)
                    else:
                        os.unlink(name, dir_fd=self._fd)
            if self._key(self.path.lstat()) != self._identity or self.path.is_symlink():
                raise OperationError("TRANSACTION_IDENTITY", "Directory changed during cleanup")
            os.rmdir(self.path)
            self.assert_absent()
        except (OSError, OperationError) as error:
            self._error = (
                error
                if isinstance(error, OperationError)
                else OperationError(
                    "TRANSACTION_CLEANUP", f"Cannot remove owned directory: {self.path}"
                )
            )
            if self._error is error:
                raise
            raise self._error from error
        finally:
            os.close(self._fd)
