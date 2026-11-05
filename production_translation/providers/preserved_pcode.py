"""Production translation provider v0.1.0: call the ENTIRE original generator.

No reduced rewrite, opcode shortlist or fabricated translation; the original
physical-bank verifier, P-code semantics and native C++ emitters are reused.
"""

def generate_project(document, rom, output, overlays=()):
    from nativepilot.generator import generate_project as original_generator
    return original_generator(document, rom, output, overlays)
