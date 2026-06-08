from .constants import CONTEXT_MODES, SOURCE_TYPES, TRUST_LEVELS
from .errors import ERROR_CODES, context_error
from .validation import assert_non_empty_string, assert_plain_object


def classify_context_source(input_value):
    assert_plain_object(input_value, "input")

    if input_value.get("clientSupplied") is True and input_value.get("connectorVerified") is True:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "context cannot be both client-supplied and connector-verified",
            details={"fields": ["clientSupplied", "connectorVerified"]},
        )

    if input_value.get("clientSupplied") is True:
        return {
            "sourceType": SOURCE_TYPES["CLIENT_SELECTION_TEXT"],
            "trustLevel": TRUST_LEVELS["CLIENT_SUPPLIED"],
            "clientSupplied": True,
            "connectorVerified": False,
        }

    if input_value.get("connectorVerified") is True:
        return {
            "sourceType": _source_type_for_connector_context(input_value.get("contextMode")),
            "trustLevel": TRUST_LEVELS["CONNECTOR_VERIFIED"],
            "clientSupplied": False,
            "connectorVerified": True,
        }

    raise context_error(
        ERROR_CODES["VALIDATION_ERROR"],
        "context source must be classified",
        details={"requiredOneOf": ["clientSupplied", "connectorVerified"]},
    )


def normalize_provenance(input_value):
    assert_plain_object(input_value, "input")
    classification = classify_context_source(input_value)
    assert_non_empty_string(input_value.get("connector"), "input.connector")
    assert_non_empty_string(input_value.get("resourceId"), "input.resourceId")

    return {
        "sourceType": classification["sourceType"],
        "trustLevel": classification["trustLevel"],
        "connector": input_value["connector"],
        "resourceId": input_value["resourceId"],
        "resourceVersion": input_value.get("resourceVersion"),
        "selectionAnchor": input_value.get("selectionAnchor"),
        "capturedAt": input_value.get("capturedAt"),
        "clientSupplied": classification["clientSupplied"],
        "connectorVerified": classification["connectorVerified"],
    }


def assert_connector_verified_for_write_back(context):
    if not is_connector_verified_write_back_eligible(context):
        raise context_error(
            ERROR_CODES["CONNECTOR_VERIFICATION_REQUIRED"],
            "connector-verified resource revision and target metadata are required for write-back",
            http_status=422,
            details={
                "contextId": _get(context, "contextId"),
                "trustLevel": _get(context, "trustLevel"),
                "sourceType": _get(context, "sourceType"),
                "hasResourceRevision": bool(_get(context, "resourceRevision")),
                "hasAnchorOrRange": bool(
                    _get_nested(context, ("anchors", "selectionAnchor"))
                    or _get_nested(context, ("anchors", "targetRange"))
                ),
                "hasOriginalTextHash": bool(_target_original_text_hash(context)),
                "truncated": _get_nested(context, ("metadata", "contentLimit", "truncated")) is True,
                "redacted": _get_nested(context, ("metadata", "redaction", "redacted")) is True,
            },
        )
    return True


def connector_verified_write_back_target_metadata(context):
    assert_connector_verified_for_write_back(context)
    anchors = _get(context, "anchors") or {}
    resource_ref = _get(context, "resourceRef") or {}
    original_text_hash = _target_original_text_hash(context)

    return {
        "contextId": _get(context, "contextId"),
        "provider": _get(context, "provider"),
        "resourceRef": {
            "provider": resource_ref.get("provider"),
            "resourceId": resource_ref.get("resourceId"),
        },
        "contextMode": _get(context, "contextMode"),
        "resourceRevision": _get(context, "resourceRevision"),
        "targetRange": anchors.get("targetRange"),
        "selectionAnchor": anchors.get("selectionAnchor"),
        "originalTextHash": original_text_hash,
        "sourceType": _get(context, "sourceType"),
        "trustLevel": _get(context, "trustLevel"),
        "capturedAt": _get(context, "capturedAt"),
    }


def is_connector_verified_write_back_eligible(context):
    return (
        _get(context, "connectorVerified") is True
        and _get(context, "trustLevel") == TRUST_LEVELS["CONNECTOR_VERIFIED"]
        and isinstance(_get(context, "contentHash"), str)
        and len(_get(context, "contentHash").strip()) > 0
        and bool(_get(context, "resourceRevision"))
        and bool(_get_nested(context, ("anchors", "selectionAnchor")) or _get_nested(context, ("anchors", "targetRange")))
        and bool(_target_original_text_hash(context))
        and _get_nested(context, ("metadata", "contentLimit", "truncated")) is not True
        and _get_nested(context, ("metadata", "redaction", "redacted")) is not True
    )


def _source_type_for_connector_context(context_mode):
    if context_mode == CONTEXT_MODES["SELECTION"]:
        return SOURCE_TYPES["CONNECTOR_SELECTION"]
    if context_mode == CONTEXT_MODES["ACTIVE_RESOURCE"]:
        return SOURCE_TYPES["CONNECTOR_RESOURCE_EXCERPT"]
    if context_mode == CONTEXT_MODES["VISIBLE_REGION"]:
        return SOURCE_TYPES["CONNECTOR_VISIBLE_REGION"]
    if context_mode == CONTEXT_MODES["WORKSPACE"]:
        return SOURCE_TYPES["CONNECTOR_WORKSPACE_EXCERPT"]
    return SOURCE_TYPES["SCREEN_CAPTURE"]


def _get(context, key):
    return context.get(key) if isinstance(context, dict) else None


def _get_nested(context, keys):
    current = context
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _target_original_text_hash(context):
    anchors_hash = _get_nested(context, ("anchors", "originalTextHash"))
    metadata_hash = _get_nested(context, ("metadata", "writeBackTarget", "originalTextHash"))
    for value in (anchors_hash, metadata_hash):
        if isinstance(value, str) and len(value.strip()) > 0:
            return value
    return None
