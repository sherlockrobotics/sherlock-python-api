"""Manual smoke check against a live Sherlock instance.

Unlike ``tests/``, this talks to a real server. Run it with the process
endpoints in mind::

    SHERLOCK_PORT=8080 SHERLOCK_PROCESS_ID=<32-hex-id> python examples/smoke_check.py

The functions are named ``check_*`` rather than ``test_*`` on purpose, so that
pytest never collects them and fires live HTTP during a normal test run.
"""

from __future__ import annotations

import os
from time import sleep

from sherlock_api import (
    CreateNotificationRequest,
    CreateProcessModalDialogRequest,
    DialogResult,
    DialogType,
    Language,
    SherlockAPIClient,
)

SHERLOCK_URL = os.getenv("SHERLOCK_URL", "http://localhost")
SHERLOCK_PORT = os.getenv("SHERLOCK_PORT", "8080")
PROCESS_ID = os.getenv("SHERLOCK_PROCESS_ID", "8957CBFC162F6A1F713F269CE8BD6F8A")


def make_client() -> SherlockAPIClient:
    return SherlockAPIClient(
        sherlock_url=SHERLOCK_URL,
        sherlock_port=SHERLOCK_PORT,
        sherlock_process_id=PROCESS_ID,
    )


def check_get_env_vars(client: SherlockAPIClient) -> None:
    print("env vars:", client.get_env_vars())


def check_get_env_state(client: SherlockAPIClient) -> None:
    print("env state:", client.get_env_state())


def check_get_process_state(client: SherlockAPIClient) -> None:
    print("process state:", client.get_process_state())
    print("running:", client.is_process_running())


def check_post_notification(client: SherlockAPIClient) -> None:
    client.post_notification(
        CreateNotificationRequest("Smoke check", "Hello from sherlock-api.")
    )
    print("notification sent")


def check_create_and_delete_modal(client: SherlockAPIClient) -> None:
    modal_id = client.post_modal(
        CreateProcessModalDialogRequest(
            DialogType.ContinueAbort, Language.English, "Smoke check: continue?"
        )
    )
    print("modal id:", modal_id)

    result = client.get_modal(modal_id, timeout=5_000)
    print("modal result:", result)

    if result is DialogResult.NoResponse:
        sleep(1)
        client.delete_modal(modal_id)
        print("modal dismissed")


def main() -> None:
    with make_client() as client:
        check_get_process_state(client)
        check_get_env_state(client)
        check_get_env_vars(client)
        check_post_notification(client)
        check_create_and_delete_modal(client)


if __name__ == "__main__":
    main()
