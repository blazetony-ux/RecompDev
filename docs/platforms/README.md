# Platform support inventory

**Status:** Current as of v0.4.5. A prepared source or historical investigation is not equivalent to a production runtime plugin.

| Platform | CPU | Existing implementation | Production qualification |
| --- | --- | --- | --- |
| [Sega Master System](mastersystem.md) | Z80 | Harness machine DLL and preserved production recovery stack | Real Shinobi execution observed; gameplay parity unresolved |
| [Sega Mega Drive](megadrive.md) | Motorola 68000 / Z80 | Historical investigation/preparation code preserved | No interchangeable production MD machine DLL |
| [PlayStation 1](playstation.md) | MIPS R3000A | Historical investigation/preparation code preserved | No interchangeable production PS1 machine DLL |

New machines should plug into the same generic controller and translator contracts. Do not fork the entire recompilation workflow for each console or game.
