# standalone_export — component changelog

## [0.1.1] - 2026-11-14

- **Changed:** Release-identity acceptance tests now read the current workspace version from the authoritative registry rather than retaining a fixed `v0.4.9.34` expectation that would otherwise reject every legitimate future release. No standalone exporter implementation or output ABI is modified.
- **Validation:** Reruns the original source-attested synthetic native export, 3-frame independent execution, rights/overwrite/tamper checks and release-version match under the new v0.4.9.35 version. The canonical Windows installer full suite remains mandatory.
- **Compatibility:** v0.4.9.34 exported bundles retain their recorded provenance and current independently generated binaries retain the same manifest, embedded-data and runtime semantics. No ROM/CPU-specific export changes or claimed game parity.

## [0.1.0] - 2026-11-14

- **Changed:** Introduced the independent v1 standalone application export contract, first generated-native-project adapter, bounded source-attested binary embedding and a trusted native build recipe. The shared exporter has no CPU, mapper or game-specific branches; adapter-specific code lives in its own module.
- **Validation:** Native Z80 synthetic loop builds to a separately launchable application without an external source binary; independent frame execution, source SHA match, unchanged generated translation and bundle hash verification are tested. Negative tests cover rights, provenance tamper, symlink injection, output overwrite and corrupted binaries. Windows full MSVC acceptance remains required before promotion.
- **Compatibility:** Existing runtime host/CPU/machine DLL ABIs, generated native code, active runtime slots, source Git history and all frozen historical files remain unchanged. A second ISA/console adapter, complete coverage, authorised real-game export and reference hardware parity remain explicitly unqualified.
