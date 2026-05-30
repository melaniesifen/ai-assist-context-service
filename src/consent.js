import { CONSENT_STATUSES, CONTEXT_MODES } from "./constants.js";
import { ERROR_CODES, contextError } from "./errors.js";
import { validateContextMode } from "./modes.js";
import {
  assertNonEmptyString,
  assertPlainObject,
  optionalNonEmptyString,
  toDate
} from "./validation.js";

export function validateContextConsentGrant(grant, request, { now = new Date() } = {}) {
  assertPlainObject(grant, "grant");
  assertPlainObject(request, "request");

  validateGrantShape(grant);
  validateContextRequestShape(request);
  validateContextMode(grant.contextMode);

  const mismatches = [];
  collectMismatch(mismatches, grant.tenantId, request.tenantId, "tenantId");
  collectMismatch(mismatches, grant.userId, request.userId, "userId");
  collectMismatch(mismatches, grant.provider, request.provider, "provider");

  if (!contextModeCovers(grant.contextMode, request.contextMode)) {
    mismatches.push("contextMode");
  }
  if (!resourceBoundaryCovers(grant, request)) {
    mismatches.push("resourceRef");
  }
  if (mismatches.length > 0) {
    throw contextError(ERROR_CODES.CONSENT_DENIED, "consent grant does not cover the context request", {
      httpStatus: 403,
      details: { fields: mismatches }
    });
  }

  if (grant.status !== CONSENT_STATUSES.ACTIVE) {
    throw contextError(ERROR_CODES.CONSENT_DENIED, "consent grant is not active", {
      httpStatus: 403,
      details: { grantId: grant.grantId, status: grant.status }
    });
  }

  if (grant.expiresAt && toDate(grant.expiresAt, "grant.expiresAt").getTime() <= now.getTime()) {
    throw contextError(ERROR_CODES.CONSENT_DENIED, "consent grant has expired", {
      httpStatus: 403,
      details: { grantId: grant.grantId }
    });
  }

  return { valid: true, grantId: grant.grantId };
}

export function validateConsentForContextRequest(request, { now = new Date() } = {}) {
  assertPlainObject(request, "request");
  validateContextRequestShape(request);

  if (request.contextMode === CONTEXT_MODES.SELECTION && request.explicitUserAction === true) {
    return { valid: true, grantId: request.consentGrant?.grantId ?? null, explicitUserAction: true };
  }

  if (!request.consentGrant) {
    throw contextError(ERROR_CODES.CONSENT_REQUIRED, "an active consent grant is required", {
      httpStatus: 403,
      details: { contextMode: request.contextMode, provider: request.provider }
    });
  }

  return validateContextConsentGrant(request.consentGrant, request, { now });
}

export function validateContextRequestShape(request) {
  assertNonEmptyString(request.tenantId, "request.tenantId");
  assertNonEmptyString(request.userId, "request.userId");
  assertNonEmptyString(request.provider, "request.provider");
  validateContextMode(request.contextMode);
  assertPlainObject(request.resourceRef, "request.resourceRef");
  assertNonEmptyString(request.resourceRef.provider, "request.resourceRef.provider");
  assertNonEmptyString(request.resourceRef.resourceId, "request.resourceRef.resourceId");

  if (request.resourceRef.provider !== request.provider) {
    throw contextError(ERROR_CODES.VALIDATION_ERROR, "request.resourceRef.provider must match request.provider", {
      details: { fields: ["request.provider", "request.resourceRef.provider"] }
    });
  }
}

function validateGrantShape(grant) {
  assertNonEmptyString(grant.grantId, "grant.grantId");
  assertNonEmptyString(grant.tenantId, "grant.tenantId");
  assertNonEmptyString(grant.userId, "grant.userId");
  assertNonEmptyString(grant.provider, "grant.provider");
  assertNonEmptyString(grant.contextMode, "grant.contextMode");
  assertNonEmptyString(grant.status, "grant.status");
  toDate(grant.grantedAt, "grant.grantedAt");
  optionalNonEmptyString(grant.revokedAt, "grant.revokedAt");
  if (grant.revokedAt) {
    toDate(grant.revokedAt, "grant.revokedAt");
  }
  if (grant.expiresAt) {
    toDate(grant.expiresAt, "grant.expiresAt");
  }

  const validStatuses = Object.values(CONSENT_STATUSES);
  if (!validStatuses.includes(grant.status)) {
    throw contextError(ERROR_CODES.VALIDATION_ERROR, "grant.status is not recognized", {
      details: { field: "grant.status", allowedStatuses: validStatuses }
    });
  }

  if ([CONTEXT_MODES.SELECTION, CONTEXT_MODES.ACTIVE_RESOURCE].includes(grant.contextMode)) {
    assertPlainObject(grant.resourceRef, "grant.resourceRef");
    assertNonEmptyString(grant.resourceRef.provider, "grant.resourceRef.provider");
    assertNonEmptyString(grant.resourceRef.resourceId, "grant.resourceRef.resourceId");
  }

  if (grant.contextMode === CONTEXT_MODES.WORKSPACE) {
    assertPlainObject(grant.workspaceBoundary, "grant.workspaceBoundary");
    assertNonEmptyString(grant.workspaceBoundary.boundaryId, "grant.workspaceBoundary.boundaryId");
  }

  if (!Array.isArray(grant.scopes) || grant.scopes.length === 0) {
    throw contextError(ERROR_CODES.VALIDATION_ERROR, "grant.scopes must contain at least one scope", {
      details: { field: "grant.scopes" }
    });
  }
}

function contextModeCovers(grantMode, requestedMode) {
  return grantMode === requestedMode;
}

function resourceBoundaryCovers(grant, request) {
  if (request.contextMode === CONTEXT_MODES.WORKSPACE) {
    return grant.workspaceBoundary?.boundaryId === request.workspaceBoundary?.boundaryId;
  }

  const requestedResourceId = request.resourceRef?.resourceId;
  if (!requestedResourceId) {
    return false;
  }
  return (
    grant.resourceRef?.provider === request.provider &&
    grant.resourceRef?.provider === request.resourceRef?.provider &&
    grant.resourceRef?.resourceId === requestedResourceId
  );
}

function collectMismatch(mismatches, actual, expected, fieldName) {
  if (actual !== expected) {
    mismatches.push(fieldName);
  }
}
