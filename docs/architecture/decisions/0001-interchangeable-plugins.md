# ADR 0001 — Interchangeable plugins and preserved legacy code

**Status:** Accepted architectural direction, partial implementation. Recorded: 2026-11-04.

## Context

Earlier recovery work disproportionately concentrated on the Sega Master System/Z80 path. The project must support multiple CPUs and machines without continually changing the orchestration layer. Working Ghidra/discovery/native-recovery findings must not be discarded during migration.

## Decision

Keep one generic controller, with independently replaceable CPU, machine, translator and hardware modules. Preserve the original production services behind explicit adapters while gradually moving their responsibilities behind genuinely swappable, versioned contracts. Use explicit source SHA-256 provenance and independent parity checks.

## Consequences

The current C++ DLL harness is not sufficient evidence of production interchangeability. The next gate requires a real-ROM production execution demonstrating selected plugin usage and safe rollback, without modifying the original 642 files.
