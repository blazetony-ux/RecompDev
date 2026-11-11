"""CPU/machine-neutral, bounded progress accounting for live native recovery.

This is controller bookkeeping, not decoding, source mapping, or execution.
The machine adapter supplies a source-attested stopped frontier and only a
verified native activation acknowledgement can complete an attempt.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_RECOVERY_ATTEMPTS = 512

class FrontierError(ValueError):
    """A stable, actionable recovery-lifecycle error token."""

@dataclass(frozen=True)
class Frontier:
    address: int
    physical: int
    mapping: tuple[int, ...]

    @classmethod
    def from_observation(cls, observed: dict) -> 'Frontier':
        """Use only a previously source-attested adapter observation.

        Validation here is CPU-neutral; it intentionally does not assume a
        16-bit program counter, a four-bank SMS mapper, or any CPU ISA.
        """
        address = observed.get('pc')
        physical = observed.get('physical_offset')
        mapping = observed.get('mapper')
        if (type(address) is not int or type(physical) is not int or
            address < 0 or physical < 0 or address > 0xffffffffffffffff or
            physical > 0xffffffffffffffff or not isinstance(mapping, (list, tuple)) or
            len(mapping) > 64 or any(type(x) is not int or x < 0 or
                                   x > 0xffffffffffffffff for x in mapping)):
            raise FrontierError('RECOVERY_FRONTIER_INVALID')
        return cls(address, physical, tuple(mapping))

class RecoveryFrontiers:
    def __init__(self, max_attempts: int):
        if type(max_attempts) is not int or not 1 <= max_attempts <= MAX_RECOVERY_ATTEMPTS:
            raise FrontierError('RECOVERY_BUDGET_INVALID')
        self.max_attempts = max_attempts
        self._attempts: dict[Frontier, int] = {}
        self._confirmed: set[Frontier] = set()

    @property
    def attempts(self) -> int:
        return len(self._attempts)

    @property
    def confirmed(self) -> int:
        return len(self._confirmed)

    def request(self, observation: dict) -> tuple[int, Frontier]:
        """Reserve one new attempt, rejecting a gap we already attempted.

        The caller must validate ROM bytes and the mapping through the machine
        plugin before this method. Failed compilation is NOT marked confirmed.
        """
        frontier = Frontier.from_observation(observation)
        if frontier in self._attempts:
            raise FrontierError('REPEATED_LIVE_GAP_NO_NEW_CODE')
        if self.attempts >= self.max_attempts:
            raise FrontierError('LIVE_RECOVERY_LIMIT')
        index = self.attempts + 1
        self._attempts[frontier] = index
        return index, frontier

    def confirm(self, index: int, frontier: Frontier) -> None:
        """Call only after a source-bound guest activation receipt verifies."""
        if type(index) is not int or self._attempts.get(frontier) != index:
            raise FrontierError('RECOVERY_ACTIVATION_SEQUENCE_MISMATCH')
        if frontier in self._confirmed:
            raise FrontierError('RECOVERY_ACTIVATION_ALREADY_CONFIRMED')
        self._confirmed.add(frontier)
