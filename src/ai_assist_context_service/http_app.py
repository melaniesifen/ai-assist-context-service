from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from .constants import CONTEXT_MODES, FUTURE_CONTEXT_MODES, MVP_CONTEXT_MODES
from .errors import ContextServiceError
from .modes import validate_context_mode


SERVICE_NAME = "ai-assist-context-service"
_SESSION_PREFIX = "/resource-sessions/"
_CONTEXT_MODE_SUFFIX = "/context-mode"
_CONTEXT_PREVIEW_SUFFIX = "/context-preview"


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
                return _error_response(
                    503,
                    "CONTEXT_PREVIEW_DEPENDENCY_UNAVAILABLE",
                    "Context preview requires deployed consent and connector dependencies.",
                    category="DEPENDENCY",
                    retryable=False,
                    details={"resourceSessionId": session_id, "contextMode": context_mode},
                )

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
