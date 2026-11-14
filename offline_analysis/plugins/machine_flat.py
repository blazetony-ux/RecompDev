"""Address mapping for flat cartridge and load-addressed executable images.

Machine-neutral implementation: address window is supplied by the format plugin.
"""
from offline_analysis.model import Unresolved
ANALYSIS_ABI=2

def initial(image): return ()
def key(state): return ''
def resolve(image,pc,state):
    offset=pc-image.load_address
    if offset<0 or offset>=image.data_length:
        raise Unresolved('ADDRESS_NOT_IN_LOADED_SOURCE')
    return image.data_offset+offset

def transition(image,instruction,state,registers): return state,()
def inventory(image,data):
    return [{'id':'loaded-code-window','start':image.data_offset,'bytes':image.data_length,
             'entry':image.entries[0].pc,'role':'potential-executable-source'}]
def probes(image): return ()
