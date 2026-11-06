# workspace_governance — component contract

**Status:** workspace; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Git-managed documentation structure, changelog checks and release gates.

## Source and interface

`workspace/manager.py; workspace/docs_governance.py; tools/apply_workspace_docs.py`. **Build target:** None (service/tooling). Component kind: `tooling`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Changes release tooling only; no native binary is installed or rebuilt. Baseline tests: `workspace.tests.test_docs_governance; v044_workspace_contract`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).

## Coordinated bridge migration, v0.1.1

Source ownership in `workspace/manager.py` now recognises the independent `production_cpu_bridge` component, the Z80 gate C header, and the production gate regression suite. Routine plugin updates must continue to respect component boundaries; the one-time v0.4.6 patch spans components deliberately and has its own transactional source update and validation gate. All build outputs, runtime DLLs and evidence remain outside the Git checkout.

## v0.4.9.7 candidate interface (0.1.4)

Mandatory binding development contract, approved pre-build report and handover/release acknowledgement. The authoritative registry is `workspace/components.json`; use the ABI declarations in `harness/include/rd_native_discovery_v1.h`. New policy omissions automatically fail documentation governance; no ROM or binary modifications. No Shinobi-specific logic is introduced; independently measured gameplay parity remains unverified.
