from ai_assist_context_service import (
    CONSENT_STATUSES,
    CONTEXT_MODES,
    ERROR_CODES,
    validate_active_consent_for_apply_target,
    validate_consent_for_context_request,
    validate_context_consent_grant,
)
from tests.common import NOW, ContextServiceTestCase, active_grant, context_request


class ConsentTests(ContextServiceTestCase):
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
