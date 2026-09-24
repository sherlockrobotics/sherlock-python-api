"""Client tests. Every HTTP call is mocked; no Sherlock server is required."""

from __future__ import annotations

import io
import logging

import pytest
import responses
from PIL import Image

from sherlock_api import (
    CreateNotificationRequest,
    CreateProcessModalDialogRequest,
    DecisionClass,
    DialogResult,
    DialogType,
    Language,
    ProcessState,
    SherlockAPIClient,
    SherlockAPIError,
    SherlockBadRequestError,
    SherlockConfigurationError,
    SherlockNotFoundError,
    SherlockServerError,
    SherlockTimeoutError,
)

from .conftest import BASE_URL

# ----------------------------------------------------------------------
# Construction and configuration
# ----------------------------------------------------------------------


def test_requires_a_port():
    with pytest.raises(SherlockConfigurationError, match="SHERLOCK_PORT"):
        SherlockAPIClient()


def test_configuration_error_is_a_value_error():
    """Older code catches ValueError; that must keep working."""
    with pytest.raises(ValueError):
        SherlockAPIClient()


def test_env_vars_are_read_at_construction_not_import(monkeypatch):
    """Regression: os.getenv used to sit in the constructor's defaults."""
    monkeypatch.setenv("SHERLOCK_URL", "http://elsewhere")
    monkeypatch.setenv("SHERLOCK_PORT", "9999")
    monkeypatch.setenv("SHERLOCK_CASE_ID", "case-from-env")

    with SherlockAPIClient() as client:
        assert client.sherlock_api_url == "http://elsewhere:9999"
        assert client.sherlock_case_id == "case-from-env"


def test_arguments_win_over_environment(monkeypatch):
    monkeypatch.setenv("SHERLOCK_PORT", "9999")
    with SherlockAPIClient(sherlock_port=8080) as client:
        assert client.sherlock_api_url == "http://localhost:8080"


def test_trailing_slash_is_stripped_from_url():
    with SherlockAPIClient("http://localhost/", 8080) as client:
        assert client.sherlock_api_url == "http://localhost:8080"


def test_supplied_session_is_not_closed():
    import requests

    session = requests.Session()
    with SherlockAPIClient(sherlock_port=8080, session=session):
        pass
    assert session.adapters, "caller-owned session should still be usable"
    session.close()


# ----------------------------------------------------------------------
# Error mapping
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, SherlockBadRequestError),
        (404, SherlockNotFoundError),
        (408, SherlockTimeoutError),
        (500, SherlockServerError),
        (503, SherlockServerError),
    ],
)
@responses.activate
def test_status_codes_map_to_exception_classes(client, status, expected):
    responses.add(responses.GET, f"{BASE_URL}/case/c1", status=status, body="boom")
    with pytest.raises(expected) as info:
        client.get_case("c1")
    assert info.value.status_code == status
    assert info.value.method == "GET"
    assert info.value.url == f"{BASE_URL}/case/c1"


@responses.activate
def test_api_error_is_a_runtime_error(client):
    responses.add(responses.GET, f"{BASE_URL}/case/c1", status=500)
    with pytest.raises(RuntimeError):
        client.get_case("c1")


@responses.activate
def test_long_error_bodies_are_truncated(client):
    responses.add(responses.GET, f"{BASE_URL}/case/c1", status=500, body="x" * 5000)
    with pytest.raises(SherlockServerError) as info:
        client.get_case("c1")
    assert len(info.value.body) < 600
    assert "more chars" in info.value.body


# ----------------------------------------------------------------------
# Files
# ----------------------------------------------------------------------


@responses.activate
def test_get_file_tolerates_a_charset_parameter(client):
    png = b"\x89PNG\r\n\x1a\n" + b"rest"
    responses.add(
        responses.GET,
        f"{BASE_URL}/file/h1",
        body=png,
        content_type="application/octet-stream; charset=binary",
    )
    assert client.get_file("h1") == (png, ".png")


