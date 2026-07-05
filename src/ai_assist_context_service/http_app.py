from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from .constants import CONTEXT_MODES, FUTURE_CONTEXT_MODES, MVP_CONTEXT_MODES
from .errors import ContextServiceError
from .modes import validate_context_mode
from .read_path import read_context_with_consent


SERVICE_NAME = "ai-assist-context-service"
_SESSION_PREFIX = "/resource-sessions/"
_CONTEXT_MODE_SUFFIX = "/context-mode"
_CONTEXT_PREVIEW_SUFFIX = "/context-preview"
_CONTEXT_CONSENT_SUFFIX = "/context-consent"
_DEFAULT_ACTIVE_RESOURCE_CONSENT_TTL_HOURS = 8


def handle_http_request(
    *,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    query_string: str = "",
    body: bytes | None = None,
) -> dict[str, Any]:
    app = ContextHttpApplication()
    parsed = urlparse(path)
    query = parse_qs(query_string or parsed.query)
    return app.handle(
        method=method.upper(),
        path=parsed.path,
        headers=headers or {},
        query=query,
        body=body,
    )


class ContextHttpApplication:
    def __init__(
        self,
        *,
        connector_read_context: Any | None = None,
        load_consent_grant: Any | None = None,
        consent_grant_repository: Any | None = None,
        require_google_oauth: Any | None = None,
    ) -> None:
        self.connector_read_context = connector_read_context
        self.load_consent_grant = load_consent_grant
        self.consent_grant_repository = consent_grant_repository
        self.require_google_oauth = require_google_oauth

    def handle(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        query: dict[str, list[str]],
        body: bytes | None,
    ) -> dict[str, Any]:
        del query
        try:
            _require_bearer(headers)
            if method == "GET" and path == "/context-modes":
                return _json_response(200, {"contextModes": _context_modes_payload()})

            session_id = _resource_session_route_id(path, _CONTEXT_MODE_SUFFIX)
            if method == "PUT" and session_id is not None:
                payload = _json_body(body)
                context_mode = _require_string(payload.get("contextMode"), "contextMode")
                validate_context_mode(context_mode)
                return _json_response(
                    200,
                    {
                        "resourceSessionId": session_id,
                        "contextMode": context_mode,
                        "supported": True,
                        "status": "validated",
                    },
                )

            session_id = _resource_session_route_id(path, _CONTEXT_PREVIEW_SUFFIX)
            if method == "POST" and session_id is not None:
                payload = _json_body(body)
                context_mode = _require_string(payload.get("contextMode"), "contextMode")
                validate_context_mode(context_mode)
                if self.connector_read_context is not None:
                    request = _context_preview_request(
                        payload,
                        headers=headers,
                        session_id=session_id,
                        context_mode=context_mode,
                    )
                    if self.load_consent_grant is not None:
                        consent_grant = self.load_consent_grant(request, payload.get("consentGrantId"))
                        if consent_grant is not None:
                            request["consentGrant"] = consent_grant
                    result = read_context_with_consent(
                        request,
                        self.connector_read_context,
                    )
                    return _json_response(200, result)
                return _error_response(
                    503,
                    "CONTEXT_PREVIEW_DEPENDENCY_UNAVAILABLE",
                    "Context preview requires deployed consent and connector dependencies.",
                    category="DEPENDENCY",
                    retryable=False,
                    details={"resourceSessionId": session_id, "contextMode": context_mode},
                )

            session_id = _resource_session_route_id(path, _CONTEXT_CONSENT_SUFFIX)
            if method == "POST" and session_id is not None:
                payload = _json_body(body)
                request = _context_consent_request(payload, headers=headers, session_id=session_id)
                if self.consent_grant_repository is None:
                    return _error_response(
                        503,
                        "CONTEXT_CONSENT_DEPENDENCY_UNAVAILABLE",
                        "Context consent requires deployed consent persistence.",
                        category="DEPENDENCY",
                        retryable=False,
                        details={"resourceSessionId": session_id, "contextMode": request["contextMode"]},
                    )
                if self.require_google_oauth is not None:
                    self.require_google_oauth(request)
                existing = self.consent_grant_repository.load_grant_for_request(request, payload.get("consentGrantId"))
                if existing is not None:
                    return _json_response(200, _consent_response(existing, refreshed=True))
                created = self.consent_grant_repository.create_google_docs_active_resource_grant(
                    _grant_from_request(request, payload)
                )
                return _json_response(201, _consent_response(created, refreshed=False))

            return _error_response(
                404,
                "ROUTE_NOT_FOUND",
                "Route is not implemented by the context service.",
                category="VALIDATION",
            )
        except ContextServiceError as error:
            return _error_response(
                error.http_status,
                error.code,
                str(error),
                category=error.category or _category_for_status(error.http_status),
                retryable=error.retryable,
                target=error.target,
                details=error.details,
            )
        except ValueError as error:
            return _error_response(400, "VALIDATION_ERROR", str(error), category="VALIDATION")
        except Exception:
            return _error_response(
                502,
                "CONTEXT_CONNECTOR_DEPENDENCY_FAILED",
                "Context connector dependency failed.",
                category="DEPENDENCY",
                retryable=False,
            )


def _context_modes_payload() -> list[dict[str, Any]]:
    return [
        {
            "contextMode": mode,
            "supported": mode in MVP_CONTEXT_MODES,
            "mvpStatus": "supported" if mode in MVP_CONTEXT_MODES else "deferred",
        }
        for mode in (
            CONTEXT_MODES["SELECTION"],
            CONTEXT_MODES["ACTIVE_RESOURCE"],
            *FUTURE_CONTEXT_MODES,
        )
    ]


