from ai_assist_context_service import CONTEXT_MODES, ERROR_CODES, validate_context_mode
from tests.common import ContextServiceTestCase


class ModeTests(ContextServiceTestCase):
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

    def test_public_readme_helpers_import_from_package_surface(self):
        from ai_assist_context_service import build_context_log_metadata, normalize_context

        self.assertTrue(callable(build_context_log_metadata))
        self.assertTrue(callable(normalize_context))
