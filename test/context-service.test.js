import test from "node:test";
import assert from "node:assert/strict";
import {
  CONSENT_STATUSES,
  CONTEXT_MODES,
  ERROR_CODES,
  REDACTION_POLICIES,
  assertConnectorVerifiedForWriteBack,
  buildContextLogMetadata,
  hashContent,
  isConnectorVerifiedWriteBackEligible,
  normalizeContext,
  validateConsentForContextRequest,
  validateContextConsentGrant,
  validateContextMode
} from "../src/index.js";

const NOW = new Date("2026-05-29T12:00:00.000Z");

function activeGrant(overrides = {}) {
  return {
    grantId: "grant-1",
    tenantId: "tenant-1",
    userId: "user-1",
    provider: "google_docs",
    contextMode: CONTEXT_MODES.ACTIVE_RESOURCE,
    resourceRef: { provider: "google_docs", resourceId: "doc-1" },
    workspaceBoundary: null,
    scopes: ["docs.read"],
    status: CONSENT_STATUSES.ACTIVE,
    grantedAt: "2026-05-29T11:00:00.000Z",
    revokedAt: null,
    expiresAt: "2026-05-29T13:00:00.000Z",
    ...overrides
  };
}

function contextInput(overrides = {}) {
  return {
    contextId: "ctx-1",
    tenantId: "tenant-1",
    userId: "user-1",
    sessionId: "session-1",
    provider: "google_docs",
    resourceRef: { provider: "google_docs", resourceId: "doc-1" },
    contextMode: CONTEXT_MODES.ACTIVE_RESOURCE,
    connector: "google_docs",
    content: "Useful document context",
    resourceRevision: "rev-1",
    anchors: { targetRange: { startIndex: 0, endIndex: 6 } },
    connectorVerified: true,
    ...overrides
  };
}

test("validateContextMode accepts only MVP-supported modes", () => {
  assert.equal(validateContextMode(CONTEXT_MODES.SELECTION), CONTEXT_MODES.SELECTION);
  assert.equal(validateContextMode(CONTEXT_MODES.ACTIVE_RESOURCE), CONTEXT_MODES.ACTIVE_RESOURCE);

  assert.throws(() => validateContextMode(CONTEXT_MODES.SCREEN), {
    code: ERROR_CODES.CONTEXT_MODE_UNSUPPORTED
  });
  assert.throws(() => validateContextMode("UNKNOWN_MODE"), {
    code: ERROR_CODES.VALIDATION_ERROR
  });
});

test("SELECTION can be consented by explicit user action without a persisted grant", () => {
  const result = validateConsentForContextRequest({
    tenantId: "tenant-1",
    userId: "user-1",
    provider: "google_docs",
    contextMode: CONTEXT_MODES.SELECTION,
    resourceRef: { provider: "google_docs", resourceId: "doc-1" },
    explicitUserAction: true
  });

  assert.deepEqual(result, { valid: true, grantId: null, explicitUserAction: true });
});

test("explicit SELECTION still validates identity and resource shape", () => {
  assert.throws(
    () =>
      validateConsentForContextRequest({
        contextMode: CONTEXT_MODES.SELECTION,
        explicitUserAction: true
      }),
    { code: ERROR_CODES.VALIDATION_ERROR }
  );

  assert.throws(
    () =>
      validateConsentForContextRequest({
        tenantId: "tenant-1",
        userId: "user-1",
        provider: "google_docs",
        contextMode: CONTEXT_MODES.SELECTION,
        resourceRef: { provider: "not_google_docs", resourceId: "doc-1" },
        explicitUserAction: true
      }),
    {
      code: ERROR_CODES.VALIDATION_ERROR,
      details: { fields: ["request.provider", "request.resourceRef.provider"] }
    }
  );
});

