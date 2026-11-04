"""Game-independent recovery-target classification and bounded planning.

Recovery is a source-authenticated recompile/replay action. No interpreters,
manual ROM patches, or magic game addresses are permitted in the core.
"""
from dataclasses import asdict, dataclass
from nativecore.registry import capabilities

MISSING_CODE={'UNTRANSLATED_INITIAL_CODE','BANKED_CODE_NOT_TRANSLATED'}

@dataclass(frozen=True)
class RecoveryTarget:
    system: str
    cpu: str
    logical_pc: int
    physical_offset: int
    region: str
    slot: int
    bank: int
    entry_pc: int
    reason: str

    def key(self):
        return (self.system,self.region,self.physical_offset)

    def record(self):
        return asdict(self)


def classify(system,rom_size,trace):
    if not isinstance(trace,dict) or trace.get('status') not in MISSING_CODE:
        return None
    cap=capabilities(system)
    if not cap['native_execution']:
        raise ValueError('NATIVE_RECOVERY_ADAPTER_NOT_INTEGRATED: '+system)
    pc=trace.get('pc');mapper=trace.get('mapper')
    if type(pc)!=int or not 0<=pc<0xc000:
        raise ValueError('MISSING_CODE_OUTSIDE_ROM: hardware or RAM execution adapter required')
    # The bank resolver belongs to the system adapter, never to the core.
    from nativecore.adapters import provider_for
    context=provider_for(system).map_entry(rom_size,pc,mapper)
    physical=context['entry_physical']
    if physical<0x400:
        region='fixed-rom-vector' if pc in (0,0x38,0x66) else 'fixed-rom-code'
    elif physical==pc and trace['status']=='UNTRANSLATED_INITIAL_CODE':
        region='initial-rom-code'
    else:
        region='mapped-rom-bank'
    return RecoveryTarget(system,cap['cpu'],pc,physical,region,context['slot'],
                          context['bank'],pc,trace['status'])

class RecoveryPlanner:
    def __init__(self,max_recoveries):
        if type(max_recoveries)!=int or not 0<=max_recoveries<=24:
            raise ValueError('Recovery budget must be an integer from 0 to 24')
        self.budget=max_recoveries
        self.seen=set()
        self.count=0

    def claim(self,target):
        if target is None:return 'NOT_RECOVERABLE'
        if self.count>=self.budget:return 'RECOVERY_BUDGET_EXHAUSTED'
        if target.key() in self.seen:return 'REPEATED_STOP_NO_NEW_EVIDENCE'
        self.seen.add(target.key());self.count+=1
        return 'RECOVERY_QUEUED'
