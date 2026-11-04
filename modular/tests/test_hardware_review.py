"""Portable hardware review regression coverage (two unrelated synthetic captures)."""
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from modular.hardware_review import analyze_evidence,write_png,read_png,read_ppm,compare_image
from modular.asset_decoders.sms import decode_tile,decode_cram


def make_fixture(root,red=False):
    folder=root/'recovery/round-00/sessions/attempt-01/frame-00004'
    folder.mkdir(parents=True)
    img=bytes(([255,0,0] if red else [0,0,255])*64)
    (folder/'native-frame.ppm').write_bytes(b'P6\n8 8\n255\n'+img)
    with wave.open(str(folder/'native-frame.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100)
        w.writeframes(b'\x00\x00'*10 if red else b'\x00\x00\x01\x00'*5)
    frame_hardware=[]
    for n in range(1,5):
        frame_hardware.append({'frame':n,'guest_cycles':n*59659,'steps':n*4100,
           'irqs':n//2,'vdp_writes':n*50,'psg_writes':11,
           'cram_writes':n*4,'palette_nonzero_bytes':1})
    (folder/'continuous-session.json').write_text(json.dumps({
        'frames':4,'status':'FRAME_BUDGET_REACHED','native_steps':16400,
        'guest_psg_writes':11,'audio_nonzero_samples':0 if red else 5,
        'vblank_events':4,'maskable_interrupts':2,'frame_hashes':[1,1,2,2],
        'frame_hardware':frame_hardware}))
    return folder


class TestHardwareReview(unittest.TestCase):
    def test_no_source_buffers_no_false_tile_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);make_fixture(p/'a',red=True)
            result=analyze_evidence(p/'a',p/'out')
            self.assertEqual(result['asset_recovery']['status'],'RAW_VRAM_REQUIRED')
            self.assertEqual(result['timing']['frames_with_telemetry'],4)
            self.assertEqual(len(result['capture_images']),1)
            self.assertEqual(result['audio_captures'][0]['audio']['status'],'SILENT_PCM')
            self.assertEqual(read_png(p/'out'/result['capture_images'][0]['png'])[0:2],(8,8))
            self.assertTrue((p/'out/hardware-timeline.csv').is_file())
            self.assertIn('PSG_WRITES_BUT_SILENT_PCM',result['issues'][0])
    def test_actual_vram_cram_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);make_fixture(p/'b',red=False)
            vr=bytearray(16384)
            for i in range(8):vr[i*4]=0x80  # left column is color 1
            (p/'b/hardware-state-vram.bin').write_bytes(vr)
            (p/'b/hardware-state-cram.bin').write_bytes(bytes([0,3]+[0]*30))
            result=analyze_evidence(p/'b',p/'out')
            self.assertEqual(result['asset_recovery']['patterns'],512)
            self.assertEqual(result['asset_recovery']['distinct_tile_patterns'],2)
            self.assertEqual(result['asset_recovery']['status'],'EXPORTED_SOURCE_VRAM')
            self.assertEqual(decode_tile(vr[:32])[:8],[1,0,0,0,0,0,0,0])
            self.assertEqual(decode_cram(bytes([3]+[0]*31))[0],(255,0,0))
            self.assertTrue((p/'out/assets/sms-tiles-palette0.png').is_file())
            self.assertEqual(result['audio_captures'][0]['audio']['status'],'PCM_ACTIVITY')
    def test_reference_image_exact_vs_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);f=make_fixture(p/'a')
            native=f/'native-frame.ppm'
            w,h,rgb=read_ppm(native)
            write_png(p/'ref.png',w,h,rgb)
            identical=analyze_evidence(p/'a',p/'equal',reference_image=p/'ref.png')
            self.assertEqual(identical['reference_image']['status'],'PIXEL_EXACT_MATCH')
            write_png(p/'different.png',w,h,bytes([255,0,0])*64)
            different=analyze_evidence(p/'a',p/'diff',reference_image=p/'different.png')
            self.assertEqual(different['reference_image']['pixels_different'],64)
            self.assertTrue((p/'diff/pixel-difference.png').is_file())
    def test_reference_timing_diff_and_two_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            first=make_fixture(p/'first',True);second=make_fixture(p/'second',False)
            a=json.loads((first/'continuous-session.json').read_text())
            b=json.loads((second/'continuous-session.json').read_text())
            b['frame_hardware'][2]['guest_cycles']+=2
            (p/'external-reference.json').write_text(json.dumps(b))
            r1=analyze_evidence(p/'first',p/'r1',reference_session=p/'external-reference.json')
            r2=analyze_evidence(p/'second',p/'r2')
            self.assertEqual(r1['reference_timing']['status'],'TELEMETRY_DIFFS')
            self.assertEqual(r2['reference_image']['status'],'NOT_PROVIDED')
            self.assertEqual(r2['independent_gameplay_parity'],'NOT_ESTABLISHED')
    def test_ppm_and_png_errors_are_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);write_png(p/'a.png',1,1,bytes([0,0,0]))
            self.assertEqual(read_png(p/'a.png'),(1,1,bytes([0,0,0])))
            (p/'bad.ppm').write_bytes(b'P6\n1 1\n255\n')
            with self.assertRaises(ValueError):read_ppm(p/'bad.ppm')
            with self.assertRaises(FileNotFoundError):read_png(p/'missing.png')

if __name__=='__main__':unittest.main()
