# rd_game_recomp_v0445 — component contract

**Status:** harness; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Synthetic example native-code module generated using original P-code bridge.

## Source and interface

`harness/generated/rd_game_recomp_v0445.cpp; harness/include/rd_pcode_bridge.hpp`. **Build target:** `rd_game_recomp_v0445`. Component kind: `compiled-plugin`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Fixture parity does not establish whole-ROM translation. Baseline tests: `production_pcode_hybrid_parity; production_pcode_native_one`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).
