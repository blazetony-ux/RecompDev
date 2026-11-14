"""SMS cartridge detection only. Mapper and ISA remain independent plugins."""
from offline_analysis.model import Image, Seed
ANALYSIS_ABI=1

def inspect(data: bytes) -> Image | None:
    if len(data) < 0x8000 or len(data) % 0x4000 != 0 or len(data) > 4*1024*1024:
        return None
    headers=[hex(pos) for pos in (0x1ff0,0x3ff0,0x7ff0) if data[pos:pos+8] == b'TMR SEGA']
    if not headers: return None
    return Image('sega-master-system','z80','sms-banked',
                 (Seed(0,'reset'),Seed(0x38,'interrupt-vector-candidate'),Seed(0x66,'nmi-vector-candidate')),
                 0,len(data),0,0x4000,{'header_locations':headers,'bank_count':len(data)//0x4000})
