"""Machine-readable input diagnostics, with JSON Pointer locations."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


class InputError(ValueError):
    def __init__(self, issue: Issue):
        super().__init__(issue.message)
        self.issue = issue
