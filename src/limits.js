import { DEFAULT_MAX_CONTEXT_BYTES } from "./constants.js";
import { ERROR_CODES, contextError } from "./errors.js";

export function applyContextByteLimit(content, options = {}) {
  const {
    maxBytes = DEFAULT_MAX_CONTEXT_BYTES,
    oversizedBehavior = "truncate",
    rejectionReason = "context content exceeds maxBytes"
  } = options;

  const originalBytes = Buffer.byteLength(content, "utf8");
  if (originalBytes <= maxBytes) {
    return {
      content,
      metadata: {
        truncated: false,
        originalBytes,
        returnedBytes: originalBytes,
        maxBytes
      }
    };
  }

  if (oversizedBehavior === "reject") {
    throw contextError(ERROR_CODES.CONTEXT_TOO_LARGE, rejectionReason, {
      httpStatus: 413,
      details: { originalBytes, maxBytes }
    });
  }

  const truncatedContent = truncateUtf8(content, maxBytes);
  return {
    content: truncatedContent,
    metadata: {
      truncated: true,
      originalBytes,
      returnedBytes: Buffer.byteLength(truncatedContent, "utf8"),
      maxBytes,
      truncationReason: "maxBytes"
    }
  };
}

function truncateUtf8(content, maxBytes) {
  let byteCount = 0;
  let output = "";
  for (const char of content) {
    const charBytes = Buffer.byteLength(char, "utf8");
    if (byteCount + charBytes > maxBytes) {
      break;
    }
    output += char;
    byteCount += charBytes;
  }
  return output;
}
