# Current runtime architecture and data flow

**Status:** Current implementation; not the completed plugin target.

## Real ROM processing (production)

`RecompDev.exe` (compiled controller) → `modular/cli.py` and `modular/controller.py` → registered `legacy.discovery` (`discovery.engine`) → `legacy.preparation` (`nativeprep.engine`, using Ghidra when available) → `legacy.recovery` (`tools/Run-Continuous-Recovery-v0445.py` and preserved native recovery engines). Native C++ is generated and compiled in the preserved workflow; missing code can be recovered with verified source bytes and replayed until a bounded stop condition.

The real pipeline reads the user's ROM without copying it and snapshots the owner catalogue into isolated working data. It writes evidence to the external evidence root. The original `legacy/RecompDev-v0.4.0.45` source is not modified.

## Compiled harness (separate)

`RecompDevHarness.exe` → `rd_cpu_z80.dll` or selected CPU → `rd_machine_sms.dll` or `rd_machine_synthetic.dll` → optional `rd_game_*`, display/audio/input and discovery DLLs. Their API is declared in `harness/include/rd_plugin.h` with `rd_get_plugin_v1` and an ABI version. This proves loader and fixture behaviour but does not automatically change the Python native recovery service.

## Target architecture (planned)

Controller → versioned source/CPU and machine contracts → translator/code generator → host compiler → generated game module; system memory/device/IRQ APIs remain separate and swappable. Each release must say whether it is harness-only, production adapter, or production plugin.

## Evidence and replay

Versioned evidence contains per-run manifests, recovery reports, hardware captures, working catalogue snapshots and upload ZIPs. Cache artifacts may be invalidated; historical run evidence should not be erased when cache is cleaned. GPU/PSG and cycle parity require independent reference traces; the current hardware counters alone are insufficient.
