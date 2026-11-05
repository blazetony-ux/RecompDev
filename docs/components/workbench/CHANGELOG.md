# Workbench — independent changelog

## [0.1.0] - 2026-11-04

- **Changed:** Restored a standalone developer Workbench as a local read-only SQLite catalogue web service with table navigation, schema inspection, bounded row browsing, limited column filtering and fixed JSON endpoints. Added a one-step PowerShell launcher and external log directory.
- **Validation:** Real SQLite fixture tests verify 403 token checks, rejected POST requests, SQL read-only enforcement, escaped HTML against embedded script text, limited result pagination, blob summaries and unchanged database SHA-256 after each request.
- **Compatibility:** No existing Workbench code, owner catalogue, production recovery service, controller executable or C++ DLL was modified or rebuilt for this component. The historical Workbench remains untouched inside frozen legacy sources.
