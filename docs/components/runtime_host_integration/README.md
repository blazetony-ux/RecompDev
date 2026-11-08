# Monitor/host orchestration

**Scope:** `production-host-integration`. **Version:** `0.1.0`. Canonical registry: `workspace/components.json`.

The source-only `runtime_host` bridge and launch tool stage the native publisher, start controller diagnostics and a separate viewer, process and verify typed telemetry, package logs and results in the normal evidence ZIP, and preserve original generated source. `Run-Native-Game.ps1 -ExecutionMonitor [-MonitorEvery 256]` enables it; without that switch the old run path remains unchanged. The generic compiled `rd_runtime_host` presentation DLL version 0.1.0 is untouched. Window visibility is **not** fixed, idle title-screen untranslated `0xB2E1` remains a distinct code coverage issue. Monitor and game windows are separate processes; the monitor is read-only. Event samples are evidence, not proof of full instruction-accurate disassembly or gameplay parity.

## v0.4.9.21 native terminal clock

The generated native application reports `guest_frames` directly from the final machine VDP state while retaining `frames` from the host output. Instrumented preview keeps the last sampled event separately; no clock-domain parity or original input correctness is claimed.
