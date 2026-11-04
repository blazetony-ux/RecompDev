# rd_game_probe — component contract

**Status:** harness; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Nontranslating probe-only game module for harness ROM exploration.

## Source and interface

`harness/plugins/game_probe.cpp`. **Build target:** `rd_game_probe`. Component kind: `compiled-plugin`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Returns no native code blocks; must never be counted as a complete converter. Baseline tests: `real_rom_probe_sidecar`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).
