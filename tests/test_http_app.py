import json
import unittest

from ai_assist_context_service import (
    CONSENT_STATUSES,
    CONTEXT_MODES,
    ContextServiceError,
    InMemoryContextConsentGrantRepository,
)
from ai_assist_context_service.http_app import ContextHttpApplication, handle_http_request


AUTH_HEADERS = {
    "Authorization": "Bearer test-session",
    "X-Ai-Assist-Tenant-Id": "tenant-1",
    "X-Ai-Assist-User-Id": "user-1",
    "X-Ai-Assist-Auth-Subject": "auth-subject-1",
}


def response_json(response):
    return json.loads(response["body"].decode("utf-8"))


def active_grant(**overrides):
    value = {
        "grantId": "grant-1",
        "tenantId": "tenant-1",
        "userId": "user-1",
        "provider": "google_docs",
        "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
        "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
        "scopes": ["docs.read"],
        "status": CONSENT_STATUSES["ACTIVE"],
        "grantedAt": "2026-05-29T11:00:00.000Z",
        "revokedAt": None,
        "expiresAt": "2026-07-05T13:00:00.000Z",
    }
    value.update(overrides)
    return value


class ContextHttpAppTests(unittest.TestCase):
    def test_context_modes_returns_mvp_metadata_with_no_store(self):
        response = handle_http_request(method="GET", path="/context-modes", headers=AUTH_HEADERS)
        payload = response_json(response)

        self.assertEqual(response["status"], 200)
        self.assertEqual(response["headers"]["Cache-Control"], "no-store")
        self.assertEqual(
            [item["contextMode"] for item in payload["contextModes"][:2]],
            [CONTEXT_MODES["SELECTION"], CONTEXT_MODES["ACTIVE_RESOURCE"]],
        )
        self.assertTrue(payload["contextModes"][0]["supported"])
        self.assertFalse(
            next(item for item in payload["contextModes"] if item["contextMode"] == CONTEXT_MODES["SCREEN"])[
                "supported"
            ]
        )

    def test_context_mode_update_validates_supported_mode(self):
        response = handle_http_request(
            method="PUT",
            path="/resource-sessions/session-1/context-mode",
            headers=AUTH_HEADERS,
            body=json.dumps({"contextMode": CONTEXT_MODES["SELECTION"]}).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 200)
        self.assertEqual(payload["contextMode"], CONTEXT_MODES["SELECTION"])
        self.assertEqual(payload["status"], "validated")

    def test_missing_auth_returns_401(self):
        response = handle_http_request(method="GET", path="/context-modes", headers={})

        self.assertEqual(response["status"], 401)
        self.assertEqual(response_json(response)["error"]["category"], "AUTHENTICATION")

    def test_malformed_or_unsupported_mode_returns_400(self):
        malformed = handle_http_request(
            method="PUT",
            path="/resource-sessions/session-1/context-mode",
            headers=AUTH_HEADERS,
            body=b"[]",
        )
        unsupported = handle_http_request(
            method="PUT",
            path="/resource-sessions/session-1/context-mode",
            headers=AUTH_HEADERS,
            body=json.dumps({"contextMode": CONTEXT_MODES["SCREEN"]}).encode("utf-8"),
        )

        self.assertEqual(malformed["status"], 400)
        self.assertEqual(unsupported["status"], 400)
        self.assertEqual(response_json(unsupported)["error"]["code"], "UNSUPPORTED_CONTEXT_MODE")

    def test_unknown_route_returns_404(self):
        response = handle_http_request(method="GET", path="/unknown", headers=AUTH_HEADERS)

        self.assertEqual(response["status"], 404)
        self.assertEqual(response_json(response)["error"]["code"], "ROUTE_NOT_FOUND")

    def test_context_preview_returns_safe_dependency_error(self):
        response = handle_http_request(
            method="POST",
            path="/resource-sessions/session-1/context-preview",
            headers=AUTH_HEADERS,
            body=json.dumps({"contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"]}).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 503)
        self.assertEqual(payload["error"]["category"], "DEPENDENCY")
        self.assertEqual(payload["error"]["code"], "CONTEXT_PREVIEW_DEPENDENCY_UNAVAILABLE")

    def test_context_preview_calls_injected_connector_after_consent(self):
        calls = []

        def connector(request):
            calls.append(request)
            return {
                "context": {
                    "contextId": "ctx-1",
                    "tenantId": "tenant-1",
                    "userId": "user-1",
                    "sessionId": "session-1",
                    "provider": "google_docs",
                    "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
                    "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
                    "connector": "google_docs",
                    "content": "Controlled context",
                    "resourceRevision": "rev-1",
                    "anchors": {},
                    "connectorVerified": True,
                },
                "resourceRevision": "rev-1",
            }

        grant_loads = []

        def load_grant(request, grant_id):
            grant_loads.append({"request": request, "grantId": grant_id})
            return active_grant(grantId=grant_id)

        app = ContextHttpApplication(connector_read_context=connector, load_consent_grant=load_grant)
        response = app.handle(
            method="POST",
            path="/resource-sessions/session-1/context-preview",
            headers=AUTH_HEADERS,
            query={},
            body=json.dumps(
                {
                    "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
                    "resourceId": "doc-1",
                    "consentGrantId": "grant-1",
                }
            ).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 200)
        self.assertEqual(calls[0]["tenantId"], "tenant-1")
        self.assertEqual(calls[0]["userId"], "user-1")
        self.assertEqual(calls[0]["resourceRef"]["resourceId"], "doc-1")
        self.assertEqual(calls[0]["consentGrantId"], "grant-1")
        self.assertEqual(grant_loads[0]["grantId"], "grant-1")
        self.assertNotIn("consentGrant", calls[0])
        self.assertEqual(payload["resourceRevision"], "rev-1")

    def test_context_preview_ignores_body_supplied_consent_grant_without_server_loader(self):
        calls = []
        app = ContextHttpApplication(connector_read_context=lambda request: calls.append(request))

        response = app.handle(
            method="POST",
            path="/resource-sessions/session-1/context-preview",
            headers=AUTH_HEADERS,
            query={},
            body=json.dumps(
                {
                    "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
                    "resourceId": "doc-1",
                    "consentGrant": active_grant(),
                }
            ).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 403)
        self.assertEqual(payload["error"]["code"], "CONSENT_REQUIRED")
        self.assertEqual(calls, [])

    def test_context_preview_sanitizes_untyped_connector_exception(self):
        def connector(_request):
            raise RuntimeError("raw document text with Bearer secret-token")

        app = ContextHttpApplication(
            connector_read_context=connector,
            load_consent_grant=lambda _request, grant_id: active_grant(grantId=grant_id),
        )
        response = app.handle(
            method="POST",
            path="/resource-sessions/session-1/context-preview",
            headers=AUTH_HEADERS,
            query={},
            body=json.dumps(
                {
                    "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
                    "resourceId": "doc-1",
                    "consentGrantId": "grant-1",
                }
            ).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 502)
        self.assertEqual(payload["error"]["code"], "CONTEXT_CONNECTOR_DEPENDENCY_FAILED")
        self.assertNotIn("raw document text", response["body"].decode("utf-8"))
        self.assertNotIn("secret-token", response["body"].decode("utf-8"))

    def test_context_preview_requires_server_identity_headers_before_connector(self):
        calls = []
        app = ContextHttpApplication(connector_read_context=lambda request: calls.append(request))

        response = app.handle(
            method="POST",
            path="/resource-sessions/session-1/context-preview",
            headers={"Authorization": "Bearer test-session"},
            query={},
            body=json.dumps({"contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"], "resourceId": "doc-1"}).encode("utf-8"),
        )

        self.assertEqual(response["status"], 401)
        self.assertEqual(response_json(response)["error"]["code"], "AUTH_CONTEXT_REQUIRED")
        self.assertEqual(calls, [])

    def test_context_consent_create_uses_server_identity_and_ignores_body_identity(self):
        repository = InMemoryContextConsentGrantRepository()
        oauth_checks = []

        def require_google_oauth(request):
            oauth_checks.append(request)

        app = ContextHttpApplication(consent_grant_repository=repository, require_google_oauth=require_google_oauth)
        response = app.handle(
            method="POST",
            path="/resource-sessions/session-1/context-consent",
            headers=AUTH_HEADERS,
            query={},
            body=json.dumps(
                {
                    "tenantId": "attacker-tenant",
                    "userId": "attacker-user",
                    "resourceId": "doc-1",
                    "expiresAt": "2026-07-05T13:00:00.000Z",
                }
            ).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 201)
        self.assertEqual(payload["consentGrant"]["tenantId"], "tenant-1")
        self.assertEqual(payload["consentGrant"]["userId"], "user-1")
        self.assertEqual(payload["consentGrant"]["resourceRef"]["resourceId"], "doc-1")
        self.assertEqual(payload["consentGrant"]["contextMode"], CONTEXT_MODES["ACTIVE_RESOURCE"])
        self.assertEqual(payload["consentGrant"]["scopes"], ["docs.read"])
        self.assertFalse(payload["refreshed"])
        self.assertEqual(oauth_checks[0]["authSubject"], "auth-subject-1")
        self.assertNotIn("content", response["body"].decode("utf-8"))
        self.assertNotIn("accessToken", response["body"].decode("utf-8"))

    def test_context_consent_returns_existing_active_grant_for_matching_resource(self):
        repository = InMemoryContextConsentGrantRepository([active_grant()])
        app = ContextHttpApplication(consent_grant_repository=repository)

        response = app.handle(
            method="POST",
            path="/resource-sessions/session-1/context-consent",
            headers=AUTH_HEADERS,
            query={},
            body=json.dumps({"resourceId": "doc-1"}).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 200)
        self.assertEqual(payload["consentGrant"]["grantId"], "grant-1")
        self.assertTrue(payload["refreshed"])

    def test_context_consent_fails_closed_when_google_oauth_is_missing(self):
        repository = InMemoryContextConsentGrantRepository()

        def require_google_oauth(_request):
            raise ContextServiceError(
                "GOOGLE_OAUTH_REQUIRED",
                "Connect Google before granting document context.",
                http_status=403,
                category="AUTHORIZATION",
            )

        app = ContextHttpApplication(consent_grant_repository=repository, require_google_oauth=require_google_oauth)
        response = app.handle(
            method="POST",
            path="/resource-sessions/session-1/context-consent",
            headers=AUTH_HEADERS,
            query={},
            body=json.dumps({"resourceId": "doc-1"}).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 403)
        self.assertEqual(payload["error"]["code"], "GOOGLE_OAUTH_REQUIRED")

    def test_context_consent_requires_persistence_dependency(self):
        app = ContextHttpApplication()

        response = app.handle(
            method="POST",
            path="/resource-sessions/session-1/context-consent",
            headers=AUTH_HEADERS,
            query={},
            body=json.dumps({"resourceId": "doc-1"}).encode("utf-8"),
        )

        self.assertEqual(response["status"], 503)
        self.assertEqual(response_json(response)["error"]["code"], "CONTEXT_CONSENT_DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
