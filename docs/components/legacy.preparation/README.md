# legacy.preparation — component contract

**Status:** production-workflow; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Original Ghidra/native preparation and authenticated function recovery.

## Source and interface

`legacy/RecompDev-v0.4.0.45/nativeprep/engine.py`. **Build target:** None (service/tooling). Component kind: `legacy-service`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Requires Ghidra for fresh real-ROM native function preparation. Source is frozen. Baseline tests: `v041_test_real_native_preparation_reports_missing_ghidra`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).
