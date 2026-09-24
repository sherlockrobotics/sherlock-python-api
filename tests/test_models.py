"""Serialization tests: the wire format is the contract with the server."""

from __future__ import annotations

import base64

import pytest

from sherlock_api import (
    CreateBatchLogRequest,
    CreateBatchRequest,
    CreateCaseLogRequest,
    CreateCaseRequest,
    CreateImageLogRequest,
    CreateImageRequest,
    CreateMeasurementRequest,
    CreateNotificationRequest,
    CreateProcessModalDialogRequest,
    DecisionClass,
    DialogType,
    Language,
    LogType,
    NotificationAttachment,
    RobotPlatform,
    guess_extension_by_magic,
    is_valid_uuid32,
)


def test_create_case_request():
    req = CreateCaseRequest("My case", RobotPlatform.UNIVERSAL_ROBOTS, "proc")
    assert req.to_dict() == {
        "case_name": "My case",
        "robot_platform": "UniversalRobots",
        "robot_procedure": "proc",
        "thumbnail": None,
    }


def test_create_batch_request():
    assert CreateBatchRequest("case-1", "Run 1").to_dict() == {
        "case_id": "case-1",
        "batch_name": "Run 1",
    }


def test_create_image_request_keeps_image_data_wire_field():
    req = CreateImageRequest("batch-1", "part.png", DecisionClass.NotOk, "abc123")
    assert req.image_hash == "abc123"
    assert req.to_dict() == {
        "batch_id": "batch-1",
        "image_name": "part.png",
        "decision_class": "NotOk",
        "image_data": "abc123",
    }


@pytest.mark.parametrize(
    ("cls", "association"),
    [
        (CreateCaseLogRequest, "case_id"),
        (CreateBatchLogRequest, "batch_id"),
        (CreateImageLogRequest, "image_id"),
    ],
)
def test_log_requests_nest_their_association(cls, association):
    assert cls("id-1", LogType.Warning, "careful").to_dict() == {
        "association": {association: "id-1"},
        "log_type": "Warning",
        "body": "careful",
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", "12"), (12, "12"), (12.5, "12.5")],
)
def test_measurement_stringifies_numbers(value, expected):
    assert CreateMeasurementRequest("img-1", "width", value).to_dict() == {
        "image_id": "img-1",
        "key": "width",
        "value": expected,
    }


def test_modal_request_keys_message_by_language():
    req = CreateProcessModalDialogRequest(DialogType.YesNo, Language.German, "Weiter?")
    assert req.to_dict() == {
        "dialog_type": "YesNo",
        "message": {"German": "Weiter?"},
    }


def test_notification_base64_encodes_attachments():
    req = CreateNotificationRequest(
        "Title",
        "Body",
        [NotificationAttachment("a.bin", "application/octet-stream", b"\x00\x01")],
    )
    payload = req.to_dict()
    assert payload["title"] == "Title"
    assert payload["attachments"][0]["dataBase64"] == base64.b64encode(
        b"\x00\x01"
    ).decode("ascii")


def test_notification_accepts_none_attachments():
    req = CreateNotificationRequest("Title", "Body", None)
    assert req.attachments == []
    assert req.to_dict()["attachments"] == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("8957CBFC162F6A1F713F269CE8BD6F8A", True),
        ("8957cbfc162f6a1f713f269ce8bd6f8a", True),
        ("8957CBFC-162F-6A1F-713F-269CE8BD6F8A", False),
        ("nope", False),
        ("", False),
    ],
)
def test_is_valid_uuid32(value, expected):
    assert is_valid_uuid32(value) is expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\x89PNG\r\n\x1a\n...", ".png"),
        (b"\xff\xd8\xff\xe0", ".jpg"),
        (b"%PDF-1.7", ".pdf"),
        (b"PK\x03\x04", ".zip"),
        (b"\x25\x21PS-Adobe-3.0", ".ps"),
        (b"\xef\xbb\xbfhello", ".txt"),
        (b"plain text\nsecond line\n", ".txt"),
        (b"no trailing newline", ".txt"),
        # Binary payloads that happen to contain a newline byte used to be
        # misreported as text by the old `b"\n" in data[:512]` check.
        (b"\x00\x01\x02\n\x03", ".bin"),
        (b"\x7fELF\x02\x01\x01\n\x00", ".bin"),
        (b"", ".bin"),
    ],
)
def test_guess_extension_by_magic(data, expected):
    assert guess_extension_by_magic(data) == expected


def test_guess_extension_handles_multibyte_split_at_the_cutoff():
    """A UTF-8 character straddling the 512-byte window must not crash."""
    data = ("a" * 511).encode() + "ü".encode()
    assert guess_extension_by_magic(data) == ".txt"
