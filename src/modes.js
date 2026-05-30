import { CONTEXT_MODES, MVP_CONTEXT_MODES } from "./constants.js";
import { ERROR_CODES, contextError } from "./errors.js";

export function validateContextMode(contextMode) {
  const allowedModes = Object.values(CONTEXT_MODES);
  if (!allowedModes.includes(contextMode)) {
    throw contextError(ERROR_CODES.VALIDATION_ERROR, "contextMode is not recognized", {
      details: { field: "contextMode", allowedModes }
    });
  }

  if (!MVP_CONTEXT_MODES.includes(contextMode)) {
    throw contextError(ERROR_CODES.CONTEXT_MODE_UNSUPPORTED, "contextMode is not supported in MVP", {
      httpStatus: 422,
      details: { contextMode, supportedModes: MVP_CONTEXT_MODES }
    });
  }

  return contextMode;
}

export function isMvpContextMode(contextMode) {
  return MVP_CONTEXT_MODES.includes(contextMode);
}
