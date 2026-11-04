# rd_game_fixture — component contract

**Status:** harness; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Hardcoded native instruction fixture with source-byte checking.

## Source and interface

`harness/plugins/game_fixture.cpp`. **Build target:** `rd_game_fixture`. Component kind: `compiled-plugin`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Synthetic instructions, not a game conversion or production output. Baseline tests: `native_only_single_block; compiled_byte_mismatch_rejected`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).
