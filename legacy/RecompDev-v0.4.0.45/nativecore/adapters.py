"""Recovery interface implemented by console adapters, not by a game name.

Other systems must register an implementation explicitly before the shared
scheduler can use it. Registry metadata alone does not grant execution support.
"""
from typing import Protocol

class RecoveryProvider(Protocol):
    def map_entry(self,rom_size:int,pc:int,mapper): ...
    def recover(self,rom_path,source_sha,target_id,pc,mapper,output): ...

class MasterSystemRecovery:
    def map_entry(self,rom_size,pc,mapper):
        from nativepilot.recovery import bank_context
        return bank_context(rom_size,pc,mapper)

    def recover(self,rom_path,source_sha,target_id,pc,mapper,output):
        from nativepilot.recovery import recover_bank
        return recover_bank(rom_path,source_sha,target_id,pc,mapper,output)

PROVIDERS={'mastersystem':MasterSystemRecovery()}

def provider_for(system):
    try:return PROVIDERS[system]
    except KeyError:raise ValueError('SYSTEM_RECOVERY_PROVIDER_NOT_INTEGRATED: '+system) from None
