"""HTTP client for the Sherlock REST API."""

from __future__ import annotations

import logging
import os
from io import BytesIO
from types import TracebackType
from typing import Any, cast

import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .batches import CreateBatchRequest
from .cases import CreateCaseRequest
from .exceptions import (
    SherlockAPIError,
    SherlockConfigurationError,
    exception_for_status,
    truncate_body,
)
from .files import guess_extension_by_magic
from .images import CreateImageRequest, DecisionClass
from .logs import (
    CreateBatchLogRequest,
    CreateCaseLogRequest,
    CreateImageLogRequest,
    LogRequest,
    LogType,
)
from .measurements import CreateMeasurementRequest
from .process import (
    CreateNotificationRequest,
    CreateProcessModalDialogRequest,
    DialogResult,
    ProcessState,
)

__all__ = ["SherlockAPIClient", "DEFAULT_URL", "DEFAULT_TIMEOUT"]

logger = logging.getLogger(__name__)

JSONDict = dict[str, Any]
JSONList = list[dict[str, Any]]

#: Base URL used when neither an argument nor ``SHERLOCK_URL`` is given.
DEFAULT_URL = "http://localhost"
#: Default per-request timeout in seconds.
DEFAULT_TIMEOUT = 30.0

_RETRY_STATUSES = (502, 503, 504)
_RETRY_METHODS = frozenset({"GET", "DELETE"})


def _as_object(response: requests.Response) -> JSONDict:
    return cast(JSONDict, response.json())


def _as_array(response: requests.Response) -> JSONList:
    return cast(JSONList, response.json())


