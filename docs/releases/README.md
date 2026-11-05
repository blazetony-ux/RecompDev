# Workspace release notes and provenance

**Status:** Current release catalogue. Workspace releases identify tested source and documentation combinations, not necessarily new controller binaries.

- [v0.4.9 — Input-driven native recovery](v0.4.9.md)
- [v0.4.8 — Independent generic native runtime host](v0.4.8.md)
- [v0.4.7 — Full production translation adapter + Workbench](v0.4.7.md)
- [v0.4.6 — Production CPU admission bridge](v0.4.6.md)
- [v0.4.5 — Documentation and governance](v0.4.5.md)
- [v0.4.4 — Initial Git-managed workspace](../history/v0.4.4/WORKSPACE-v0.4.4.md)
- [Historical source provenance](provenance/README.md)
- [Historical validation reports](validation/README.md)

Release claims must distinguish cross-platform CI/local tests, owner Windows logs, and gaps requiring real-ROM parity. Compiled component changelogs are indexed under [components](../components/README.md). Runtime logs and evidence ZIPs belong outside the Git source checkout.

- [v0.4.9.1 — Recovery short-build fix](v0.4.9.1.md): external build paths, history reuse and compile-failure safety.

- [v0.4.9.3 — Movement correctness instrumentation](v0.4.9.3.md): guest controller readbacks, scroll/SAT diagnostics and opt-in evidence capture.

- [v0.4.9.4 — Generic state observation](v0.4.9.4.md): reusable memory-region telemetry through replaceable providers.