test("ACTIVE_RESOURCE requires an active matching grant", () => {
  assert.throws(
    () =>
      validateConsentForContextRequest({
        tenantId: "tenant-1",
        userId: "user-1",
        provider: "google_docs",
        contextMode: CONTEXT_MODES.ACTIVE_RESOURCE,
        resourceRef: { provider: "google_docs", resourceId: "doc-1" }
      }),
    { code: ERROR_CODES.CONSENT_REQUIRED }
  );

  const result = validateConsentForContextRequest(
    {
      tenantId: "tenant-1",
      userId: "user-1",
      provider: "google_docs",
      contextMode: CONTEXT_MODES.ACTIVE_RESOURCE,
      resourceRef: { provider: "google_docs", resourceId: "doc-1" },
      consentGrant: activeGrant()
    },
    { now: NOW }
  );

  assert.deepEqual(result, { valid: true, grantId: "grant-1" });
});

test("ACTIVE_RESOURCE rejects resourceRef provider drift before grant coverage checks", () => {
  assert.throws(
    () =>
      validateConsentForContextRequest(
        {
          tenantId: "tenant-1",
          userId: "user-1",
          provider: "google_docs",
          contextMode: CONTEXT_MODES.ACTIVE_RESOURCE,
          resourceRef: { provider: "not_google_docs", resourceId: "doc-1" },
          consentGrant: activeGrant()
        },
        { now: NOW }
      ),
    {
      code: ERROR_CODES.VALIDATION_ERROR,
      details: { fields: ["request.provider", "request.resourceRef.provider"] }
    }
  );
});

test("validateContextConsentGrant rejects wrong tenant, revoked, and expired grants", () => {
  const request = {
    tenantId: "tenant-1",
    userId: "user-1",
    provider: "google_docs",
    contextMode: CONTEXT_MODES.ACTIVE_RESOURCE,
    resourceRef: { provider: "google_docs", resourceId: "doc-1" }
  };

  assert.throws(() => validateContextConsentGrant(activeGrant({ tenantId: "other" }), request, { now: NOW }), {
    code: ERROR_CODES.CONSENT_DENIED,
    details: { fields: ["tenantId"] }
  });
  assert.throws(
    () => validateContextConsentGrant(activeGrant({ status: CONSENT_STATUSES.REVOKED }), request, { now: NOW }),
    { code: ERROR_CODES.CONSENT_DENIED }
  );
  assert.throws(
    () =>
      validateContextConsentGrant(activeGrant({ expiresAt: "2026-05-29T11:59:00.000Z" }), request, { now: NOW }),
    { code: ERROR_CODES.CONSENT_DENIED }
  );
});

test("normalizeContext marks client-supplied selected text as non-writeback context", () => {
  const context = normalizeContext(
    contextInput({
      contextMode: CONTEXT_MODES.SELECTION,
      content: "selected by browser",
      clientSupplied: true,
      connectorVerified: undefined,
      resourceRevision: null,
      anchors: {}
    }),
    { now: NOW }
  );

  assert.equal(context.sourceType, "client_selection_text");
  assert.equal(context.trustLevel, "client_supplied");
  assert.equal(context.clientSupplied, true);
  assert.equal(context.connectorVerified, false);
  assert.equal(context.contentHash, hashContent("selected by browser"));
  assert.equal(isConnectorVerifiedWriteBackEligible(context), false);
  assert.throws(() => assertConnectorVerifiedForWriteBack(context), {
    code: ERROR_CODES.CONNECTOR_VERIFICATION_REQUIRED
  });
});

test("normalizeContext marks connector-verified context with provenance and writeback eligibility", () => {
  const context = normalizeContext(contextInput(), { now: NOW });

  assert.equal(context.sourceType, "connector_resource_excerpt");
  assert.equal(context.trustLevel, "connector_verified");
  assert.equal(context.provenance.connector, "google_docs");
  assert.equal(context.provenance.resourceVersion, "rev-1");
  assert.equal(context.connectorVerified, true);
  assert.equal(isConnectorVerifiedWriteBackEligible(context), true);
  assert.equal(assertConnectorVerifiedForWriteBack(context), true);
});

