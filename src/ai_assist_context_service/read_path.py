from .consent import validate_consent_for_context_request
from .context import normalize_context
from .errors import ERROR_CODES, context_error
from .validation import assert_plain_object


def read_context_with_consent(request, connector_read_context, options=None):
    """Validate consent before invoking an injected connector read boundary."""
    options = options or {}
    if not callable(connector_read_context):
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "connector_read_context must be callable",
            details={"field": "connector_read_context"},
        )

    consent_options = {}
    if "now" in options:
        consent_options["now"] = options["now"]
    consent = validate_consent_for_context_request(request, consent_options)
    connector_result = connector_read_context(_connector_request(request, consent))
    assert_plain_object(connector_result, "connectorResult")

    context_input = connector_result.get("context")
    assert_plain_object(context_input, "connectorResult.context")
    normalize_options = {"oversizedBehavior": options.get("oversizedBehavior", "truncate")}
    for key in ("now", "ttlMs", "maxBytes", "redactionPolicy", "redactionRules"):
        if key in options:
            normalize_options[key] = options[key]
    context = normalize_context(context_input, normalize_options)

    return {
        "consent": consent,
        "context": context,
        "resourceRevision": connector_result.get("resourceRevision") or context.get("resourceRevision"),
    }


def _connector_request(request, consent):
    connector_request = {key: value for key, value in request.items() if key != "consentGrant"}
    if consent.get("grantId"):
        connector_request["consentGrantId"] = consent["grantId"]
    return connector_request
