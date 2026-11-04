# controller — component contract

**Status:** production-entrypoint; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Compiled command entry point; runs workspace manager commands and preserved Python orchestration.

## Source and interface

`controller/main.cpp; modular/cli.py; modular/controller.py`. **Build target:** `RecompDev`. Component kind: `controller`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Not a replacement for individual native recovery services; changing controller governance code does not imply a new compiled EXE. Baseline tests: `v042_compiled_controller_version; v042_compiled_controller_registry; v042_compiled_controller_e2e`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).
