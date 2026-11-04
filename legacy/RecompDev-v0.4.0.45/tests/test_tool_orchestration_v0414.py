"""Architecture-neutral tool orchestration acceptance and adversarial evidence tests.

Synthetic fixtures are author-created bytes, not copied commercial binaries.
Fake analyzer processes exercise orchestration only; do not assert Ghidra/Rizin
or real-game parity until those owner-installed executables are separately run.
"""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tooling.analysis import parse_ghidra,parse_rizin,reconcile
from tooling.orchestrator import authorize_tool,analyze,discover,Blocked
from tooling.triage import decide


def fixture(file,isa,base):
    content={'z80':bytes.fromhex('3e423200c0c9'),
             'm68k':bytes.fromhex('70014e75'),
             'mips':bytes.fromhex('010008240800e003')}
    raw=content[isa];file.write_bytes(raw)
    return raw,hashlib.sha256(raw).hexdigest()

def ghidra_doc(raw,sha,base):
    return {'schema':'recomp-function-pcode-v1','source_sha256':sha,
          'functions':[{'entry':base,'body_min':base,'body_max':base+len(raw)-1,
             'name':'fixture','instructions':[{'address':base,'length':len(raw),
               'bytes_sha256':hashlib.sha256(raw).hexdigest()}]}]}

