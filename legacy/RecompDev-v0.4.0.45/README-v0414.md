# RecompDev v0.4.0.14 — Architecture-First Tool Orchestration

## Purpose and current limits

This is a **cross-target tooling release**, not a game-specific startup or graphics patch. It carries forward v0.4.0.13's source-authenticated Z80 native pilot and experimental MAME external trace capture. It adds an owner-authorized Ghidra + Rizin analysis coordinator, source-attested function-boundary reconciliation, bounded external process execution, a minimal evidence-driven investigation planner, an architecture charter, and executable release acceptance tests.

**NOT CLAIMED:** fully autonomous recompilation, verified Ghidra/Rizin execution on your machine, M68000/MIPS native execution, full-game parity, native qualification or gameplay. These remain formal blockers. Three *synthetic* ISA inputs test the analysis interface; they do not prove a native codegen backend for those ISAs.

## Installation — PowerShell one-liners

Close the old Workbench. Keep v0.4.0.13 installed as an independent rollback point.

**1. Extract**

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.14-Architecture-First-Tool-Orchestration.zip" -DestinationPath 'C:\Projects' -Force
```

**2. Launch**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.14\Run-Workbench.ps1'
```

**3. Run tests (optional, comprehensive)**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.14\Verify-v0414.ps1'
```

Workbench: `http://127.0.0.1:8777/tooling`. The new working catalogue is `catalogue.v0414-working.sqlite`; this is initialized using a SQLite backup of the most recent existing working catalogue, beginning with v0.4.0.13. No previous installation is overwritten.

## New tool coordination

All calls are owner-authorized, shell-free and bounded. The coordinator never downloads tools or ROMs. Run these from PowerShell:

**List actual integration contracts** (does not launch tools):

```powershell
py -3 'C:\Projects\RecompDev-v0.4.0.14\tools\Tool-Orchestrator.py' capabilities
```

**Inventory known local tool directories without launching anything** (change `C:\Tools` if required):

```powershell
py -3 'C:\Projects\RecompDev-v0.4.0.14\tools\Tool-Orchestrator.py' discover --tool-root 'C:\Tools'
```

**Example dual analyzer run** on your own **raw** Motorola 68000 program, with explicit base address and known entry (replace the sample binary and both tool paths with the real values):

```powershell
$r='C:\Projects\RecompDev-v0.4.0.14'; py -3 "$r\tools\Tool-Orchestrator.py" analyze --input 'C:\MyOriginalPrograms\test68k.bin' --isa m68k --base 0x0 --entry 0x0 --rizin 'C:\Tools\Rizin\rizin.exe' --ghidra 'C:\Tools\Ghidra\support\analyzeHeadless.bat' --allow-tool-root 'C:\Tools' --require-dual --output "$r\evidence\tooling-v0414\jobs\run-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

The analyzer executes Rizin's `aflj` function query and the existing RecompDev Ghidra instruction-byte/P-code exporter. The source SHA-256 is rechecked after analysis; Ghidra-reported instruction hashes are independently verified against owner-local bytes. These produce **function-boundary hypotheses**, not verified native execution. If either required analyzer fails or output cannot be verified, the dual-engine job is **blocked**, not promoted. The original input never gets bundled into the evidence directory.

To try Rizin alone, omit `--ghidra` and `--require-dual`; the result will explicitly be `SINGLE_ENGINE_ONLY`. For a raw Z80 mapping, `--isa z80` is available with Rizin; the new raw Ghidra runner is intentionally restricted to the M68000 and MIPS language profiles from the existing codebase until the Z80 Ghidra language profile is validated independently. For image containers, raw base/entry must be based on the actual mapping; this coordinator does not silently interpret console headers, ROM banks or relocations.

Results are stored under the selected `--output` directory:

- `analysis-job.json`: source SHA, tool-entrypoint hashes, exit codes, log checksums, statuses
- `ghidra-functions.json`: SHA-claimed, subsequently source-byte-attested P-code export (when enabled)
- `rizin-aflj.json`: Rizin's source-addressed function hypotheses (when enabled)
- `reconciliation.json`: agreeing/conflicting/sole-owner entry points; no native parity claim
- `investigation-plan.json`: deterministic next evidence request; never edits source or promotes candidates
- `ghidra-output.log`, `rizin-output.log`: bounded execution logs

Never share the commercial source file, generated native project, or private emulator BIOS when collecting evidence. Evidence may still include metadata (addresses, names, hashes) from your own binaries; review before sharing.

## MAME capture portability fix

The experimental existing MAME wrapper now explicitly supplies the executable's `roms` path, rather than relying on MAME's working directory, which is the isolated capture directory. You can add your own approved BIOS paths with `--rom-root 'C:\Roms'` (repeatable); the capture still requires the exact ROM SHA. The MAME launcher remains separate from the new static multi-tool coordinator, and CPU-step alignment is still absent.

## Architectural milestones and acceptance

`PLATFORM_CHARTER.json` codifies architecture-first release rules. `tools/Validate-Architecture.py` runs three **author-created** raw binary targets (Z80, M68000, MIPS) through the same reconciliation code and checks source hashes and not-overstated parity flags. The new unit tests include forged Ghidra instruction hashes, source mutations, unapproved tool paths, symlink escapes, engine failures, output caps and boundary disagreements. A Linux fixture subprocess tests two separate raw ISAs through the real process orchestration contract, but uses a **fake analyzer program** and does not validate real Ghidra/Rizin behaviour. Tests on Windows also exercise the pure cross-ISA analysis path.

Milestone summary:

| Milestone | Release status |
|---|---|
| M1: same analysis API across targets | PARTIAL, synthetic fixtures only |
| M2: real independent engine provenance | BLOCKED until owner-run real Ghidra + Rizin |
| M3: two executable native ISA backends | BLOCKED (only experimental Z80 native pilot) |
| M4: autonomous semantic repair with rollback | BLOCKED |
| M5: verified live native dispatch | BLOCKED |

No metric is silently promoted because an engine compiled or two static analyzers agreed on a function entry. Refer to `BUILD_VALIDATION_v0414.json` for the explicit attestation scope and to `NEXT_BUILD_HANDOFF_v0414.md` for the next acceptance gate.

## Security and platform notes

Executable entrypoints must be under the explicitly approved `--allow-tool-root` and have expected names. Tool-entry SHA-256 is checked before and after. Logs are capped at 2 MiB and default process timeout is 180 seconds (maximum 3,600); output files have size/schema checks, immutable job directories and source-after-run verification. On timeout, an external process tree is terminated when supported. These are **resource and provenance controls**, not a general-purpose secure sandbox for malicious software. Run only trusted, legally obtained tools and your own binaries; Ghidra may create ephemeral private analysis projects in the system temp directory that are removed on normal completion.

Reference links: [Ghidra headless documentation](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md) and [Rizin CLI handbook](https://book.rizin.re/src/first_steps/commandline_options.html).
