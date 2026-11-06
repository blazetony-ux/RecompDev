# rd_format_sms — independent changelog

## [0.1.0] - 2026-11-05

- **Changed:** Added independently loadable compiled `rd_format_sms` native format provider with versioned C ABI and bounded structural detection; no game-specific data or branch logic.
- **Validation:** Synthetic native-discovery CTest fixture, malformed input rejection and CPU-independent loader-kind verification. Windows DLL deployment and commercial-game parity not yet qualified.
- **Compatibility:** Uses separate format kind/ABI; existing `RD_DiscoveryApi` event-recording plugin and Shinobi runtime are unchanged.
