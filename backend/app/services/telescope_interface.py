"""
Abstract contract for "a telescope we can command and read state from".

`TelescopeSimulator` (this stage) is the only implementation right now.
A real hardware adapter (e.g. wrapping ASCOM/INDI) would implement this
same interface and could be swapped in via `get_telescope_backend()`
without touching any API route — routes only ever depend on
`TelescopeInterface`, never on `TelescopeSimulator` directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TelescopeState:
    telescope_id: int
    ra_deg: float
    dec_deg: float
    altitude_deg: float
    azimuth_deg: float
    tracking: bool
    slewing: bool
    dome_state: str  # "closed" | "opening" | "open" | "closing"
    camera_state: str  # "idle" | "exposing" | "reading_out" | "error"
    current_target_id: int | None
    is_simulated: bool


class TelescopeInterface(ABC):
    @abstractmethod
    def get_status(self, telescope_id: int) -> TelescopeState: ...

    @abstractmethod
    def slew_to(self, telescope_id: int, ra_deg: float, dec_deg: float, target_id: int | None = None) -> TelescopeState: ...

    @abstractmethod
    def stop_tracking(self, telescope_id: int) -> TelescopeState: ...

    @abstractmethod
    def start_tracking(self, telescope_id: int) -> TelescopeState: ...

    @abstractmethod
    def open_dome(self, telescope_id: int) -> TelescopeState: ...

    @abstractmethod
    def close_dome(self, telescope_id: int) -> TelescopeState: ...

    @abstractmethod
    def park(self, telescope_id: int) -> TelescopeState: ...
