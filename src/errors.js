export class ContextServiceError extends Error {
  constructor(code, message, { httpStatus = 400, details = {}, retryable = false } = {}) {
    super(message);
    this.name = "ContextServiceError";
    this.code = code;
    this.httpStatus = httpStatus;
    this.details = details;
    this.retryable = retryable;
  }
}

export const ERROR_CODES = Object.freeze({
  VALIDATION_ERROR: "VALIDATION_ERROR",
  CONTEXT_MODE_UNSUPPORTED: "CONTEXT_MODE_UNSUPPORTED",
  CONSENT_REQUIRED: "CONSENT_REQUIRED",
  CONSENT_DENIED: "CONSENT_DENIED",
  CONTEXT_TOO_LARGE: "CONTEXT_TOO_LARGE",
  CONNECTOR_VERIFICATION_REQUIRED: "CONNECTOR_VERIFICATION_REQUIRED"
});

export function contextError(code, message, options) {
  return new ContextServiceError(code, message, options);
}

export function isContextServiceError(error) {
  return error instanceof ContextServiceError;
}
