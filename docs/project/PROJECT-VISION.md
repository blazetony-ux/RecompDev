# Project vision and non-negotiable constraints

**Status:** Current. Last reviewed: 2026-11-04.

## Outcome

RecompDev is a reusable recompilation **toolchain**. It should identify real machine code in an existing game binary, preserve source-byte provenance, translate verified instructions into native C++ for the host architecture, and bind them to modular implementations of the source machine's hardware. The target is a native game distribution no longer depending on the source ROM. This remains a **goal** rather than an achieved capability.

## Architecture

- The controller is generic: it loads CPU, system, mapper, video, audio, input, translator, discovery and asset services selected by the detected/declared hardware, not by the game title.
- CPU plugins interpret and/or lower **CPU-specific** instructions; machine plugins supply memory maps, banking, interrupts, devices and timing. The controller owns orchestration and evidence management.
- Components have independent versions and can be built, tested, activated and rolled back without touching unrelated DLLs. Runtime compatibility must be checked, not assumed.
- Preserved legacy discovery, Ghidra preparation and native recovery remain authoritative **until** behavioural equivalence is independently demonstrated. Do not discard or rewrite their findings merely to improve the modular appearance.
- Master System, Mega Drive and PS1 are intended plugin targets; neither a new console-specific pipeline nor a Shinobi-specific workaround constitutes architectural progress.

## Evidence rules

A source-verified instruction address proves the source bytes matched, not that translated semantics, interrupt timing, graphics, audio or gameplay are correct. Real reference comparisons must have aligned inputs, frame position and ROM identity. A generated native DLL or a 120-frame headless result does not prove the final ROM-independent game objective.

## Development and preservation

The local Git checkout (`C:\Projects\RecompDev`) holds source, tests and documentation. Build outputs, installed binaries, caches, working databases, logs and evidence are external siblings. The 642-file original source-preservation manifest stays mandatory. Git history and local bundles are not a substitute for an off-machine backup of the catalogue, source or evidence.
