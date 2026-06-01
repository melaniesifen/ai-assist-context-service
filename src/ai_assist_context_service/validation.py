from datetime import datetime, timezone

from .errors import ERROR_CODES, context_error


def assert_plain_object(value, field_name):
    if not isinstance(value, dict):
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            f"{field_name} must be an object",
            details={"field": field_name},
        )


def assert_non_empty_string(value, field_name):
    if not isinstance(value, str) or len(value.strip()) == 0:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            f"{field_name} must be a non-empty string",
            details={"field": field_name},
        )


def optional_non_empty_string(value, field_name):
    if value is None:
        return
    assert_non_empty_string(value, field_name)


def assert_date_like(value, field_name):
    try:
        _parse_datetime(value)
    except (TypeError, ValueError) as exc:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            f"{field_name} must be an ISO-8601 timestamp",
            details={"field": field_name},
        ) from exc


def to_datetime(value, field_name):
    assert_date_like(value, field_name)
    return _parse_datetime(value)


def _parse_datetime(value):
    if not isinstance(value, str):
        raise TypeError("timestamp must be a string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed.astimezone(timezone.utc)
