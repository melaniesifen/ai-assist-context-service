import { assertNonEmptyString } from "./validation.js";

export const REDACTION_POLICIES = Object.freeze({
  NONE: "none",
  MVP_DEFAULT: "mvp_default"
});

const DEFAULT_REDACTION_RULES = Object.freeze([
  {
    id: "email_address",
    pattern: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/giu,
    replacement: "<redacted:email_address>"
  },
  {
    id: "api_key_like_secret",
    pattern: /\b(?:sk|pk|api|token|secret)[_-][A-Za-z0-9_-]{16,}\b/gu,
    replacement: "<redacted:secret>"
  },
  {
    id: "bearer_token",
    pattern: /\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b/giu,
    replacement: "Bearer <redacted:token>"
  }
]);

export function applyContextRedaction(content, options = {}) {
  assertNonEmptyString(content, "content");
  const policy = options.policy ?? REDACTION_POLICIES.NONE;

  if (policy === REDACTION_POLICIES.NONE) {
    return {
      content,
      metadata: {
        policy,
        redacted: false,
        rulesApplied: []
      }
    };
  }

  if (policy !== REDACTION_POLICIES.MVP_DEFAULT) {
    throw new TypeError(`Unsupported redaction policy: ${policy}`);
  }

  const rules = options.rules ?? DEFAULT_REDACTION_RULES;
  let redactedContent = content;
  const rulesApplied = [];

  for (const rule of rules) {
    const nextContent = redactedContent.replace(rule.pattern, rule.replacement);
    if (nextContent !== redactedContent) {
      rulesApplied.push(rule.id);
      redactedContent = nextContent;
    }
  }

  return {
    content: redactedContent,
    metadata: {
      policy,
      redacted: rulesApplied.length > 0,
      rulesApplied
    }
  };
}
