# Task Breakdown

Update this file as implementation progresses. Check off completed tasks in the same change that implements them.

Canonical cross-repo tasks live in `../ai-assist-architecture/implementation-task-breakdown.md`. This repo owns the context-service portions of `CTX-*`, `SAFE-*`, `OPS-*`, and `REPO-001` items, grounded by `../ai-assist-architecture/lld-context-connectors.md`.

Migration gate: The approved direction is to migrate this repo from the temporary JavaScript ESM bootstrap to Python. Do not continue broad new feature work until that migration is completed or explicitly deferred.

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

## Pending Architecture Tasks

- [ ] REPO-001: decide final language/runtime, framework, package manager, package layout, migration cost, deployment target, and test strategy for this repo.
- [x] REPO-002: migrate the context-service bootstrap to a Python package layout with equivalent behavior and tests before broad new feature work continues.
- [ ] CTX-001: align mode constants and unsupported-mode error shape with versioned shared contracts after `ai-assist-contracts` publishes them.
- [ ] CTX-002: add a persistence adapter for `ContextConsentGrants` with tenant-aware lookup, revocation, expiry, and resource/workspace boundary queries.
- [ ] CTX-002: add adapter-boundary checks that prevent connector calls when consent is missing, revoked, expired, or resource-mismatched.
- [ ] CTX-003: add context preview HTTP or internal-service contract that derives `tenantId` and `userId` from authenticated identity.
- [ ] CTX-003: define final truncation/windowing policy for `ACTIVE_RESOURCE` context and expose deterministic metadata for omitted content.
- [ ] CTX-004: add contract tests proving write-back proposals require connector-verified resource, revision, anchor/range, and hash metadata.
- [ ] CTX-005: add integration contract tests with `ai-assist-google-docs-adapter` for list/read/verify handoff and normalized connector errors.
- [ ] CTX-005 / E2E-002: add integration tests for context preview using consent validation, Google Docs adapter handoff, and connector-verified normalized context.
- [ ] CTX-006: expand failure coverage for stale resource refs, revoked provider tokens, connector API failures, and user-facing recovery codes.
- [ ] CTX-006 / E2E-005: add operational validation for missing consent, expired/revoked grants, stale resource refs, oversized context, and adapter dependency failures.
- [ ] SAFE-003: document and test that context content remains transient unless stored by the proposed-actions path.
- [x] SAFE-004: add redaction hook interface and deterministic MVP redaction if selected, with no raw redaction output in logs.
- [x] OPS-003: add metadata-only logging adapter rules for future HTTP/internal adapters.
- [ ] OPS-004 / INFRA-004: add deployment pipeline checks for context service config, consent store access, metadata-only logs, metrics, and dependency health.
- [ ] Quality: raise line coverage to at least 95% after adapter boundaries are added.

## Future Production Tasks

- [ ] CTX-001: add `VISIBLE_REGION` only after client visible-region integration and future readiness gates exist.
- [ ] CTX-002: add `WORKSPACE` consent boundaries, retrieval policy, and stronger rate-limit assumptions.
- [ ] CTX-002 / SAFE-004: add `SCREEN` consent, redaction, and no-retention controls after explicit product readiness.
