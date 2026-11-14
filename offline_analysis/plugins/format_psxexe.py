"""PS-X EXE format; PS1 CD images and arbitrary overlays are not claimed."""
from offline_analysis.model import Image, Seed
ANALYSIS_ABI=2

def inspect(data: bytes) -> Image | None:
    if not data.startswith(b'PS-X EXE') or len(data)<0x804: return None
    entry=int.from_bytes(data[0x10:0x14],'little')
    base=int.from_bytes(data[0x18:0x1c],'little')
    size=int.from_bytes(data[0x1c:0x20],'little')
    if size<4 or size>len(data)-0x800 or entry%4 or base%4 or entry<base or entry+4>base+size: return None
    return Image('sony-psx-exe','mips-r3000a','psx-executable-flat',
                 (Seed(entry,'ps-x-exe-entry'),),0x800,size,base,0,
                 {'load_address':base,'entry':entry,'executable_bytes':size,
                  'scope':'PS-X EXE payload, not complete PS1 disc or BIOS'})
