"""Request models and enums for interacting with a running Sherlock process."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    "DialogType",
    "Language",
    "DialogResult",
    "ProcessState",
    "CreateProcessModalDialogRequest",
    "NotificationAttachment",
    "CreateNotificationRequest",
]


class DialogType(Enum):
    """Set of buttons shown on a modal dialog."""

    Ok = "Ok"
    ContinueAbort = "ContinueAbort"
    YesNo = "YesNo"


class Language(Enum):
    """Language a modal dialog message is written in."""

    English = "English"
    German = "German"


class DialogResult(Enum):
    """Outcome of a modal dialog.

    ``NoResponse`` is returned by
    :meth:`sherlock_api.SherlockAPIClient.get_modal` when the poll timed out
    before the operator answered.
    """

    Ok = "Ok"
    Continue = "Continue"
    Abort = "Abort"
    Yes = "Yes"
    No = "No"
    Rejected = "Rejected"
    NoResponse = "NoResponse"


class ProcessState(Enum):
    """Run state of a Sherlock process."""

    Running = "Running"
    Paused = "Paused"
    Stopped = "Stopped"


@dataclass
class CreateProcessModalDialogRequest:
    """Payload for :meth:`sherlock_api.SherlockAPIClient.post_modal`.

    Args:
        dialog_type: Which buttons the dialog offers.
        language: Language ``body`` is written in.
        body: Message shown to the operator.
    """

    dialog_type: DialogType
    language: Language
    body: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /process/{id}/modal``."""
        return {
            "dialog_type": self.dialog_type.value,
            "message": {self.language.value: self.body},
        }


@dataclass
class NotificationAttachment:
    """A binary attachment on a notification.

    Args:
        name: Filename shown to the operator.
        mime: MIME type of ``data``.
        data: Raw attachment bytes; base64-encoded on serialization.
    """

    name: str
    mime: str
    data: bytes

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the attachment object embedded in a notification."""
        return {
            "name": self.name,
            "mime": self.mime,
            "dataBase64": base64.b64encode(self.data).decode("ascii"),
        }


@dataclass
class CreateNotificationRequest:
    """Payload for :meth:`sherlock_api.SherlockAPIClient.post_notification`.

    Args:
        title: Notification headline.
        content: Notification body text.
        attachments: Optional binary attachments. ``None`` is treated as
            "no attachments" and normalized to an empty list.
    """

    title: str
    content: str
    attachments: list[NotificationAttachment] | None = None

    def __post_init__(self) -> None:
        if self.attachments is None:
            self.attachments = []

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /process/{id}/notification``."""
        return {
            "title": self.title,
            "content": self.content,
            "attachments": [a.to_dict() for a in (self.attachments or [])],
        }
