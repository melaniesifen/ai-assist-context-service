from datetime import datetime, timezone

from .constants import CONSENT_STATUSES, CONTEXT_MODES
from .errors import ERROR_CODES, context_error
from .modes import validate_context_mode
from .validation import (
    assert_non_empty_string,
    assert_plain_object,
    optional_non_empty_string,
    to_datetime,
)


def validate_context_consent_grant(grant, request, options=None):
    options = options or {}
    now = _utc_datetime(options.get("now", datetime.now(timezone.utc)))
    assert_plain_object(grant, "grant")
    assert_plain_object(request, "request")

    _validate_grant_shape(grant)
    validate_context_request_shape(request)
    validate_context_mode(grant.get("contextMode"))

    mismatches = []
    _collect_mismatch(mismatches, grant.get("tenantId"), request.get("tenantId"), "tenantId")
    _collect_mismatch(mismatches, grant.get("userId"), request.get("userId"), "userId")
    _collect_mismatch(mismatches, grant.get("provider"), request.get("provider"), "provider")

    if not _context_mode_covers(grant.get("contextMode"), request.get("contextMode")):
        mismatches.append("contextMode")
    if not _resource_boundary_covers(grant, request):
        mismatches.append("resourceRef")
    if len(mismatches) > 0:
        raise context_error(
            ERROR_CODES["CONSENT_DENIED"],
            "consent grant does not cover the context request",
            http_status=403,
            details={"fields": mismatches},
        )

    if grant.get("status") != CONSENT_STATUSES["ACTIVE"]:
        raise context_error(
            ERROR_CODES["CONSENT_DENIED"],
            "consent grant is not active",
            http_status=403,
            details={"grantId": grant.get("grantId"), "status": grant.get("status")},
        )

    if grant.get("expiresAt") and to_datetime(grant["expiresAt"], "grant.expiresAt") <= now:
        raise context_error(
            ERROR_CODES["CONSENT_DENIED"],
            "consent grant has expired",
            http_status=403,
            details={"grantId": grant.get("grantId")},
        )

    return {"valid": True, "grantId": grant["grantId"]}


def validate_consent_for_context_request(request, options=None):
    options = options or {}
    now = _utc_datetime(options.get("now", datetime.now(timezone.utc)))
    assert_plain_object(request, "request")
    validate_context_request_shape(request)

    if request.get("contextMode") == CONTEXT_MODES["SELECTION"] and request.get("explicitUserAction") is True:
        consent_grant = request.get("consentGrant") or {}
        return {
            "valid": True,
            "grantId": consent_grant.get("grantId"),
            "explicitUserAction": True,
        }

    if not request.get("consentGrant"):
        raise context_error(
            ERROR_CODES["CONSENT_REQUIRED"],
            "an active consent grant is required",
            http_status=403,
            details={"contextMode": request.get("contextMode"), "provider": request.get("provider")},
        )

    return validate_context_consent_grant(request["consentGrant"], request, {"now": now})


def validate_active_consent_for_apply_target(request, options=None):
    """Require active persisted consent before an apply-action connector mutation."""
    options = options or {}
    now = _utc_datetime(options.get("now", datetime.now(timezone.utc)))
    assert_plain_object(request, "request")
    validate_context_request_shape(request)

    if not request.get("consentGrant"):
        raise context_error(
            ERROR_CODES["CONSENT_REQUIRED"],
            "an active consent grant is required before apply-action mutation",
            http_status=403,
            details={"contextMode": request.get("contextMode"), "provider": request.get("provider")},
        )

    return validate_context_consent_grant(request["consentGrant"], request, {"now": now})


def validate_context_request_shape(request):
    assert_non_empty_string(request.get("tenantId"), "request.tenantId")
    assert_non_empty_string(request.get("userId"), "request.userId")
    assert_non_empty_string(request.get("provider"), "request.provider")
    validate_context_mode(request.get("contextMode"))
    assert_plain_object(request.get("resourceRef"), "request.resourceRef")
    assert_non_empty_string(request["resourceRef"].get("provider"), "request.resourceRef.provider")
    assert_non_empty_string(request["resourceRef"].get("resourceId"), "request.resourceRef.resourceId")

    if request["resourceRef"].get("provider") != request.get("provider"):
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "request.resourceRef.provider must match request.provider",
            details={"fields": ["request.provider", "request.resourceRef.provider"]},
        )


def _validate_grant_shape(grant):
    assert_non_empty_string(grant.get("grantId"), "grant.grantId")
    assert_non_empty_string(grant.get("tenantId"), "grant.tenantId")
    assert_non_empty_string(grant.get("userId"), "grant.userId")
    assert_non_empty_string(grant.get("provider"), "grant.provider")
    assert_non_empty_string(grant.get("contextMode"), "grant.contextMode")
    assert_non_empty_string(grant.get("status"), "grant.status")
    to_datetime(grant.get("grantedAt"), "grant.grantedAt")
    optional_non_empty_string(grant.get("revokedAt"), "grant.revokedAt")
    if grant.get("revokedAt"):
        to_datetime(grant["revokedAt"], "grant.revokedAt")
    if grant.get("expiresAt"):
        to_datetime(grant["expiresAt"], "grant.expiresAt")

    valid_statuses = tuple(CONSENT_STATUSES.values())
    if grant.get("status") not in valid_statuses:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "grant.status is not recognized",
            details={"field": "grant.status", "allowedStatuses": valid_statuses},
        )

    if grant.get("contextMode") in (CONTEXT_MODES["SELECTION"], CONTEXT_MODES["ACTIVE_RESOURCE"]):
        assert_plain_object(grant.get("resourceRef"), "grant.resourceRef")
        assert_non_empty_string(grant["resourceRef"].get("provider"), "grant.resourceRef.provider")
        assert_non_empty_string(grant["resourceRef"].get("resourceId"), "grant.resourceRef.resourceId")

    if grant.get("contextMode") == CONTEXT_MODES["WORKSPACE"]:
        assert_plain_object(grant.get("workspaceBoundary"), "grant.workspaceBoundary")
        assert_non_empty_string(grant["workspaceBoundary"].get("boundaryId"), "grant.workspaceBoundary.boundaryId")

    if not isinstance(grant.get("scopes"), list) or len(grant["scopes"]) == 0:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "grant.scopes must contain at least one scope",
            details={"field": "grant.scopes"},
        )


def _context_mode_covers(grant_mode, requested_mode):
    return grant_mode == requested_mode


def _resource_boundary_covers(grant, request):
    if request.get("contextMode") == CONTEXT_MODES["WORKSPACE"]:
        return (
            (grant.get("workspaceBoundary") or {}).get("boundaryId")
            == (request.get("workspaceBoundary") or {}).get("boundaryId")
        )

    requested_resource_id = (request.get("resourceRef") or {}).get("resourceId")
    if not requested_resource_id:
        return False
    return (
        (grant.get("resourceRef") or {}).get("provider") == request.get("provider")
        and (grant.get("resourceRef") or {}).get("provider") == (request.get("resourceRef") or {}).get("provider")
        and (grant.get("resourceRef") or {}).get("resourceId") == requested_resource_id
    )


def _collect_mismatch(mismatches, actual, expected, field_name):
    if actual != expected:
        mismatches.append(field_name)


def _utc_datetime(value):
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
