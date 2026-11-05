"""Opt-in guest-cycle input capture installed into a staged native project.

The generated CPU/translator source and frozen legacy source are NEVER edited.
This adapter instruments only the disposable generated interactive frontend.
"""
from __future__ import annotations
from pathlib import Path

MARKER = 'RECOMPDEV_GUEST_INPUT_TAP_V1'
OLD = 'if(input==hw::InputBackend::Live)runtime.record_input(runtime.cycles(),{0,view.buttons(),0,0});'
NEW = '''if(input==hw::InputBackend::Live){
    const auto guest_cycle=runtime.cycles();
    const auto guest_buttons=view.buttons();
    runtime.record_input(guest_cycle,{0,guest_buttons,0,0});
    recomp::hw::GuestInputTap::instance().sample(guest_cycle,0,guest_buttons);
   } // RECOMPDEV_GUEST_INPUT_TAP_V1'''

def instrument(project:Path)->dict:
    project=Path(project)
    path=project/'interactive.cpp'
    if not path.is_file():
        raise ValueError('Native project has no interactive frontend for guest-cycle capture')
    src=path.read_text(encoding='utf8')
    if MARKER in src:
        return {'status':'ALREADY_INSTRUMENTED'}
    if src.count(OLD)!=1:
        raise ValueError('Native input callback changed: refusing unverified instrumentation')
    if '#include "live_sms.hpp"' not in src:
        raise ValueError('Native input frontend missing expected include anchor')
    text=src.replace('#include "live_sms.hpp"',
                     '#include "live_sms.hpp"\n#include "hardware/rd_guest_input_tap.hpp"',1).replace(OLD,NEW,1)
    path.write_text(text,encoding='utf8')
    return {'status':'INSTRUMENTED','cpu_guest_source_unchanged':True,
            'modified_frontend':'interactive.cpp', 'replay_schema':'RECOMP_INPUT_CYCLES_V1'}
