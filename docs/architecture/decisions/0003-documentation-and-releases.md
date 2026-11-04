# ADR 0003 — Meaningful documentation and release gates

**Status:** Accepted and implemented by the v0.4.5 workspace update. Recorded: 2026-11-04.

## Context

Old instructions, release provenance and current architectural direction were scattered at repository root, making handovers unreliable. Automatically bumping unrelated component versions would defeat independent development.

## Decision

Authoritative Markdown documentation belongs under `docs/`, with a short root README and workspace CHANGELOG. Retain superseded content under `docs/history/`; never rewrite preserved `legacy/` or `baselines/` material. Each updated component must have its own meaningful changelog entry. Release tooling checks the documentation index, file references and version alignment before a Git commit or workspace tag.

## Consequences

Documentation-only releases may create a new workspace tag and a versioned governance-tool change without recompiling the controller or unrelated DLLs. A source release must distinguish build/test observations from unproven hardware parity and state the next blocking gap.
