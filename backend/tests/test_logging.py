# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# _JsonFormatter/_TextFormatter's handling of logging.info(..., extra={...})
# — the structured-fields mechanism chat_service's per-turn tool-selection
# telemetry relies on (see app/services/chat_service.py's "chat_tool_selection"
# log line).

import json
import logging

from app.core.logging import _JsonFormatter, _TextFormatter


def _make_record(*, extra: dict | None = None) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="turn complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return record


def test_json_formatter_includes_extra_fields() -> None:
    record = _make_record(extra={"event": "chat_tool_selection", "tools_used": ["web_search"]})

    payload = json.loads(_JsonFormatter().format(record))

    assert payload["message"] == "turn complete"
    assert payload["event"] == "chat_tool_selection"
    assert payload["tools_used"] == ["web_search"]


def test_json_formatter_without_extra_has_only_fixed_fields() -> None:
    record = _make_record()

    payload = json.loads(_JsonFormatter().format(record))

    assert set(payload) == {"timestamp", "level", "logger", "message", "request_id"}


def test_text_formatter_appends_extra_fields() -> None:
    formatter = _TextFormatter("%(levelname)-8s | [%(request_id)s] | %(message)s")
    record = _make_record(extra={"tool_hops": 2})

    output = formatter.format(record)

    assert "turn complete" in output
    assert "tool_hops=2" in output


def test_text_formatter_without_extra_is_unchanged() -> None:
    formatter = _TextFormatter("%(levelname)-8s | [%(request_id)s] | %(message)s")
    record = _make_record()

    output = formatter.format(record)

    assert output == "INFO     | [req-123] | turn complete"
