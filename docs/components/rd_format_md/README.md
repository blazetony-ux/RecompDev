# rd_format_md — native format discovery plugin

**Status:** `harness` independent compiled-plugin candidate v0.1.0; authoritative component registry: `workspace/components.json`.

## Responsibility and ABI

Mega Drive cartridge structure. Checks SEGA header and plausible 68000 reset vector, explicitly blocking malformed entry geometry. Owns no controller, CPU execution or rendering logic.

Source: `harness/plugins/format_md.cpp`. Built as `rd_format_md.dll` on Windows using the native structural format ABI `harness/include/rd_native_discovery_v1.h`, loaded by the compiled `RecompDev.exe`. The plugin exports `rd_get_plugin_v1` with kind `RD_FORMAT_KIND` and a `RD_FormatApiV1` callback; bad plugin kinds and API sizes are rejected.

## Evidence and limits

Source bytes are read-only; results are only structural candidates. Synthetic fixtures exercise the same plugin interface across CPU families. Real-game executable semantics, Ghidra analysis, translation, native generation and parity remain separate unqualified milestones. `workspace/components.json` owns the active version, and the [changelog](CHANGELOG.md) records all changes.
