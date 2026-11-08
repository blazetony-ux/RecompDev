# analysis_integration — independent component history

## [0.3.5] - 2026-11-08

- **Changed:** Reusable integration without CPU/game assumptions.
- **Validation:** Synthetic tests locally; owner Windows regression gates pending.
- **Compatibility:** Schema, ROM and immutable evidence contracts preserved; runtime parity not asserted.

- **COMPAT-023:** Exact Windows `ESC[2K\r` `aflj` prefix can terminate a recognized formatting line before a JSON array. Only that approved CR boundary is admitted; generic standalone CR, unknown ANSI/OSC, garbage, malformed/duplicate/trailing JSON and hash mismatches continue to fail closed. Raw Rizin logs remain unchanged, with five prefix bytes reflected in audit.
- **Validation:** Exact raw-byte regression fixture and negative boundary cases pass locally. Real Alex Kidd/Bank Panic parser and downstream controller retest pending owner Windows v23 install. Do not promote Rizin boundary guesses to translated executable code.


## [0.3.4] - 2026-11-07

- **Changed:** Source-attested preview recovery preflight accepts immutable `cycle-01` through `cycle-128` session identities, including three-digit cycle IDs, without relaxing the original mapper or ROM identity tests.
- **Validation:** New boundary tests reject cycle 129 and verify session parser limits alongside native controller and diagnostics budgets; final Windows owner tests pending.
- **Compatibility:** Earlier v0.4.9.20 preview archives remain in their original source directories and continue to require exact matching source, job and translation SHA-256.

## [0.3.3] - 2026-11-07

- **Changed:** Add `preview_frontier.py` with exact manifest checks, source/ROM/mapper/PC/SP/guest-stop attestation and immutable `recovery_history.import_previous` preview injection; no address guessing.
- **Validation:** Adversarial ZIP mutation, wrong ROM, wrong job/cycle, source replacement, missing state and cross-session inheritance tests; native source verification remains mandatory.
- **Compatibility:** Prior `resume` and provider contracts unchanged; incomplete v0.4.9.19 preview ZIPs rejected, and Python analysis ABI migration remains pending.

## [0.3.2] - 2026-11-07

- **Changed:** Source-attested initial Ghidra/Rizin outputs can be reused across immediately consecutive sessions after SHA-256 matching ROM bytes, authorised external tool executables, maintained provider code/Java scripts, all input artifacts, Ghidra instruction bytes and deterministic Rizin reconciliation. Old v0.4.9.17 sessions or altered tools trigger fresh analysis; tampered artifacts fail closed.
- **Recovery:** Most recent previously verified runtime-stop seed and bank export are supplied first to the native translation stage; no speculative instruction semantics, process-state restoration or changed CPU/console ABI.
- **Validation:** Mock-tool no-process cache hit, source mismatch, binary drift, modified IR/reconciliation negative tests. Authentic Windows reuse and >896 frames still require owner runs.


- **Compatibility:** No C++ plugin ABI modifications; no state restoration or gameplay qualification; historical v0.4.9.17 evidence remains usable through fresh Ghidra/Rizin analysis.

## [0.3.1] - 2026-11-07

- **Changed:** Previous-session `--resume-from` imports the already verified `imported-history` ledger from its immediately preceding session plus new genuine stops; all previously copied stop/overlay bytes are SHA-256-checked, ROM/mapper/Ghidra instruction re-attested, bounded and recopied into a new immutable output. No external provenance paths are traversed.
- **Validation:** Three linked synthetic sessions retain every source-attested stop and focused export; malicious inherited file mutation, missing audit, forged bank evidence, original-ROM mismatch and source byte mismatch fail closed. Real Windows Ghidra/Rizin gameplay parity remains unproven.
- **Compatibility:** Existing v0.4.9.14 one-run importer and output schema remain valid, as do source-verified native translation gates. The temporary Python analysis adapter remains and CPU-neutral compiled provider contracts are future work.

## [0.3.0] - 2026-11-07

- **Changed:** Maintained headless Ghidra process launch, active Java export scripts, SHA-256 byte-bound raw P-code export validation and source-attested Ghidra/Rizin reconciliation, without imports from frozen Python analysis modules.
- **Added:** Optional `--resume-from` imports previous ROM-identity-verified native stop seeds and bank-scoped Ghidra exports to a fresh evidence directory; rejects forged mappings, instruction hashes, duplicate states and unsafe paths. Does not resume process state or reuse unverified binaries.
- **Validation:** Direct unit tests check source-authenticated import, malicious path rejection, byte tampering and archival reconciliation parity; owner Windows real Ghidra/recovery remains pending.
- **Compatibility:** Controller C++/DLL ABIs unchanged; Python orchestration, non-analysis legacy components and 1,800-frame real-ROM parity remain open.

## [0.2.0] - 2026-11-07

- **Changed:** Native-owned *process* provider (maintained Python implementation, not a compiled DLL): eliminated active imports of `tooling.orchestrator._attempt_rizin` and legacy `authorize_tool`, retained Rizin subprocess options and controller-facing normalized `aflj` evidence.
- **Fixed:** The actual Windows Rizin 0.9.1 standalone `ESC[2K` console line, which v0.4.9.12 rejected. Added bounded ANSI audit, warning-free direct JSON, unknown-format rejection, fail-closed executable/time/output/source provenance.
- **Validation:** Cross-ISA option negotiation, parser warnings/ANSI/negative test corpus and dual synthetic-ROM native-controller orchestration. Real installed Ghidra/Rizin and game parity remain Windows owner acceptance gates.
- **Compatibility:** Compiled controller, DLLs and frozen 642 history files unchanged; Ghidra and reconciliation/recovery legacy imports remain tracked and must be removed in subsequent versions.

## [0.1.1] - 2026-11-07

- **Changed:** Added independently testable, strict Rizin 0.9.1 warning-prefixed `aflj` recovery in the *active* provider boundary. Preserve original subprocess log, retain the historical `UNPARSABLE_JSON` result in a separate audit, and publish SHA-256-bound normalized JSON only after full validation.
- **Validation:** Parser unit tests exercise real warning syntax, ANSI/CRLF, malformed or ambiguous output, unexpected preambles/trailers, malformed function types and record cap; synthetic dual-ROM compiled-controller process mock now emits warnings. Real tool and MSVC revalidation remain owner-run acceptance gates.
- **Compatibility:** No change to the 642 frozen historical files, source admission, CPU/hardware/translators, compiled interfaces or existing approved external-tool allowlists. Legacy process invocation is still temporary and must be removed behind a replaceable analysis-provider ABI.

## [0.1.0] - 2026-11-07

- **Changed:** Introduced explicit tool-root-authorized Ghidra and Rizin source-analysis adapters, SHA-256-verified P-code export and non-executable Rizin boundary reconciliation, plus controller-owned bounded native recompilation and observed-stop recovery iteration.
- **Changed:** Added actual-PC, observed-mapper Ghidra re-analysis on missing-code stops, source-attested bank overlays and fail-closed rejection of forged physical bank mappings.
- **Validation:** Synthetic dual-ROM compiled-controller and analyzer-process integration, source-identity rejection, unapproved-tool refusal, generated C++ compilation and observed-app state contract pass locally. Windows real-tool execution, full autonomous recovery through multiple genuine ROM gaps, second commercial ROM and input/audio/video parity are not yet demonstrated.
- **Compatibility:** No source files under `legacy/` or `baselines/` modified; existing compiled CPU/machine/runtime interfaces and v0.4.9.9 stable installer retained. Native source-verification owns admission; historical Python runs analysis only.
