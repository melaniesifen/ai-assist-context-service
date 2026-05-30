import { CONTEXT_MODES, SOURCE_TYPES, TRUST_LEVELS } from "./constants.js";
import { ERROR_CODES, contextError } from "./errors.js";
import { assertNonEmptyString, assertPlainObject } from "./validation.js";

export function classifyContextSource(input) {
  assertPlainObject(input, "input");

  if (input.clientSupplied === true && input.connectorVerified === true) {
    throw contextError(ERROR_CODES.VALIDATION_ERROR, "context cannot be both client-supplied and connector-verified", {
      details: { fields: ["clientSupplied", "connectorVerified"] }
    });
  }

  if (input.clientSupplied === true) {
    return {
      sourceType: SOURCE_TYPES.CLIENT_SELECTION_TEXT,
      trustLevel: TRUST_LEVELS.CLIENT_SUPPLIED,
      clientSupplied: true,
      connectorVerified: false
    };
  }

  if (input.connectorVerified === true) {
    return {
      sourceType: sourceTypeForConnectorContext(input.contextMode),
      trustLevel: TRUST_LEVELS.CONNECTOR_VERIFIED,
      clientSupplied: false,
      connectorVerified: true
    };
  }

  throw contextError(ERROR_CODES.VALIDATION_ERROR, "context source must be classified", {
    details: { requiredOneOf: ["clientSupplied", "connectorVerified"] }
  });
}

export function normalizeProvenance(input) {
  assertPlainObject(input, "input");
  const classification = classifyContextSource(input);
  assertNonEmptyString(input.connector, "input.connector");
  assertNonEmptyString(input.resourceId, "input.resourceId");

  return {
    sourceType: classification.sourceType,
    trustLevel: classification.trustLevel,
    connector: input.connector,
    resourceId: input.resourceId,
    resourceVersion: input.resourceVersion ?? null,
    selectionAnchor: input.selectionAnchor ?? null,
    capturedAt: input.capturedAt,
    clientSupplied: classification.clientSupplied,
    connectorVerified: classification.connectorVerified
  };
}

export function assertConnectorVerifiedForWriteBack(context) {
  if (!isConnectorVerifiedWriteBackEligible(context)) {
    throw contextError(
      ERROR_CODES.CONNECTOR_VERIFICATION_REQUIRED,
      "connector-verified resource revision and target metadata are required for write-back",
      {
        httpStatus: 422,
        details: {
          contextId: context?.contextId,
          trustLevel: context?.trustLevel,
          sourceType: context?.sourceType,
          hasResourceRevision: Boolean(context?.resourceRevision),
          hasAnchorOrRange: Boolean(context?.anchors?.selectionAnchor || context?.anchors?.targetRange),
          truncated: context?.metadata?.contentLimit?.truncated === true
        }
      }
    );
  }
  return true;
}

export function isConnectorVerifiedWriteBackEligible(context) {
  return (
    context?.connectorVerified === true &&
    context?.trustLevel === TRUST_LEVELS.CONNECTOR_VERIFIED &&
    typeof context?.contentHash === "string" &&
    Boolean(context?.resourceRevision) &&
    Boolean(context?.anchors?.selectionAnchor || context?.anchors?.targetRange) &&
    context?.metadata?.contentLimit?.truncated !== true
  );
}

function sourceTypeForConnectorContext(contextMode) {
  if (contextMode === CONTEXT_MODES.SELECTION) {
    return SOURCE_TYPES.CONNECTOR_SELECTION;
  }
  if (contextMode === CONTEXT_MODES.ACTIVE_RESOURCE) {
    return SOURCE_TYPES.CONNECTOR_RESOURCE_EXCERPT;
  }
  if (contextMode === CONTEXT_MODES.VISIBLE_REGION) {
    return SOURCE_TYPES.CONNECTOR_VISIBLE_REGION;
  }
  if (contextMode === CONTEXT_MODES.WORKSPACE) {
    return SOURCE_TYPES.CONNECTOR_WORKSPACE_EXCERPT;
  }
  return SOURCE_TYPES.SCREEN_CAPTURE;
}
