# sherlock-api

Python client for the [Sherlock](https://github.com/kirillmeisser/sherlock-python-api) REST API.
Build your own Sherlock applications — create cases and batches, upload
inspection images with measurements, write log entries, and drive modal dialogs
and notifications in a running Sherlock process.

## Install

```bash
pip install sherlock-api
```

Requires Python 3.10+.

## Quickstart

```python
from PIL import Image
from sherlock_api import (
    SherlockAPIClient,
    CreateCaseRequest,
    CreateBatchRequest,
    RobotPlatform,
    DecisionClass,
)

with SherlockAPIClient(sherlock_port=8080) as client:
    case = client.post_case(
        CreateCaseRequest(
            "Bushing inspection", RobotPlatform.UNIVERSAL_ROBOTS, "0A0E012F7772596B03D92AAA544763BB"
        )
    )
    batch = client.post_batch(CreateBatchRequest(case["id"], "Batch 1"))

    image, measurements = client.upload_image_with_measurements(
        Image.open("part.png"),
        "part.png",
        DecisionClass.Ok,
        [("diameter_mm", 12.04), ("roundness", 0.98)],
        batch["id"],
    )

    client.log_batch_info(batch["id"], f"Uploaded {image['image_name']}")
```

## Configuration

Every constructor argument falls back to an environment variable. A script
launched *by* Sherlock gets these for free, so `SherlockAPIClient()` with no
arguments is usually all you need:

| Argument | Environment variable | Default |
| --- | --- | --- |
| `sherlock_url` | `SHERLOCK_URL` | `http://localhost` |
| `sherlock_port` | `SHERLOCK_PORT` | — (required) |
| `sherlock_process_id` | `SHERLOCK_PROCESS_ID` | `None` |
| `sherlock_case_id` | `SHERLOCK_CASE_ID` | `None` |
| `sherlock_batch_id` | `SHERLOCK_BATCH_ID` | `None` |

The three id defaults are used whenever you omit the corresponding argument —
`client.get_case()` reads `sherlock_case_id`, `client.get_batch()` reads
`sherlock_batch_id`, and the process methods read `sherlock_process_id`. Omitting
an argument that has no default raises `SherlockConfigurationError`.

Keyword-only options: `request_timeout` (seconds, default `30.0`), `max_retries`
(default `3`, applied to connection errors and 502/503/504 on GET and DELETE),
and `session` to supply your own `requests.Session`.

## Modal dialogs

`post_modal` returns a modal id; `get_modal` long-polls for the operator's
answer and returns `DialogResult.NoResponse` if the poll expires. Its `timeout`
is in **milliseconds** and is enforced by the server — the client timeout is
widened automatically to outlast it.

```python
from sherlock_api import (
    CreateProcessModalDialogRequest,
    DialogType,
    DialogResult,
    Language,
)

modal_id = client.post_modal(
    CreateProcessModalDialogRequest(DialogType.YesNo, Language.English, "Part looks OK?")
)

result = client.get_modal(modal_id, timeout=30_000)
if result is DialogResult.NoResponse:
    client.delete_modal(modal_id)
```

## Notifications

```python
from sherlock_api import CreateNotificationRequest, NotificationAttachment

client.post_notification(
    CreateNotificationRequest(
        "Batch finished",
        "42 parts inspected, 3 rejected.",
        [NotificationAttachment("report.pdf", "application/pdf", pdf_bytes)],
    )
)
```

A notification sent to a process that no longer exists is logged as a warning
on the `sherlock_api.client` logger rather than raised — it is fire-and-forget.

## API surface

| Area | Methods |
| --- | --- |
| Files | `get_file`, `post_file`, `post_file_from_memory` |
| Cases | `get_cases`, `get_case`, `post_case` |
| Batches | `get_batch`, `get_batches_for_case`, `post_batch` |
| Images | `get_image`, `get_images_for_batch`, `post_image`, `upload_image`, `upload_image_with_measurement`, `upload_image_with_measurements` |
| Logs | `get_log`, `post_log`, `log_{case,batch,image}_{error,warning,info}` |
| Measurements | `get_measurement`, `post_measurement`, `delete_measurement` |
| Processes | `get_process_state`, `is_process_running`, `get_env_state`, `get_env_vars`, `post_modal`, `get_modal`, `delete_modal`, `post_notification` |

Methods returning JSON return the parsed `dict` or `list` from the server as-is.

## Errors

```text
SherlockError
├── SherlockConfigurationError   (also a ValueError)  missing port or id
└── SherlockAPIError             (also a RuntimeError) unexpected HTTP status
    ├── SherlockBadRequestError  400
    ├── SherlockNotFoundError    404
    ├── SherlockTimeoutError     408
    └── SherlockServerError      5xx
```

`SherlockAPIError` carries `.status_code`, `.reason`, `.body` (truncated to 500
characters), `.method` and `.url`.

```python
from sherlock_api import SherlockNotFoundError

try:
    client.get_case("0" * 32)
except SherlockNotFoundError as err:
    print(err.status_code, err.url)
```

Network-level failures (`requests.ConnectionError`, `requests.Timeout`)
propagate from `requests` unchanged.

## Logging

The library logs to the `sherlock_api` logger and attaches a `NullHandler`, so
it stays silent until your application configures logging:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest            # offline, no Sherlock server needed
ruff check .
mypy src/
```

`examples/smoke_check.py` exercises the process endpoints against a live
Sherlock instance.

## License

Apache-2.0. See [LICENSE](LICENSE).
