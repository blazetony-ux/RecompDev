# Input recovery component changelog

## [0.1.0] - 2026-11-05

- **Changed:** Introduced a CPU- and game-neutral guest-cycle button-transition recorder in staged generated native frontends, deterministic `RECOMP_INPUT_CYCLES_V1` replay ingestion from authenticated runtime evidence and guarded input-driven native recovery through the original source-verified engine. Earlier wall-clock-only host inputs are explicitly labelled estimates, with stop-PC/status/frame reproducibility required before recovery.
- **Validation:** Six replay/security/guest-code-preservation unit tests, unchanged translated C++ SHA-256, CMake build and execution of an authenticated synthetic compiled game with a real replay CSV, existing generic host tests and 40 existing CTest regressions on Linux. Real Shinobi recovery beyond the newly observed `0x7BE8` address remains for owner Windows testing.
- **Compatibility:** New separately versioned source-only component; v0.4.4 compiled controller, v0.2.0 Z80 DLL, v0.1.0 generic runtime host DLL, original legacy recovery/translator, unrelated plugins and the 642 frozen historical files remain unchanged. Builds may regenerate the staged **game application**, not RecompDev core or unrelated DLLs.
