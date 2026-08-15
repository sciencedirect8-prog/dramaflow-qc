from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(slots=True)
class CheckResult:
    name: str
    status: Status
    actual: str = ""
    expected: str = ""
    detail: str = ""


@dataclass(slots=True)
class QCReport:
    target: str
    results: list[CheckResult] = field(default_factory=list)
    sha256: str | None = None

    @property
    def final_status(self) -> Status:
        if any(item.status == Status.FAIL for item in self.results):
            return Status.FAIL
        if any(item.status == Status.WARNING for item in self.results):
            return Status.WARNING
        return Status.PASS
