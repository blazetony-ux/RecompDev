# rd_translation_pcode — native source-attested P-code lowering DLL

**Scope:** `production-translation`. **Version:** `0.3.0`. Declared in `workspace/components.json`, with independent [component changelog](CHANGELOG.md). Compiled target: `rd_translation_pcode.dll` on Windows (Linux `.so` for development). 

## Responsibility and architecture

Independent versioned `RD_TranslationRequestV1` / `RD_TranslationResultV1` ABI defined by `translation_pcode/include/rd_translation_v1.h`. The compiled `RecompDev.exe` loads it using the selected runtime DLL directory; there is no game-title or ROM-hash special case. It accepts a base source-attested Ghidra `recomp-function-pcode-v1` JSON export plus optional Ghidra bank-function exports from the same ROM/source ID; each instruction's recorded physical ROM bytes and SHA-256 must match original source before native lowering. The translated code is linked to **maintained active runtime and presentation DLLs** via `runtime_sms/templates` rather than copying frozen runtime sources. The frozen originals remain reference-only.

## Outputs

Default full-runtime backend emits source-bound `translated.cpp`, a generated nativepilot CMake project, `RecompDevNativePilot` and `RecompDevNativeApp` in an external evidence/build directory. A separate `--backend game-dll` mode creates `rd_game_pcode.dll`, loadable by the compiled controller's previously migrated `--stage native-execute` pipeline. The DLL itself performs P-code to C++ lowering, not a compatibility call to Python. New compiled binaries still require the matching original ROM at execution for source verification.

### Example (PowerShell, one line)

`& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' --stage native-translate --rom 'C:
oms\MASTERSYSTEM\<your-rom>.sms' --export 'C:\Projects\RecompDev-Evidence\<existing-base-ghidra-export>.json' --history-root 'C:\Projects\RecompDev-Evidence'`

Use a genuine Ghidra export from the *same* ROM. `--history-root` is optional, read-only and scans only bounded preexisting `bank-functions.json` files; the DLL independently verifies their provenance and every candidate instruction. For the unit-test synthetic export only, `--allow-synthetic-export` opts out of Ghidra-origin admission. `--out` sets a custom output folder; otherwise output goes under the versioned `v0.4.9.10/native-translate` evidence root. `--no-compile` creates source only; test fixtures also accept `--plugin-dir`, and `--source-root` points to the installed Git checkout if a runtime source-pointer is missing.

## Scope exclusions and acceptance

No Ghidra analysis/discovery, dynamic execution-gap recovery, complete instruction/varnode parity or full historic 1,800-frame Shinobi equivalence is claimed. The old Ghidra analysis and recovery services remain transitional; generated SMS machine state is now a standalone DLL, but the C++ `rd::State` ABI is not yet a universal machine-plugin protocol. The approved next acceptance gate is real Shinobi Ghidra export -> fresh native compile -> deterministic frame/guest-state comparison plus one second Master System game. Until then release functional parity is **BLOCKED**. Test: `v04910_native_pcode_translation_compile_execute`, including output comparison against the frozen Python generator; see [release documentation](../../releases/v0.4.9.10.md).

## v0.4.9.10 maintained-runtime cutover (0.3.0)

The newly generated full native project uses `runtime_sms/templates` and its CMake build links independent SMS state/video/host DLL targets. It **does not** compile or copy the frozen original runtime. This is a source dependency migration, not evidence of equivalent 1,800-frame Shinobi graphics, control or generic machine-ABI parity; verification remains blocked. See [runtime component](../rd_sms_native_runtime/README.md) and [candidate release](../../releases/v0.4.9.10.md).