test("write-back eligibility requires a non-empty content hash", () => {
  const context = normalizeContext(contextInput(), { now: NOW });

  assert.equal(isConnectorVerifiedWriteBackEligible({ ...context, contentHash: "   " }), false);
  assert.throws(() => assertConnectorVerifiedForWriteBack({ ...context, contentHash: "" }), {
    code: ERROR_CODES.CONNECTOR_VERIFICATION_REQUIRED
  });
});

test("normalizeContext can apply deterministic MVP redaction before hashing and byte limits", () => {
  const context = normalizeContext(
    contextInput({
      content: "Email owner@example.com with Bearer abcdefghijklmnopqrstuvwxyz123456"
    }),
    {
      now: NOW,
      redactionPolicy: REDACTION_POLICIES.MVP_DEFAULT
    }
  );

  assert.equal(
    context.content,
    "Email <redacted:email_address> with Bearer <redacted:token>"
  );
  assert.equal(context.contentHash, hashContent(context.content));
  assert.deepEqual(context.metadata.redaction, {
    policy: REDACTION_POLICIES.MVP_DEFAULT,
    redacted: true,
    rulesApplied: ["email_address", "bearer_token"]
  });
  assert.equal(isConnectorVerifiedWriteBackEligible(context), false);
  assert.throws(() => assertConnectorVerifiedForWriteBack(context), {
    code: ERROR_CODES.CONNECTOR_VERIFICATION_REQUIRED,
    details: {
      contextId: "ctx-1",
      trustLevel: "connector_verified",
      sourceType: "connector_resource_excerpt",
      hasResourceRevision: true,
      hasAnchorOrRange: true,
      truncated: false,
      redacted: true
    }
  });
});

test("MVP redaction matches bearer token schemes case-insensitively", () => {
  const context = normalizeContext(
    contextInput({
      content: "authorization: bEaReR abcdefghijklmnopqrstuvwxyz123456"
    }),
    {
      now: NOW,
      redactionPolicy: REDACTION_POLICIES.MVP_DEFAULT
    }
  );

  assert.equal(context.content, "authorization: Bearer <redacted:token>");
  assert.deepEqual(context.metadata.redaction.rulesApplied, ["bearer_token"]);
});

test("buildContextLogMetadata omits raw content and keeps only safe context metadata", () => {
  const context = normalizeContext(contextInput({ content: "private document content" }), { now: NOW });
  const metadata = buildContextLogMetadata(context);

  assert.equal(Object.hasOwn(metadata, "content"), false);
  assert.equal(Object.hasOwn(metadata, "provenance"), false);
  assert.deepEqual(metadata.contentBytes, {
    originalBytes: 24,
    returnedBytes: 24,
    maxBytes: 65536,
    truncated: false
  });
  assert.equal(metadata.contentHash, hashContent("private document content"));
  assert.equal(metadata.connectorVerified, true);
});

test("normalizeContext truncates oversized content when safe", () => {
  const context = normalizeContext(contextInput({ content: "abcdef" }), {
    now: NOW,
    maxBytes: 4
  });

  assert.equal(context.content, "abcd");
  assert.equal(context.metadata.contentLimit.truncated, true);
  assert.equal(context.metadata.contentLimit.originalBytes, 6);
  assert.equal(context.metadata.contentLimit.returnedBytes, 4);
  assert.equal(isConnectorVerifiedWriteBackEligible(context), false);
  assert.throws(() => assertConnectorVerifiedForWriteBack(context), {
    code: ERROR_CODES.CONNECTOR_VERIFICATION_REQUIRED,
    details: {
      contextId: "ctx-1",
      trustLevel: "connector_verified",
      sourceType: "connector_resource_excerpt",
      hasResourceRevision: true,
      hasAnchorOrRange: true,
      truncated: true,
      redacted: false
    }
  });
});

test("normalizeContext rejects oversized content when complete content is required", () => {
  assert.throws(
    () =>
      normalizeContext(contextInput({ content: "abcdef" }), {
        now: NOW,
        maxBytes: 4,
        oversizedBehavior: "reject"
      }),
    {
      code: ERROR_CODES.CONTEXT_TOO_LARGE,
      httpStatus: 413
    }
  );
});
