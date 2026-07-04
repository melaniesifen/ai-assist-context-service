from datetime import datetime, timezone

from ai_assist_context_service import (
    CONSENT_STATUSES,
    CONTEXT_MODES,
    DynamoDbContextConsentGrantRepository,
    ERROR_CODES,
    InMemoryContextConsentGrantRepository,
    build_google_docs_active_resource_grant,
)
from tests.common import NOW, ContextServiceTestCase, active_grant


class FakeDynamoTable:
    def __init__(self):
        self.items = {}
        self.put_calls = []
        self.query_pages = None

    def put_item(self, **kwargs):
        item = kwargs["Item"]
        self.put_calls.append(kwargs)
        self.items[(item["tenantId"], item["userId#provider#contextMode#grantId"])] = dict(item)
        return {}

    def get_item(self, **kwargs):
        key = kwargs["Key"]
        item = self.items.get((key["tenantId"], key["userId#provider#contextMode#grantId"]))
        return {"Item": dict(item)} if item else {}

    def query(self, **kwargs):
        if self.query_pages:
            return self.query_pages.pop(0)
        tenant_id = kwargs["ExpressionAttributeValues"][":tenantId"]
        sort_prefix = kwargs["ExpressionAttributeValues"][":sortKeyPrefix"]
        return {
            "Items": [
                dict(item)
                for (item_tenant_id, sort_key), item in self.items.items()
                if item_tenant_id == tenant_id and sort_key.startswith(sort_prefix)
            ]
        }


def lookup_request(**overrides):
    value = {
        "tenantId": "tenant-1",
        "userId": "user-1",
        "provider": "google_docs",
        "contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"],
        "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
    }
    value.update(overrides)
    return value


class ContextConsentGrantRepositoryTests(ContextServiceTestCase):
    def test_build_google_docs_active_resource_grant_requires_metadata_only_active_resource_shape(self):
        grant = build_google_docs_active_resource_grant(
            {
                "tenantId": "tenant-1",
                "userId": "user-1",
                "resourceRef": {"resourceId": "doc-1", "displayName": "Controlled Doc"},
                "expiresAt": "2026-05-29T13:00:00.000Z",
            },
            now=NOW,
        )

        self.assertEqual(grant["provider"], "google_docs")
        self.assertEqual(grant["contextMode"], CONTEXT_MODES["ACTIVE_RESOURCE"])
        self.assertEqual(grant["resourceRef"]["provider"], "google_docs")
        self.assertEqual(grant["resourceRef"]["resourceId"], "doc-1")
        self.assertEqual(grant["workspaceBoundary"], None)
        self.assertEqual(grant["status"], CONSENT_STATUSES["ACTIVE"])
        self.assertNotIn("content", grant)
        self.assertNotIn("accessToken", grant)

        self.assert_context_error(
            lambda: build_google_docs_active_resource_grant(
                {
                    "tenantId": "tenant-1",
                    "userId": "user-1",
                    "contextMode": CONTEXT_MODES["SELECTION"],
                    "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
                    "expiresAt": "2026-05-29T13:00:00.000Z",
                },
                now=NOW,
            ),
            ERROR_CODES["VALIDATION_ERROR"],
        )

    def test_in_memory_repository_loads_only_active_matching_user_resource_grants(self):
        repository = InMemoryContextConsentGrantRepository(
            [
                active_grant(grantId="grant-active"),
                active_grant(grantId="grant-revoked", status=CONSENT_STATUSES["REVOKED"]),
                active_grant(grantId="grant-expired", expiresAt="2026-05-29T11:59:00.000Z"),
                active_grant(grantId="grant-other-user", userId="user-2"),
                active_grant(grantId="grant-other-resource", resourceRef={"provider": "google_docs", "resourceId": "doc-2"}),
            ]
        )

        self.assertEqual(
            repository.load_grant_for_request(lookup_request(), "grant-active", now=NOW)["grantId"],
            "grant-active",
        )
        self.assertIsNone(repository.load_grant_for_request(lookup_request(), "grant-revoked", now=NOW))
        self.assertIsNone(repository.load_grant_for_request(lookup_request(), "grant-expired", now=NOW))
        self.assertIsNone(repository.load_grant_for_request(lookup_request(), "grant-other-user", now=NOW))
        self.assertIsNone(repository.load_grant_for_request(lookup_request(), "grant-other-resource", now=NOW))
        self.assertEqual([grant["grantId"] for grant in repository.list_active_grants(lookup_request(), now=NOW)], ["grant-active"])

    def test_in_memory_repository_creates_and_revokes_active_resource_grants(self):
        repository = InMemoryContextConsentGrantRepository()
        created = repository.create_google_docs_active_resource_grant(
            {
                "grantId": "grant-new",
                "tenantId": "tenant-1",
                "userId": "user-1",
                "resourceRef": {"provider": "google_docs", "resourceId": "doc-1"},
                "scopes": ["docs.read"],
                "expiresAt": "2026-05-29T13:00:00.000Z",
            },
            now=NOW,
        )
        revoked = repository.revoke_grant(lookup_request(), "grant-new", now=datetime(2026, 5, 29, 12, 30, tzinfo=timezone.utc))

        self.assertEqual(created["grantId"], "grant-new")
        self.assertEqual(revoked["status"], CONSENT_STATUSES["REVOKED"])
        self.assertEqual(revoked["revokedAt"], "2026-05-29T12:30:00.000Z")
        self.assertIsNone(repository.load_grant_for_request(lookup_request(), "grant-new", now=NOW))

    def test_dynamodb_repository_uses_consent_grant_table_keys_and_filters_active_lookup(self):
        table = FakeDynamoTable()
        repository = DynamoDbContextConsentGrantRepository(table)
        created = repository.create_google_docs_active_resource_grant(active_grant(grantId="grant-1"), now=NOW)
        repository.create_google_docs_active_resource_grant(
            active_grant(grantId="grant-2", resourceRef={"provider": "google_docs", "resourceId": "doc-2"}),
            now=NOW,
        )

        self.assertEqual(created["grantId"], "grant-1")
        self.assertEqual(
            table.put_calls[0]["Item"]["userId#provider#contextMode#grantId"],
            "user-1#google_docs#ACTIVE_RESOURCE#grant-1",
        )
        self.assertEqual(table.put_calls[0]["Item"]["ttl"], 1780059600)
        self.assertEqual(
            repository.load_grant_for_request(lookup_request(), "grant-1", now=NOW)["grantId"],
            "grant-1",
        )
        self.assertIsNone(repository.load_grant_for_request(lookup_request(), "grant-2", now=NOW))
        self.assertEqual([grant["grantId"] for grant in repository.list_active_grants(lookup_request(), now=NOW)], ["grant-1"])

    def test_dynamodb_repository_reads_all_query_pages_before_filtering(self):
        table = FakeDynamoTable()
        table.query_pages = [
            {
                "Items": [active_grant(grantId="grant-other", resourceRef={"provider": "google_docs", "resourceId": "doc-2"})],
                "LastEvaluatedKey": {"tenantId": "tenant-1", "userId#provider#contextMode#grantId": "user-1#google_docs#ACTIVE_RESOURCE#grant-other"},
            },
            {
                "Items": [active_grant(grantId="grant-target")],
            },
        ]
        repository = DynamoDbContextConsentGrantRepository(table)

        self.assertEqual(
            repository.load_grant_for_request(lookup_request(), now=NOW)["grantId"],
            "grant-target",
        )
