#!/usr/bin/env python3
"""No external tools required; verify strict Rizin 0.9.1 aflj compatibility."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis_integration.rizin_compat import normalize_rizin_log, RizinCompatibilityError

W1 = 'WARNING: invalid address from 0x00009d81'
W2 = 'WARNING: invalid address from 0x0002a121'
FUNCTIONS = [{'offset': 0, 'size': 1, 'name': 'fcn.00000000'},
             {'offset': 2, 'size': 190, 'name': 'fcn.00000002'}]


class RizinOutputCompatibilityTests(unittest.TestCase):
    def normalize(self, source, *, log_status='UNPARSABLE_JSON', sha=None):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            log = wd / 'rizin-output.log'
            blob = source if isinstance(source, bytes) else source.encode('utf-8')
            log.write_bytes(blob)
            before = log.read_bytes()
            try:
                audit = normalize_rizin_log(log, wd / 'rizin-aflj.json',
                    wd / 'rizin-compatibility.json', legacy_status=log_status,
                    expected_log_hash=sha or hashlib.sha256(blob).hexdigest())
            except (RizinCompatibilityError, OSError):
                self.assertEqual(log.read_bytes(), before)
                self.assertFalse((wd / 'rizin-aflj.json').exists())
                self.assertFalse((wd / 'rizin-compatibility.json').exists())
                raise
            self.assertEqual(log.read_bytes(), before)
            self.assertEqual(json.loads((wd / 'rizin-compatibility.json').read_text()), audit)
            self.assertEqual(hashlib.sha256((wd / 'rizin-aflj.json').read_bytes()).hexdigest(),
                audit['normalized_sha256'])
            return audit, json.loads((wd / 'rizin-aflj.json').read_text())

    def test_real_windows_rizin_091_erase_line_prefix(self):
        prefix = '\x1b[2K\n' + W1 + '\n' + W2 + '\n'
        audit, records = self.normalize(prefix + json.dumps(FUNCTIONS))
        self.assertEqual(records, FUNCTIONS)
        self.assertEqual(audit['warning_count'], 2)
        self.assertEqual(audit['erase_line_count'], 1)
        self.assertEqual(audit['diagnostic_prefix_bytes'], len(prefix.encode('utf8')))

    def test_direct_provider_accepts_warning_free_json(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            raw = (json.dumps(FUNCTIONS) + '\n').encode()
            log = folder/'rizin-output.log'
            log.write_bytes(raw)
            audit = normalize_rizin_log(log, folder/'rizin-aflj.json',
                folder/'rizin-provider.json', expected_log_hash=hashlib.sha256(raw).hexdigest())
            self.assertEqual(audit['warning_count'], 0)
            self.assertIsNone(audit['historical_parser_status'])
            self.assertEqual(audit['normalization'], 'strict-rizin-aflj-ansi-v2')

    def test_unknown_ansi_sequences_rejected(self):
        for control in ('\x1b[2J', '\x1b[H', '\x1b]0;test\x07', '\x1b[2Kbogus'):
            with self.subTest(control=repr(control)), self.assertRaises(RizinCompatibilityError):
                self.normalize(control + '\n' + W1 + '\n' + json.dumps(FUNCTIONS))

    def test_real_rizin_091_warning_format(self):
        prefix = W1 + '\r\n' + W2 + '\r\n'
        audit, records = self.normalize(prefix + json.dumps(FUNCTIONS))
        self.assertEqual(records, FUNCTIONS)
        self.assertEqual(audit['warning_count'], 2)
        self.assertEqual(audit['historical_parser_status'], 'UNPARSABLE_JSON')
        self.assertEqual(audit['diagnostic_prefix_bytes'], len(prefix.encode()))

    def test_ansi_colored_warnings_with_whitespace(self):
        data = '\x1b[33m' + W1 + '\x1b[0m\n' + W2 + '\n\n  ' + json.dumps(FUNCTIONS) + ' \r\n'
        audit, _ = self.normalize(data)
        self.assertEqual(audit['warning_count'], 2)

    def test_empty_and_large_function_arrays(self):
        _, items = self.normalize(W1 + '\n[]')
        self.assertEqual(items, [])
        medium = [{'offset': x, 'size': 1} for x in range(200)]
        _, items = self.normalize(W1 + '\n' + json.dumps(medium))
        self.assertEqual(len(items), 200)

    def test_wrong_or_unknown_preamble_rejected(self):
        for bad in ('ERROR: failed\n', 'NOTE: unknown\n', W1 + '\nWARNING: bad\n',
                    '\x1b[2J' + W1 + '\n', 'garbage\n', ''):
            with self.subTest(bad=bad), self.assertRaises(RizinCompatibilityError):
                self.normalize(bad + json.dumps(FUNCTIONS))

    def test_trailing_material_and_multiple_arrays_rejected(self):
        for suffix in ('\nERROR: extra', '\n[]', ' {"x":1}', '\nWARNING: invalid address from 0x2'):
            with self.subTest(suffix=suffix), self.assertRaises(RizinCompatibilityError):
                self.normalize(W1 + '\n' + json.dumps(FUNCTIONS) + suffix)

    def test_invalid_json_and_function_record_rejected(self):
        for blob in ('[', '{}', '[true]', '[null]', '[{"offset":0}]',
                     '[{"offset":true,"size":1}]', '[{"offset":-1,"size":1}]',
                     '[{"offset":0,"size":0}]', '[{"offset":0,"size":1e5}]',
                     '[{"offset":0,"size":NaN}]',
                     '[{"offset":0,"offset":1,"size":1}]',
                     '[{"offset":0,"size":1,"confidence":1e999}]',
                     '[{"offset":18446744073709551616,"size":1}]'):
            with self.subTest(blob=blob), self.assertRaises(RizinCompatibilityError):
                self.normalize(W1 + '\n' + blob)

    def test_rejects_function_limit(self):
        raw = json.dumps([{'offset':n,'size':1} for n in range(20_001)])
        with self.assertRaisesRegex(RizinCompatibilityError, 'LIST_INVALID'):
            self.normalize(W1 + '\n' + raw)

    def test_log_size_hash_invalid_utf8_and_state(self):
        for kwargs in ({'sha': '0'*64}, {'log_status':'TOOL_ERROR'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(RizinCompatibilityError):
                self.normalize(W1+'\n[]', **kwargs)
        with self.assertRaises(RizinCompatibilityError):
            self.normalize((W1+'\n').encode()+b'\xff[]')
        with self.assertRaises(RizinCompatibilityError):
            self.normalize((W1+'\n').encode()+b' '*8193+b'[]')

    def test_unrelated_architecture_offsets_not_rejected(self):
        # Parser never assumes Z80 width or Master System ROM addresses.
        sample = [{'offset':0x100000000,'size':0x10000}]
        _, data = self.normalize(W1 + '\n'+json.dumps(sample))
        self.assertEqual(data, sample)


if __name__ == '__main__':
    unittest.main()
