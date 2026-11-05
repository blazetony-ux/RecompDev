# RecompDev documentation index

**Status:** Current. Last reviewed: 2026-11-05.

This is the starting point for anyone developing, debugging or handing over RecompDev. Documents under the categories below are *normative* unless explicitly labelled **Historical**, **Experimental**, or **Proposed**. Consult actual source and tests whenever a document and code disagree.

| Topic | Authoritative entry | What it answers |
| --- | --- | --- |
| Project goals and status | [Project overview](project/PROJECT-VISION.md) | What is being built and what remains unproved? |
| Conversation handover | [Current handover](project/HANDOVER.md) | What should the next developer do, without relying on chat history? |
| Priorities | [Roadmap](project/ROADMAP.md) | What is next, and what is deliberately deferred? |
| Architecture | [Architecture contract](architecture/ARCHITECTURE-CONTRACT.md) | Which component boundaries may not be violated? |
| Runtime data flow | [Controller and services](architecture/DATA-FLOW.md) | What runs in the compiled harness versus real recovery? |
| Component inventory | [Components](components/README.md) | What is versioned, compiled, and actually wired into production? |
| Production recovery | [Production pipeline](recompilation/PRODUCTION-PIPELINE.md) | Which preserved engines and code-attestation gates are used? |
| Hardware state | [Validation gaps](research/HARDWARE-VALIDATION-GAPS.md) | What is captured and what is still missing? |
| Platforms | [System index](platforms/README.md) | What exists for SMS, Mega Drive and PS1? |
| Development | [Workspace](development/WORKSPACE.md) | How are components built, tested and rolled back? |
| Release approvals | [Release process](development/RELEASE-PROCESS.md) | Which docs/tests/version checks gate publication? |
| Documentation rules | [Documentation standards](development/DOCUMENTATION-STANDARDS.md) | What makes a document valid and useful? |
| Decisions | [Architecture decision index](architecture/decisions/README.md) | Why did architectural choices change? |
| Current release | [v0.4.5 release](releases/v0.4.5.md) | What changed without touching compiled binaries? |
| Old releases | [Historical index](history/README.md) | Where did older instructions and evidence originate? |

## Rules for authoritative documents

Active documents cite specific paths, versions, known test conditions and explicit limitations. Historical notes remain readable but their old installation paths are not current instructions. Never treat synthetic harness tests as proof of real-ROM gameplay parity, and never treat frame-budget completion as a ROM-independent, playable output.

Release notes and component changelogs live in Git with the source. Generated captures, WAVs, logs, working SQLite snapshots and user-upload ZIPs live outside Git in versioned `RecompDev-Evidence` directories.

## Production plugin integration

- [Phase 1 design, limitations and data flow](recompilation/PRODUCTION-PIPELINE.md)
- [Versioned source-gate bridge](components/production_cpu_bridge/README.md)
- [Workspace v0.4.6 release notes](releases/v0.4.6.md)

## Workspace v0.4.7 additions

- [Production translator adapter and full legacy generator](components/production_translation/README.md) — explains the new selectable boundary and its documented limitations.
- [Standalone Workbench read-only catalogue viewer](components/workbench/README.md) — local launch command, data permissions and browser interface.
- [v0.4.7 release and test limits](releases/v0.4.7.md) — what is real, what has been tested and what remains unproven.

## Workspace v0.4.9 input-driven native recovery

- [Replay recording, source-authenticated recovery and bounded replay validation](components/input_recovery/README.md)
- [v0.4.9 release scope and known limits](releases/v0.4.9.md)
