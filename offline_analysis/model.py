"""Versioned, CPU-neutral contracts for offline source interrogation.

These are static byte-decoding contracts, NOT proof of program reachability,
complete instruction semantics, successful recompilation or gameplay parity.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

ANALYSIS_ABI = 1

@dataclass(frozen=True)
class Seed:
    pc: int
    reason: str

@dataclass(frozen=True)
class Image:
    profile: str
    cpu: str
    machine: str
    entries: tuple[Seed, ...]
    data_offset: int
    data_length: int
    load_address: int = 0
    bank_bytes: int = 0
    details: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Instruction:
    length: int
    flow: str = 'next' # next, jump, branch, call, return, indirect, stop
    target: int | None = None
    conditional: bool = False
    delay_slots: int = 0
    effects: dict[str, Any] = field(default_factory=dict)
    mnemonic: str = 'unspecified'

class Unresolved(Exception):
    """Explicit static-analysis uncertainty; never silently admit a code byte."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)
