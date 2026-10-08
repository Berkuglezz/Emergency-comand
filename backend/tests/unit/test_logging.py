import logging

import pytest

from app.core.logging import REDACTED, RedactingFilter, redact


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        ("login password=hunter2 ok", "hunter2"),
        ('payload {"password": "hunter2"}', "hunter2"),
        ("Authorization: Bearer abc.def-ghi", "abc.def-ghi"),
        ("refresh_token=xyz123; Path=/", "xyz123"),
        ("cookie: session=abc", "session=abc"),
        ("token eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl", "eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl"),
    ],
)
def test_redact_hides_sensitive_values(message: str, secret: str) -> None:
    redacted = redact(message)
    assert secret not in redacted
    assert REDACTED in redacted


def test_redact_keeps_ordinary_messages() -> None:
    message = "GET /api/v1/health 200"
    assert redact(message) == message


def test_filter_redacts_formatted_args() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="credenciales %s",
        args=("password=hunter2",),
        exc_info=None,
    )
    assert RedactingFilter().filter(record)
    assert "hunter2" not in record.getMessage()
