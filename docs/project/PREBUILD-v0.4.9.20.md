# PREBUILD v0.4.9.20 — preview gap handoff

**Baseline:** v0.4.9.19 owner-promoted Git `main` `31154cdb00180bda1c2eb366e563047c4e41fb75`. **Track:** infrastructure source-only.

## Scope

Take the real owner preview's untranslated stop at `0xADAF` as a hardware-agnostic diagnosed class, **not** a game-specific patch. A complete new preview must capture original actual native mapper/SP, source SHA-256 and PC/physical offset; the input-neutral owner capture is not evidence that Z caused a failure. Keep preview read-only, use explicit `resume --preview-stop` with no-write preflight, have the existing native ROM/mapper discovery DLL verify recovered instructions, and preserve accepted stop via cumulative immutable history. Display distinct guest and host frame counters and a clear blocked guest status.

## Historical job boundary

The v0.4.9.18 Shinobi recovery job was compiled against an earlier DLL directory; the compiled controller intentionally forbids silently changing providers during `resume`. Use a new v0.4.9.20 job with explicitly imported history, followed by its own new preview, to test `--preview-stop`. Do not claim a successful cross-provider hot resume.

## Gates

Source-check and hash all ZIP members, ROM, previous orchestration and generated translated source; reject v0.4.9.19 incomplete ZIPs, fake input, bad PC/mapper/ROM/source, duplicates and any action that mutates a previous session or active runtime. Test source read-only preflight and controller forwarding, native synthetic end-to-end preview, old-job lookup, 642 protected historical files, docs governance, native build and full owner Windows CTest. No change to CPU/machine/video plugin ABI and no claimed qualified gameplay or 1,800-frame completion. See [release](../releases/v0.4.9.20.md).
