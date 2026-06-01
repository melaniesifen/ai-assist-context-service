import re

from .validation import assert_non_empty_string

REDACTION_POLICIES = {
    "NONE": "none",
    "MVP_DEFAULT": "mvp_default",
}

DEFAULT_REDACTION_RULES = (
    {
        "id": "email_address",
        "pattern": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        "replacement": "<redacted:email_address>",
    },
    {
        "id": "api_key_like_secret",
        "pattern": re.compile(r"\b(?:sk|pk|api|token|secret)[_-][A-Za-z0-9_-]{16,}\b"),
        "replacement": "<redacted:secret>",
    },
    {
        "id": "bearer_token",
        "pattern": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE),
        "replacement": "Bearer <redacted:token>",
    },
)


def apply_context_redaction(content, options=None):
    options = options or {}
    assert_non_empty_string(content, "content")
    policy = options.get("policy", REDACTION_POLICIES["NONE"])
    if policy is None:
        policy = REDACTION_POLICIES["NONE"]

    if policy == REDACTION_POLICIES["NONE"]:
        return {
            "content": content,
            "metadata": {
                "policy": policy,
                "redacted": False,
                "rulesApplied": [],
            },
        }

    if policy != REDACTION_POLICIES["MVP_DEFAULT"]:
        raise TypeError(f"Unsupported redaction policy: {policy}")

    rules = options.get("rules") or DEFAULT_REDACTION_RULES
    redacted_content = content
    rules_applied = []

    for rule in rules:
        next_content = rule["pattern"].sub(rule["replacement"], redacted_content)
        if next_content != redacted_content:
            rules_applied.append(rule["id"])
            redacted_content = next_content

    return {
        "content": redacted_content,
        "metadata": {
            "policy": policy,
            "redacted": len(rules_applied) > 0,
            "rulesApplied": rules_applied,
        },
    }
