import { ERROR_CODES, contextError } from "./errors.js";

export function assertPlainObject(value, fieldName) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw contextError(ERROR_CODES.VALIDATION_ERROR, `${fieldName} must be an object`, {
      details: { field: fieldName }
    });
  }
}

export function assertNonEmptyString(value, fieldName) {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw contextError(ERROR_CODES.VALIDATION_ERROR, `${fieldName} must be a non-empty string`, {
      details: { field: fieldName }
    });
  }
}

export function optionalNonEmptyString(value, fieldName) {
  if (value === undefined || value === null) {
    return;
  }
  assertNonEmptyString(value, fieldName);
}

export function assertDateLike(value, fieldName) {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    throw contextError(ERROR_CODES.VALIDATION_ERROR, `${fieldName} must be an ISO-8601 timestamp`, {
      details: { field: fieldName }
    });
  }
}

export function toDate(value, fieldName) {
  assertDateLike(value, fieldName);
  return new Date(value);
}