@responses.activate
def test_get_file_rejects_an_unexpected_content_type(client):
    responses.add(
        responses.GET, f"{BASE_URL}/file/h1", body="<html>", content_type="text/html"
    )
    with pytest.raises(SherlockAPIError, match="Content-Type"):
        client.get_file("h1")


@responses.activate
def test_post_file_from_memory_strips_quotes(client):
    responses.add(responses.POST, f"{BASE_URL}/file", status=201, body='"deadbeef"')
    assert client.post_file_from_memory(io.BytesIO(b"data")) == "deadbeef"


@responses.activate
def test_post_file_reads_from_disk(client, tmp_path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"\x01\x02")
    responses.add(responses.POST, f"{BASE_URL}/file", status=201, body='"cafe"')

    assert client.post_file(str(path)) == "cafe"
    assert responses.calls[0].request.body == b"\x01\x02"


# ----------------------------------------------------------------------
# Id fallbacks
# ----------------------------------------------------------------------


@responses.activate
def test_get_case_falls_back_to_the_client_case_id():
    responses.add(responses.GET, f"{BASE_URL}/case/case-9", json={"id": "case-9"})
    with SherlockAPIClient(
        "http://sherlock.test", 8080, sherlock_case_id="case-9"
    ) as client:
        assert client.get_case()["id"] == "case-9"


@responses.activate
def test_get_batch_falls_back_to_the_client_batch_id():
    responses.add(responses.GET, f"{BASE_URL}/batch/batch-9", json={"id": "batch-9"})
    with SherlockAPIClient(
        "http://sherlock.test", 8080, sherlock_batch_id="batch-9"
    ) as client:
        assert client.get_batch()["id"] == "batch-9"


def test_missing_id_raises_configuration_error(client):
    with pytest.raises(SherlockConfigurationError, match="case_id"):
        client.get_case()
    with pytest.raises(SherlockConfigurationError, match="batch_id"):
        client.get_images_for_batch()
    with pytest.raises(SherlockConfigurationError, match="process_id"):
        client.get_env_vars()


# ----------------------------------------------------------------------
# Images and measurements
# ----------------------------------------------------------------------


@responses.activate
def test_upload_image_posts_bytes_then_metadata(client):
    responses.add(responses.POST, f"{BASE_URL}/file", status=201, body='"hash-1"')
    responses.add(responses.POST, f"{BASE_URL}/image", status=201, json={"id": "img-1"})

    result = client.upload_image(
        Image.new("RGB", (2, 2)), "part.png", DecisionClass.Ok, "batch-1"
    )

    assert result == {"id": "img-1"}
    assert responses.calls[0].request.body.startswith(b"\x89PNG")
    assert responses.calls[1].request.body == (
        b'{"batch_id": "batch-1", "image_name": "part.png", '
        b'"decision_class": "Ok", "image_data": "hash-1"}'
    )


@responses.activate
def test_upload_image_honours_the_image_format(client):
    responses.add(responses.POST, f"{BASE_URL}/file", status=201, body='"hash-1"')
    responses.add(responses.POST, f"{BASE_URL}/image", status=201, json={"id": "img-1"})

    client.upload_image(
        Image.new("RGB", (2, 2)),
        "part.jpg",
        DecisionClass.Ok,
        "batch-1",
        image_format="JPEG",
    )

    assert responses.calls[0].request.body.startswith(b"\xff\xd8\xff")


@responses.activate
def test_upload_image_with_measurements_returns_image_and_measurements(client):
    responses.add(responses.POST, f"{BASE_URL}/file", status=201, body='"hash-1"')
    responses.add(responses.POST, f"{BASE_URL}/image", status=201, json={"id": "img-1"})
    responses.add(responses.POST, f"{BASE_URL}/measurement", status=201, json={"id": "m"})

    image, measurements = client.upload_image_with_measurements(
        Image.new("RGB", (2, 2)),
        "part.png",
        DecisionClass.Ok,
        [("width", 1), ("height", 2.5)],
        "batch-1",
    )

    assert image == {"id": "img-1"}
    assert measurements == [{"id": "m"}, {"id": "m"}]


