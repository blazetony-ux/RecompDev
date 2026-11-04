"""Production DLL source gate: real frozen verifier, authentic fixture, DLL hash and blocking."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from modular import cpu_production, controller
from migration import controller as preservation

ROM=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
EXPORT=ROOT/'harness/examples/recomp-pcode/function-export.json'


def candidate():
    from workspace.manager import binary_path
    name=Path(os.environ.get('RECOMPDEV_CPU_GATE_TEST_DLL',''))
    return name if name.is_file() else binary_path('rd_cpu_z80',ROOT)


@contextmanager
def active_test_plugin(plugin):
    """Isolated external runtime; never changes actual machine active DLLs."""
    with tempfile.TemporaryDirectory(prefix='recompdev-cpu-gate-',
                                        ignore_cleanup_errors=(os.name=='nt')) as temp:
        projects=Path(temp)
        binary=projects/'RecompDev-Runtime'/'active'/plugin.name
        stored=projects/'RecompDev-Runtime'/'versions'/'rd_cpu_z80'/'0.2.0'/plugin.name
        binary.parent.mkdir(parents=True);stored.parent.mkdir(parents=True)
        shutil.copy2(plugin,binary);shutil.copy2(plugin,stored)
        digest=hashlib.sha256(binary.read_bytes()).hexdigest()
        lock=projects/'RecompDev-Runtime'/'active-components.json'
        lock.write_text(json.dumps({'active':{'rd_cpu_z80':{
            'version':'0.2.0','sha256':digest,
            'active_path':str(binary),'binary':str(stored),
            'git_commit':'test-candidate'}}}),encoding='utf8')
        with patch.dict(os.environ, {'RECOMPDEV_PROJECTS_ROOT':str(projects)}):
            yield binary,stored,lock


class TestProductionCpuGate(unittest.TestCase):
    def test_legacy_original_authentication(self):
        result=preservation.pcode_verify(ROM,EXPORT,[])
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['physically_attested_instructions'],6)

    def test_selected_compiled_cpu_dll_receives_all_attested_instructions(self):
        binary=candidate()
        if not binary.is_file():self.skipTest('Build rd_cpu_z80 DLL before running native admission test')
        with active_test_plugin(binary):
            result=cpu_production.admit(ROM,EXPORT,mode='required')
            self.assertEqual(result['status'],'PLUGIN_SOURCE_GATE_PASSED')
            self.assertEqual(result['verified_instruction_addresses'],6)
            self.assertEqual(result['length_checked'],6)
            self.assertEqual(result['length_unverified'],0)
            self.assertEqual(result['selected_plugin']['sha256'],hashlib.sha256(binary.read_bytes()).hexdigest())
            self.assertFalse(result['guest_execution_via_this_dll'])

    def test_native_opcode_length_contradiction_fails_closed(self):
        binary=candidate()
        if not binary.is_file():self.skipTest('Build rd_cpu_z80 DLL first')
        with active_test_plugin(binary):
            selected=cpu_production.select_cpu_plugin(required=True)
            fn=selected[2]
            import ctypes
            ins=(ctypes.c_uint8*2)(0x3e,0x42)
            decision=cpu_production.GateDecision()
            decision.struct_size=ctypes.sizeof(decision)
            self.assertEqual(fn(ins,2,3,ctypes.byref(decision)),1)
            self.assertEqual(decision.expected_length,2)
            self.assertEqual(fn(ins,1,3,ctypes.byref(decision)),-1)

    def test_hash_tamper_is_blocker_not_legacy_fallback(self):
        binary=candidate()
        if not binary.is_file():self.skipTest('Build rd_cpu_z80 DLL first')
        with active_test_plugin(binary) as (active,_,_):
            active.write_bytes(b'not a native module')
            with self.assertRaisesRegex(cpu_production.GateError,'CPU_PLUGIN_SHA256_MISMATCH'):
                cpu_production.admit(ROM,EXPORT,mode='auto')

    def test_explicit_legacy_fallback(self):
        self.assertEqual(cpu_production.admit(ROM,EXPORT,mode='legacy')['status'],
                         'EXPLICIT_LEGACY_FALLBACK')

    def test_missing_plugin_is_explicit_or_blocking(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ,{'RECOMPDEV_PROJECTS_ROOT':temp}):
                self.assertEqual(cpu_production.admit(ROM,EXPORT,mode='auto')['status'],
                                 'LEGACY_FALLBACK_NO_ACTIVE_PLUGIN')
                with self.assertRaisesRegex(cpu_production.GateError,'REQUIRED_CPU_PLUGIN_NOT_INSTALLED'):
                    cpu_production.admit(ROM,EXPORT,mode='required')

    def test_controller_uses_real_export_and_cpu_plugin_before_legacy_recovery(self):
        binary=candidate()
        if not binary.is_file():self.skipTest('Build rd_cpu_z80 DLL first')
        with active_test_plugin(binary):
            with tempfile.TemporaryDirectory(prefix='recompdev-real-gate-run-') as temp:
                # Real preserved discovery/preparation/native recovery, not a mock.
                result=controller.run_rom(ROM,Path(temp)/'run',stage='recover',export=str(EXPORT),
                      budget=10,steps=40,frames=1,recoveries=0,timeout=150,
                      cpu_plugin_mode='required')
                self.assertEqual(result['authenticated_export']['status'],'PASS',result)
                self.assertEqual(result['production_cpu_gate']['status'],'PLUGIN_SOURCE_GATE_PASSED',result)
                self.assertEqual(result['production_cpu_gate']['verified_instruction_addresses'],6)
                self.assertTrue(Path(temp,'run','production-cpu-gate.json').is_file())
                self.assertTrue(Path(temp,'run','recovery','continuous-recovery-report.json').is_file())
                self.assertTrue(result['source_image_unchanged'])
                self.assertFalse(result['production_catalogue_mutated'])

    def test_controller_stops_before_native_compilation_for_tampered_plugin(self):
        binary=candidate()
        if not binary.is_file():self.skipTest('Build rd_cpu_z80 DLL first')
        with active_test_plugin(binary) as (active,_,_):
            active.write_bytes(b'tampered')
            with tempfile.TemporaryDirectory() as temp:
                result=controller.run_rom(ROM,Path(temp)/'run',stage='recover',export=str(EXPORT),
                       budget=10,steps=40,frames=1,recoveries=0,timeout=150,
                       cpu_plugin_mode='required')
                self.assertEqual(result['status'],'RECOVERY_BLOCKED_CPU_PLUGIN',result)
                self.assertNotIn('legacy_recovery_status',result)
                self.assertFalse(Path(temp,'run','recovery').exists())
                self.assertTrue(result['source_image_unchanged'])
                self.assertFalse(result['production_catalogue_mutated'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Alternate native DLL smoke uses Linux C compiler')
    def test_replacing_binary_changes_gate_decision_on_authenticated_bytes(self):
        base=candidate()
        if not base.is_file():self.skipTest('Build rd_cpu_z80 DLL first')
        with active_test_plugin(base):
            good=cpu_production.admit(ROM,EXPORT,mode='required')
            self.assertEqual(good['verified_instruction_addresses'],6)
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'deny.c'; dll=Path(td)/'rd_cpu_z80.so'
            src.write_text('#include <stdint.h>\nstruct Decision {uint32_t size,abi,family,declared,expected,opcode;};\nint rd_z80_source_gate_v1(const uint8_t *b,uint32_t n,uint32_t p,struct Decision *d){\n if(!d || !b || !n || n>8) return -2;\n d->abi=0x10000;d->declared=n;d->expected=n;d->family=1;d->opcode=b[0];\n return -1;}\n')
            proc=subprocess.run(['cc','-shared','-fPIC',str(src),'-o',str(dll)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            # Fresh DLL identity/path. Never overwrite a loaded shared library.
            with active_test_plugin(dll):
                with self.assertRaisesRegex(cpu_production.GateError,'CPU_PLUGIN_REJECTED_AT_PHYSICAL'):
                    cpu_production.admit(ROM,EXPORT,mode='required')

if __name__=='__main__':unittest.main()
