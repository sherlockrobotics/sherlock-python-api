"""Request models for Sherlock log entries.

A log entry is always associated with exactly one case, batch or image; the
three request classes differ only in which association they serialize.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias

__all__ = [
    "LogType",
    "CreateCaseLogRequest",
    "CreateBatchLogRequest",
    "CreateImageLogRequest",
    "LogRequest",
]


class LogType(Enum):
    """Severity of a log entry."""

    Info = "Info"
    Warning = "Warning"
    Error = "Error"


@dataclass
class CreateCaseLogRequest:
    """A log entry associated with a case."""

    case_id: str
    log_type: LogType
    body: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /log``."""
        return {
            "association": {"case_id": self.case_id},
            "log_type": self.log_type.value,
            "body": self.body,
        }


@dataclass
class CreateBatchLogRequest:
    """A log entry associated with a batch."""

    batch_id: str
    log_type: LogType
    body: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /log``."""
        return {
            "association": {"batch_id": self.batch_id},
            "log_type": self.log_type.value,
            "body": self.body,
        }


@dataclass
class CreateImageLogRequest:
    """A log entry associated with an image."""

    image_id: str
    log_type: LogType
    body: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /log``."""
        return {
            "association": {"image_id": self.image_id},
            "log_type": self.log_type.value,
            "body": self.body,
        }


#: Any of the three log request payloads.
LogRequest: TypeAlias = (
    CreateCaseLogRequest | CreateBatchLogRequest | CreateImageLogRequest
)
