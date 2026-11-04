"""Binary container mapping plug-ins. No runtime or emulator hardware."""
from dataclasses import dataclass

def u32be(b, off):
    return int.from_bytes(b[off:off+4], 'big')


def u32le(b, off):
    return int.from_bytes(b[off:off+4], 'little')


@dataclass(frozen=True)
class Image:
    container: str
    isa: str
    endian: str
    start: int
    stop: int
    file_offset: int
    entry: int
    alignment: int
    data: bytes
    warnings: tuple

    def offset(self, addr):
        return self.file_offset + (addr - self.start)

    def valid(self, addr):
        return self.start <= addr < self.stop and (addr - self.start) % self.alignment == 0


def open_image(data, fmt='auto', isa=None, endian=None, base=None, entry=None):
    if fmt == 'auto':
        if len(data) >= 0x200 and b'SEGA' in data[0x100:0x110]:
            fmt = 'megadrive'
        elif data.startswith(b'PS-X EXE'):
            fmt = 'psx-exe'
        else:
            raise ValueError('unknown input: specify --format raw --isa ... --endian ... --base ... --entry ...; disc images need a separate extraction adapter')
    if fmt == 'megadrive':
        if len(data) < 0x206 or b'SEGA' not in data[0x100:0x110]:
            raise ValueError('no verifiable Mega Drive header; no entry guessed')
        pc = u32be(data, 4)
        if pc < 0x200 or pc >= len(data) or pc % 2:
            raise ValueError('invalid Mega Drive reset vector')
        if isa not in (None, 'm68k') or endian not in (None, 'big'):
            raise ValueError('Mega Drive cartridge adapter expects m68k big-endian')
        return Image(fmt, 'm68k', 'big', 0x200, len(data), 0x200, pc, 2, data,
                     ('Reset vector supplies a static seed, not exhaustive proof of code.',
                      'Code may be reached indirectly or from interrupts; static pass does not run hardware.'))
    if fmt == 'psx-exe':
        if len(data) < 0x800 or not data.startswith(b'PS-X EXE'):
            raise ValueError('invalid PS-X EXE header')
        load = u32le(data, 0x18)
        stated = u32le(data, 0x1c)
        pc = u32le(data, 0x10)
        available = len(data)-0x800
        if stated < 4 or stated > available or load % 4 or pc % 4 or pc < load or pc >= load + stated:
            raise ValueError('invalid PS-X EXE load layout / entry, refusing speculative offset mapping')
        if isa not in (None, 'mips') or endian not in (None, 'little'):
            raise ValueError('PS-X EXE adapter expects MIPS little-endian')
        return Image(fmt, 'mips', 'little', load, load+stated, 0x800, pc, 4, data,
                     ('PS-X EXE is a program file, not a PlayStation disc ISO reader.',
                      'MIPS branch delay slots and load delays require a verified ISA semantics plugin; seed walking halts at control transfers.'))
    if fmt == 'raw':
        if isa not in ('m68k', 'mips') or endian not in ('big','little') or base is None or entry is None:
            raise ValueError('raw requires --isa m68k|mips --endian big|little --base and --entry')
        if (isa == 'm68k' and endian != 'big') or (isa == 'mips' and endian != 'little'):
            raise ValueError('MVP supports m68k big and mips little only')
        alignment = 2 if isa == 'm68k' else 4
        if entry < base or entry >= base + len(data) or (entry-base) % alignment:
            raise ValueError('raw entry not in supplied mapped region')
        return Image(fmt,isa,endian,base,base+len(data),0,entry,alignment,data,
                     ('Raw base/entry are supplied assertions, not inferred proof.',))
    raise ValueError('unsupported format; supported: auto, megadrive, psx-exe, raw')


