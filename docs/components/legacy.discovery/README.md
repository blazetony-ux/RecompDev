# legacy.discovery — component contract

**Status:** production-workflow; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Original discovery.engine analysis via the preserved Python adapter.

## Source and interface

`legacy/RecompDev-v0.4.0.45/discovery/engine.py; modular/plugins/legacy.py`. **Build target:** None (service/tooling). Component kind: `legacy-service`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Production adapter, not a loadable C++ DLL. Original source is frozen. Baseline tests: `migration_production_bridge; v041_test_real_original_discovery_parity`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).
