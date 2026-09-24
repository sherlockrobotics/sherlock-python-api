from __future__ import annotations

import pytest

from sherlock_api import SherlockAPIClient

BASE_URL = "http://sherlock.test:8080"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Keep a developer's real SHERLOCK_* variables out of the tests."""
    for name in (
        "SHERLOCK_URL",
        "SHERLOCK_PORT",
        "SHERLOCK_PROCESS_ID",
        "SHERLOCK_CASE_ID",
        "SHERLOCK_BATCH_ID",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client():
    with SherlockAPIClient(
        sherlock_url="http://sherlock.test",
        sherlock_port=8080,
        request_timeout=1.0,
        max_retries=0,
    ) as c:
        yield c
