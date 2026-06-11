from ai_assist_context_service import (
    CONTEXT_MODES,
    ERROR_CODES,
    connector_verified_write_back_target_metadata,
    hash_content,
    is_connector_verified_write_back_eligible,
    normalize_context,
    assert_connector_verified_for_write_back,
)
from tests.common import NOW, ContextServiceTestCase, context_input


class ProvenanceTests(ContextServiceTestCase):
    def test_connector_verified_write_back_target_metadata_excludes_raw_context_content(self):
        context = normalize_context(
            context_input(
                content="private target text inside a broader active resource excerpt",
                anchors={
                    "targetRange": {"startIndex": 0, "endIndex": 7},
                    "originalTextHash": hash_content("private"),
                },
            ),
            {"now": NOW},
        )

        metadata = connector_verified_write_back_target_metadata(context)

        self.assertEqual(
            metadata,
            {
                "contextId": "ctx-1",
                "provider": "google_docs",
                "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
                "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
                "resourceRevision": "rev-1",
                "targetRange": {"startIndex": 0, "endIndex": 7},
                "selectionAnchor": None,
                "originalTextHash": hash_content("private"),
                "sourceType": "connector_resource_excerpt",
                "trustLevel": "connector_verified",
                "capturedAt": "2026-05-29T12:00:00.000Z",
            },
        )
        self.assertNotIn("content", metadata)
        self.assertNotIn("provenance", metadata)

    def test_connector_verified_write_back_target_metadata_accepts_metadata_target_hash(self):
        context = normalize_context(
            context_input(
                contextMode=CONTEXT_MODES["SELECTION"],
                content="selected connector text",
                anchors={"selectionAnchor": {"startIndex": 2, "endIndex": 10}},
                metadata={"writeBackTarget": {"originalTextHash": hash_content("selected")}},
            ),
            {"now": NOW},
        )

        metadata = connector_verified_write_back_target_metadata(context)

        self.assertEqual(metadata["sourceType"], "connector_selection")
        self.assertEqual(metadata["selectionAnchor"], {"startIndex": 2, "endIndex": 10})
        self.assertEqual(metadata["originalTextHash"], hash_content("selected"))

    def test_connector_verified_write_back_target_metadata_rejects_missing_target_hash(self):
        context = normalize_context(
            context_input(anchors={"targetRange": {"startIndex": 0, "endIndex": 6}}),
            {"now": NOW},
        )

        self.assertFalse(is_connector_verified_write_back_eligible(context))
        self.assert_context_error(
            lambda: connector_verified_write_back_target_metadata(context),
            ERROR_CODES["CONNECTOR_VERIFICATION_REQUIRED"],
            http_status=422,
            details={
                "contextId": "ctx-1",
                "trustLevel": "connector_verified",
                "sourceType": "connector_resource_excerpt",
                "hasResourceRevision": True,
                "hasAnchorOrRange": True,
                "hasOriginalTextHash": False,
                "truncated": False,
                "redacted": False,
            },
        )

    def test_connector_verified_write_back_target_metadata_rejects_client_supplied_context(self):
        context = normalize_context(
            context_input(
                contextMode=CONTEXT_MODES["SELECTION"],
                content="client supplied selected text",
                clientSupplied=True,
                connectorVerified=None,
                resourceRevision=None,
                anchors={},
            ),
            {"now": NOW},
        )

        self.assert_context_error(
            lambda: connector_verified_write_back_target_metadata(context),
            ERROR_CODES["CONNECTOR_VERIFICATION_REQUIRED"],
            http_status=422,
        )

    def test_write_back_eligibility_requires_a_non_empty_content_hash(self):
        context = normalize_context(context_input(), {"now": NOW})

        self.assertFalse(is_connector_verified_write_back_eligible({**context, "contentHash": "   "}))
        self.assert_context_error(
            lambda: assert_connector_verified_for_write_back({**context, "contentHash": ""}),
            ERROR_CODES["CONNECTOR_VERIFICATION_REQUIRED"],
        )
