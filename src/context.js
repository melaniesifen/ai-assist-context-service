import { randomUUID } from "node:crypto";
import { DEFAULT_CONTEXT_TTL_MS } from "./constants.js";
import { applyContextByteLimit } from "./limits.js";
import { validateContextMode } from "./modes.js";
import { hashContent } from "./hash.js";
import { classifyContextSource, normalizeProvenance } from "./provenance.js";
import { applyContextRedaction } from "./redaction.js";
import { assertNonEmptyString, assertPlainObject } from "./validation.js";

export function normalizeContext(input, options = {}) {
  assertPlainObject(input, "input");
  const now = options.now ?? new Date();
  const capturedAt = input.capturedAt ?? now.toISOString();
  const expiresAt =
    input.expiresAt ?? new Date(now.getTime() + (options.ttlMs ?? DEFAULT_CONTEXT_TTL_MS)).toISOString();

  validateContextMode(input.contextMode);
  assertNonEmptyString(input.tenantId, "input.tenantId");
  assertNonEmptyString(input.userId, "input.userId");
  assertNonEmptyString(input.sessionId, "input.sessionId");
  assertNonEmptyString(input.provider, "input.provider");
  assertPlainObject(input.resourceRef, "input.resourceRef");
  assertNonEmptyString(input.resourceRef.resourceId, "input.resourceRef.resourceId");
  assertNonEmptyString(input.content, "input.content");

  const redactionResult = applyContextRedaction(input.content, {
    policy: options.redactionPolicy,
    rules: options.redactionRules
  });
  const limitResult = applyContextByteLimit(redactionResult.content, {
    maxBytes: options.maxBytes,
    oversizedBehavior: options.oversizedBehavior ?? "truncate",
    rejectionReason: "context content exceeds configured safe limit"
  });
  const classification = classifyContextSource(input);
  const provenance = normalizeProvenance({
    ...input,
    capturedAt,
    resourceId: input.resourceRef.resourceId,
    resourceVersion: input.resourceRevision ?? input.resourceVersion ?? null,
    selectionAnchor: input.anchors?.selectionAnchor ?? null
  });

  return {
    contextId: input.contextId ?? randomUUID(),
    tenantId: input.tenantId,
    userId: input.userId,
    sessionId: input.sessionId,
    provider: input.provider,
    resourceRef: input.resourceRef,
    contextMode: input.contextMode,
    sourceType: classification.sourceType,
    trustLevel: classification.trustLevel,
    content: limitResult.content,
    contentHash: hashContent(limitResult.content),
    anchors: input.anchors ?? {},
    resourceRevision: input.resourceRevision ?? null,
    metadata: {
      ...(input.metadata ?? {}),
      redaction: redactionResult.metadata,
      contentLimit: limitResult.metadata
    },
    provenance,
    capturedAt,
    expiresAt,
    clientSupplied: classification.clientSupplied,
    connectorVerified: classification.connectorVerified
  };
}
