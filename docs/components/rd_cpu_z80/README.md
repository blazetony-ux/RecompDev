# rd_cpu_z80 — component contract

**Status:** harness; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Small Z80 interpreter with explicit unsupported-opcode failure for synthetic harness fixtures.

## Source and interface

`harness/plugins/cpu_z80.cpp; harness/include/rd_plugin.h`. **Build target:** `rd_cpu_z80`. Component kind: `compiled-plugin`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Not a complete Z80 interpreter; not used in production Shinobi translation. Baseline tests: `unsupported_opcode_rejected; hybrid_main_parity; native_only_single_block`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).

## Production source-admission ABI, v0.2.0

Alongside the unchanged harness interpreter, this DLL now exports `rd_z80_source_gate_v1` from the C contract at `harness/include/rd_production_cpu_v1.h`. The production bridge invokes it on physically attested instruction bytes before frozen native code generation. The selected DLL identity is pinned by version and SHA-256; unknown IX/IY-prefixed lengths are reported as not independently verified. **This is not execution through `rd_cpu_z80`** and does not establish whole-game semantic correctness. See the [bridge component](../production_cpu_bridge/README.md).
