"""Capability-negotiated, not a fictitious universal ROM decoder."""
ADAPTERS = [
    dict(system='Mega Drive',containers=['.md','.gen','.bin'], identity='implemented: header title/product', program='existing v0.2 mapped cartridge', isa='m68k: existing v0.2',runtime='not implemented'),
    dict(system='PlayStation 1',containers=['.iso','.bin','.img','.psx'],identity='implemented: SYSTEM.CNF in basic ISO9660 Mode1, PS-X EXE project hint',program='existing v0.2 PS-X EXE only; disc executable extraction missing',isa='mips-r3000a: partial existing v0.2',runtime='not implemented'),
    dict(system='PlayStation 2',containers=['.iso','.bin','.img','.elf'],identity='implemented: SYSTEM.CNF BOOT2 in basic ISO9660 Mode1',program='planned: disc ELF extraction, EE ELF section/relocation support',isa='r5900/EE + IOP: not implemented',runtime='not implemented'),
    dict(system='Xbox 360',containers=['.xex','.iso','.stfs','.con','.live','.pirs'],identity='implemented: standalone XEX2 ExecutionId and STFS package header',program='planned: XDVDFS, XEX compression/decryption via permitted tooling, PE section mapping',isa='PowerPC 64-bit big-endian: not implemented',runtime='not implemented'),
    dict(system='Original Xbox',containers=['.xbe','.iso'],identity='planned: XBE certificate and XDVDFS',program='planned',isa='x86: not implemented',runtime='not implemented'),
    dict(system='PSP / PS3',containers=['.sfo','.iso','.pkg','.pbp'],identity='implemented: PARAM.SFO strings (standalone)',program='planned',isa='MIPS Allegrex / PowerPC Cell: not implemented',runtime='not implemented'),
    dict(system='Nintendo / Sega / other future platforms',containers=['.nes','.sfc','.smc','.gba','.gb','.gbc','.z64','.n64','.v64','.gcm','.wbfs','.cue'],identity='planned: per-format metadata and mapping plugins',program='planned',isa='per-platform plugin, not yet implemented',runtime='not implemented'),
]
