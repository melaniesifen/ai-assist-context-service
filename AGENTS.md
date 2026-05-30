# AGENTS.md

## Repo Purpose

`ai-assist-context-service` owns context mode validation, `ContextConsentGrants`, normalized context shape, provenance, trust classification, truncation, and redaction hooks.

## Agent Instructions

- Read `README.md`, `ai-assist-platform-context.md`, and `../ai-assist-architecture/lld-context-connectors.md` before changing behavior.
- MVP supports `SELECTION` and `ACTIVE_RESOURCE`; `VISIBLE_REGION`, `WORKSPACE`, and `SCREEN` are future modes.
- Enforce consent before connector calls for modes that require grants.
- Mark context as `client_supplied` or `connector_verified`. Client-supplied content may inform the model but cannot authorize write-back.
- Do not log raw selected text, document text, prompts, screenshots, OCR, accessibility trees, provider keys, or OAuth tokens.
- Add tests for missing consent, expired/revoked grants, unsupported modes, oversized context, provenance fields, and write-back eligibility.

## Commands

- Run tests with `node --test`.
- `npm` may not be available in this environment; prefer the direct Node command.

## Review Notes

Before committing, review whether any new path lets unverified client content become mutation authority or bypasses mode/consent enforcement.
