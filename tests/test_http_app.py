import json
import unittest

from ai_assist_context_service import CONTEXT_MODES
from ai_assist_context_service.http_app import handle_http_request


AUTH_HEADERS = {"Authorization": "Bearer test-session"}


def response_json(response):
    return json.loads(response["body"].decode("utf-8"))


class ContextHttpAppTests(unittest.TestCase):
    def test_context_modes_returns_mvp_metadata_with_no_store(self):
        response = handle_http_request(method="GET", path="/context-modes", headers=AUTH_HEADERS)
        payload = response_json(response)

        self.assertEqual(response["status"], 200)
        self.assertEqual(response["headers"]["Cache-Control"], "no-store")
        self.assertEqual(
            [item["contextMode"] for item in payload["contextModes"][:2]],
            [CONTEXT_MODES["SELECTION"], CONTEXT_MODES["ACTIVE_RESOURCE"]],
        )
        self.assertTrue(payload["contextModes"][0]["supported"])
        self.assertFalse(
            next(item for item in payload["contextModes"] if item["contextMode"] == CONTEXT_MODES["SCREEN"])[
                "supported"
            ]
        )

    def test_context_mode_update_validates_supported_mode(self):
        response = handle_http_request(
            method="PUT",
            path="/resource-sessions/session-1/context-mode",
            headers=AUTH_HEADERS,
            body=json.dumps({"contextMode": CONTEXT_MODES["SELECTION"]}).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 200)
        self.assertEqual(payload["contextMode"], CONTEXT_MODES["SELECTION"])
        self.assertEqual(payload["status"], "validated")

    def test_missing_auth_returns_401(self):
        response = handle_http_request(method="GET", path="/context-modes", headers={})

        self.assertEqual(response["status"], 401)
        self.assertEqual(response_json(response)["error"]["category"], "AUTHENTICATION")

    def test_malformed_or_unsupported_mode_returns_400(self):
        malformed = handle_http_request(
            method="PUT",
            path="/resource-sessions/session-1/context-mode",
            headers=AUTH_HEADERS,
            body=b"[]",
        )
        unsupported = handle_http_request(
            method="PUT",
            path="/resource-sessions/session-1/context-mode",
            headers=AUTH_HEADERS,
            body=json.dumps({"contextMode": CONTEXT_MODES["SCREEN"]}).encode("utf-8"),
        )

        self.assertEqual(malformed["status"], 400)
        self.assertEqual(unsupported["status"], 400)
        self.assertEqual(response_json(unsupported)["error"]["code"], "UNSUPPORTED_CONTEXT_MODE")

    def test_unknown_route_returns_404(self):
        response = handle_http_request(method="GET", path="/unknown", headers=AUTH_HEADERS)

        self.assertEqual(response["status"], 404)
        self.assertEqual(response_json(response)["error"]["code"], "ROUTE_NOT_FOUND")

    def test_context_preview_returns_safe_dependency_error(self):
        response = handle_http_request(
            method="POST",
            path="/resource-sessions/session-1/context-preview",
            headers=AUTH_HEADERS,
            body=json.dumps({"contextMode": CONTEXT_MODES["ACTIVE_RESOURCE"]}).encode("utf-8"),
        )
        payload = response_json(response)

        self.assertEqual(response["status"], 503)
        self.assertEqual(payload["error"]["category"], "DEPENDENCY")
        self.assertEqual(payload["error"]["code"], "CONTEXT_PREVIEW_DEPENDENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
