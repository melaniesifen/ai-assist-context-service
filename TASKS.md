# Task Breakdown

Update this file as implementation progresses. Check off completed tasks in the same change that implements them.

Canonical cross-repo tasks live in `../ai-assist-architecture/implementation-task-breakdown.md`. This repo owns the context-service portions of `CTX-*`, `SAFE-*`, `OPS-*`, and `REPO-001` items, grounded by `../ai-assist-architecture/lld-context-connectors.md`. Any `SAFE-*`, `OPS-*`, `INFRA-*`, or `E2E-*` item listed here is the context-service-owned slice of that cross-cutting task, not the whole workspace task.

Migration status: The repo has been migrated from the temporary JavaScript ESM bootstrap to Python for the current local package scope. Broad new feature work may continue in Python after the parent migration checkpoint.

## Completed Bootstrap

- [x] REPO-001 bootstrap: create dependency-light Node.js ESM package with direct `node:test` coverage commands.
- [x] CTX-001 repo-local: implement MVP context mode validation for `SELECTION` and `ACTIVE_RESOURCE`.
- [x] CTX-001 repo-local: reject `VISIBLE_REGION`, `WORKSPACE`, and `SCREEN` as deferred modes with typed errors.
- [x] CTX-002 repo-local: validate `ContextConsentGrant` identity, status, expiry, provider, mode, and resource coverage.
- [x] CTX-002 repo-local: allow explicit-user-action `SELECTION` without a persisted grant for MVP.
- [x] CTX-003 repo-local: implement normalized context helpers with provider, resource, mode, content hash, size metadata, provenance, revision, and truncation metadata.
- [x] CTX-004 repo-local: distinguish `client_supplied` from `connector_verified` context and block client-supplied context from write-back eligibility.
- [x] CTX-006 repo-local: cover unsupported mode, missing consent, expired/revoked grant, oversized context, and unsafe write-back eligibility with unit tests.
- [x] OPS-003 bootstrap: keep this domain package free of raw-content logging paths.
- [x] Repo hygiene: document tests and coverage commands, and ignore prompts, feedback, coverage output, dependencies, and build artifacts.
- [x] Repo hygiene: standardize Python package layout to `src/ai_assist_context_service/` with tests in `tests/`.
- [x] Repo hygiene: add `pyproject.toml` package discovery for the `src/` layout.

## Pending Architecture Tasks

- [x] REPO-001: decide final language/runtime, framework, package manager, package layout, migration cost, deployment target, and test strategy for this repo.
- [x] REPO-002: migrate the context-service bootstrap to a Python package layout with equivalent behavior and tests before broad new feature work continues.
- [x] CTX-001: align mode constants and unsupported-mode error shape with versioned shared contracts after `ai-assist-contracts` publishes them.
- [x] CTX-002: add a persistence adapter for `ContextConsentGrants` with tenant-aware lookup, revocation, expiry, and resource/workspace boundary queries.
- [x] M11-T3 / CTX-002: implement Google Docs `ACTIVE_RESOURCE`
  `ContextConsentGrants` persistence using the locked metadata-only shape:
  `grantId`, derived `tenantId`, derived `userId`, provider, `contextMode`,
  `resourceRef`, future-only `workspaceBoundary`, scopes, status, `grantedAt`,
  `revokedAt`, and `expiresAt`.
- [x] M11-T3 / CTX-002: ensure grant lookup authorizes `grantId` or resource
  lookup results against derived tenant/user, provider, context mode, and
  resource ID before connector calls.
- [x] M11-T3 / CTX-002: remove static dogfood consent JSON from the deployed
  normal read/apply path or keep it disabled by default as an owner-only local
  emergency override.
- [x] CTX-002: add adapter-boundary checks that prevent connector calls when consent is missing, revoked, expired, or resource-mismatched.
- [ ] CTX-003: add context preview HTTP or internal-service contract that derives `tenantId` and `userId` from authenticated identity.
- [x] CTX-003: define final truncation/windowing policy for `ACTIVE_RESOURCE` context and expose deterministic metadata for omitted content.
- [x] CTX-004: add contract tests proving write-back proposals require connector-verified resource, revision, anchor/range, and hash metadata.
- [ ] CTX-005: add integration contract tests with `ai-assist-google-docs-adapter` for list/read/verify handoff and normalized connector errors.
- [ ] CTX-005 / E2E-002: add integration tests for context preview using consent validation, Google Docs adapter handoff, and connector-verified normalized context.
- [ ] CTX-006: expand failure coverage for stale resource refs, revoked provider tokens, connector API failures, and user-facing recovery codes.
- [ ] CTX-006 / E2E-005: add operational validation for missing consent, expired/revoked grants, stale resource refs, oversized context, and adapter dependency failures.
- [ ] SAFE-003: document and test that context content remains transient unless stored by the proposed-actions path.
- [x] SAFE-004: add redaction hook interface and deterministic MVP redaction if selected, with no raw redaction output in logs.
- [x] OPS-003: add metadata-only logging adapter rules for future HTTP/internal adapters.
- [ ] OPS-004 / INFRA-004: add deployment pipeline checks for context service config, consent store access, metadata-only logs, metrics, and dependency health.
- [ ] Quality: raise line coverage to at least 95% after adapter boundaries are added.

