# RecompDev v0.4.0.3 — Unified Native Preparation

This is a full, versioned, Windows-first build inheriting all v0.4.0.2 features. It **does not replace** v0.4.0.2 and does not modify original game images.

## Installing

1. Extract `RecompDev-v0.4.0.3-Unified-Native-Preparation.zip` to `C:\Projects`. The archive contains the folder `RecompDev-v0.4.0.3`.
2. Close any previous Workbench occupying port 8777.
3. Double-click `C:\Projects\RecompDev-v0.4.0.3\Start-Workbench.cmd`.
4. Open `http://127.0.0.1:8777/discovery` in your browser.

On first launch, Workbench creates `catalogue.v0403-working.sqlite` as an independent SQLite backup. It prefers your **v0.4.0.2 working catalogue** (with Shinobi and its discovery evidence), then earlier releases; previous installs remain untouched. The existing generated PNG previews from v0.4.0, .1, and .2 remain available read-only.

## Using the new third stage

On **Autonomous Discovery**, use **Prepare for Native Recompilation**:

1. Select **Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms** from the imported-game dropdown. If not listed, import and discover it in the Add ROMs section first.
2. Click **Prepare selected game**. The page shows the job's progress, errors, and completion report.
3. Open **Native Recompilation**; the **Prepared game targets** panel shows its CPU, target and readiness status, and **Prepared function candidates** shows any metadata recovered by Ghidra.

No PowerShell is required for these in-app steps. The CLI is optional:

`py -3 -m nativeprep.engine --db <WORKING_DB> --source-id <DISCOVERY_SOURCE_ID> --output <EVIDENCE_DIRECTORY> --allowed-root C:\Roms`

## What it really does

- Uses the existing discovery source ID and independently recomputes complete SHA-256 for supported ROMs before creating a target in the existing `targets` table. It records an evidence-linked row in `native_preparations_v0403`. A mismatch fails closed.
- Supports initial **Master System and Game Gear Z80 ROM** registration and source-verified Ghidra analysis for the **initial 48 KiB ROM view (addresses 0x0000–0xBFFF)**. Addresses 0xC000–0xFFFF are RAM and are not loaded as ROM. Additional cartridge ROM banks are explicitly NOT analysed yet.
- Searches for a headless Ghidra installation, including your previous `C:\Projects\_Old\Tools\Ghidra-*\support\analyzeHeadless.bat` location. Alternatively set `RECOMPDEV_GHIDRA` to its full path or `GHIDRA_HOME` to the Ghidra installation folder.
- Runs Ghidra in a disposable local project. It exports metadata and raw P-code to the local evidence directory. Every recovered instruction's hash is checked against the registered original ROM bytes. Candidate boundaries remain **unverified**.
- Reuses any valid source-matched Mega Drive Ghidra export from a previous installation. If none exists, can run the pre-existing Mega Drive Ghidra extractor.
- Reports `NEEDS_EXECUTABLE_EXTRACTOR` for unsupported imported game formats, instead of pretending to support their CPUs.
- Creates **grouped discovery backlog tasks** for native analysis, Z80 translation, unresolved ROM bank mapping and independent function-boundary confirmation.
- Uses one bounded local worker, an origin/token-protected browser action, approved ROM roots, and a separate SQLite working catalogue. No ROM bytes are served via HTTP.

## Limits and honest interpretation

- `CANDIDATES_RECOVERED_TRANSLATOR_NEEDED`: Ghidra returned source-byte-attested Z80 function candidate metadata, but **no Z80-to-C++ translator or runtime parity is implemented**.
- `NEEDS_GHIDRA`: Native target registered but the headless analyzer is missing or not located.
- `ANALYSIS_FAILED`: The Ghidra invocation or export validation failed. Open the job's `.ghidra.log` file for details.
- `PREVIOUS_CANDIDATES_RETAINED`: Previously imported candidates remain available even though the new analysis attempt did not finish.
- Candidate functions do not mean complete recovered or behaviourally verified functions. No banked code has been proven recovered.
- The Master System was not analysed with real Ghidra on Windows in the local packaging environment. Verify using Shinobi on your computer and inspect the Workbench results.

## Evidence

Each preparation produces `evidence\native-prepare-v0403\jobs\<jobid>\preparation-report.json` and `worker.log`, plus a Ghidra JSON export and log when analysis runs. The database stores target and candidate records and groups capability blockers without spawning one redundant task per candidate.

### For this specific next acceptance test

You should see Shinobi under **Prepared game targets** on the Native page. If Ghidra is available and successfully analyses the initial bank, you should also see Z80 candidate entries. Their status will correctly state that translation is still needed.