def _resource_session_route_id(path: str, suffix: str) -> str | None:
    if not path.startswith(_SESSION_PREFIX) or not path.endswith(suffix):
        return None
    session_id = path[len(_SESSION_PREFIX) : -len(suffix)]
    if not session_id or "/" in session_id:
        return None
    return session_id


def _context_preview_request(
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    session_id: str,
    context_mode: str,
) -> dict[str, Any]:
    resource_ref = payload.get("resourceRef") or {
        "provider": "google_docs",
        "resourceId": payload.get("resourceId"),
    }
    if not isinstance(resource_ref, dict):
        raise ValueError("resourceRef must be an object.")
    tenant_id = _header(headers, "x-ai-assist-tenant-id")
    user_id = _header(headers, "x-ai-assist-user-id")
    if not tenant_id or not user_id:
        raise ContextServiceError(
            "AUTH_CONTEXT_REQUIRED",
            "Authenticated tenant and user context are required.",
            http_status=401,
            category="AUTHENTICATION",
        )
    request = {
        "tenantId": tenant_id,
        "userId": user_id,
        "sessionId": session_id,
        "provider": payload.get("provider") or resource_ref.get("provider") or "google_docs",
        "contextMode": context_mode,
        "resourceRef": resource_ref,
        "explicitUserAction": payload.get("explicitUserAction"),
        "requestId": _header(headers, "x-request-id"),
        "googleAccountId": payload.get("googleAccountId"),
        "selectionRange": payload.get("selectionRange"),
    }
    return {key: value for key, value in request.items() if value is not None}


def _context_consent_request(
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    session_id: str,
) -> dict[str, Any]:
    resource_ref = payload.get("resourceRef") or {
        "provider": "google_docs",
        "resourceId": payload.get("resourceId"),
    }
    if not isinstance(resource_ref, dict):
        raise ValueError("resourceRef must be an object.")
    tenant_id = _header(headers, "x-ai-assist-tenant-id")
    user_id = _header(headers, "x-ai-assist-user-id")
    auth_subject = _header(headers, "x-ai-assist-auth-subject")
    if not tenant_id or not user_id or not auth_subject:
        raise ContextServiceError(
            "AUTH_CONTEXT_REQUIRED",
            "Authenticated tenant, user, and subject context are required.",
            http_status=401,
            category="AUTHENTICATION",
        )
    request = {
        "tenantId": tenant_id,
        "userId": user_id,
        "authSubject": auth_subject,
        "sessionId": session_id,
        "provider": "google_docs",
        "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
        "resourceRef": {
            **resource_ref,
            "provider": resource_ref.get("provider") or "google_docs",
        },
        "requestId": _header(headers, "x-request-id"),
        "googleAccountId": payload.get("googleAccountId"),
    }
    return {key: value for key, value in request.items() if value is not None}


def _grant_from_request(request: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    expires_at = payload.get("expiresAt") or _isoformat_z(now + timedelta(hours=_DEFAULT_ACTIVE_RESOURCE_CONSENT_TTL_HOURS))
    return {
        "tenantId": request["tenantId"],
        "userId": request["userId"],
        "provider": request["provider"],
        "contextMode": request["contextMode"],
        "resourceRef": request["resourceRef"],
        "scopes": payload.get("scopes") or ["docs.read"],
        "expiresAt": expires_at,
    }


def _consent_response(grant: dict[str, Any], *, refreshed: bool) -> dict[str, Any]:
    return {
        "consentGrant": {
            "grantId": grant["grantId"],
            "tenantId": grant["tenantId"],
            "userId": grant["userId"],
            "provider": grant["provider"],
            "contextMode": grant["contextMode"],
            "resourceRef": grant["resourceRef"],
            "scopes": grant["scopes"],
            "status": grant["status"],
            "grantedAt": grant["grantedAt"],
            "revokedAt": grant.get("revokedAt"),
            "expiresAt": grant.get("expiresAt"),
        },
        "refreshed": refreshed,
    }


def _isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _require_bearer(headers: dict[str, str]) -> str:
    normalized = {str(key).lower(): value for key, value in headers.items()}
    authorization = normalized.get("authorization", "")
    if not authorization.startswith("Bearer ") or not authorization[len("Bearer ") :].strip():
        raise ContextServiceError(
            "AUTHENTICATION_REQUIRED",
            "Bearer product session token is required.",
            http_status=401,
            category="AUTHENTICATION",
        )
    return authorization[len("Bearer ") :].strip()


def _header(headers: dict[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return value
    return None


def _json_body(body: bytes | str | None) -> dict[str, Any]:
    if body in {None, b"", ""}:
        return {}
    raw = body.decode("utf-8") if isinstance(body, bytes) else body
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("JSON request body must be an object.")
    return parsed


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _json_response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    }


def _error_response(
    status: int,
    code: str,
    message: str,
    *,
    category: str,
    retryable: bool = False,
    target: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error = {
        "code": code,
        "category": category,
        "message": message,
        "retryable": retryable,
    }
    if target is not None:
        error["target"] = target
    if details:
        error["details"] = details
    return _json_response(status, {"error": error, "service": SERVICE_NAME})


def _category_for_status(status: int) -> str:
    if status == 401:
        return "AUTHENTICATION"
    if status == 403:
        return "AUTHORIZATION"
    if status >= 500:
        return "DEPENDENCY"
    return "VALIDATION"
