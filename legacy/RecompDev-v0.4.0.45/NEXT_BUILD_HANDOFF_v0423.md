# v0.4.0.23 handoff — reusable native application integration

## Delivered and qualified in local tests

- Generated code and hardware runtime are linked into an optional standalone host binary, not only a trace executable.
- CPU-independent bounded continuous host session, headless frames/audio, source-authenticated owner-ROM launcher, fail-closed missing-code boundary.
- Deterministic input at guest-cycle boundaries; native Z80 test programs demonstrate effect on rendered output.
- Separate compiler-backed, source-attested synthetic Z80 targets and a non-SMS generic CPU/session verify reusable architecture.
- Existing native pilot and bank-recovery tools preserved. Versioned independent catalogue with v0.4.0.22 snapshot lookup.

## Blocked/unknown

- Owner Windows GDI+waveOut runtime acceptance not yet tested; MAME parity unestablished; audio/video hardware only approximate.
- Genuine Shinobi full-code coverage, correct graphics, gameplay, automatic recovery/repair are not demonstrated.
- Native guest bus still SMS-specific in its adapter; generic device Rack not yet authoritative for that guest. This is the highest-priority architectural debt.

## Next unskippable qualification

Run Win32 host from an author-created synthetic Z80 fixture using the owner's compiler, and produce matching headless image/audio fingerprints; independent MAME vs native aligned checkpoint needed before CPU/hardware correctness promotion. Do not mistake nonblack pixels or frame count for gameplay qualification.
