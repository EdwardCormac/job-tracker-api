import json
import logging
import sys

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.logging_config import JsonFormatter
from app.main import app


def request_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == "app.request"]


def test_json_formatter_outputs_standard_and_extra_fields() -> None:
    record = logging.makeLogRecord(
        {
            "name": "app.test",
            "levelno": logging.WARNING,
            "levelname": "WARNING",
            "msg": "Hello %s",
            "args": ("world",),
            "fields": {"path": "/applications"},
        }
    )

    entry = json.loads(JsonFormatter().format(record))

    assert entry["level"] == "WARNING"
    assert entry["logger"] == "app.test"
    assert entry["message"] == "Hello world"
    assert entry["path"] == "/applications"
    assert entry["timestamp"].endswith("+00:00")


def test_json_formatter_keeps_traceback_in_one_line() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.makeLogRecord({"msg": "failed", "exc_info": sys.exc_info()})

    line = JsonFormatter().format(record)

    assert "\n" not in line
    assert "ValueError: boom" in json.loads(line)["exception"]


def test_request_is_logged_with_status_and_duration(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="app.request")

    client.get("/applications/999")

    [record] = request_records(caplog)
    fields = getattr(record, "fields")
    assert record.levelno == logging.INFO
    assert fields["method"] == "GET"
    assert fields["path"] == "/applications/999"
    assert fields["status_code"] == 404
    assert fields["duration_ms"] >= 0


def test_health_checks_are_logged_at_debug(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="app.request")

    client.get("/health/live")

    [record] = request_records(caplog)
    assert record.levelno == logging.DEBUG


def test_unhandled_error_is_logged_as_500(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    def buggy_db() -> None:
        raise RuntimeError("secret internal detail")

    app.dependency_overrides[get_db] = buggy_db
    caplog.set_level(logging.DEBUG, logger="app.request")

    TestClient(app, raise_server_exceptions=False).get("/applications")

    [record] = request_records(caplog)
    assert getattr(record, "fields")["status_code"] == 500
