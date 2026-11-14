"""Conservative cartridge detection and reset-vector validation."""
from offline_analysis.model import Image, Seed
ANALYSIS_ABI=1

def inspect(data: bytes) -> Image | None:
    if not (0x200 <= len(data) <= 16*1024*1024) or len(data)%2: return None
    if b'SEGA' not in data[0x100:0x110]: return None
    initial_sp=int.from_bytes(data[:4],'big')
    entry=int.from_bytes(data[4:8],'big')
    if entry&1 or entry<0x200 or entry>=len(data): return None
    return Image('sega-mega-drive','m68000','cartridge-flat',
                 (Seed(entry,'reset-vector'),),0,len(data),0,0,
                 {'initial_sp':initial_sp,'reset_vector':entry,'region':'cartridge-only'})
