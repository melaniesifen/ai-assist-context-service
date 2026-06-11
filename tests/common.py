from datetime import datetime, timezone
import unittest

from ai_assist_context_service import CONSENT_STATUSES, CONTEXT_MODES, hash_content


NOW = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)


def active_grant(**overrides):
    value = {
        "grantId": "grant-1",
        "tenantId": "tenant-1",
        "userId": "user-1",
        "provider": "google_docs",
        "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
        "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
        "workspaceBoundary": None,
        "scopes": ["docs.read"],
        "status": CONSENT_STATUSES["ACTIVE"],
        "grantedAt": "2026-05-29T11:00:00.000Z",
        "revokedAt": None,
        "expiresAt": "2026-05-29T13:00:00.000Z",
    }
    value.update(overrides)
    return value


def context_input(**overrides):
    value = {
        "contextId": "ctx-1",
        "tenantId": "tenant-1",
        "userId": "user-1",
        "sessionId": "session-1",
        "provider": "google_docs",
        "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
        "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
        "connector": "google_docs",
        "content": "Useful document context",
        "resourceRevision": "rev-1",
        "anchors": {
            "targetRange": {"startIndex": 0, "endIndex": 6},
            "originalTextHash": hash_content("Useful"),
        },
        "connectorVerified": True,
    }
    value.update(overrides)
    return value


def context_request(**overrides):
    value = {
        "tenantId": "tenant-1",
        "userId": "user-1",
        "provider": "google_docs",
        "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
        "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
        "consentGrant": active_grant(),
    }
    value.update(overrides)
    return value


class ContextServiceTestCase(unittest.TestCase):
    def assert_context_error(self, callable_value, code=None, http_status=None, details=None):
        with self.assertRaises(Exception) as caught:
            callable_value()
        error = caught.exception
        if code is not None:
            self.assertEqual(error.code, code)
        if http_status is not None:
            self.assertEqual(error.http_status, http_status)
        if details is not None:
            self.assertEqual(error.details, details)
        return error
