from .constants import DEFAULT_MAX_CONTEXT_BYTES
from .errors import ERROR_CODES, context_error


def apply_context_byte_limit(content, options=None):
    options = options or {}
    max_bytes = options.get("max_bytes", DEFAULT_MAX_CONTEXT_BYTES)
    if max_bytes is None:
        max_bytes = DEFAULT_MAX_CONTEXT_BYTES
    oversized_behavior = options.get("oversized_behavior", "truncate")
    rejection_reason = options.get("rejection_reason", "context content exceeds maxBytes")

    original_bytes = len(content.encode("utf-8"))
    if original_bytes <= max_bytes:
        return {
            "content": content,
            "metadata": {
                "truncated": False,
                "originalBytes": original_bytes,
                "returnedBytes": original_bytes,
                "maxBytes": max_bytes,
            },
        }

    if oversized_behavior == "reject":
        raise context_error(
            ERROR_CODES["CONTEXT_TOO_LARGE"],
            rejection_reason,
            http_status=413,
            details={"originalBytes": original_bytes, "maxBytes": max_bytes},
        )

    truncated_content = _truncate_utf8(content, max_bytes)
    return {
        "content": truncated_content,
        "metadata": {
            "truncated": True,
            "originalBytes": original_bytes,
            "returnedBytes": len(truncated_content.encode("utf-8")),
            "maxBytes": max_bytes,
            "truncationReason": "maxBytes",
        },
    }


def _truncate_utf8(content, max_bytes):
    byte_count = 0
    output = []
    for char in content:
        char_bytes = len(char.encode("utf-8"))
        if byte_count + char_bytes > max_bytes:
            break
        output.append(char)
        byte_count += char_bytes
    return "".join(output)
