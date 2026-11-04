# ADR 0002 — Git checkout and external artifact roots

**Status:** Accepted and established in v0.4.4. Recorded: 2026-11-04.

## Context

Copying complete version-numbered project directories caused redundant builds, scattered evidence and unclear source ownership.

## Decision

Use one local Git checkout under `C:\Projects\RecompDev`. Keep binaries, intermediate builds, caches, run logs, evidence, owner catalogues and immutable original ZIPs in separate sibling directories. Track original source SHA manifests in Git. Release tags describe validated workspace combinations; individual component versions move only when that component changes.

## Consequences

Per-plugin builds can run without modifying tracked files. Runtime binary versions must remain immutable and rollback-capable. Git is not an external backup; maintain a separate Git bundle and off-machine copy for disaster recovery.
