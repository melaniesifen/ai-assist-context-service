# AI Assist Context Service

Dependency-light Node.js ESM bootstrap for the context service domain layer.

## MVP Boundary

This package owns pure context-domain behavior:

- Validate MVP context modes: `SELECTION` and `ACTIVE_RESOURCE`.
- Reject deferred modes: `VISIBLE_REGION`, `WORKSPACE`, and `SCREEN`.
- Validate `ContextConsentGrant` shape, status, expiry, tenant/user/provider ownership, and resource coverage.
- Allow `SELECTION` through explicit user action without requiring a persisted grant in MVP.
- Normalize context records with content hashes, provenance, trust level, anchors, resource revision, capture time, and expiry.
- Classify context as client-supplied or connector-verified.
- Enforce that write-back requires connector-verified revision plus anchor or range metadata.
- Truncate oversized context when safe, or reject it with `CONTEXT_TOO_LARGE`.
- Optionally apply deterministic MVP redaction before hashing and byte-limit checks.
- Build metadata-only log records that exclude raw context content and provenance details.

The service does not own product authentication, connector API calls, model calls, prompt assembly, proposed action persistence, or document write-back.

## Privacy Rules

The domain helpers return raw `content` to orchestration, but the package does not log content. Callers should log only metadata such as request IDs, context mode, provider, content byte counts, truncation state, and typed error codes.

Use `buildContextLogMetadata` when an adapter needs context observability fields. It intentionally omits `content` and full provenance. Use `redactionPolicy: REDACTION_POLICIES.MVP_DEFAULT` with `normalizeContext` when MVP deterministic redaction is selected for a context path.

## Future API Adapters

HTTP or queue adapters should wrap this domain layer later. Those adapters should:

- Derive `tenantId` and `userId` from authenticated server-side identity.
- Load grants from the consent store before connector calls.
- Call connector adapters only after mode and consent validation pass.
- Map `ContextServiceError` to the shared platform error envelope.
- Keep raw content out of logs and long-term persistence.

## Task Breakdown

Implementation tasks are tracked in [TASKS.md](TASKS.md). Update the checkboxes there in the same change that implements or verifies a task.

## Testing And Coverage

Run the unit tests with either command:

```sh
node --test
npm test
```

View the built-in coverage report in the terminal:

```sh
node --experimental-test-coverage --test
npm run coverage
```

The coverage command uses Node's built-in test runner and prints a text report. If later tooling writes HTML, LCOV, TAP, JUnit, or build output, those generated paths are ignored by `.gitignore`.
