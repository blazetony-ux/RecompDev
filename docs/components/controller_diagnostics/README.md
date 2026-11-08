# Controller diagnostics API

**Latest v0.4.9.23 contract:** v0.4.9.23: CPU-neutral `watch_summary` is an approved display event. Intentional display sampling, transport overflows, GUI queue drops and source-capture truncation are different counters and must not be combined.


**Scope:** `controller-diagnostics`. **Version:** `0.1.0`. Canonical registry: `workspace/components.json`.

The controller owns one CPU- and console-neutral event stream named `recompdev.controller.diagnostics.v1`. The native-game launcher starts `ControllerDiagnostics` during a run, receives typed events from the staged game producer and publishes them to read-only subscribers on `127.0.0.1` using a random per-run token. Subscribers cannot issue execution or plugin-control commands. The compiled `RecompDev.exe` remains at 0.4.4; the broker is an **orchestrator-owned Python controller service**, not yet embedded into the compiled controller. The provider and GUI have no direct connection. Events: `instruction`, `frame`, `input`, `hardware`, `stop`, `notice` and `session`. JSON Lines, 4096-byte maximum per event, last 512 kept, per-subscriber queue 256 with oldest-drop and no slowdown to the guest. Version or add event types deliberately; no debugger execution controls in this release.

## v0.4.9.20 terminal result event

`native_result` is one more strictly bounded read-only event from the owner-approved controller to its token-authenticated monitor. It conveys final reported process status and separately labelled host and guest frame counters. It is not an input, debug-breakpoint or program-control channel, and accepts no guest mutation requests.

## v0.4.9.22 display overflow audit

The subscriber channel remains localhost/token-authenticated and read-only, but now counts event drops when an individual 256-item display channel fills. Its subscriber receives a `notice` with cumulative `display_dropped` counts; the native monitor displays broker transport drops separately from its own bounded UI reader-queue drops and rejected JSON events. These are *presentation losses*, not proof of dropped executed instructions. The preview worker continues writing native event evidence to a distinct local file, and the upload ZIP remains bounded to a 5,000-event excerpt.
