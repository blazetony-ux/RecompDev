"""Versioned, hardware-neutral offline code-discovery contracts.

AbstractFacts carries ISA-labelled constants; CPU providers own register meanings,
while machine providers own address translation and mapping side effects. Static
facts are not execution or semantic equivalence certification.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Any

ANALYSIS_ABI=2

@dataclass(frozen=True)
class Seed:
    pc:int
    reason:str

@dataclass(frozen=True)
class Image:
    profile:str
    cpu:str
    machine:str
    entries:tuple[Seed,...]
    data_offset:int
    data_length:int
    load_address:int=0
    bank_bytes:int=0
    details:dict[str,Any]=field(default_factory=dict)

@dataclass(frozen=True)
class Instruction:
    length:int
    flow:str='next'
    target:int|None=None
    conditional:bool=False
    delay_slots:int=0
    effects:dict[str,Any]=field(default_factory=dict)
    mnemonic:str='unspecified'

@dataclass(frozen=True)
class AbstractFacts:
    """Immutable, deterministically ordered known constants; absent means unknown."""
    pairs:tuple[tuple[str,int],...]=()
    def get(self,name:str)->int|None:
        for k,v in self.pairs:
            if k==name:return v
        return None
    def change(self,*,set_values:dict[str,int]|None=None,clear:tuple[str,...]=())->'AbstractFacts':
        values=dict(self.pairs)
        for name in clear:values.pop(name,None)
        for name,value in (set_values or {}).items():values[name]=value
        return AbstractFacts(tuple(sorted(values.items())))

class Unresolved(Exception):
    """Explicit uncertainty, never silently admitted as qualified code."""
    def __init__(self,reason:str):
        self.reason=reason
        super().__init__(reason)
