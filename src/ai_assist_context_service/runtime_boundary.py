from .read_path import read_context_with_consent
from .validation import assert_non_empty_string, assert_plain_object
from .errors import ERROR_CODES, context_error


def context_request_with_server_identity(client_request, server_identity):
    """Build a context request from authenticated identity, not client identity."""
    assert_plain_object(client_request, "client_request")
    assert_plain_object(server_identity, "server_identity")
    assert_non_empty_string(server_identity.get("tenantId"), "server_identity.tenantId")
    assert_non_empty_string(server_identity.get("userId"), "server_identity.userId")

    identity_drift = []
    for field_name in ("tenantId", "userId"):
        if client_request.get(field_name) is not None and client_request[field_name] != server_identity[field_name]:
            identity_drift.append(field_name)
    if identity_drift:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "client identity fields must match authenticated server identity",
            http_status=403,
            details={"fields": identity_drift},
        )

    request = {key: value for key, value in client_request.items() if key not in ("tenantId", "userId")}
    request["tenantId"] = server_identity["tenantId"]
    request["userId"] = server_identity["userId"]
    return request


def read_context_with_server_identity(client_request, server_identity, connector_read_context, options=None):
    request = context_request_with_server_identity(client_request, server_identity)
    return read_context_with_consent(request, connector_read_context, options)
