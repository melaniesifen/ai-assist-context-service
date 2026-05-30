export const CONTEXT_MODES = Object.freeze({
  SELECTION: "SELECTION",
  ACTIVE_RESOURCE: "ACTIVE_RESOURCE",
  VISIBLE_REGION: "VISIBLE_REGION",
  WORKSPACE: "WORKSPACE",
  SCREEN: "SCREEN"
});

export const MVP_CONTEXT_MODES = Object.freeze([
  CONTEXT_MODES.SELECTION,
  CONTEXT_MODES.ACTIVE_RESOURCE
]);

export const FUTURE_CONTEXT_MODES = Object.freeze([
  CONTEXT_MODES.VISIBLE_REGION,
  CONTEXT_MODES.WORKSPACE,
  CONTEXT_MODES.SCREEN
]);

export const CONSENT_STATUSES = Object.freeze({
  ACTIVE: "active",
  REVOKED: "revoked",
  EXPIRED: "expired"
});

export const SOURCE_TYPES = Object.freeze({
  CLIENT_SELECTION_TEXT: "client_selection_text",
  CONNECTOR_SELECTION: "connector_selection",
  CONNECTOR_RESOURCE_EXCERPT: "connector_resource_excerpt",
  CONNECTOR_VISIBLE_REGION: "connector_visible_region",
  CONNECTOR_WORKSPACE_EXCERPT: "connector_workspace_excerpt",
  SCREEN_CAPTURE: "screen_capture"
});

export const TRUST_LEVELS = Object.freeze({
  CLIENT_SUPPLIED: "client_supplied",
  CONNECTOR_VERIFIED: "connector_verified",
  SYSTEM_VERIFIED: "system_verified"
});

export const DEFAULT_CONTEXT_TTL_MS = 15 * 60 * 1000;
export const DEFAULT_MAX_CONTEXT_BYTES = 64 * 1024;
