import unittest
from nativecore.reference_event_comparison import compare_reference_native

S='a'*64
SUMMARY={'metadata':{'rom_sha256':S},'trace':{'status':'COMPLETE_CARTRIDGE_EXECUTION_OBSERVATION',
        'cartridge_cpu_execution':[{'pc':173}]}}
class ReferenceEventComparisonTests(unittest.TestCase):
    def test_port_read_ram_and_cram(self):
        m=[{'type':'io_read','port':221,'pc':19,'value':63},
           {'type':'io_write','subtype':'vdp_control','pc':0x1078,'frame':93,'value':0},
           {'type':'io_write','subtype':'vdp_control','pc':0x107d,'frame':93,'value':0xc0},
           {'type':'io_write','subtype':'vdp_data','pc':0x1082,'frame':93,'value':42},
           {'type':'ram_write','address':0xc006,'pc':0x228,'value':129},
           {'type':'ram_write','address':0xc006,'pc':0x2b0,'value':193}]
        n=[{'kind':'INPUT_READ','address':221,'pc':19,'value':255},
           {'kind':'CRAM_WRITE','step':1,'address':0,'pc':0x1082,'value':0},
           {'kind':'RAM_WATCH_WRITE','address':0xc006,'pc':0xfb,'value':128}]
        r=compare_reference_native(m,n,[],S,SUMMARY)
        self.assertEqual(r['matching_guest_pc_input_mismatches'][0]['native'],'0xFF')
        self.assertEqual(r['mame_cram']['first_nonzero']['value'],42)
        self.assertIn('WATCHED_RAM_STATE_SEQUENCE_DIFFERS:0xC006',r['findings'])
        self.assertEqual(r['cpu_parity'],'NOT_ESTABLISHED')
    def test_fail_closed_on_rom_mismatch(self):
        with self.assertRaises(ValueError):compare_reference_native([],[],[],S,{'metadata':{'rom_sha256':'b'*64},'trace':SUMMARY['trace']})
    def test_command_latch_vram_not_palette(self):
        m=[{'type':'io_write','subtype':'vdp_control','pc':1,'frame':1,'value':0},
           {'type':'io_write','subtype':'vdp_control','pc':2,'frame':1,'value':0x40},
           {'type':'io_write','subtype':'vdp_data','pc':3,'frame':1,'value':42}]
        r=compare_reference_native(m,[],[],S,SUMMARY)
        self.assertEqual(r['mame_cram']['writes'],0)
if __name__=='__main__': unittest.main()
