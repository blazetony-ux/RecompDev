# Sega Master System support

**Status:** Partial production integration; no validated gameplay parity.

The C++ harness loads `rd_machine_sms.dll` from `harness/plugins/machine_sms.cpp`, backed by `harness/systems/mastersystem/runtime.hpp` and SMS hardware adapters. The original preserved Python/native recovery path includes SMS memory maps, banking, VDP, PSG, interrupts and input logic; it does not currently consume the harness DLL as the selected production machine implementation.

Owner Shinobi evidence confirms native recovery reaching a 120-frame budget and recorded VDP/CRAM/PSG activity, but the audio PCM remained silent and captured hardware registers were incomplete. Per-frame counters and final-frame images do not establish independent reference parity. [Hardware gaps](../research/HARDWARE-VALIDATION-GAPS.md) details needed captures.

Required next gate: instrument source hardware state, compare matched emulator observations and prove production plugin replacement without a core rebuild. Cross-game real-ROM validation should include additional titles; synthetic harness tests are only fixture validation.
