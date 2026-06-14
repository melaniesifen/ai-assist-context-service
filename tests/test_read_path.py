from ai_assist_context_service import (
    CONSENT_STATUSES,
    CONTEXT_MODES,
    hash_content,
    read_context_with_consent,
)
from tests.common import NOW, ContextServiceTestCase, active_grant, context_input, context_request


class ReadPathTests(ContextServiceTestCase):
    def test_read_context_with_consent_skips_connector_when_consent_is_missing_or_invalid(self):
        calls = []

        def connector(_request):
            calls.append("called")
            return {"context": context_input(), "resourceRevision": "rev-1"}

        failure_requests = [
            context_request(consentGrant=None),
            context_request(consentGrant=active_grant(status=CONSENT_STATUSES["REVOKED"])),
            context_request(consentGrant=active_grant(status=CONSENT_STATUSES["EXPIRED"])),
            context_request(consentGrant=active_grant(expiresAt="2026-05-29T11:59:00.000Z")),
            context_request(consentGrant=active_grant(userId="other-user")),
            context_request(consentGrant=active_grant(tenantId="other-tenant")),
            context_request(consentGrant=active_grant(provider="not_google_docs")),
            context_request(
                consentGrant=active_grant(resourceRef={"provider": "google_docs", "resourceId": "other-doc"})
            ),
        ]

        for request in failure_requests:
            with self.subTest(request=request):
                self.assert_context_error(
                    lambda request=request: read_context_with_consent(request, connector, {"now": NOW}),
                )

        self.assertEqual(calls, [])

    def test_read_context_with_consent_invokes_connector_after_active_matching_consent(self):
        calls = []

        def connector(request):
            calls.append(request)
            return {
                "context": context_input(
                    contextMode=CONTEXT_MODES["SELECTION"],
                    sourceType=None,
                    anchors={"selectionAnchor": {"startIndex": 1, "endIndex": 5}},
                    content="Selected connector text",
                    revisionMetadata={
                        "provider": "google_docs",
                        "revisionId": "rev-1",
                        "modifiedTime": "2026-05-29T11:00:00.000Z",
                    },
                ),
                "resourceRevision": "rev-1",
            }

        result = read_context_with_consent(
            context_request(
                contextMode=CONTEXT_MODES["SELECTION"],
                consentGrant=active_grant(contextMode=CONTEXT_MODES["SELECTION"]),
            ),
            connector,
            {"now": NOW},
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["resourceRef"]["resourceId"], "doc-1")
        self.assertEqual(calls[0]["consentGrantId"], "grant-1")
        self.assertNotIn("consentGrant", calls[0])
        self.assertEqual(result["consent"], {"valid": True, "grantId": "grant-1"})
        self.assertEqual(result["resourceRevision"], "rev-1")
        self.assertEqual(result["context"]["contextMode"], CONTEXT_MODES["SELECTION"])
        self.assertEqual(result["context"]["sourceType"], "connector_selection")
        self.assertEqual(result["context"]["trustLevel"], "connector_verified")
        self.assertEqual(
            result["context"]["revisionMetadata"],
            {
                "provider": "google_docs",
                "revisionId": "rev-1",
                "modifiedTime": "2026-05-29T11:00:00.000Z",
            },
        )
        self.assertEqual(result["context"]["contentHash"], hash_content("Selected connector text"))
        self.assertEqual(result["context"]["provenance"]["selectionAnchor"], {"startIndex": 1, "endIndex": 5})