class CrossArchitectureTests(unittest.TestCase):
    def test_same_reconciliation_engine_for_three_architectures(self):
        """Two ISAs is a release gate; a third detects accidental ISA dispatch assumptions."""
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);hashes=[]
            for arch,base in [('z80',0),('m68k',0x1000),('mips',0x80000000)]:
                src=root/(arch+'.bin');raw,sha=fixture(src,arch,base);hashes.append(sha)
                gh=root/(arch+'-gh.json');rz=root/(arch+'-rz.json')
                gh.write_text(json.dumps(ghidra_doc(raw,sha,base)))
                rz.write_text(json.dumps([{'offset':base,'size':len(raw),'name':'fcn.0'}]))
                result=reconcile(src,base,arch,gh,rz)
                self.assertEqual(result['stats'],{'AGREED_ENTRY_AND_EXTENT':1})
                self.assertEqual(result['verification']['native_parity'],'NOT_TESTED')
                self.assertFalse(result['candidates'][0]['native_qualified'])
                self.assertEqual(result['source_sha256'],sha)
            self.assertEqual(len(set(hashes)),3)
    def test_independent_engine_disagreement_is_recorded_not_discarded(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);src=d/'input.bin';raw,sha=fixture(src,'m68k',0)
            gh=d/'gh.json';rz=d/'rz.json';gh.write_text(json.dumps(ghidra_doc(raw,sha,0)))
            rz.write_text(json.dumps([{'offset':0,'size':2},{'offset':2,'size':2}]))
            out=reconcile(src,0,'m68k',gh,rz)
            self.assertEqual(out['stats']['AGREED_ENTRY_DIFFERENT_EXTENT'],1)
            self.assertEqual(out['stats']['RIZIN_ONLY'],1)
    def test_forged_ghidra_instruction_hash_is_fatal(self):
        raw=b'\0\1';sha=hashlib.sha256(raw).hexdigest();doc=ghidra_doc(raw,sha,0)
        doc['functions'][0]['instructions'][0]['bytes_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'byte hash mismatch'):
            parse_ghidra(doc,sha,raw,0)
    def test_claimed_source_hash_does_not_establish_provenance(self):
        raw=b'\0\1';sha=hashlib.sha256(raw).hexdigest();doc=ghidra_doc(raw,'f'*64,0)
        with self.assertRaisesRegex(ValueError,'source identity'):
            parse_ghidra(doc,sha,raw,0)
    def test_outside_source_candidate_quarantined(self):
        funcs,w=parse_rizin([{'offset':4000,'size':4}],0,10)
        self.assertFalse(funcs);self.assertEqual(w[0]['reason'],'OUTSIDE_INPUT_MAP')
    def test_overlapping_ghidra_instructions_are_rejected(self):
        raw=b'\x01\x02\x03';sha=hashlib.sha256(raw).hexdigest();doc=ghidra_doc(raw,sha,0)
        doc['functions'][0]['instructions']=[
            {'address':0,'length':2,'bytes_sha256':hashlib.sha256(raw[:2]).hexdigest()},
            {'address':1,'length':2,'bytes_sha256':hashlib.sha256(raw[1:]).hexdigest()}]
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            parse_ghidra(doc,sha,raw,0)
    def test_stall_plan_not_parity_or_auto_patch(self):
        plan=decide({'status':'SELECTED_IO_DIVERGED','pc_aligned':False,'step_aligned':False,'frame_aligned':False})
        self.assertEqual(plan['next_action'],'CAPTURE_COMMON_BOOT_SOURCE_AND_RESET_ANCHOR')
        self.assertFalse(plan['automatic_source_edit'])

class AuthorizedToolTests(unittest.TestCase):
    def test_allow_root_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);inside=d/'safe';outside=d/'other';inside.mkdir();outside.mkdir()
            r=inside/'rizin';r.write_text('test');o=outside/'rizin';o.write_text('outside')
            self.assertEqual(authorize_tool(r,[inside],'rizin'),r.resolve())
            with self.assertRaisesRegex(ValueError,'outside approved'):
                authorize_tool(o,[inside],'rizin')
            try:
                link=inside/'link';link.symlink_to(o)
            except (OSError,NotImplementedError):pass
            else:
                with self.assertRaisesRegex(ValueError,'outside approved'):
                    authorize_tool(link,[inside],'rizin')
            found=discover([inside]);self.assertEqual(len(found['tools']),1)
            self.assertTrue(found['no_executables_ran'])
    @unittest.skipIf(os.name=='nt','POSIX fake-executable fixture only, not an actual Rizin test')
    def test_runs_authorized_process_for_two_binary_sources(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);tools=root/'tools';tools.mkdir();exe=tools/'rizin'
            exe.write_text('#!/usr/bin/env python3\nimport json\nprint(json.dumps([{"offset":0,"size":4,"name":"synthetic"}]))\n')
            exe.chmod(0o755)
            for arch in ('m68k','mips'):
                src=root/(arch+'.bin');fixture(src,arch,0)
                result=analyze(src,root/(arch+'-job'),arch,0,0,rizin=exe,allow_tool_roots=[tools],timeout=8)
                self.assertEqual(result['status'],'SINGLE_ENGINE_ONLY',result)
                self.assertEqual(json.loads((root/(arch+'-job')/'investigation-plan.json').read_text())['next_action'], 'RUN_INDEPENDENT_SECOND_STATIC_ANALYZER')
                doc=json.loads((root/(arch+'-job')/'reconciliation.json').read_text())
                self.assertEqual(doc['source_sha256'],hashlib.sha256(src.read_bytes()).hexdigest())
                self.assertEqual(doc['stats']['RIZIN_ONLY'],1)
                self.assertEqual(doc['verification']['native_parity'],'NOT_TESTED')
    @unittest.skipIf(os.name=='nt','POSIX fake-executable fixture only')
    def test_missing_required_dual_engine_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);tools=root/'tools';tools.mkdir()
            rz=tools/'rizin';rz.write_text('#!/usr/bin/env python3\nprint("[]")\n');rz.chmod(0o755)
            gh=tools/'analyzeHeadless';gh.write_text('#!/usr/bin/env python3\nimport sys\nsys.exit(3)\n');gh.chmod(0o755)
            src=root/'m68k.bin';fixture(src,'m68k',0)
            result=analyze(src,root/'evidence','m68k',0,0,rz,gh,[tools],8,True)
            self.assertEqual(result['status'],'BLOCKED_DUAL_EVIDENCE',result)
            self.assertFalse((root/'evidence'/'reconciliation.json').exists())
    @unittest.skipIf(os.name=='nt','POSIX fake-executable fixture only')
    def test_tool_output_limit_and_source_mutation_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);tools=root/'tools';tools.mkdir();rz=tools/'rizin'
            rz.write_text('#!/usr/bin/env python3\nimport sys\nsys.stdout.write("A"*3000000)\n');rz.chmod(0o755)
            src=root/'m68k.bin';fixture(src,'m68k',0)
            result=analyze(src,root/'overflow','m68k',0,0,rizin=rz,allow_tool_roots=[tools],timeout=8)
            self.assertEqual(result['status'],'BLOCKED_NO_VALID_EVIDENCE',result)
            self.assertEqual(result['engines']['rizin']['status'],'OUTPUT_LIMIT')
            # Replace with a process that modifies the source, proving the post-run SHA gate.
            rz.write_text('#!/usr/bin/env python3\nimport sys,json,pathlib\nf=pathlib.Path(sys.argv[-1]);f.write_bytes(f.read_bytes()+b"X");print("[]")\n')
            result=analyze(src,root/'mutation','m68k',0,0,rizin=rz,allow_tool_roots=[tools],timeout=8)
            self.assertEqual(result['status'],'BLOCKED_AUTHENTICATION_OR_EXECUTION')
            self.assertIn('Source changed',result['error'])

if __name__=='__main__':unittest.main()

class ArchitecturePolicyTests(unittest.TestCase):
    def test_policy_gate_reports_no_unsupported_qualifications(self):
        from tooling.gates import validate
        from tooling.orchestrator import ROOT
        proof=validate(ROOT,run_tests=False)
        self.assertIn('SYNTHETIC',proof['status'])
        self.assertEqual(proof['real_tool_execution'],'NOT_TESTED')
        self.assertEqual(proof['native_gameplay_parity'],'NOT_TESTED')
        self.assertEqual(len(proof['fixtures']),3)
    def test_policy_gate_fails_if_charter_weakens(self):
        from tooling.gates import validate
        from tooling.orchestrator import ROOT
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            import shutil
            shutil.copytree(ROOT/'tooling',folder/'tooling')
            shutil.copytree(ROOT/'tests',folder/'tests')
            doc=json.loads((ROOT/'PLATFORM_CHARTER.json').read_text())
            doc['release_policy']['source_provenance_required']=False
            (folder/'PLATFORM_CHARTER.json').write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'policy violation'):
                validate(folder,run_tests=False)
