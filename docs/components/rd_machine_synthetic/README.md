# rd_machine_synthetic — component contract

**Status:** harness; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Independent synthetic memory/bus/mapping machine to test interchangeability.

## Source and interface

`harness/plugins/machine_synthetic.cpp`. **Build target:** `rd_machine_synthetic`. Component kind: `compiled-plugin`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

A test substitute, not an actual console hardware implementation. Baseline tests: `alternate_machine_parity; production_pcode_alternate_machine`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).
