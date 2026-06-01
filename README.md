# AI Assist Context Service

Stdlib-only Python package for the context service domain layer.

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

Use `build_context_log_metadata` when an adapter needs context observability fields. It intentionally omits `content` and full provenance. Use `{"redactionPolicy": REDACTION_POLICIES["MVP_DEFAULT"]}` with `normalize_context` when MVP deterministic redaction is selected for a context path.

```python
from ai_assist_context_service import (
    REDACTION_POLICIES,
    build_context_log_metadata,
    normalize_context,
)

context = normalize_context(
    input_value,
    {"redactionPolicy": REDACTION_POLICIES["MVP_DEFAULT"]},
)
metadata = build_context_log_metadata(context)
```

## Runtime And Dependencies

The current package uses Python standard library modules only. Runtime code
lives under `src/ai_assist_context_service/`, with tests under `tests/`.
`pyproject.toml` documents the package name and `src/` package discovery without
adding runtime dependencies. Add repo-local dependency/tooling manifests before
adding libraries, package managers, formatters, coverage tools, HTTP frameworks,
or deployment tooling.

## Future API Adapters

HTTP or queue adapters should wrap this domain layer later. Those adapters should:

- Derive `tenantId` and `userId` from authenticated server-side identity.
- Load grants from the consent store before connector calls.
- Call connector adapters only after mode and consent validation pass.
- Map `ContextServiceError` to the shared platform error envelope.
- Keep raw content out of logs and long-term persistence.

## Task Breakdown

Implementation tasks are tracked in [TASKS.md](TASKS.md). Update the checkboxes there in the same change that implements or verifies a task.

## Testing

Run the unit tests with the stdlib test runner:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

Compile the package and tests with:

```sh
PYTHONPATH=src python3 -m compileall src tests
```

Coverage tooling is deferred until a repo-local Python tooling decision is made.
If later tooling writes virtualenvs, caches, HTML, LCOV, JUnit, build, or
distribution output, those generated paths are ignored by `.gitignore`.
