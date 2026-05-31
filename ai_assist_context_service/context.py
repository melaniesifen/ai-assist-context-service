from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .constants import DEFAULT_CONTEXT_TTL_MS
from .hash import hash_content
from .limits import apply_context_byte_limit
from .modes import validate_context_mode
from .provenance import classify_context_source, normalize_provenance
from .redaction import apply_context_redaction
from .validation import assert_non_empty_string, assert_plain_object


def normalize_context(input_value, options=None):
    options = options or {}
    assert_plain_object(input_value, "input")
    now = options.get("now", datetime.now(timezone.utc))
    captured_at = input_value.get("capturedAt", _to_iso(now))
    ttl_ms = options.get("ttlMs", DEFAULT_CONTEXT_TTL_MS)
    expires_at = input_value.get("expiresAt", _to_iso(now + timedelta(milliseconds=ttl_ms)))

    validate_context_mode(input_value.get("contextMode"))
    assert_non_empty_string(input_value.get("tenantId"), "input.tenantId")
    assert_non_empty_string(input_value.get("userId"), "input.userId")
    assert_non_empty_string(input_value.get("sessionId"), "input.sessionId")
    assert_non_empty_string(input_value.get("provider"), "input.provider")
    assert_plain_object(input_value.get("resourceRef"), "input.resourceRef")
    assert_non_empty_string(input_value["resourceRef"].get("resourceId"), "input.resourceRef.resourceId")
    assert_non_empty_string(input_value.get("content"), "input.content")

    redaction_result = apply_context_redaction(
        input_value["content"],
        {
            "policy": options.get("redactionPolicy"),
            "rules": options.get("redactionRules"),
        },
    )
    limit_result = apply_context_byte_limit(
        redaction_result["content"],
        {
            "max_bytes": options.get("maxBytes"),
            "oversized_behavior": options.get("oversizedBehavior", "truncate"),
            "rejection_reason": "context content exceeds configured safe limit",
        },
    )
    classification = classify_context_source(input_value)
    anchors = input_value.get("anchors") or {}
    provenance = normalize_provenance(
        {
            **input_value,
            "capturedAt": captured_at,
            "resourceId": input_value["resourceRef"]["resourceId"],
            "resourceVersion": input_value.get("resourceRevision") or input_value.get("resourceVersion"),
            "selectionAnchor": anchors.get("selectionAnchor"),
        }
    )

    return {
        "contextId": input_value.get("contextId") or str(uuid4()),
        "tenantId": input_value["tenantId"],
        "userId": input_value["userId"],
        "sessionId": input_value["sessionId"],
        "provider": input_value["provider"],
        "resourceRef": input_value["resourceRef"],
        "contextMode": input_value["contextMode"],
        "sourceType": classification["sourceType"],
        "trustLevel": classification["trustLevel"],
        "content": limit_result["content"],
        "contentHash": hash_content(limit_result["content"]),
        "anchors": anchors,
        "resourceRevision": input_value.get("resourceRevision"),
        "metadata": {
            **(input_value.get("metadata") or {}),
            "redaction": redaction_result["metadata"],
            "contentLimit": limit_result["metadata"],
        },
        "provenance": provenance,
        "capturedAt": captured_at,
        "expiresAt": expires_at,
        "clientSupplied": classification["clientSupplied"],
        "connectorVerified": classification["connectorVerified"],
    }


def _to_iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