@responses.activate
def test_delete_measurement_expects_204(client):
    responses.add(responses.DELETE, f"{BASE_URL}/measurement/m1", status=204)
    assert client.delete_measurement("m1") is None


# ----------------------------------------------------------------------
# Logs
# ----------------------------------------------------------------------


@responses.activate
def test_log_helpers_target_the_right_association(client):
    responses.add(responses.POST, f"{BASE_URL}/log", status=201, json={"id": "log-1"})

    client.log_case_error("case-1", "bad")
    client.log_batch_warning("batch-1", "hmm")
    client.log_image_info("image-1", "fyi")

    bodies = [call.request.body for call in responses.calls]
    assert b'{"case_id": "case-1"}' in bodies[0]
    assert b'"log_type": "Error"' in bodies[0]
    assert b'{"batch_id": "batch-1"}' in bodies[1]
    assert b'{"image_id": "image-1"}' in bodies[2]


# ----------------------------------------------------------------------
# Processes
# ----------------------------------------------------------------------


@responses.activate
def test_get_process_state_returns_none_for_unknown_process(client):
    responses.add(responses.GET, f"{BASE_URL}/process/p1/running", status=404)
    assert client.get_process_state("p1") is None
    assert client.is_process_running("p1") is False


@responses.activate
def test_get_process_state_parses_the_enum(client):
    responses.add(
        responses.GET, f"{BASE_URL}/process/p1/running", status=200, body="Running"
    )
    assert client.get_process_state("p1") is ProcessState.Running


@responses.activate
def test_get_modal_returns_no_response_on_408(client):
    responses.add(responses.GET, f"{BASE_URL}/process/p1/modal/m1", status=408)
    assert client.get_modal("m1", "p1") is DialogResult.NoResponse


@responses.activate
def test_get_modal_outlasts_its_server_side_long_poll(client):
    responses.add(
        responses.GET, f"{BASE_URL}/process/p1/modal/m1", status=200, body="Yes"
    )
    assert client.get_modal("m1", "p1", timeout=60_000) is DialogResult.Yes

    request = responses.calls[0].request
    assert request.params["timeout"] == "60000"
    # request_timeout is 1.0s in the fixture; the long poll must widen it.
    assert request.req_kwargs["timeout"] == pytest.approx(65.0)


@responses.activate
def test_post_modal_uses_the_client_process_id():
    responses.add(
        responses.POST, f"{BASE_URL}/process/p9/modal", status=201, body="modal-1"
    )
    with SherlockAPIClient(
        "http://sherlock.test", 8080, sherlock_process_id="p9"
    ) as client:
        modal_id = client.post_modal(
            CreateProcessModalDialogRequest(DialogType.Ok, Language.English, "Hi")
        )
    assert modal_id == "modal-1"


@responses.activate
def test_delete_modal_expects_204(client):
    responses.add(responses.DELETE, f"{BASE_URL}/process/p1/modal/m1", status=204)
    assert client.delete_modal("m1", "p1") is None


@responses.activate
def test_post_notification_logs_instead_of_raising_on_404(client, caplog):
    responses.add(responses.POST, f"{BASE_URL}/process/p1/notification", status=404)
    with caplog.at_level(logging.WARNING, logger="sherlock_api.client"):
        client.post_notification(CreateNotificationRequest("t", "c"), "p1")
    assert "cannot be found" in caplog.text


@responses.activate
def test_post_notification_still_raises_on_other_errors(client):
    responses.add(responses.POST, f"{BASE_URL}/process/p1/notification", status=500)
    with pytest.raises(SherlockServerError):
        client.post_notification(CreateNotificationRequest("t", "c"), "p1")


@responses.activate
def test_get_env_state_returns_raw_text(client):
    responses.add(
        responses.GET, f"{BASE_URL}/process/p1/vars/state", status=200, body="changed"
    )
    assert client.get_env_state("p1") == "changed"
