# Production CPU admission bridge

**Scope:** `production-workflow`. **Registry:** `workspace/components.json`. This is a source-only component with independent versioning, not a compiled executable or a replacement native translator.

On a `--stage recover` run, the preserved original source verifier authenticates Ghidra instruction evidence against exact physical ROM offsets. This bridge chooses the deployed `rd_cpu_z80` DLL from the immutable runtime version store and active lock, checks its SHA-256 identity, and invokes its `rd_z80_source_gate_v1` entry point on every unique authenticated instruction before launching legacy native recompilation.

- `--cpu-plugin auto` (default): use the installed active DLL; if no DLL is installed, report explicit legacy fallback. A corrupt or missing ABI DLL is a hard recovery blocker.
- `--cpu-plugin required`: refuse recovery unless an active versioned CPU DLL approves every instruction.
- `--cpu-plugin legacy`: explicitly bypass the CPU admission gate while retaining the historical source-authentication verifier.

The result is saved to `production-cpu-gate.json`, embedded in `controller-report.json` and `run-provenance.json`, and included in the external upload-ready evidence ZIP. This is a **production instruction-admission gate**, not Z80 semantic translation or execution parity. The legacy P-code translator and native execution path remain intact. The interface is defined in `harness/include/rd_production_cpu_v1.h`.

## Development

The independently versioned plugin is `rd_cpu_z80`; after editing its source and its own changelog, build/test/accept it in the permanent workspace. The bridge implementation itself is `modular/cpu_production.py` and may be tested using `python -B -m unittest modular.tests.test_production_cpu -q`. Preserve the original `legacy/` and `baselines/` trees.
