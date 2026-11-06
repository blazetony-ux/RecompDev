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

## v0.4.9.7 candidate interface (0.4.5)

Native C++ `--stage discover` plugin loading and report generation; legacy discovery available via an explicit compatibility stage. The authoritative registry is `workspace/components.json`; use the ABI declarations in `harness/include/rd_native_discovery_v1.h`. Changed native controller and added a strict, versioned format discovery ABI; existing Python prepare/recover workflow remains transitional. No Shinobi-specific logic is introduced; independently measured gameplay parity remains unverified.

## v0.4.6 native migration (workspace/v0.4.9.9)

Shared compiled native game runner moved into controller; executes preserved P-code game DLL with strict full-source identity and no Python execution for native-execute. Existing prepare/recover remain transitional. See [the release](../../releases/v0.4.9.9.md) for what still uses Python and for test limitations. No title-specific workarounds or production gameplay-parity claim.
