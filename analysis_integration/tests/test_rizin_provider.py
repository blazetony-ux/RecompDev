#!/usr/bin/env python3
"""Direct Rizin provider contract tests; no real ROM/tool installation required."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis_integration.rizin_provider import (execute_rizin, RizinProviderError,
                                                  ARCHITECTURES, SCHEMA)
from analysis_integration.tool_authorization import authorize_tool, ToolAuthorizationError

WARNING = b'WARNING: invalid address from 0x00009d81\n'
PREFIX = b'\x1b[2K\n' + WARNING
AFLJ = b'[{' + b'"offset": 0, "size": 2, "name":"test"' + b'}]\n'


class RizinProviderTests(unittest.TestCase):
    def setup_fixture(self, folder: Path):
        tools = folder / 'tools'
        tools.mkdir()
        executable = tools / ('rizin.exe' if os.name == 'nt' else 'rizin')
        executable.write_bytes(b'test-executable')
        source = folder / 'unrelated-binary.bin'
        source.write_bytes(b'\x01\x02\x03\x04')
        workspace = folder / 'analysis'
        workspace.mkdir()
        return executable, source, workspace

    def call_stub(self, response: bytes, *, status='EXITED', return_code=0, isa='z80'):
        with tempfile.TemporaryDirectory() as td:
            executable, source, workspace = self.setup_fixture(Path(td))
            seen = []
            def fake_runner(argv, timeout, logfile):
                seen.append(argv)
                logfile.write_bytes(response)
                return {'status':status, 'return_code':return_code,
                        'log_sha256':hashlib.sha256(response).hexdigest(),
                        'log_bytes':len(response)}
            with mock.patch('analysis_integration.rizin_provider._run_bounded', side_effect=fake_runner):
                try:
                    result = execute_rizin(executable, source, 0, isa, workspace, 25)
                except RizinProviderError:
                    self.assertEqual((workspace/'rizin-output.log').read_bytes(), response)
                    self.assertFalse((workspace/'rizin-aflj.json').exists())
                    raise
            self.assertEqual(result['schema'],SCHEMA)
            self.assertEqual(result['historical_runner_used'],False)
            self.assertEqual(result['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual((workspace/'rizin-output.log').read_bytes(),response)
            audit=json.loads((workspace/'rizin-provider.json').read_text())
            self.assertEqual(audit['original_log_sha256'],result['log_sha256'])
            self.assertEqual(result['function_count'],1)
            return result, seen[0], audit

    def test_real_windows_prefix_and_own_provider_audit(self):
        result, argv, audit = self.call_stub(PREFIX + AFLJ)
        self.assertEqual(result['warning_count'],1)
        self.assertEqual(audit['erase_line_count'],1)
        self.assertEqual(result['backend'],'recompdev-owned-rizin-v1')
        self.assertIn('aflj',argv)
        self.assertIn('-N',argv)
        self.assertIn('-A',argv)
        self.assertIn('z80',argv)

    def test_compat_023_exact_windows_erase_cr_boundary(self):
        # Alex Kidd and Bank Panic both emitted b"\x1b[2K\r[{...}]" on Windows.
        # The regression is the exact five-byte prefix, not an LF substitute.
        raw_prefix = bytes.fromhex('1B5B324B0D')
        self.assertEqual(raw_prefix, b'\x1b[2K\r')
        for isa in ARCHITECTURES:
            with self.subTest(isa=isa):
                result, _, audit = self.call_stub(raw_prefix + AFLJ, isa=isa)
                self.assertEqual(result['function_count'], 1)
                self.assertEqual(result['warning_count'], 0)
                self.assertEqual(audit['erase_line_count'], 1)
                self.assertEqual(audit['diagnostic_prefix_bytes'], 5)
                self.assertEqual(audit['original_log_sha256'],
                                 hashlib.sha256(raw_prefix + AFLJ).hexdigest())

    def test_compat_023_rejects_unknown_cr_framing(self):
        for invalid in (b'\r' + AFLJ,
                        b'\x1b[2J\r' + AFLJ,
                        b'\x1b[1K\r' + AFLJ,
                        b'\x1b[2K\x1b[0m\r' + AFLJ,
                        b'\x1b[2K\r' + AFLJ + b'invalid',
                        b'\x1b[2K\r[{"offset":0,"offset":2,"size":3}]',
                        b'\x1b[2K\r[{"offset":0,"size":0}]',
                        b'\x1b[2K\r[{"offset":0,"size":2}]\n[{}]'):
            with self.subTest(blob=invalid[:24]), self.assertRaisesRegex(RizinProviderError, 'RIZIN_OUTPUT_REJECTED'):
                self.call_stub(invalid)

    def test_clean_json_and_cross_isa_cli(self):
        for isa, (arch, bits) in ARCHITECTURES.items():
            with self.subTest(isa=isa):
                result,argv,audit=self.call_stub(AFLJ,isa=isa)
                self.assertEqual(result['warning_count'],0)
                self.assertEqual(audit['erase_line_count'],0)
                self.assertEqual(argv[argv.index('-a')+1],arch)
                self.assertEqual(argv[argv.index('-b')+1],bits)

    def test_unknown_diagnostics_fail_closed_preserve_raw(self):
        for blob in (b'ERROR: failed\n' + AFLJ, b'\x1b[2J\n' + AFLJ,
                     PREFIX + AFLJ + b'garbage', WARNING + b'[{"offset":0}]'):
            with self.subTest(blob=blob[:20]),self.assertRaisesRegex(RizinProviderError,'RIZIN_OUTPUT_REJECTED'):
                self.call_stub(blob)

    def test_nonzero_exit_and_timeout_do_not_normalize(self):
        for status,code in [('TOOL_ERROR',1),('TIMEOUT',-1),('OUTPUT_LIMIT',-1)]:
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as td:
                    executable,source,workspace=self.setup_fixture(Path(td))
                    def run(argv, timeout, log):
                        log.write_bytes(AFLJ)
                        return {'status':status,'return_code':code,
                                'log_sha256':hashlib.sha256(AFLJ).hexdigest(),
                                'log_bytes':len(AFLJ)}
                    with mock.patch('analysis_integration.rizin_provider._run_bounded',side_effect=run):
                        out=execute_rizin(executable,source,0,'z80',workspace,20)
                    self.assertEqual(out['status'],status)
                    self.assertFalse((workspace/'rizin-aflj.json').exists())
                    self.assertTrue((workspace/'rizin-process.json').exists())

    def test_explicit_tool_authorization(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            exe,_,_=self.setup_fixture(folder)
            self.assertEqual(authorize_tool(exe,(folder/'tools',),'rizin'),exe.resolve())
            for roots,kind in (((), 'rizin'), ((folder,), 'unknown'), ((folder/'nope',), 'rizin')):
                with self.subTest(roots=roots,kind=kind),self.assertRaises((ToolAuthorizationError,OSError)):
                    authorize_tool(exe,roots,kind)
            outside=folder/'other';outside.mkdir()
            with self.assertRaises(ToolAuthorizationError):
                authorize_tool(exe,(outside,),'rizin')

    def test_rejects_unqualified_arguments_and_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            exe,src,workspace=self.setup_fixture(Path(td))
            for base,isa,timeout in ((True,'z80',30),(-1,'z80',30),(0,'other',30),(0,'z80',0)):
                with self.subTest(base=base,isa=isa,timeout=timeout),self.assertRaises(RizinProviderError):
                    execute_rizin(exe,src,base,isa,workspace,timeout)
            (workspace/'rizin-output.log').write_bytes(b'old evidence')
            with self.assertRaisesRegex(RizinProviderError,'WORKSPACE_NOT_EMPTY'):
                execute_rizin(exe,src,0,'z80',workspace,20)

    @unittest.skipIf(os.name=='nt','Windows subprocess tested by native controller mock executable')
    def test_actual_bounded_subprocess_and_raw_log(self):
        with tempfile.TemporaryDirectory() as td:
            exe,src,workspace=self.setup_fixture(Path(td))
            exe.write_text('#!/usr/bin/env python3\nimport sys\nsys.stdout.buffer.write(' +
                           repr(PREFIX+AFLJ) + ')\n')
            exe.chmod(0o755)
            result=execute_rizin(exe,src,0,'mips',workspace,15)
            self.assertEqual(result['status'],'EXITED')
            self.assertEqual(result['function_count'],1)
            self.assertEqual((workspace/'rizin-output.log').read_bytes(),PREFIX+AFLJ)


if __name__=='__main__':
    unittest.main()
