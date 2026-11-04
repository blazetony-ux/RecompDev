"""Explicit system-to-native-host adapters; no implicit interpreter fallback.

The common campaign is ISA-agnostic. Each machine declares a compilation
provider and a host-session provider; unsupported systems fail closed.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class NativeHostAdapter:
    system: str
    cpu: str
    pilot_module: str
    pilot_function: str
    session_script: str
    reference_parity: str = 'NOT_ESTABLISHED'

HOSTS={
    'mastersystem':NativeHostAdapter('mastersystem','z80',
       'nativepilot.engine','pilot','tools/Run-Continuous-Native.py'),
}

def host_for(system):
    try:return HOSTS[system]
    except KeyError:raise ValueError('CONTINUOUS_MACHINE_ADAPTER_NOT_AVAILABLE: '+str(system)) from None
