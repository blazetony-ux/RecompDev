# discovery_integration — independently versioned component

## [0.1.0] - 2026-11-05

- **Changed:** Added a controller-mediated, registry-selected, versioned read-only structural probe, authenticated catalogue inspector, and bounded sector-aware ISO9660 executable/TIM validator using preserved historical providers. No game-specific addressing or CPU instruction lowerer was added.
- **Validation:** Synthetic Mega Drive, Master System, PS-X EXE, 2048/2352 ISO and per-source catalogue tests, negative input/cached-work cases, unchanged native application CTest gates and documentation governance.
- **Compatibility:** `production-workflow` tooling only; no compiled DLL/API changes or frozen historical edits. Existing Shinobi native recovery/monitor flows remain intact and their previous results are not re-qualified by this component.

- **Windows packaging correction (v0.4.9.6 installer WindowsFix1):** The synthetic source-scoping regression now explicitly closes its temporary SQLite fixture connection before `TemporaryDirectory` cleanup. `sqlite3.Connection` used as a context manager only commits or rolls back; it does not close its file handle. This is test-fixture lifecycle only; no production database, provider or controller change. A closed-handle assertion protects against regression on Linux too.
