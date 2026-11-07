# rd_sms_native_runtime — maintained SMS execution-state DLL

**Scope:** `production-machine-runtime`. **Version:** `0.1.1`. Target: `rd_sms_native_runtime` (`.dll` on Windows). See `workspace/components.json` and [changelog](CHANGELOG.md) for the authoritative registry and component version.

This maintained implementation of the previous SMS native machine-state logic now lives in `runtime_sms/include/runtime.hpp`, `runtime_sms/src/runtime.cpp` and the copied-and-maintained CPU-neutral hardware contracts in `runtime_sms/include/hardware/`. It contains ROM/mapper, registers, RAM/VRAM/CRAM, interrupts, timing, PSG and source-attested P-code execution state. The original 581-file historical source remains frozen as a regression reference, not a production compile input.

`rd_sms_native_runtime_abi()` returns `0x00010000`. The exported `rd::State`, `rd::mask`, and `rd::evaluate` interfaces presently use a **C++ same-compiler DLL ABI** and are not yet a portable machine-neutral C interface. Do not confuse independent build units with fully interchangeable runtime machines across unrelated CPU architectures. This game runtime still loads/verifies the original ROM, and Ghidra analysis/recovery still has historical Python adapters.

The runtime delegates frame rendering to [rd_video_sms_mode4](../rd_video_sms_mode4/README.md) through its versioned C ABI; generated applications link [rd_runtime_host](../rd_runtime_host/README.md) to display frames and poll buttons. Synthetic parity, native ABI smoke, and legacy dependency gates run in CTest. **Real Shinobi video, controls and 1,800-frame execution through these NEW DLLs require Windows verification.**

Generated v0.4.9.11 continuous applications emit observed stack-pointer and source-size data for bounded recovery; this is additive report metadata, not a new runtime DLL ABI or parity guarantee.
