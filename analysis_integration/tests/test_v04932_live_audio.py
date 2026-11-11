"""v0.4.9.32: native live audio is no longer silently disabled."""
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from analysis_integration.live_session import live_audio_backend,record_audio_evidence,RecoveryBlocked,main

class LiveAudioTests(unittest.TestCase):
    def test_live_defaults_to_speaker_not_null(self):
        self.assertEqual(live_audio_backend('auto'), 'speaker')
        self.assertEqual(live_audio_backend('auto',True), 'capture')
    def test_explicit_capture_and_null(self):
        self.assertEqual(live_audio_backend('capture'),'capture')
        self.assertEqual(live_audio_backend('null'),'null')
    def test_invalid_and_synthetic_speaker_fail_closed(self):
        for name in ('','headphone','SPEAKER'):
            with self.assertRaisesRegex(RecoveryBlocked,'LIVE_AUDIO_BACKEND_INVALID'):
                live_audio_backend(name)
        with self.assertRaisesRegex(RecoveryBlocked,'SYNTHETIC_TEST_REQUIRES_NO_AUDIO_DEVICE'):
            live_audio_backend('speaker',True)
    def test_capture_observed_pcm_and_wav_hash(self):
        with tempfile.TemporaryDirectory() as t:
            game=Path(t)/'game'
            wav=Path(str(game)+'.wav')
            with wave.open(str(wav),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100)
                w.writeframes(b'\x01\x00'*100)
            d=record_audio_evidence({'audio_backend':'capture','audio_samples':100,
                'audio_nonzero_samples':17},game,'capture')
            self.assertTrue(d['audible_pcm_observed'])
            self.assertEqual(d['wav_bytes'],244)
            self.assertEqual(len(d['wav_sha256']),64)
            self.assertFalse(d['hardware_parity_qualified'])
    def test_mismatched_wav_sample_count_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            game=Path(t)/'game'
            with wave.open(str(game)+'.wav','wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100)
                w.writeframes(b'\x01\x00'*20)
            with self.assertRaisesRegex(RecoveryBlocked,'NATIVE_AUDIO_WAV_METRICS_MISMATCH'):
                record_audio_evidence({'audio_backend':'capture','audio_samples':100,
                     'audio_nonzero_samples':5},game,'capture')
    def test_null_cannot_masquerade_as_audio(self):
        with tempfile.TemporaryDirectory() as t:
            d=record_audio_evidence({'audio_backend':'null','audio_samples':120,
                'audio_nonzero_samples':0},Path(t)/'game','null')
            self.assertFalse(d['audible_pcm_observed'])
            self.assertNotIn('wav_sha256',d)
    def test_missing_wav_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(RecoveryBlocked,'NATIVE_AUDIO_WAV_MISSING'):
                record_audio_evidence({'audio_backend':'capture','audio_samples':100,
                     'audio_nonzero_samples':5},Path(t)/'game','capture')
    def test_native_audio_backend_or_metrics_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'game'
            with self.assertRaisesRegex(RecoveryBlocked,'NATIVE_AUDIO_BACKEND_MISMATCH'):
                record_audio_evidence({'audio_backend':'null','audio_samples':0,'audio_nonzero_samples':0},p,'speaker')
            for n in (-1,101,True,'5'):
                with self.subTest(n=n):
                    with self.assertRaisesRegex(RecoveryBlocked,'NATIVE_AUDIO_METRICS_INVALID'):
                        record_audio_evidence({'audio_backend':'null','audio_samples':100,'audio_nonzero_samples':n},p,'null')
    def test_main_parses_explicit_audio_without_starting_session(self):
        import argparse
        with patch('analysis_integration.live_session.run',return_value=0) as run:
            self.assertEqual(main(['play','test.sms','--audio','capture','--controller-exe','fake','--source-root','fake']),0)
            self.assertEqual(run.call_args[0][0].audio,'capture')
