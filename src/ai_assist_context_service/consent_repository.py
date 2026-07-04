from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .consent import validate_context_consent_grant, validate_context_request_shape
from .constants import CONSENT_STATUSES, CONTEXT_MODES
from .errors import ERROR_CODES, context_error
from .validation import assert_non_empty_string, assert_plain_object, to_datetime


DEFAULT_CONSENT_GRANT_TABLE_ENV = "CONSENT_GRANT_TABLE_NAME"
GOOGLE_DOCS_PROVIDER = "google_docs"
GOOGLE_DOCS_ACTIVE_RESOURCE_SCOPES = ("docs.read", "docs.write")


class ContextConsentGrantRepository:
    """Repository contract for metadata-only context consent grants."""

    def create_google_docs_active_resource_grant(self, grant: dict[str, Any], *, now: Any | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def load_grant_for_request(self, request: dict[str, Any], grant_id: str | None = None, *, now: Any | None = None) -> dict[str, Any] | None:
        raise NotImplementedError

    def revoke_grant(self, request: dict[str, Any], grant_id: str, *, now: Any | None = None) -> dict[str, Any] | None:
        raise NotImplementedError

    def list_active_grants(self, request: dict[str, Any], *, now: Any | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError


class InMemoryContextConsentGrantRepository(ContextConsentGrantRepository):
    def __init__(self, grants: list[dict[str, Any]] | None = None) -> None:
        self._grants: dict[tuple[str, str], dict[str, Any]] = {}
        for grant in grants or []:
            stored = _normalize_persisted_grant(grant)
            self._grants[_grant_key(stored)] = stored

    def create_google_docs_active_resource_grant(self, grant: dict[str, Any], *, now: Any | None = None) -> dict[str, Any]:
        created = build_google_docs_active_resource_grant(grant, now=now)
        self._grants[_grant_key(created)] = deepcopy(created)
        return deepcopy(created)

    def load_grant_for_request(self, request: dict[str, Any], grant_id: str | None = None, *, now: Any | None = None) -> dict[str, Any] | None:
        for grant in self._candidate_grants(request, grant_id):
            if _grant_is_valid_for_request(grant, request, now=now):
                return deepcopy(grant)
        return None

    def revoke_grant(self, request: dict[str, Any], grant_id: str, *, now: Any | None = None) -> dict[str, Any] | None:
        assert_non_empty_string(grant_id, "grantId")
        existing = self.load_grant_for_request(request, grant_id, now=now)
        if existing is None:
            return None
        revoked = {
            **existing,
            "status": CONSENT_STATUSES["REVOKED"],
            "revokedAt": _isoformat_z(_utc_datetime(now or datetime.now(timezone.utc))),
        }
        self._grants[_grant_key(revoked)] = revoked
        return deepcopy(revoked)

    def list_active_grants(self, request: dict[str, Any], *, now: Any | None = None) -> list[dict[str, Any]]:
        return [
            deepcopy(grant)
            for grant in self._candidate_grants(request, None)
            if _grant_is_valid_for_request(grant, request, now=now)
        ]

    def _candidate_grants(self, request: dict[str, Any], grant_id: str | None) -> list[dict[str, Any]]:
        _validate_active_resource_lookup_request(request)
        if grant_id is not None:
            assert_non_empty_string(grant_id, "grantId")
        candidates: list[dict[str, Any]] = []
        for grant in self._grants.values():
            if grant.get("tenantId") != request.get("tenantId"):
                continue
            if grant_id is not None and grant.get("grantId") != grant_id:
                continue
            if grant_id is None and not _grant_matches_lookup_scope(grant, request):
                continue
            candidates.append(grant)
        return candidates


class DynamoDbContextConsentGrantRepository(ContextConsentGrantRepository):
    def __init__(self, table: Any) -> None:
        if table is None:
            raise TypeError("table is required")
        self.table = table

    def create_google_docs_active_resource_grant(self, grant: dict[str, Any], *, now: Any | None = None) -> dict[str, Any]:
        created = build_google_docs_active_resource_grant(grant, now=now)
        item = _grant_to_item(created)
        self.table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(tenantId) AND attribute_not_exists(#sortKey)",
            ExpressionAttributeNames={"#sortKey": "userId#provider#contextMode#grantId"},
        )
        return created

    def load_grant_for_request(self, request: dict[str, Any], grant_id: str | None = None, *, now: Any | None = None) -> dict[str, Any] | None:
        candidates = _query_candidates(self.table, request, grant_id)
        for candidate in candidates:
            grant = _normalize_persisted_grant(candidate)
            if _grant_is_valid_for_request(grant, request, now=now):
                return grant
        return None

    def revoke_grant(self, request: dict[str, Any], grant_id: str, *, now: Any | None = None) -> dict[str, Any] | None:
        assert_non_empty_string(grant_id, "grantId")
        existing = self.load_grant_for_request(request, grant_id, now=now)
        if existing is None:
            return None
        revoked_at = _isoformat_z(_utc_datetime(now or datetime.now(timezone.utc)))
        updated = {
            **existing,
            "status": CONSENT_STATUSES["REVOKED"],
            "revokedAt": revoked_at,
        }
        self.table.put_item(Item=_grant_to_item(updated))
        return updated

    def list_active_grants(self, request: dict[str, Any], *, now: Any | None = None) -> list[dict[str, Any]]:
        return [
            grant
            for grant in (_normalize_persisted_grant(item) for item in _query_candidates(self.table, request, None))
            if _grant_is_valid_for_request(grant, request, now=now)
        ]


def build_google_docs_active_resource_grant(grant: dict[str, Any], *, now: Any | None = None) -> dict[str, Any]:
    assert_plain_object(grant, "grant")
    resource_ref = grant.get("resourceRef")
    assert_plain_object(resource_ref, "grant.resourceRef")
    now_value = _utc_datetime(now or datetime.now(timezone.utc))
    granted_at = grant.get("grantedAt") or _isoformat_z(now_value)
    expires_at = grant.get("expiresAt")
    if not expires_at:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "grant.expiresAt must be provided for active-resource consent",
            details={"field": "grant.expiresAt"},
        )
    built = {
        "grantId": _string_or_generated(grant.get("grantId"), "grantId"),
        "tenantId": _required_string(grant.get("tenantId"), "grant.tenantId"),
        "userId": _required_string(grant.get("userId"), "grant.userId"),
        "provider": grant.get("provider") or GOOGLE_DOCS_PROVIDER,
        "contextMode": grant.get("contextMode") or CONTEXT_MODES["ACTIVE_RESOURCE"],
        "resourceRef": {
            **resource_ref,
            "provider": resource_ref.get("provider") or GOOGLE_DOCS_PROVIDER,
        },
        "workspaceBoundary": None,
        "scopes": _scopes(grant.get("scopes")),
        "status": grant.get("status") or CONSENT_STATUSES["ACTIVE"],
        "grantedAt": granted_at,
        "revokedAt": grant.get("revokedAt"),
        "expiresAt": expires_at,
    }
    if built["provider"] != GOOGLE_DOCS_PROVIDER or built["contextMode"] != CONTEXT_MODES["ACTIVE_RESOURCE"]:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "only Google Docs ACTIVE_RESOURCE grants can be created by this helper",
            details={"fields": ["grant.provider", "grant.contextMode"]},
        )
    validate_context_consent_grant(
        built,
        {
            "tenantId": built["tenantId"],
            "userId": built["userId"],
            "provider": built["provider"],
            "contextMode": built["contextMode"],
            "resourceRef": built["resourceRef"],
        },
        {"now": now_value},
    )
    return built


