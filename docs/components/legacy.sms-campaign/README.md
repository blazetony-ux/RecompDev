# legacy.sms-campaign — component contract

**Status:** production-workflow; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Original multi-ROM Master System campaign runner.

## Source and interface

`legacy/RecompDev-v0.4.0.45/tools/Run-SMS-Campaign-v0445.py`. **Build target:** None (service/tooling). Component kind: `legacy-service`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

An invoked campaign is not evidence that all ROMs or gameplay passed. Baseline tests: `migration_legacy_regressions`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).
