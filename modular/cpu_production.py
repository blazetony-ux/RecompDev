"""Authenticated Z80 source-instruction admission using the active DLL.

This is a real production gate before native compilation, not a replacement Z80
interpreter or translator. No owner ROM bytes are written into report artifacts.
The frozen legacy verifier remains authoritative for physical address mapping and
source hashes; the selected native CPU plugin additionally admits/rejects those
exact bytes. An installed/broken plugin must NEVER be silently bypassed.
"""
from __future__ import annotations
import ctypes
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABI = 0x00010000


class GateError(RuntimeError):
    pass


class GateDecision(ctypes.Structure):
    _fields_ = [('struct_size', ctypes.c_uint32),
                ('abi_version', ctypes.c_uint32),
                ('opcode_family', ctypes.c_uint32),
                ('declared_length', ctypes.c_uint32),
                ('expected_length', ctypes.c_uint32),
                ('opcode', ctypes.c_uint32)]


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def select_cpu_plugin(root=ROOT, *, required=False):
    """Version-store/hash-bound load. A missing plugin is distinct from corruption."""
    from workspace.manager import read_state, roots
    root = Path(root).resolve()
    doc = read_state(root)['active'].get('rd_cpu_z80')
    if doc is None:
        if required:
            raise GateError('REQUIRED_CPU_PLUGIN_NOT_INSTALLED: rd_cpu_z80')
        return None
    runtime = roots(root)['runtime'].resolve()
    expected = runtime / 'active' / ('rd_cpu_z80.dll' if __import__('os').name == 'nt' else
                                      'rd_cpu_z80.dylib' if __import__('sys').platform == 'darwin' else 'rd_cpu_z80.so')
    actual = Path(doc.get('active_path', '')).resolve()
    if actual != expected or not actual.is_file():
        raise GateError('CPU_PLUGIN_SELECTION_PATH_INVALID')
    stored = Path(doc.get('binary', '')).resolve()
    if not stored.is_relative_to(runtime / 'versions' / 'rd_cpu_z80') or not stored.is_file() or stored.parent.name != doc.get('version'):
        raise GateError('CPU_PLUGIN_VERSION_STORE_INVALID')
    digest = doc.get('sha256')
    if not digest or _sha(actual) != digest or _sha(stored) != digest:
        raise GateError('CPU_PLUGIN_SHA256_MISMATCH: active/version-store binary is not the approved candidate')
    # Existing installations can still run original recovery while the new
    # candidate is staged. The older DLL never advertised the gate extension.
    # This compatibility fallback is explicit; --cpu-plugin required rejects it.
    if doc.get('version') == '0.1.0':
        if required:
            raise GateError('CPU_PLUGIN_UPGRADE_REQUIRED_FOR_SOURCE_GATE')
        return {'legacy_without_gate':doc}
    try:
        library = ctypes.CDLL(str(actual))
        fn = library.rd_z80_source_gate_v1
    except (OSError, AttributeError) as exc:
        raise GateError('CPU_PLUGIN_ABI_UNAVAILABLE: '+str(exc)) from exc
    fn.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32, ctypes.c_uint32,
                   ctypes.POINTER(GateDecision)]
    fn.restype = ctypes.c_int
    return doc, library, fn


def admit(rom, export, *, root=ROOT, mode='auto', output=None):
    """Enforce approval for every unique source-attested physical instruction.

    Caller must have already invoked preservation.pcode_verify. We independently
    call its original verify_export for authenticated physical mappings; never
    infer the physical address from a banked virtual Z80 PC.
    """
    if mode not in ('auto', 'required', 'legacy'):
        raise ValueError('Unknown CPU plugin mode: '+str(mode))
    report = {'schema':'recompdev-production-cpu-gate-v1', 'cpu':'z80',
              'mode':mode, 'native_translation_engine':'preserved v0.4.0.45 P-code generator',
              'source_rom_embedded':False, 'guest_execution_via_this_dll':False,
              'semantic_parity':'NOT_ESTABLISHED'}
    if mode == 'legacy':
        report.update(status='EXPLICIT_LEGACY_FALLBACK',selected_plugin=None)
    else:
        selected = select_cpu_plugin(root,required=(mode=='required'))
        if selected is None:
            report.update(status='LEGACY_FALLBACK_NO_ACTIVE_PLUGIN',selected_plugin=None)
        elif isinstance(selected,dict):
            report.update(status='LEGACY_FALLBACK_PRE_GATE_PLUGIN',
                          selected_plugin={'component':'rd_cpu_z80',
                              'version':selected['legacy_without_gate']['version'],
                              'sha256':selected['legacy_without_gate']['sha256']})
        else:
            doc, library, fn = selected
            # Retain `library` for lifetime of ctypes function pointers.
            from nativepilot.generator import verify_export
            rom = Path(rom).resolve(strict=True)
            export = Path(export).resolve(strict=True)
            evidence = json.loads(export.read_text(encoding='utf8'))
            if evidence.get('schema') != 'recomp-function-pcode-v1':
                raise GateError('SOURCE_EXPORT_SCHEMA_MISMATCH')
            verified, _, _ = verify_export(evidence,rom)
            raw = rom.read_bytes()
            families = {'base':0,'cb':0,'ed':0,'ix_iy':0}
            count = 0
            unknown_length = 0
            accepted_bytes = 0
            for physical, instruction in sorted(verified.items()):
                length = instruction['length']
                segment = raw[physical:physical+length]
                # The original verifier checked the hash. Keep that invariant
                # explicit at this trust boundary before entering the DLL.
                if hashlib.sha256(segment).hexdigest() != instruction['bytes_sha256']:
                    raise GateError(f'SOURCE_BYTE_HASH_CHANGED_AT_{physical:08x}')
                input_bytes = (ctypes.c_uint8 * len(segment)).from_buffer_copy(segment)
                decision = GateDecision()
                decision.struct_size = ctypes.sizeof(GateDecision)
                status = fn(input_bytes,len(segment),physical,ctypes.byref(decision))
                if status not in (1,2) or decision.abi_version != ABI or decision.declared_length != length:
                    raise GateError(f'CPU_PLUGIN_REJECTED_AT_PHYSICAL_{physical:08x}: code={status}, '
                                    f'expected_length={decision.expected_length}, declared={length}')
                if decision.opcode != segment[0] or decision.opcode_family not in (1,2,3,4):
                    raise GateError(f'CPU_PLUGIN_INVALID_DECISION_AT_{physical:08x}')
                families[('base','cb','ed','ix_iy')[decision.opcode_family-1]] += 1
                count += 1
                accepted_bytes += length
                unknown_length += (status==2)
            if count == 0:
                raise GateError('NO_ATTESTED_INSTRUCTIONS_ADMITTED')
            report.update(status='PLUGIN_SOURCE_GATE_PASSED',
                selected_plugin={'component':'rd_cpu_z80', 'version':doc['version'],
                    'sha256':doc['sha256'], 'active_path':doc['active_path'],
                    'git_commit':doc.get('git_commit'), 'source_gate_abi':ABI},
                verified_instruction_addresses=count,verified_byte_span_total=accepted_bytes,
                opcode_families=families,length_unverified=unknown_length,
                length_checked=count-unknown_length,
                scope='source-byte admission BEFORE legacy native translation; not execution replacement')
    if output:
        output = Path(output)
        if output.exists():
            raise FileExistsError('CPU production gate report already exists: '+str(output))
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return report
