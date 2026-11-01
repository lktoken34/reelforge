"""Own one private directory and remove only its files after supervised children finish."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from reelforge.core.errors import OperationError
from reelforge.core.transaction import OwnedDirectory


@contextmanager
def private_directory(parent: Path, prefix: str = ".reelforge-audio-") -> Iterator[Path]:
    if prefix not in (".reelforge-audio-", ".register-"):
        raise OperationError("AUDIO_TRANSACTION", "Unsupported private transaction prefix")
    owner = OwnedDirectory(parent, prefix)
    try:
        yield owner.path
    finally:
        owner.cleanup()