def _query_candidates(table: Any, request: dict[str, Any], grant_id: str | None) -> list[dict[str, Any]]:
    _validate_active_resource_lookup_request(request)
    if grant_id is not None:
        assert_non_empty_string(grant_id, "grantId")
        sort_key = _sort_key(request["userId"], request["provider"], request["contextMode"], grant_id)
        response = table.get_item(
            Key={
                "tenantId": request["tenantId"],
                "userId#provider#contextMode#grantId": sort_key,
            }
        )
        item = response.get("Item") if isinstance(response, dict) else None
        return [item] if isinstance(item, dict) else []

    prefix = _sort_key_prefix(request["userId"], request["provider"], request["contextMode"])
    items: list[dict[str, Any]] = []
    kwargs = {
        "KeyConditionExpression": "tenantId = :tenantId AND begins_with(#sortKey, :sortKeyPrefix)",
        "ExpressionAttributeNames": {"#sortKey": "userId#provider#contextMode#grantId"},
        "ExpressionAttributeValues": {":tenantId": request["tenantId"], ":sortKeyPrefix": prefix},
    }
    while True:
        response = table.query(**kwargs)
        page_items = response.get("Items", []) if isinstance(response, dict) else []
        items.extend(item for item in page_items if isinstance(item, dict))
        last_key = response.get("LastEvaluatedKey") if isinstance(response, dict) else None
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def _validate_active_resource_lookup_request(request: dict[str, Any]) -> None:
    validate_context_request_shape(request)
    if request.get("provider") != GOOGLE_DOCS_PROVIDER or request.get("contextMode") != CONTEXT_MODES["ACTIVE_RESOURCE"]:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "only Google Docs ACTIVE_RESOURCE consent lookup is supported",
            details={"fields": ["request.provider", "request.contextMode"]},
        )


