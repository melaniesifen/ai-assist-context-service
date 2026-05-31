import { assertPlainObject } from "./validation.js";

export function buildContextLogMetadata(context) {
  assertPlainObject(context, "context");
  const contentLimit = context.metadata?.contentLimit ?? {};

  return {
    contextId: context.contextId ?? null,
    tenantId: context.tenantId ?? null,
    userId: context.userId ?? null,
    sessionId: context.sessionId ?? null,
    provider: context.provider ?? null,
    resourceRef: context.resourceRef
      ? {
          provider: context.resourceRef.provider ?? null,
          resourceId: context.resourceRef.resourceId ?? null
        }
      : null,
    contextMode: context.contextMode ?? null,
    sourceType: context.sourceType ?? null,
    trustLevel: context.trustLevel ?? null,
    contentHash: context.contentHash ?? null,
    contentBytes: {
      originalBytes: contentLimit.originalBytes ?? null,
      returnedBytes: contentLimit.returnedBytes ?? null,
      maxBytes: contentLimit.maxBytes ?? null,
      truncated: contentLimit.truncated === true
    },
    redaction: context.metadata?.redaction
      ? {
          policy: context.metadata.redaction.policy,
          redacted: context.metadata.redaction.redacted === true,
          rulesApplied: [...(context.metadata.redaction.rulesApplied ?? [])]
        }
      : null,
    clientSupplied: context.clientSupplied === true,
    connectorVerified: context.connectorVerified === true,
    capturedAt: context.capturedAt ?? null,
    expiresAt: context.expiresAt ?? null
  };
}
