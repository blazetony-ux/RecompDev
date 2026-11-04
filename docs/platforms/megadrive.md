# Sega Mega Drive support

**Status:** Historical preparatory work only; no production-interchangeable Mega Drive machine plugin.

The preserved v0.4.0.45 source includes prior Motorola 68000 / Mega Drive analysis and preparatory experiments. This work must be inventoried and reused where source-verified rather than rewritten around a particular game. The active C++ harness does not currently load a functional `rd_machine_megadrive.dll`, and its Z80 fixture CPU is not a complete solution for the Mega Drive's mixed processors.

Before production qualification: define 68000 instruction/translator contracts, machine memory/VDP/audio interfaces and inter-CPU coordination; then validate real ROM behaviour independently. Do not claim game completion or executable parity from older code archaeology alone.
