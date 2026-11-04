"""Explicit capability registry for multi-console native recompilation.

'Registered' is not 'native supported'. Every stage is independently declared.
Names are canonical internal systems from discovery, not game-specific IDs.
"""
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class CpuAdapter:
    cpu: str
    instruction_export: str
    native_codegen: str
    parity: str
    notes: str

@dataclass(frozen=True)
class SystemAdapter:
    system: str
    cpu: str
    image_mapping: str
    hardware_runtime: str
    recovery: str
    notes: str

CPUS = {
    'z80': CpuAdapter('z80', 'ghidra-pcode-tested', 'experimental-cpp-lowering', 'not-tested',
                      'Source-hash-attested Z80 instruction records; not complete CPU semantics.'),
    'm68k': CpuAdapter('m68k', 'ghidra-and-capstone-partial', 'not-integrated-in-native-execution', 'not-tested',
                       'Earlier function recovery tooling exists; no unified executable pilot.'),
    'mips': CpuAdapter('mips', 'ghidra-and-capstone-partial', 'not-integrated-in-native-execution', 'not-tested',
                       'PS-X EXE function analysis exists; no full PS1 runtime or unified executable pilot.'),
}
SYSTEMS = {
    'mastersystem': SystemAdapter('mastersystem', 'z80', 'sega-16kb-mapper',
                'partial-vdp-psg-irq', 'ghidra-seeded-rom-regions', 'Native execution pilot enabled; hardware parity unverified.'),
    'gamegear': SystemAdapter('gamegear', 'z80', 'format-recognized-only', 'not-integrated',
                             'not-integrated', 'Shared CPU is not sufficient for native Game Gear execution.'),
    'megadrive': SystemAdapter('megadrive', 'm68k', 'megadrive-cartridge-existing', 'not-integrated',
                              'graph-recovery-existing', 'Function discovery/preparation only in unified Workbench.'),
    'psx-exe': SystemAdapter('psx-exe', 'mips', 'psx-exe-existing', 'not-integrated',
                            'graph-recovery-existing', 'Executable image only; whole-disc extraction needs further adapters.'),
}

def capabilities(system):
    sys=SYSTEMS.get(system)
    if sys is None:
        return {'system':system,'registered':False,'native_execution':False,
                'blockers':['SYSTEM_ADAPTER_MISSING']}
    cpu=CPUS[sys.cpu]
    executable=(sys.system=='mastersystem')
    return {'system':sys.system,'registered':True,'cpu':sys.cpu,
            'cpu_adapter':asdict(cpu),'system_adapter':asdict(sys),
            'native_execution':executable,
            'native_output':'cpp-to-host-x86-64' if executable else 'not-integrated',
            'blockers':(['CPU_PARITY_NOT_VALIDATED','HARDWARE_PARITY_NOT_VALIDATED'] if executable else
              ['NATIVE_CODEGEN_NOT_INTEGRATED','HARDWARE_RUNTIME_NOT_INTEGRATED']),
            'native_execution_note':'Pilot stage; x86-64 C++ compilation is not behavioural verification.'}

def all_capabilities():
    return {'schema':'recomp-native-capabilities-v0409',
            'architectures':[asdict(x) for x in CPUS.values()],
            'systems':[capabilities(s) for s in SYSTEMS],
            'principle':'Game-independent capability stages; no unsupported CPU claims.'}
