CONTEXT_MODES = {
    "SELECTION": "SELECTION",
    "ACTIVE_RESOURCE": "ACTIVE_RESOURCE",
    "VISIBLE_REGION": "VISIBLE_REGION",
    "WORKSPACE": "WORKSPACE",
    "SCREEN": "SCREEN",
}

MVP_CONTEXT_MODES = (
    CONTEXT_MODES["SELECTION"],
    CONTEXT_MODES["ACTIVE_RESOURCE"],
)

FUTURE_CONTEXT_MODES = (
    CONTEXT_MODES["VISIBLE_REGION"],
    CONTEXT_MODES["WORKSPACE"],
    CONTEXT_MODES["SCREEN"],
)

CONSENT_STATUSES = {
    "ACTIVE": "active",
    "REVOKED": "revoked",
    "EXPIRED": "expired",
}

SOURCE_TYPES = {
    "CLIENT_SELECTION_TEXT": "client_selection_text",
    "CONNECTOR_SELECTION": "connector_selection",
    "CONNECTOR_RESOURCE_EXCERPT": "connector_resource_excerpt",
    "CONNECTOR_VISIBLE_REGION": "connector_visible_region",
    "CONNECTOR_WORKSPACE_EXCERPT": "connector_workspace_excerpt",
    "SCREEN_CAPTURE": "screen_capture",
}

TRUST_LEVELS = {
    "CLIENT_SUPPLIED": "client_supplied",
    "CONNECTOR_VERIFIED": "connector_verified",
    "SYSTEM_VERIFIED": "system_verified",
}

DEFAULT_CONTEXT_TTL_MS = 15 * 60 * 1000
DEFAULT_MAX_CONTEXT_BYTES = 64 * 1024
