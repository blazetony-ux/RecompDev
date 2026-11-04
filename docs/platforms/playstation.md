# Sony PlayStation 1 support

**Status:** Historical preparatory work only; no production-interchangeable PlayStation machine plugin.

The frozen v0.4.0.45 source contains earlier MIPS/R3000A and PlayStation-related exploratory analysis. It is preserved for later inventory, but the active C++ plugin registry has no production PS1 machine, R3000A CPU or PS1 GPU/SPU implementation.

Planned components include an R3000A decoder/translator and separately modelled memory, coprocessor, GPU, SPU, DMA and timing services behind a common controller contract. These are target architecture requirements, not built features; the current release cannot claim PS1 ROM recompilation parity.