def _grant_is_valid_for_request(grant: dict[str, Any], request: dict[str, Any], *, now: Any | None) -> bool:
    try:
        validate_context_consent_grant(grant, request, {"now": _utc_datetime(now or datetime.now(timezone.utc))})
        return True
    except Exception:
        return False


def _grant_matches_lookup_scope(grant: dict[str, Any], request: dict[str, Any]) -> bool:
    resource_ref = grant.get("resourceRef") if isinstance(grant.get("resourceRef"), dict) else {}
    request_resource_ref = request.get("resourceRef") if isinstance(request.get("resourceRef"), dict) else {}
    return (
        grant.get("userId") == request.get("userId")
        and grant.get("provider") == request.get("provider")
        and grant.get("contextMode") == request.get("contextMode")
        and resource_ref.get("provider") == request_resource_ref.get("provider")
        and resource_ref.get("resourceId") == request_resource_ref.get("resourceId")
    )


def _normalize_persisted_grant(item: dict[str, Any]) -> dict[str, Any]:
    assert_plain_object(item, "grant")
    grant = deepcopy(item)
    grant.pop("userId#provider#contextMode#grantId", None)
    grant.pop("ttl", None)
    return grant


def _grant_to_item(grant: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(grant)
    item["userId#provider#contextMode#grantId"] = _sort_key(
        grant["userId"],
        grant["provider"],
        grant["contextMode"],
        grant["grantId"],
    )
    if grant.get("expiresAt"):
        item["ttl"] = int(to_datetime(grant["expiresAt"], "grant.expiresAt").timestamp())
    return item


def _grant_key(grant: dict[str, Any]) -> tuple[str, str]:
    return (
        grant["tenantId"],
        _sort_key(grant["userId"], grant["provider"], grant["contextMode"], grant["grantId"]),
    )


def _sort_key(user_id: str, provider: str, context_mode: str, grant_id: str) -> str:
    return f"{user_id}#{provider}#{context_mode}#{grant_id}"


def _sort_key_prefix(user_id: str, provider: str, context_mode: str) -> str:
    return f"{user_id}#{provider}#{context_mode}#"


def _required_string(value: Any, field_name: str) -> str:
    assert_non_empty_string(value, field_name)
    return value.strip()


def _string_or_generated(value: Any, field_name: str) -> str:
    if value is None:
        return f"grant_{uuid4().hex}"
    return _required_string(value, field_name)


def _scopes(value: Any) -> list[str]:
    if value is None:
        return list(GOOGLE_DOCS_ACTIVE_RESOURCE_SCOPES)
    if not isinstance(value, list):
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "grant.scopes must contain at least one scope",
            details={"field": "grant.scopes"},
        )
    normalized = [scope.strip() for scope in value if isinstance(scope, str) and scope.strip()]
    if not normalized:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "grant.scopes must contain at least one scope",
            details={"field": "grant.scopes"},
        )
    return normalized


def _utc_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        return to_datetime(value, "now")
    if not isinstance(value, datetime):
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "now must be a datetime or ISO-8601 timestamp",
            details={"field": "now"},
        )
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
