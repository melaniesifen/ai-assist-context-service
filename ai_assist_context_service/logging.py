from .validation import assert_plain_object


def build_context_log_metadata(context):
    assert_plain_object(context, "context")
    content_limit = (context.get("metadata") or {}).get("contentLimit") or {}
    redaction = (context.get("metadata") or {}).get("redaction")

    return {
        "contextId": context.get("contextId"),
        "tenantId": context.get("tenantId"),
        "userId": context.get("userId"),
        "sessionId": context.get("sessionId"),
        "provider": context.get("provider"),
        "resourceRef": (
            {
                "provider": context["resourceRef"].get("provider"),
                "resourceId": context["resourceRef"].get("resourceId"),
            }
            if context.get("resourceRef")
            else None
        ),
        "contextMode": context.get("contextMode"),
        "sourceType": context.get("sourceType"),
        "trustLevel": context.get("trustLevel"),
        "contentHash": context.get("contentHash"),
        "contentBytes": {
            "originalBytes": content_limit.get("originalBytes"),
            "returnedBytes": content_limit.get("returnedBytes"),
            "maxBytes": content_limit.get("maxBytes"),
            "truncated": content_limit.get("truncated") is True,
        },
        "redaction": (
            {
                "policy": redaction.get("policy"),
                "redacted": redaction.get("redacted") is True,
                "rulesApplied": list(redaction.get("rulesApplied") or []),
            }
            if redaction
            else None
        ),
        "clientSupplied": context.get("clientSupplied") is True,
        "connectorVerified": context.get("connectorVerified") is True,
        "capturedAt": context.get("capturedAt"),
        "expiresAt": context.get("expiresAt"),
    }
