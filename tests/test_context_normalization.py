from ai_assist_context_service import (
    CONTEXT_MODES,
    ERROR_CODES,
    REDACTION_POLICIES,
    assert_connector_verified_for_write_back,
    hash_content,
    is_connector_verified_write_back_eligible,
    normalize_context,
)
from tests.common import NOW, ContextServiceTestCase, context_input


class ContextNormalizationTests(ContextServiceTestCase):
    def test_normalize_context_marks_client_supplied_selected_text_as_non_writeback_context(self):
        context = normalize_context(
            context_input(
                contextMode=CONTEXT_MODES["SELECTION"],
                content="selected by browser",
                clientSupplied=True,
                connectorVerified=None,
                resourceRevision=None,
                anchors={},
            ),
            {"now": NOW},
        )

        self.assertEqual(context["sourceType"], "client_selection_text")
        self.assertEqual(context["trustLevel"], "client_supplied")
        self.assertTrue(context["clientSupplied"])
        self.assertFalse(context["connectorVerified"])
        self.assertEqual(context["contentHash"], hash_content("selected by browser"))
        self.assertFalse(context["metadata"]["truncated"])
        self.assertEqual(context["metadata"]["contentLength"], len("selected by browser"))
        self.assertFalse(is_connector_verified_write_back_eligible(context))
        self.assert_context_error(
            lambda: assert_connector_verified_for_write_back(context),
            ERROR_CODES["CONNECTOR_VERIFICATION_REQUIRED"],
        )

    def test_normalize_context_marks_connector_verified_context_with_provenance_and_writeback_eligibility(self):
        context = normalize_context(context_input(), {"now": NOW})

        self.assertEqual(context["sourceType"], "connector_resource_excerpt")
        self.assertEqual(context["trustLevel"], "connector_verified")
        self.assertEqual(context["provenance"]["connector"], "google_docs")
        self.assertEqual(context["provenance"]["resourceVersion"], "rev-1")
        self.assertEqual(context["resourceRevision"], "rev-1")
        self.assertFalse(context["metadata"]["truncated"])
        self.assertEqual(context["metadata"]["contentLength"], len("Useful document context"))
        self.assertEqual(context["metadata"]["contentLimit"]["truncated"], False)
        self.assertTrue(context["connectorVerified"])
        self.assertTrue(is_connector_verified_write_back_eligible(context))
        self.assertTrue(assert_connector_verified_for_write_back(context))

    def test_normalize_context_can_apply_deterministic_mvp_redaction_before_hashing_and_byte_limits(self):
        context = normalize_context(
            context_input(content="Email owner@example.com with Bearer abcdefghijklmnopqrstuvwxyz123456"),
            {"now": NOW, "redactionPolicy": REDACTION_POLICIES["MVP_DEFAULT"]},
        )

        self.assertEqual(
            context["content"],
            "Email <redacted:email_address> with Bearer <redacted:token>",
        )
        self.assertEqual(context["contentHash"], hash_content(context["content"]))
        self.assertEqual(
            context["metadata"]["redaction"],
            {
                "policy": REDACTION_POLICIES["MVP_DEFAULT"],
                "redacted": True,
                "rulesApplied": ["email_address", "bearer_token"],
            },
        )
        self.assertFalse(is_connector_verified_write_back_eligible(context))
        self.assert_context_error(
            lambda: assert_connector_verified_for_write_back(context),
            ERROR_CODES["CONNECTOR_VERIFICATION_REQUIRED"],
            details={
                "contextId": "ctx-1",
                "trustLevel": "connector_verified",
                "sourceType": "connector_resource_excerpt",
                "hasResourceRevision": True,
                "hasAnchorOrRange": True,
                "hasOriginalTextHash": True,
                "truncated": False,
                "redacted": True,
            },
        )

    def test_mvp_redaction_matches_bearer_token_schemes_case_insensitively(self):
        context = normalize_context(
            context_input(content="authorization: bEaReR abcdefghijklmnopqrstuvwxyz123456"),
            {"now": NOW, "redactionPolicy": REDACTION_POLICIES["MVP_DEFAULT"]},
        )

        self.assertEqual(context["content"], "authorization: Bearer <redacted:token>")
        self.assertEqual(context["metadata"]["redaction"]["rulesApplied"], ["bearer_token"])

    def test_normalize_context_truncates_oversized_content_when_safe(self):
        context = normalize_context(context_input(content="abcdef"), {"now": NOW, "maxBytes": 4})

        self.assertEqual(context["content"], "abcd")
        self.assertTrue(context["metadata"]["truncated"])
        self.assertEqual(context["metadata"]["contentLength"], 4)
        self.assertEqual(context["metadata"]["originalContentLength"], 6)
        self.assertEqual(context["metadata"]["truncationReason"], "MAX_CONTEXT_BYTES")
        self.assertTrue(context["metadata"]["contentLimit"]["truncated"])
        self.assertEqual(context["metadata"]["contentLimit"]["originalBytes"], 6)
        self.assertEqual(context["metadata"]["contentLimit"]["returnedBytes"], 4)
        self.assertFalse(is_connector_verified_write_back_eligible(context))
        self.assert_context_error(
            lambda: assert_connector_verified_for_write_back(context),
            ERROR_CODES["CONNECTOR_VERIFICATION_REQUIRED"],
            details={
                "contextId": "ctx-1",
                "trustLevel": "connector_verified",
                "sourceType": "connector_resource_excerpt",
                "hasResourceRevision": True,
                "hasAnchorOrRange": True,
                "hasOriginalTextHash": True,
                "truncated": True,
                "redacted": False,
            },
        )

    def test_truncation_preserves_utf8_character_boundaries(self):
        context = normalize_context(context_input(content="abéz"), {"now": NOW, "maxBytes": 4})

        self.assertEqual(context["content"], "abé")
        self.assertEqual(context["metadata"]["contentLimit"]["returnedBytes"], 4)

    def test_normalize_context_rejects_oversized_content_when_complete_content_is_required(self):
        self.assert_context_error(
            lambda: normalize_context(
                context_input(content="abcdef"),
                {"now": NOW, "maxBytes": 4, "oversizedBehavior": "reject"},
            ),
            ERROR_CODES["CONTEXT_TOO_LARGE"],
            http_status=413,
        )
