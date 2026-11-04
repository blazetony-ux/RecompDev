# RecompDev architectural contract and migration handover

## Nonnegotiable architecture

- One generic compiled RecompDev controller, configured by CPU, machine,
  audio, video, input, analysis, asset and translator components.
- Hardware components must be replaceable independently. No console-specific
  rewrite of the central orchestration for each new CPU or game.
- CPU plugins decode/translate CPU instructions; system plugins define memory,
  mapping, interrupts, devices and timing; the controller assembles services.
- Final native game code and recovered resources should not require an original
  ROM during execution. This goal is **not yet demonstrated** by the current run.
- A source-verified instruction does not establish behavioural correctness.
  All parity claims require independent emulator/hardware comparisons.

## Permanent workspace from v0.4.4 onward

- `C:\Projects\RecompDev` is the **sole Git checkout**. Existing versioned
  installations are preserved for migration audit and must never be overwritten.
- Build products: `RecompDev-Build`. Activated controller and versioned binary
  plugins: `RecompDev-Runtime`. Cache: `RecompDev-Cache`.
- Production catalogue: `RecompDev-Data` (read-only source of truth).
- Evidence and logs: `RecompDev-Evidence/v<workspace-version>/<run-id>`;
  automatic SHA-verified upload ZIP beside each run.
- Historical ZIP archives and rollback backups: `RecompDev-Archive`.
- Original v0.4.0.45 source and harness v0.3 remain immutable, verified
  file-by-file (581 + 61 = 642 preserved source/fixture files).

## Independently versioned components

`workspace/components.json` declares each component's own version, target and
scope. Update only the changed component, then build, test, commit and activate
it individually. Runtime binaries have immutable version/hash identities and
rollback is a binary switch, not a compilation. Git workspace tags name a
validated combination, and do not force version increments on unchanged parts.

## Honesty gate: production plugin gap

Compiled plugins currently run through the **C++ harness**. The actual Shinobi
native recovery pipeline still calls `legacy.discovery`, `legacy.preparation`
and `legacy.recovery` adapters from preserved v0.4.0.45 Python modules.
The workspace manager explicitly marks those scopes; a DLL replacement is not
yet proof that production legacy recovery uses that DLL.

**Next production migration gate:** swap a CPU/hardware/translator plugin while
holding the central controller and legacy source SHA unchanged, and show a
real-ROM native-recovery execution difference or parity in independent evidence.
Do not claim that gate passed merely because synthetic CTest fixtures pass.

## Windows lifecycle

One-time self-contained bootstrap. Subsequent edits should be small file
replacements followed by `plugin bump`, `plugin accept` and, for official
snapshots, `plugin release workspace/vX.Y.Z`. Failed builds do not commit or
activate. Never wipe existing catalogue, evidence, old releases or caches.
