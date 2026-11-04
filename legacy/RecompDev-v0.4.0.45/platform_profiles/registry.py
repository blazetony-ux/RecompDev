"""v0.4.0.34 conservative, data-only Z80 platform compatibility gate.

A shared CPU is NOT evidence of compatible ROM mapping, port I/O, interrupts,
VDP, audio, or bank registers. Never use extension alone to authorise execution.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib

@dataclass(frozen=True)
class Profile:
    system: str
    cpu: str
    rom_layout: str
    memory: str
    io: str
    video: str
    audio: str
    native_runtime: str

PROFILES = {
 'mastersystem': Profile('mastersystem','z80','sega8-cartridge','sms-mapper','sms-ports','sms-vdp','sn76489','nativepilot-sms-experimental'),
 'gamegear': Profile('gamegear','z80','sega8-cartridge','gamegear-mapper','gamegear-ports','gg-vdp','sn76489-stereo','not-integrated'),
 'spectrum48': Profile('spectrum48','z80','spectrum-snapshot-or-raw','spectrum48-memory','ula-ports','ula','beeper','not-integrated'),
 'spectrum128': Profile('spectrum128','z80','spectrum-snapshot-or-raw','spectrum128-paging','ula-ay-ports','ula','ay8912','not-integrated'),
 'msx1': Profile('msx1','z80','msx-cartridge','msx-slots','msx-ppi-vdp-ports','tms9918','ay8910','not-integrated'),
 'cpc464': Profile('cpc464','z80','cpc-snapshot-or-disk','cpc-banking','cpc-gate-array-ports','cpc-gate-array','ay8912','not-integrated'),
 'colecovision': Profile('colecovision','z80','coleco-cartridge','coleco-memory','coleco-vdp-ports','tms9918','sn76489','not-integrated'),
}

EXTENSION_HINTS={'.sms':'mastersystem','.gg':'gamegear','.z80':'spectrum48',
 '.sna':'spectrum48','.tap':'spectrum48','.tzx':'spectrum48','.dsk':'cpc464',
 '.cas':'msx1','.col':'colecovision'}

def assess(system, evidence='owner-asserted'):
    """Explicit qualification status: only SMS has a bounded experimental runtime."""
    p=PROFILES.get(system)
    if not p:
        return {'system':system,'cpu':'unknown','classification':evidence,
                'native_status':'BLOCKED_UNKNOWN_PLATFORM','missing':['cpu-identification','hardware-adapter']}
    enabled=(system=='mastersystem' and evidence in ('structural-header','owner-asserted'))
    return {**asdict(p),'classification':evidence,
            'native_status':'EXPERIMENTAL_SMS_NATIVE_PILOT' if enabled else 'BLOCKED_NO_MATCHING_NATIVE_HARDWARE',
            'missing':[] if enabled else ['platform-specific-memory-map','port-io','interrupts','video-audio','native-runtime'],
            'cpu_reuse':'Z80_RECOMPILATION_SEMANTICS_ONLY',
            'independent_hardware_parity':'NOT_ESTABLISHED'}

def inspect_source(path, asserted_system=None):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    if path.stat().st_size>64*1024*1024:raise ValueError('source too large for bounded platform inspection')
    if asserted_system and asserted_system not in PROFILES:
        raise ValueError('unregistered platform: '+asserted_system)
    with path.open('rb') as f:
        digest=hashlib.sha256(); head=f.read(0x210)
        digest.update(head)
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
        sega8=False
        for offset in (0x1ff0,0x3ff0,0x7ff0):
            if path.stat().st_size>=offset+16:
                f.seek(offset)
                if f.read(8)==b'TMR SEGA':sega8=True;break
    suffix=path.suffix.lower()
    hint=EXTENSION_HINTS.get(suffix)
    if sega8 and suffix in ('.sms','.gg'):
        system=hint;evidence='structural-header'
    elif sega8:
        system=asserted_system or 'sega8-ambiguous';evidence='sega8-header-but-ambiguous-system'
    else:
        system=asserted_system or hint or 'unknown';evidence='owner-asserted' if asserted_system else 'extension-hint-only'
    result=assess(system,evidence)
    # Filename hints alone can never turn on a native hardware implementation.
    if evidence=='extension-hint-only' and system=='mastersystem':
        result['native_status']='BLOCKED_UNVERIFIED_PLATFORM_IDENTITY'
        result['missing']=['structural-header-or-explicit-platform-assertion']
    result.update({'schema':'recompdev-platform-assessment-v1','sha256':digest.hexdigest(),
                   'bytes':path.stat().st_size,'extension_hint':hint,'header_sega8':sega8,
                   'platform_asserted_by_owner':asserted_system is not None,
                   'note':'Classification is not proof of full machine compatibility or successful recompilation.'})
    return result
