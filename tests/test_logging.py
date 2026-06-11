from ai_assist_context_service import build_context_log_metadata, hash_content, normalize_context
from tests.common import NOW, ContextServiceTestCase, context_input


class LoggingTests(ContextServiceTestCase):
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
