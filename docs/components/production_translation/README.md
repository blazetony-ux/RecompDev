# Production translation — preserved native generator adapter

**Scope:** `production-workflow`. **Component:** `production_translation` in `workspace/components.json`. **Initial version:** 0.1.0. This is Python source tooling, not a new Z80 DLL or translation rewrite.

## Actual execution boundary

`modular/plugins/legacy.py` now starts `production_translation/run_recovery.py` for `legacy.recovery` subprocesses. The runner verifies the selected provider source SHA-256 and the original `nativepilot/generator.py` hash against `production_translation/providers.json`, injects the provider's `generate_project` callable into the frozen `nativecore.continuous_recovery_v0436` module **within the child process only**, and then executes the entire unchanged original `tools/Run-Continuous-Recovery-v0445.py` runner.

The default provider `preserved-pcode` at `production_translation/providers/preserved_pcode.py` simply delegates to `nativepilot.generator.generate_project` with every original argument. All original supported P-code operations, bank overlays, source attestation, C++ generation, compilation, hardware runtime, coverage cache and reset/replay remain present. Do not replace this with the small synthetic Z80 DLL interpreter.

The selected provider version, SHA-256, preserved generator hash and actual invocation counts are written to `production-translation.json` in each recovery round and exposed by the bounded recovery summary. The run provenance also records the selection. Changing an admitted provider requires a new component release and reviewed hash update. A missing, corrupt or unregistered provider refuses execution rather than silently pretending that a rewrite succeeded.

## Explicit rollback / original execution

Set `RECOMPDEV_TRANSLATOR_MODE=legacy-direct` in the calling process to invoke the exact original runner without the translation adapter. The default is `preserved-plugin`. This choice does not change the CPU source admission gate (`--cpu-plugin required`) or the native translator implementation. The frozen source files stay unchanged; there are **no new compiled C++ components** in this release.

## Acceptance evidence / limits

`python -B -m unittest production_translation.tests -v` compares generated files byte-for-byte for an authenticated synthetic fixture, verifies SHA blocking and provider selection, and executes bounded real native compilation with and without the adapter. It does **not** establish the user's earlier 600-frame Shinobi claim or independent gameplay parity. A same-ROM, same-input 600-frame regression against authentic preserved evidence is still required. The provider abstraction is presently a Python subprocess-level seam, not a native C ABI CPU translator plugin.
