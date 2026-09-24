# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-19

First packaged release. The code previously lived as loose top-level modules
that could only be imported from the repository root; it is now the installable
`sherlock-api` distribution exposing the `sherlock_api` package.

### Added

- `pip install sherlock-api`, with `requests` and `Pillow` declared as
  dependencies and `py.typed` shipped so type checkers see the inline hints.
- A single public import surface: `from sherlock_api import SherlockAPIClient, ...`.
- Exception hierarchy in `sherlock_api.exceptions` — `SherlockError`,
  `SherlockConfigurationError`, `SherlockAPIError` and the status-specific
  `SherlockBadRequestError` / `SherlockNotFoundError` / `SherlockTimeoutError` /
  `SherlockServerError`. `SherlockAPIError` subclasses `RuntimeError` and
  `SherlockConfigurationError` subclasses `ValueError`, so existing
  `except RuntimeError` / `except ValueError` handlers keep working.
- Connection reuse via a `requests.Session`, a `request_timeout` (default 30 s)
  applied to every call, and retries for connection errors and 502/503/504 on
  GET/DELETE. `SherlockAPIClient` is now a context manager and has `close()`.
- `log_case_error/warning/info` and `log_image_error/warning/info`, matching the
  batch-level helpers that already existed.
- `image_format` parameter on the `upload_image*` methods (previously always PNG).
- `SHERLOCK_URL` environment variable, alongside the existing `SHERLOCK_PORT`,
  `SHERLOCK_PROCESS_ID`, `SHERLOCK_CASE_ID` and `SHERLOCK_BATCH_ID`.
- Docstrings throughout and return type annotations on every public method.

### Fixed

- **`image_utils` imported a name that does not exist** (`post_file_from_memory`
  from `file_utils`), which made the whole library unimportable.
- **Environment variables were read at import time**, because `os.getenv(...)`
  sat in the constructor's default arguments. Any `SHERLOCK_*` variable set
  after the module was first imported was silently ignored. They are now read
  per instantiation.
- **No request had a client-side timeout**, so a call could hang forever.
  `get_modal` widens its own timeout to outlast its server-side long poll.
- `get_file` compared `Content-Type` for exact equality and so rejected a
  valid `application/octet-stream; charset=...`.
- The library called `print()` on the `post_notification` 404 path; it now logs
  to the `sherlock_api.client` logger.
- Unbounded response bodies were interpolated into exception messages; they are
  truncated to 500 characters.
- `sherlock_batch_id` was accepted by the constructor but never used; it is now
  the fallback for `get_batch`, `get_images_for_batch` and `upload_image*`.
- `.txt` detection in `guess_extension_by_magic` no longer classifies any binary
  containing a newline in its first 512 bytes as text.

### Changed (breaking)

- Import paths. `from sherlock_api_client import SherlockAPIClient` becomes
  `from sherlock_api import SherlockAPIClient`; the `*_utils` modules are now
  `sherlock_api.cases`, `.batches`, `.images`, `.logs`, `.measurements`,
  `.process`, `.files` and `.validation`.
- `post_modal`, `get_modal` and `delete_modal` take `process_id` as an optional
  trailing argument that falls back to the client's process id, like every other
  process method. `post_modal(process_id, modal)` becomes `post_modal(modal)`.
- The `upload_image*` methods take `decision_class` before `batch_id`, so that
  the now-optional `batch_id` comes last.
- `upload_image_with_measurements` returns `(image, [measurement, ...])` instead
  of `None`.
- `delete_measurement` and `delete_modal` are annotated `-> None` (unchanged
  behaviour, they never returned anything).
- Request models are dataclasses. `CreateImageRequest.image_data` is now
  `.image_hash`; the wire field is still `image_data`.
- `CreateMeasurementRequest.value` accepts `int` and `float` and stringifies
  them, instead of requiring the caller to do it.
