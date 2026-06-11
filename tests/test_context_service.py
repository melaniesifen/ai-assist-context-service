import unittest

from ai_assist_context_service import (
    CONSENT_STATUSES,
    CONTEXT_MODES,
    ERROR_CODES,
    REDACTION_POLICIES,
    assert_connector_verified_for_write_back,
    build_context_log_metadata,
    connector_verified_write_back_target_metadata,
    hash_content,
    is_connector_verified_write_back_eligible,
    normalize_context,
    read_context_with_consent,
    validate_active_consent_for_apply_target,
    validate_consent_for_context_request,
    validate_context_consent_grant,
    validate_context_mode,
)
from tests.common import NOW, ContextServiceTestCase, active_grant, context_input, context_request


class ContextServiceTests(ContextServiceTestCase):

    def test_validate_context_mode_accepts_only_mvp_supported_modes(self):
        self.assertEqual(validate_context_mode(CONTEXT_MODES["SELECTION"]), CONTEXT_MODES["SELECTION"])
        self.assertEqual(validate_context_mode(CONTEXT_MODES["ACTIVE_RESOURCE"]), CONTEXT_MODES["ACTIVE_RESOURCE"])

        self.assert_context_error(
            lambda: validate_context_mode(CONTEXT_MODES["SCREEN"]),
            ERROR_CODES["UNSUPPORTED_CONTEXT_MODE"],
            http_status=400,
        )
        error = self.assert_context_error(
            lambda: validate_context_mode(CONTEXT_MODES["VISIBLE_REGION"]),
            ERROR_CODES["UNSUPPORTED_CONTEXT_MODE"],
            http_status=400,
        )
        self.assertEqual(error.category, "VALIDATION")
        self.assertEqual(error.target, "contextMode")
        self.assert_context_error(lambda: validate_context_mode("UNKNOWN_MODE"), ERROR_CODES["VALIDATION_ERROR"])

    def test_selection_can_be_consented_by_explicit_user_action_without_persisted_grant(self):
        result = validate_consent_for_context_request(
            {
                "tenantId": "tenant-1",
                "userId": "user-1",
                "provider": "google_docs",
                "contextMode": CONTEXT_MODES["SELECTION"],
                "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
                "explicitUserAction": True,
            },
            {"now": NOW},
        )

        self.assertEqual(result, {"valid": True, "grantId": None, "explicitUserAction": True})

    def test_explicit_selection_still_validates_identity_and_resource_shape(self):
        self.assert_context_error(
            lambda: validate_consent_for_context_request(
                {
                    "contextMode": CONTEXT_MODES["SELECTION"],
                    "explicitUserAction": True,
                },
                {"now": NOW},
            ),
            ERROR_CODES["VALIDATION_ERROR"],
        )

        self.assert_context_error(
            lambda: validate_consent_for_context_request(
                {
                    "tenantId": "tenant-1",
                    "userId": "user-1",
                    "provider": "google_docs",
                    "contextMode": CONTEXT_MODES["SELECTION"],
                    "resourceRef": {"provider": "not_google_docs", "resourceId": "doc-1"},
                    "explicitUserAction": True,
                },
                {"now": NOW},
            ),
            ERROR_CODES["VALIDATION_ERROR"],
            details={"fields": ["request.provider", "request.resourceRef.provider"]},
        )

    def test_active_resource_requires_an_active_matching_grant(self):
        self.assert_context_error(
            lambda: validate_consent_for_context_request(
                {
                    "tenantId": "tenant-1",
                    "userId": "user-1",
                    "provider": "google_docs",
                    "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
                    "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
                },
                {"now": NOW},
            ),
            ERROR_CODES["CONSENT_REQUIRED"],
        )

        result = validate_consent_for_context_request(
            {
                "tenantId": "tenant-1",
                "userId": "user-1",
                "provider": "google_docs",
                "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
                "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
                "consentGrant": active_grant(),
            },
            {"now": NOW},
        )

        self.assertEqual(result, {"valid": True, "grantId": "grant-1"})

    def test_apply_target_requires_active_persisted_consent_for_selection_and_active_resource(self):
        for context_mode in (CONTEXT_MODES["SELECTION"], CONTEXT_MODES["ACTIVE_RESOURCE"]):
            with self.subTest(context_mode=context_mode):
                request = context_request(
                    contextMode=context_mode,
                    explicitUserAction=True,
                    consentGrant=active_grant(contextMode=context_mode),
                )

                self.assertEqual(
                    validate_active_consent_for_apply_target(request, {"now": NOW}),
                    {"valid": True, "grantId": "grant-1"},
                )

                self.assert_context_error(
                    lambda: validate_active_consent_for_apply_target(
                        context_request(
                            contextMode=context_mode,
                            explicitUserAction=True,
                            consentGrant=None,
                        ),
                        {"now": NOW},
                    ),
                    ERROR_CODES["CONSENT_REQUIRED"],
                    http_status=403,
                )

    def test_apply_target_rejects_revoked_expired_wrong_resource_and_wrong_provider_consent(self):
        failure_grants = [
            active_grant(status=CONSENT_STATUSES["REVOKED"]),
            active_grant(status=CONSENT_STATUSES["EXPIRED"]),
            active_grant(expiresAt="2026-05-29T11:59:00.000Z"),
            active_grant(resourceRef={"provider": "google_docs", "resourceId": "other-doc"}),
            active_grant(provider="not_google_docs"),
        ]

        for grant in failure_grants:
            with self.subTest(grant=grant):
                self.assert_context_error(
                    lambda grant=grant: validate_active_consent_for_apply_target(
                        context_request(consentGrant=grant),
                        {"now": NOW},
                    ),
                    ERROR_CODES["CONSENT_DENIED"],
                    http_status=403,
                )

    def test_active_resource_rejects_resource_ref_provider_drift_before_grant_coverage(self):
        self.assert_context_error(
            lambda: validate_consent_for_context_request(
                {
                    "tenantId": "tenant-1",
                    "userId": "user-1",
                    "provider": "google_docs",
                    "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
                    "resourceRef": {"provider": "not_google_docs", "resourceId": "doc-1"},
                    "consentGrant": active_grant(),
                },
                {"now": NOW},
            ),
            ERROR_CODES["VALIDATION_ERROR"],
            details={"fields": ["request.provider", "request.resourceRef.provider"]},
        )

    def test_validate_context_consent_grant_rejects_scoped_status_and_expiry_failures(self):
        request = {
            "tenantId": "tenant-1",
            "userId": "user-1",
            "provider": "google_docs",
            "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
            "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
        }

        self.assert_context_error(
            lambda: validate_context_consent_grant(active_grant(tenantId="other"), request, {"now": NOW}),
            ERROR_CODES["CONSENT_DENIED"],
            details={"fields": ["tenantId"]},
        )
        self.assert_context_error(
            lambda: validate_context_consent_grant(active_grant(userId="other-user"), request, {"now": NOW}),
            ERROR_CODES["CONSENT_DENIED"],
            details={"fields": ["userId"]},
        )
        self.assert_context_error(
            lambda: validate_context_consent_grant(active_grant(provider="not_google_docs"), request, {"now": NOW}),
            ERROR_CODES["CONSENT_DENIED"],
            details={"fields": ["provider"]},
        )
        self.assert_context_error(
            lambda: validate_context_consent_grant(
                active_grant(resourceRef={"provider": "google_docs", "resourceId": "other-doc"}),
                request,
                {"now": NOW},
            ),
            ERROR_CODES["CONSENT_DENIED"],
            details={"fields": ["resourceRef"]},
        )
        self.assert_context_error(
            lambda: validate_context_consent_grant(
                active_grant(status=CONSENT_STATUSES["REVOKED"]),
                request,
                {"now": NOW},
            ),
            ERROR_CODES["CONSENT_DENIED"],
        )
        self.assert_context_error(
            lambda: validate_context_consent_grant(
                active_grant(status=CONSENT_STATUSES["EXPIRED"]),
                request,
                {"now": NOW},
            ),
            ERROR_CODES["CONSENT_DENIED"],
        )
        self.assert_context_error(
            lambda: validate_context_consent_grant(
                active_grant(expiresAt="2026-05-29T11:59:00.000Z"),
                request,
                {"now": NOW},
            ),
            ERROR_CODES["CONSENT_DENIED"],
        )
        self.assert_context_error(
            lambda: validate_context_consent_grant(
                active_grant(expiresAt="2026-05-29T07:59:00.000-04:00"),
                request,
                {"now": NOW},
            ),
            ERROR_CODES["CONSENT_DENIED"],
        )

    def test_validate_context_consent_grant_rejects_offset_naive_timestamps_with_structured_error(self):
        request = {
            "tenantId": "tenant-1",
            "userId": "user-1",
            "provider": "google_docs",
            "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
            "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
        }

        self.assert_context_error(
            lambda: validate_context_consent_grant(
                active_grant(expiresAt="2026-05-29T11:59:00"),
                request,
                {"now": NOW},
            ),
            ERROR_CODES["VALIDATION_ERROR"],
            details={"field": "grant.expiresAt"},
        )

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

    def test_build_context_log_metadata_omits_raw_content_and_keeps_only_safe_context_metadata(self):
        context = normalize_context(context_input(content="private document content"), {"now": NOW})
        metadata = build_context_log_metadata(context)

        self.assertNotIn("content", metadata)
        self.assertNotIn("provenance", metadata)
        self.assertEqual(
            metadata["contentBytes"],
            {
                "originalBytes": 24,
                "returnedBytes": 24,
                "maxBytes": 65536,
                "truncated": False,
            },
        )
        self.assertEqual(metadata["contentHash"], hash_content("private document content"))
        self.assertTrue(metadata["connectorVerified"])

    def test_public_readme_helpers_import_from_package_surface(self):
        from ai_assist_context_service import build_context_log_metadata, normalize_context

        self.assertTrue(callable(build_context_log_metadata))
        self.assertTrue(callable(normalize_context))

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
        self.assertEqual(result["context"]["contentHash"], hash_content("Selected connector text"))
        self.assertEqual(result["context"]["provenance"]["selectionAnchor"], {"startIndex": 1, "endIndex": 5})


if __name__ == "__main__":
    unittest.main()