class SherlockAPIClient:
    """Client for a Sherlock instance's REST API.

    Every argument falls back to an environment variable, which is how a
    script launched *by* Sherlock receives its context::

        SHERLOCK_URL         base URL, default "http://localhost"
        SHERLOCK_PORT        port (required)
        SHERLOCK_PROCESS_ID  default process id
        SHERLOCK_CASE_ID     default case id
        SHERLOCK_BATCH_ID    default batch id

    The defaults are read when the client is constructed, so setting the
    environment after importing this module still works.

    Args:
        sherlock_url: Base URL without port, e.g. ``"http://localhost"``.
        sherlock_port: Port the Sherlock REST API listens on.
        sherlock_process_id: Default process id for the ``process`` methods.
        sherlock_case_id: Default case id for :meth:`get_case`.
        sherlock_batch_id: Default batch id for the ``batch`` methods.
        request_timeout: Per-request timeout in seconds.
        max_retries: Retry attempts for connection errors and 502/503/504 on
            idempotent requests. Pass ``0`` to disable.
        session: An existing :class:`requests.Session` to use. When given, the
            caller stays responsible for closing it and for its retry policy.

    Raises:
        SherlockConfigurationError: If no port is given and ``SHERLOCK_PORT``
            is unset.

    Example:
        >>> with SherlockAPIClient(sherlock_port=8080) as client:  # doctest: +SKIP
        ...     cases = client.get_cases()
    """

    def __init__(
        self,
        sherlock_url: str | None = None,
        sherlock_port: str | int | None = None,
        sherlock_process_id: str | None = None,
        sherlock_case_id: str | None = None,
        sherlock_batch_id: str | None = None,
        *,
        request_timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        if sherlock_url is None:
            sherlock_url = os.getenv("SHERLOCK_URL") or DEFAULT_URL
        if sherlock_port is None:
            sherlock_port = os.getenv("SHERLOCK_PORT")
        if sherlock_port is None:
            raise SherlockConfigurationError(
                "sherlock_port is None and must be provided. "
                "If started within a Sherlock process, SHERLOCK_PORT must be set."
            )

        self.sherlock_api_url = f"{sherlock_url.rstrip('/')}:{sherlock_port}"

        self.sherlock_process_id = (
            sherlock_process_id
            if sherlock_process_id is not None
            else os.getenv("SHERLOCK_PROCESS_ID")
        )
        self.sherlock_case_id = (
            sherlock_case_id
            if sherlock_case_id is not None
            else os.getenv("SHERLOCK_CASE_ID")
        )
        self.sherlock_batch_id = (
            sherlock_batch_id
            if sherlock_batch_id is not None
            else os.getenv("SHERLOCK_BATCH_ID")
        )

        self.request_timeout = request_timeout
        self._owns_session = session is None
        self._session = session if session is not None else requests.Session()

        if self._owns_session and max_retries > 0:
            retry = Retry(
                total=max_retries,
                connect=max_retries,
                read=max_retries,
                status=max_retries,
                status_forcelist=_RETRY_STATUSES,
                allowed_methods=_RETRY_METHODS,
                backoff_factor=0.3,
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP session, unless it was supplied by the caller."""
        if self._owns_session:
            self._session.close()

    def __enter__(self) -> SherlockAPIClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(sherlock_api_url={self.sherlock_api_url!r})"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...] = (200,),
        timeout: float | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Perform a request, raising :class:`SherlockAPIError` on a bad status."""
        url = self.sherlock_api_url + path
        response = self._session.request(
            method,
            url,
            timeout=self.request_timeout if timeout is None else timeout,
            **kwargs,
        )
        if response.status_code not in expected:
            body = truncate_body(response.text)
            expected_str = " or ".join(str(code) for code in expected)
            raise exception_for_status(response.status_code)(
                f"{method} {url} failed: expected {expected_str}, got "
                f"{response.status_code} {response.reason}. Body: {body}",
                status_code=response.status_code,
                reason=response.reason,
                body=body,
                method=method,
                url=url,
            )
        return response

    @staticmethod
    def _resolve(value: str | None, fallback: str | None, name: str, caller: str) -> str:
        """Return ``value``, else ``fallback``, else raise a configuration error."""
        resolved = value if value is not None else fallback
        if resolved is None:
            raise SherlockConfigurationError(
                f"{caller} failed: {name} is None and must be provided as an "
                f"argument, to the constructor, or via the environment."
            )
        return resolved

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def get_file(self, file_hash: str) -> tuple[bytes, str]:
        """Download a file by hash.

        Returns:
            The raw bytes and a guessed extension such as ``".png"``.
        """
        response = self._request("GET", f"/file/{file_hash}")
        content_type = response.headers.get("Content-Type", "")
        if content_type.split(";")[0].strip() != "application/octet-stream":
            raise SherlockAPIError(
                f"get_file failed: expected Content-Type application/octet-stream, "
                f"got {content_type!r}",
                status_code=response.status_code,
                reason=response.reason,
                method="GET",
                url=response.url,
            )
        return response.content, guess_extension_by_magic(response.content)

    def post_file(self, file_path: str) -> str:
        """Upload the file at ``file_path``.

        Returns:
            The hash Sherlock stored the file under.
        """
        with open(file_path, "rb") as f:
            binary_data = f.read()
        return self._post_bytes(binary_data)

    def post_file_from_memory(self, byte_buffer: BytesIO) -> str:
        """Upload the contents of an in-memory buffer.

        Returns:
            The hash Sherlock stored the file under.
        """
        return self._post_bytes(byte_buffer)

    def _post_bytes(self, data: bytes | BytesIO) -> str:
        response = self._request(
            "POST",
            "/file",
            expected=(201,),
            data=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        return response.content.decode().strip('"')

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    def get_cases(self) -> JSONList:
        """List every case."""
        return _as_array(self._request("GET", "/case"))

    def get_case(self, case_id: str | None = None) -> JSONDict:
        """Get one case, defaulting to the client's case id."""
        case_id = self._resolve(case_id, self.sherlock_case_id, "case_id", "get_case")
        return _as_object(self._request("GET", f"/case/{case_id}"))

    def post_case(self, case: CreateCaseRequest) -> JSONDict:
        """Create a case."""
        return _as_object(
            self._request("POST", "/case", expected=(201,), json=case.to_dict())
        )

    # ------------------------------------------------------------------
    # Batches
    # ------------------------------------------------------------------

    def get_batch(self, batch_id: str | None = None) -> JSONDict:
        """Get one batch, defaulting to the client's batch id."""
        batch_id = self._resolve(
            batch_id, self.sherlock_batch_id, "batch_id", "get_batch"
        )
        return _as_object(self._request("GET", f"/batch/{batch_id}"))

    def get_batches_for_case(self, case_id: str | None = None) -> JSONList:
        """List the batches of a case, defaulting to the client's case id."""
        case_id = self._resolve(
            case_id, self.sherlock_case_id, "case_id", "get_batches_for_case"
        )
        return _as_array(self._request("GET", f"/case/{case_id}/batches"))

    def post_batch(self, batch: CreateBatchRequest) -> JSONDict:
        """Create a batch."""
        return _as_object(
            self._request("POST", "/batch", expected=(201,), json=batch.to_dict())
        )

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def get_image(self, image_id: str) -> JSONDict:
        """Get one image's metadata."""
        return _as_object(self._request("GET", f"/image/{image_id}"))

    def get_images_for_batch(self, batch_id: str | None = None) -> JSONList:
        """List the images of a batch, defaulting to the client's batch id."""
        batch_id = self._resolve(
            batch_id, self.sherlock_batch_id, "batch_id", "get_images_for_batch"
        )
        return _as_array(self._request("GET", f"/batch/{batch_id}/images"))

    def post_image(self, image: CreateImageRequest) -> JSONDict:
        """Register an already-uploaded image with a batch."""
        return _as_object(
            self._request("POST", "/image", expected=(201,), json=image.to_dict())
        )

    def upload_image(
        self,
        img: Image.Image,
        img_filename: str,
        decision_class: DecisionClass,
        batch_id: str | None = None,
        *,
        image_format: str = "PNG",
    ) -> JSONDict:
        """Encode, upload and register a Pillow image in one call.

        Args:
            img: The image to upload.
            img_filename: Name to show in Sherlock.
            decision_class: Inspection verdict for the image.
            batch_id: Target batch; defaults to the client's batch id.
            image_format: Pillow format to encode with, e.g. ``"PNG"``.

        Returns:
            The created image object.
        """
        batch_id = self._resolve(
            batch_id, self.sherlock_batch_id, "batch_id", "upload_image"
        )
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format=image_format)
        img_byte_arr.seek(0)
        file_hash = self.post_file_from_memory(img_byte_arr)
        return self.post_image(
            CreateImageRequest(batch_id, img_filename, decision_class, file_hash)
        )

    def upload_image_with_measurement(
        self,
        img: Image.Image,
        img_filename: str,
        decision_class: DecisionClass,
        measurement_key: str,
        measurement_value: str | float | int,
        batch_id: str | None = None,
        *,
        image_format: str = "PNG",
    ) -> JSONDict:
        """Upload an image and attach a single measurement.

        Returns:
            The created measurement object.
        """
        image_json = self.upload_image(
            img, img_filename, decision_class, batch_id, image_format=image_format
        )
        return self.post_measurement(
            CreateMeasurementRequest(image_json["id"], measurement_key, measurement_value)
        )

    def upload_image_with_measurements(
        self,
        img: Image.Image,
        img_filename: str,
        decision_class: DecisionClass,
        measurements: list[tuple[str, str | float | int]],
        batch_id: str | None = None,
        *,
        image_format: str = "PNG",
    ) -> tuple[JSONDict, JSONList]:
        """Upload an image and attach several measurements.

        Returns:
            The created image object and the created measurement objects, in
            the order the measurements were given.
        """
        image_json = self.upload_image(
            img, img_filename, decision_class, batch_id, image_format=image_format
        )
        created = [
            self.post_measurement(CreateMeasurementRequest(image_json["id"], key, value))
            for key, value in measurements
        ]
        return image_json, created

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def get_log(self, log_id: str) -> JSONDict:
        """Get one log entry."""
        return _as_object(self._request("GET", f"/log/{log_id}"))

    def post_log(self, log: LogRequest) -> JSONDict:
        """Create a log entry associated with a case, batch or image."""
        return _as_object(
            self._request("POST", "/log", expected=(201,), json=log.to_dict())
        )

    def log_case_error(self, case_id: str, log_body: str) -> JSONDict:
        """Log an error against a case."""
        return self.post_log(CreateCaseLogRequest(case_id, LogType.Error, log_body))

    def log_case_warning(self, case_id: str, log_body: str) -> JSONDict:
        """Log a warning against a case."""
        return self.post_log(CreateCaseLogRequest(case_id, LogType.Warning, log_body))

    def log_case_info(self, case_id: str, log_body: str) -> JSONDict:
        """Log an informational message against a case."""
        return self.post_log(CreateCaseLogRequest(case_id, LogType.Info, log_body))

    def log_batch_error(self, batch_id: str, log_body: str) -> JSONDict:
        """Log an error against a batch."""
        return self.post_log(CreateBatchLogRequest(batch_id, LogType.Error, log_body))

    def log_batch_warning(self, batch_id: str, log_body: str) -> JSONDict:
        """Log a warning against a batch."""
        return self.post_log(CreateBatchLogRequest(batch_id, LogType.Warning, log_body))

    def log_batch_info(self, batch_id: str, log_body: str) -> JSONDict:
        """Log an informational message against a batch."""
        return self.post_log(CreateBatchLogRequest(batch_id, LogType.Info, log_body))

    def log_image_error(self, image_id: str, log_body: str) -> JSONDict:
        """Log an error against an image."""
        return self.post_log(CreateImageLogRequest(image_id, LogType.Error, log_body))

    def log_image_warning(self, image_id: str, log_body: str) -> JSONDict:
        """Log a warning against an image."""
        return self.post_log(CreateImageLogRequest(image_id, LogType.Warning, log_body))

    def log_image_info(self, image_id: str, log_body: str) -> JSONDict:
        """Log an informational message against an image."""
        return self.post_log(CreateImageLogRequest(image_id, LogType.Info, log_body))

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------

    def get_measurement(self, measurement_id: str) -> JSONDict:
        """Get one measurement."""
        return _as_object(self._request("GET", f"/measurement/{measurement_id}"))

    def post_measurement(self, measurement: CreateMeasurementRequest) -> JSONDict:
        """Create a measurement on an image."""
        return _as_object(
            self._request(
                "POST", "/measurement", expected=(201,), json=measurement.to_dict()
            )
        )

    def delete_measurement(self, measurement_id: str) -> None:
        """Delete a measurement."""
        self._request("DELETE", f"/measurement/{measurement_id}", expected=(204,))

    # ------------------------------------------------------------------
    # Processes
    # ------------------------------------------------------------------

    def get_process_state(self, process_id: str | None = None) -> ProcessState | None:
        """Get the run state of a process.

        Returns:
            ``None`` if the process is unknown, e.g. never started or already
            gone; otherwise its :class:`~sherlock_api.ProcessState`.
        """
        process_id = self._resolve(
            process_id, self.sherlock_process_id, "process_id", "get_process_state"
        )
        response = self._request(
            "GET", f"/process/{process_id}/running", expected=(200, 404)
        )
        if response.status_code == 404:
            return None
        return ProcessState(response.text)

    def is_process_running(self, process_id: str | None = None) -> bool:
        """Whether the process exists and is currently running."""
        return self.get_process_state(process_id) is ProcessState.Running

    def post_modal(
        self,
        modal: CreateProcessModalDialogRequest,
        process_id: str | None = None,
    ) -> str:
        """Show a modal dialog in a running process.

        Returns:
            The id of the created modal, for use with :meth:`get_modal`.
        """
        process_id = self._resolve(
            process_id, self.sherlock_process_id, "process_id", "post_modal"
        )
        response = self._request(
            "POST",
            f"/process/{process_id}/modal",
            expected=(201,),
            json=modal.to_dict(),
        )
        return response.text

    def get_modal(
        self,
        modal_id: str,
        process_id: str | None = None,
        timeout: int = 10_000,
    ) -> DialogResult:
        """Long-poll a modal dialog for the operator's answer.

        Args:
            modal_id: Id returned by :meth:`post_modal`.
            process_id: Owning process; defaults to the client's process id.
            timeout: How long the *server* waits for an answer, in
                milliseconds. The client timeout is widened to match.

        Returns:
            :attr:`DialogResult.NoResponse` if the poll expired before the
            operator answered.
        """
        process_id = self._resolve(
            process_id, self.sherlock_process_id, "process_id", "get_modal"
        )
        # The server holds the request open for `timeout` ms, so the client
        # timeout must outlast it or we would abort our own long poll.
        client_timeout = max(self.request_timeout, timeout / 1000 + 5)
        response = self._request(
            "GET",
            f"/process/{process_id}/modal/{modal_id}",
            expected=(200, 408),
            params={"timeout": timeout},
            timeout=client_timeout,
        )
        if response.status_code == 408:
            return DialogResult.NoResponse
        return DialogResult(response.text)

    def delete_modal(self, modal_id: str, process_id: str | None = None) -> None:
        """Dismiss a modal dialog."""
        process_id = self._resolve(
            process_id, self.sherlock_process_id, "process_id", "delete_modal"
        )
        self._request(
            "DELETE", f"/process/{process_id}/modal/{modal_id}", expected=(204,)
        )

    def post_notification(
        self,
        notification: CreateNotificationRequest,
        process_id: str | None = None,
    ) -> None:
        """Send a notification to a running process.

        A missing process is logged as a warning rather than raised, since a
        notification is fire-and-forget and the process may legitimately have
        finished in the meantime.
        """
        process_id = self._resolve(
            process_id, self.sherlock_process_id, "process_id", "post_notification"
        )
        response = self._request(
            "POST",
            f"/process/{process_id}/notification",
            expected=(204, 404),
            json=notification.to_dict(),
        )
        if response.status_code == 404:
            logger.warning(
                "post_notification: process %s cannot be found, notification dropped.",
                process_id,
            )

    def get_env_state(self, process_id: str | None = None) -> str:
        """Get the last environment variable change of a process, as a string."""
        process_id = self._resolve(
            process_id, self.sherlock_process_id, "process_id", "get_env_state"
        )
        return self._request("GET", f"/process/{process_id}/vars/state").text

    def get_env_vars(self, process_id: str | None = None) -> JSONDict:
        """Get the effective environment variables of a process."""
        process_id = self._resolve(
            process_id, self.sherlock_process_id, "process_id", "get_env_vars"
        )
        return _as_object(self._request("GET", f"/process/{process_id}/vars"))
