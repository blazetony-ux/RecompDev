# RecompDev Cross-System Bridge v0.3 — Phase A

This package adds a **read-only identity-adapter prototype and a C++ batch readiness report**. It does not overwrite the existing RecompDev executable, Workbench, `catalogue.sqlite`, RC9326 source patches, or original program files. It neither runs emulator hardware nor translates any commercial game to C++ yet.

## Existing Ridge Racer title — no action required

If you have already named Ridge Racer in the Workbench, **do not run `sync-names --apply`**. Your current `Ridge Racer` display label and the underlying target ID remain untouched by the `identify`, `adapters`, and `plan-cpp` commands. The optional `sync-names` feature is for future unnamed targets; by design it does not overwrite records whose `name_source` is `owner_alias`. In normal use, leave catalogue naming unchanged and move straight to the adapter inventory and C++ readiness report.

## Commands (from PowerShell)

All commands are single-line. Extract the ZIP into `C:\Projects` so the files are at `C:\Projects\RecompDev-CrossSystem-Bridge-v0.3`.

**Check PlayStation identity from existing owner-local project evidence:**

`py -3 'C:\Projects\RecompDev-CrossSystem-Bridge-v0.3\recomp_bridge.py' identify --input 'C:\Projects\Evidence\RecompProjects\ps1-ridge-racer-68468e09be\sources\boot.psx'`

The current PS-X EXE has no standard game title or serial. The result should report a `Ridge Racer` **project-path hint**, not an authenticated disc serial or match. For authenticated ID, run against the PS1 disc image (`.iso`, supported plain Mode1 `.bin` with track at LBA0) or extracted `SYSTEM.CNF`. Some CUE track layouts require a future adapter.

**List adapters (implemented vs planned):**

`py -3 'C:\Projects\RecompDev-CrossSystem-Bridge-v0.3\recomp_bridge.py' adapters`

**Read-only analysis of all currently catalogued function candidates:**

`py -3 'C:\Projects\RecompDev-CrossSystem-Bridge-v0.3\recomp_bridge.py' plan-cpp --db 'C:\Projects\RecompDev-Catalogue-v0.2\catalogue.sqlite' --output 'C:\Projects\Evidence\RecompCatalogue\cpp-readiness.json'`

This identifies which candidates lack verified boundaries, and aggregates the current families and call barriers. **No commercial ROM bytes are embedded in reports**. No C++ is emitted from unverifiable function candidates.

**Optional serial-to-title matching:** Supply a local UTF-8 CSV containing `system,id,title`. E.g. `ps1,SLUS-00594,Example Title`. Only unambiguous exact system+ID matches are applied, explicitly as third-party catalogue evidence. CSV is user-provided; this build does not download game indexes or guess titles from the Internet.

## Current implementation boundaries

- Implemented metadata-only: Mega Drive header, PS-X EXE project-path hints, PS1/PS2 `SYSTEM.CNF` via direct files or simple ISO9660 Mode1 images, Xbox 360 STFS display title and title ID, standalone XEX2 optional `ExecutionId` title ID when present, standalone `PARAM.SFO` strings.
- Not yet implemented: PS1/PS2 CUE multi-track reader, generalized PS1/PS2 ELF/disc executable extraction, Xbox 360 XDVDFS and protected XEX payload extraction, commercial binary IR-to-C++ conversion, qualified runtime, automatic Internet title lookup.
- System-agnostic core: common identity evidence/provenance, adapter registry, read-only plan; format and ISA rules reside only in adapters.
- The repository's existing Ghidra/Rizin/Capstone analysis integration and other adapters remain separately tracked; this package does not change them.

## Candidate-function caveat

The reported **309** entries in your three-target Workbench are static **function-entry candidates**. The SQLite database contains instruction metadata/hashes, not authenticated full function byte bodies, and most boundaries are not verified. Directly emitting C++ for all 309 would be misleading. The planned next phase re-opens SHA-verified source bytes, constructs function CFGs and typed IR, verifies calling conventions and memory effects, lowers supported units in batch, and separately validates generated programs against reference execution.

## Automatic naming without manually typing titles

From existing owner-local project source folders, the bridge can match the exact file SHA to an already registered Workbench target, extract a publisher title or project-folder name, and **preview** a safe update:

`py -3 'C:\Projects\RecompDev-CrossSystem-Bridge-v0.3\recomp_bridge.py' sync-names --db 'C:\Projects\RecompDev-Catalogue-v0.2\catalogue.sqlite' --sources-root 'C:\Projects\Evidence\RecompProjects'`

To apply only eligible SHA-matched changes, add `--apply`. This first creates `catalogue.sqlite.pre-v03-names.bak` using SQLite's backup API. It will not overwrite owner aliases or already-known header titles. Project-folder names are shown as provenance `evidence_folder`, **not** validated publisher metadata. With your `ps1-ridge-racer-.../sources/boot.psx`, this can upgrade the unhelpful `boot` label to `Ridge Racer` without manual naming. The file must match the SHA of the registered PS1 executable. Re-scanning is unnecessary.
