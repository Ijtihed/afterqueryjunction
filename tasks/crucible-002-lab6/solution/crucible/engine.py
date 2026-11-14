"""ctypes binding for the C simulation core plus the World container."""
from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass, field

EMPTY, WALL, GATE, MAT0, NID, NO_RX = 0, 1, 2, 8, 32, 255
SOLID, POWDER, LIQUID = 0, 1, 2
MAX_TICKS = 4000
MAX_CELLS = 8192

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = None


def _lib():
    global _LIB
    if _LIB is None:
        so = os.path.join(_HERE, "libcore.so")
        src = os.path.join(_HERE, "core.c")
        if not os.path.exists(so) or (
            os.path.exists(src) and os.path.getmtime(src) > os.path.getmtime(so)
        ):
            subprocess.check_call(["cc", "-O2", "-shared", "-fPIC", "-o", so, src])
        _LIB = ctypes.CDLL(so)
        _LIB.cr_settle.restype = ctypes.c_int
    return _LIB


@dataclass
class Physics:
    """Per-id tables. Ids below MAT0 are structural."""
    phase: list = field(default_factory=lambda: [0] * NID)
    grav: list = field(default_factory=lambda: [1] * NID)
    dens: list = field(default_factory=lambda: [0] * NID)
    rx: bytearray = field(default_factory=lambda: bytearray([NO_RX]) * (NID * NID * 2))
    rxneed: bytearray = field(default_factory=lambda: bytearray(NID * NID))

    def add_reaction(self, a: int, b: int, a2: int, b2: int, need_a: int = 0, need_b: int = 0) -> None:
        """need_a / need_b: how many same-kind neighbours a reacting cell must have."""
        self.rx[(a * NID + b) * 2: (a * NID + b) * 2 + 2] = bytes([a2, b2])
        self.rxneed[a * NID + b] = need_a
        if b >= MAT0:
            self.rx[(b * NID + a) * 2: (b * NID + a) * 2 + 2] = bytes([b2, a2])
            self.rxneed[b * NID + a] = need_b

    def _c(self):
        if not hasattr(self, "_cache"):
            self._cache = (
                (ctypes.c_int8 * NID)(*self.phase),
                (ctypes.c_int8 * NID)(*self.grav),
                (ctypes.c_int16 * NID)(*self.dens),
                (ctypes.c_uint8 * len(self.rx)).from_buffer_copy(bytes(self.rx)),
                (ctypes.c_uint8 * len(self.rxneed)).from_buffer_copy(bytes(self.rxneed)),
            )
        return self._cache


@dataclass
class World:
    w: int
    h: int
    cell: bytearray
    gate: bytes  # gate id per cell (0 = none); fixed for the life of the world
    aux: bytearray
    tick: int = 0

    @staticmethod
    def blank(w: int, h: int) -> "World":
        n = w * h
        if n > MAX_CELLS:
            raise ValueError("grid too large")
        return World(w, h, bytearray(n), bytes(n), bytearray((x + y) & 1 for y in range(h) for x in range(w)))

    def copy(self) -> "World":
        return World(self.w, self.h, bytearray(self.cell), self.gate, bytearray(self.aux), self.tick)

    def key(self) -> bytes:
        return bytes(self.cell) + bytes(self.aux) + bytes([self.tick & 1])

    def open_gate(self, g: int) -> int:
        n = 0
        for i, gid in enumerate(self.gate):
            if gid == g and self.cell[i] == GATE:
                self.cell[i] = EMPTY
                n += 1
        return n

    def count(self, mat: int, rect) -> int:
        x0, y0, x1, y1 = rect
        return sum(1 for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if self.cell[y * self.w + x] == mat)


@dataclass
class SettleResult:
    ticks: int
    settled: bool
    frames: list  # list[bytes], one per changing tick (may be truncated)
    reactions: dict  # (a, b) with a <= b -> count


def settle(world: World, phys: Physics, want_frames: bool = False, max_ticks: int = MAX_TICKS) -> SettleResult:
    n = world.w * world.h
    cell = (ctypes.c_uint8 * n).from_buffer(world.cell)
    aux = (ctypes.c_uint8 * n).from_buffer(world.aux)
    ph, gr, de, rx, need = phys._c()
    max_frames = max_ticks if want_frames else 0
    fbuf = (ctypes.c_uint8 * (n * max_frames))() if want_frames else None
    nframes = ctypes.c_int(0)
    settled = ctypes.c_int(0)
    rxcount = (ctypes.c_uint32 * (NID * NID))()
    ticks = _lib().cr_settle(
        world.w, world.h, cell, aux, ph, gr, de, rx, need, world.tick, max_ticks,
        fbuf, max_frames, ctypes.byref(nframes), rxcount, ctypes.byref(settled),
    )
    del cell, aux
    if ticks < 0:
        raise ValueError("bad grid")
    world.tick += ticks
    frames = []
    if want_frames:
        raw = bytes(fbuf)
        frames = [raw[k * n:(k + 1) * n] for k in range(nframes.value)]
    reactions = {}
    for a in range(MAT0, NID):
        for b in [WALL] + list(range(MAT0, NID)):
            c = rxcount[a * NID + b]
            if c:
                reactions[(a, b)] = reactions.get((a, b), 0) + c
    return SettleResult(ticks, bool(settled.value), frames, reactions)
