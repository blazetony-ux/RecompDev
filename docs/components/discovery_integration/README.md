# Discovery integration — v0.1.0

- **Registry:** `workspace/components.json` (`discovery_integration`)
- **Scope:** `production-workflow`
- **Controller contract:** `recompdev.controller.discovery.v1`
- **Provider registry:** `discovery_integration/providers.json` (`recompdev.discovery.provider-registry.v1`). The controller loads independently replaceable, version-checked `structure`, `catalogue` and `disc` providers through a stable `run(context)` interface, with no CPU-specific imports or game identification in the controller. Provider modules must be installed under the trusted discovery-integration package namespace.

The compiled RecompDev entry point already runs `modular.controller.run_rom`. After successful preserved discovery, that controller now calls the optional read-only `discovery_integration.bridge.audit` and writes `discovery-integration/universal-discovery.json` into the same immutable evidence folder. `controller-report.json` contains a brief `discovery_audit` summary; the independent execution monitor and CPU/hardware plugins do not call these providers.

The legacy scheduler is NOT source-scoped, so `legacy_run_tasks_executed` must not be interpreted as newly analysed work for the requested ROM. A zero count is explicitly `NO_NEW_LEGACY_TASKS_EXECUTED`; outstanding cached tasks are reported by authenticated source ID with their reasons. Large images retain the legacy **provisional sampled** identity, which is not a full SHA-256 authenticity guarantee. `DISCOVERY_COMPLETE` remains a legacy workflow status; the new `coverage_status` qualifies it.

For discs the provider uses the preserved ISO9660 reader to inspect logical files through 2048/2352-byte sectors, validating only actual PS-X EXE or TIM structures. Other compressed/game-specific formats are NOT decoded. Candidate file bytes are never put into the upload-ready evidence ZIP. Optional direct extraction is enabled only by `python -m discovery_integration.cli --source FILE --working-catalogue WORKING.sqlite --discovery-report DISCOVERY.json --output NEW_DIR --export-candidates`, where explicit local output is required. Output must be distinct and not in historical source or catalogue paths. No original ROM/disc is copied or altered; exported candidate bytes are for owner-local analysis, not automatic distribution.

No native 68000 or MIPS plugin is installed by this change, and no native gameplay parity or ROM independence is claimed. ROM identity and correctness still require separate verification.
