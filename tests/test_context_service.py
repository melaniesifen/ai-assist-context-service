from datetime import datetime, timezone
import unittest

from ai_assist_context_service import (
    CONSENT_STATUSES,
    CONTEXT_MODES,
    ERROR_CODES,
    REDACTION_POLICIES,
    assert_connector_verified_for_write_back,
    build_context_log_metadata,
    hash_content,
    is_connector_verified_write_back_eligible,
    normalize_context,
    validate_consent_for_context_request,
    validate_context_consent_grant,
    validate_context_mode,
)

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
        "anchors": {"targetRange": {"startIndex": 0, "endIndex": 6}},
        "connectorVerified": True,
    }
    value.update(overrides)
    return value


class ContextServiceTests(unittest.TestCase):
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

    def test_validate_context_mode_accepts_only_mvp_supported_modes(self):
        self.assertEqual(validate_context_mode(CONTEXT_MODES["SELECTION"]), CONTEXT_MODES["SELECTION"])
        self.assertEqual(validate_context_mode(CONTEXT_MODES["ACTIVE_RESOURCE"]), CONTEXT_MODES["ACTIVE_RESOURCE"])

        self.assert_context_error(
            lambda: validate_context_mode(CONTEXT_MODES["SCREEN"]),
            ERROR_CODES["CONTEXT_MODE_UNSUPPORTED"],
        )
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

    def test_validate_context_consent_grant_rejects_wrong_tenant_revoked_and_expired_grants(self):
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
            lambda: validate_context_consent_grant(
                active_grant(status=CONSENT_STATUSES["REVOKED"]),
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
        self.assertTrue(context["connectorVerified"])
        self.assertTrue(is_connector_verified_write_back_eligible(context))
        self.assertTrue(assert_connector_verified_for_write_back(context))

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


if __name__ == "__main__":
    unittest.main()
