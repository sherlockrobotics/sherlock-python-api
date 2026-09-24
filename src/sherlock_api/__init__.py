"""Python client for the Sherlock REST API.

Quickstart::

    from sherlock_api import SherlockAPIClient, CreateCaseRequest, RobotPlatform

    with SherlockAPIClient(sherlock_port=8080) as client:
        case = client.post_case(
            CreateCaseRequest("My case", RobotPlatform.UNIVERSAL_ROBOTS, "inspect")
        )

When a script is launched by Sherlock itself, the connection details come from
the ``SHERLOCK_*`` environment variables and ``SherlockAPIClient()`` needs no
arguments at all.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version

from .batches import CreateBatchRequest
from .cases import CreateCaseRequest, RobotPlatform
from .client import DEFAULT_TIMEOUT, DEFAULT_URL, SherlockAPIClient
from .exceptions import (
    SherlockAPIError,
    SherlockBadRequestError,
    SherlockConfigurationError,
    SherlockError,
    SherlockNotFoundError,
    SherlockServerError,
    SherlockTimeoutError,
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
    DialogType,
    Language,
    NotificationAttachment,
    ProcessState,
)
from .validation import is_valid_uuid32

try:
    __version__ = version("sherlock-api")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0.dev0"

# A library should not configure logging for its host application.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "__version__",
    # Client
    "SherlockAPIClient",
    "DEFAULT_URL",
    "DEFAULT_TIMEOUT",
    # Exceptions
    "SherlockError",
    "SherlockConfigurationError",
    "SherlockAPIError",
    "SherlockBadRequestError",
    "SherlockNotFoundError",
    "SherlockTimeoutError",
    "SherlockServerError",
    # Cases
    "CreateCaseRequest",
    "RobotPlatform",
    # Batches
    "CreateBatchRequest",
    # Images
    "CreateImageRequest",
    "DecisionClass",
    # Logs
    "LogType",
    "LogRequest",
    "CreateCaseLogRequest",
    "CreateBatchLogRequest",
    "CreateImageLogRequest",
    # Measurements
    "CreateMeasurementRequest",
    # Processes
    "ProcessState",
    "DialogType",
    "DialogResult",
    "Language",
    "CreateProcessModalDialogRequest",
    "CreateNotificationRequest",
    "NotificationAttachment",
    # Helpers
    "guess_extension_by_magic",
    "is_valid_uuid32",
]
