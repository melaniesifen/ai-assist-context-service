# AGENTS.md

## Repo Purpose

`ai-assist-context-service` owns context mode validation, `ContextConsentGrants`, normalized context shape, provenance, trust classification, truncation, and redaction hooks. The current implementation is a dependency-free Python package using only the standard library.

## Agent Instructions

- Read `README.md`, `ai-assist-platform-context.md`, and `../ai-assist-architecture/lld-context-connectors.md` before changing behavior.
- Do not add undeclared Python dependencies. If a future slice needs libraries or tooling, add repo-local manifests such as `pyproject.toml` or requirements files and document install/test commands.
- MVP supports `SELECTION` and `ACTIVE_RESOURCE`; `VISIBLE_REGION`, `WORKSPACE`, and `SCREEN` are future modes.
- Enforce consent before connector calls for modes that require grants.
- Mark context as `client_supplied` or `connector_verified`. Client-supplied content may inform the model but cannot authorize write-back.
- Do not log raw selected text, document text, prompts, screenshots, OCR, accessibility trees, provider keys, or OAuth tokens.
- Add tests for missing consent, expired/revoked grants, unsupported modes, oversized context, provenance fields, and write-back eligibility.
- Keep tests split by source responsibility where practical; put reused fixtures, fake clients, and assertion helpers in `tests/common.py`.

## Commands

- Run tests with `PYTHONPATH=src python3 -m unittest discover -s tests`.
- Run compile checks with `PYTHONPATH=src python3 -m compileall src tests`.
- No package install step is required for the current stdlib-only package.

## Review Notes

Before committing, review whether any new path lets unverified client content become mutation authority or bypasses mode/consent enforcement.

## Commit Messages

All commits in this repo must use this format:

```text
docs/feat/fix/(or another appropriate type): title of change

problem: <description of problem>
solution: <description of solution>
impact: <impact of this change>
reference: <reference to this change in the docs if applicable>
```