## Completed M4 Context-Service Slice

- [x] M4 / CTX-001: align MVP context-mode constants and unsupported-mode error code/status/target with shared read-path contracts.
- [x] M4 / CTX-002: verify consent validation for active, missing, revoked, expired, wrong-user, wrong-tenant, wrong-provider, and wrong-resource grants.
- [x] M4 / CTX-002: add an injected read-context boundary that skips connector calls on consent failure.
- [x] M4 / CTX-003: verify normalized `SELECTION` and `ACTIVE_RESOURCE` metadata includes provenance, trust level, revision, content hash, and truncation metadata.
- [x] M4 / CTX-004: verify client-supplied-only context remains ineligible for write-back.

## Completed M7 Context-Service Slice

- [x] M7-T4.3: verify apply-action `SELECTION` and `ACTIVE_RESOURCE` targets require active persisted consent, including missing, revoked, expired, wrong-provider, and wrong-resource failures before mutation.
- [x] M7-T4.4: expose connector-verified write-back target metadata with provider, resource, revision, anchor/range, original-text hash, and no raw context content.
- [x] M7-T4.5: verify client-supplied-only context is rejected as mutation authority.
- [x] M7-T4.6: verify context-service metadata helpers omit raw document/selection content for apply-gate observability.

## Completed M8 Real Connector Context Integration

- [x] M8-T3 / CTX-003: preserve connector revision metadata through context normalization for real Google Docs read handoff.
- [x] M8-T3 / CTX-004: verify connector-verified context remains the only write-back authority and client-supplied content cannot authorize mutation.
- [x] M8-T3 / CTX-005: verify consent validation runs before injected connector reads and connector handoff returns normalized context with real revision metadata.
- [x] M8-T3 / SAFE-003 / OPS-003: verify context-service logging helpers remain metadata-only and do not include raw document or selected text.

## Completed M9 Trusted-User MVP Hardening

- [x] M9-T5 / CTX-002: verify consent and context-mode enforcement remain server-side before connector reads.
- [x] M9-T5 / CTX-003: add an internal deployed-boundary helper that derives tenant/user identity from authenticated server context before consent validation.
- [x] M9-T5 / CTX-004 / SAFE-003: verify connector-verified revision and target metadata remain the only write-back authority and raw context stays out of log metadata.

## Completed M10 Dogfood Runtime Handler

- [x] M10 dogfood / CTX-001 / CTX-003: expose package-level `http_app.handle_http_request` for context-mode dogfood routes with MVP/deferred mode metadata, safe mode validation, no-store responses, and structured dependency/config errors for context preview until deployed consent and connector backing are available.
- [x] M10-T3 / CTX-005 / E2E-002: allow the context-preview HTTP adapter to use an injected connector read dependency after server-derived tenant/user headers and active consent validation, preserving the safe dependency error when deployed connector backing is absent.

## Completed M12 Context Consent Completion

- [x] M12-T6.1 / CTX-002 / CTX-003: expose authenticated
  `POST /resource-sessions/{sessionId}/context-consent` for Google Docs
  `ACTIVE_RESOURCE` consent creation/refresh using server-derived
  `tenantId`, `userId`, and `authSubject`.
- [x] M12-T6.2 / SAFE-003: persist metadata-only active-resource grants through
  the injected `ContextConsentGrantRepository`, ignoring browser-supplied
  tenant/user fields and returning no raw document content, OAuth tokens,
  prompts, model output, screenshots, OCR, accessibility trees, provider keys,
  or action payloads.
- [x] M12-T6.4: add deterministic HTTP-adapter tests for create/refresh,
  missing Google OAuth, missing persistence dependency, server-owned identity,
  and metadata-only consent responses.

## Future Production Tasks

- [ ] CTX-001: add `VISIBLE_REGION` only after client visible-region integration and future readiness gates exist.
- [ ] CTX-002: add `WORKSPACE` consent boundaries, retrieval policy, and stronger rate-limit assumptions.
- [ ] CTX-002 / SAFE-004: add `SCREEN` consent, redaction, and no-retention controls after explicit product readiness.
