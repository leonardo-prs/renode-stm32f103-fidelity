"""Decodificador do snapshot ABI v2 (inc/fidelity.h). Somente stdlib.

Layout: header (32 words) | rows[row_capacity][8] | trace[3][trace_capacity][4].
As capacidades vêm do header; nada é presumido além do que o C declara.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = 0x46494432          # "FID2"
VERSION = 2
WRITERS = ("MAIN", "IRQ_A", "IRQ_B")
STATES = {0: "INIT", 1: "RUNNING", 2: "DONE", 3: "FAILED"}
ERRORS = {0x80000000: "ROWS_FULL", 0x40000000: "TIMEOUT", 0x20000000: "CHECK"}

HEADER_FIELDS = (
    "magic version scenario variant state error core_hz seed row_capacity "
    "row_count trace_capacity"
).split()
CONTEXT_FIELDS = (
    "cpuid rcc_cr rcc_cfgr flash_acr dwt_ctrl aircr dbgmcu_cr observer_ticks end_ticks"
).split()


class SnapshotError(ValueError):
    """Snapshot inconsistente com a ABI v2 (nunca analisar um destes)."""


@dataclass
class TraceEntry:
    writer: int
    index: int
    ticks: int
    event: int
    trial: int
    arg: int


@dataclass
class Snapshot:
    header: dict
    rows: list[tuple[int, ...]]
    trace: list[TraceEntry] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.header["state"] == 2 and self.header["error"] == 0

    def rows_for(self, condition: int) -> list[tuple[int, ...]]:
        return [r for r in self.rows if r[1] == condition]

    def events(self, writer: int | None = None) -> list[TraceEntry]:
        return [e for e in self.trace if writer is None or e.writer == writer]


def expected_size(row_capacity: int, trace_capacity: int) -> int:
    return 128 + row_capacity * 32 + len(WRITERS) * trace_capacity * 16


def decode(raw: bytes, *, strict: bool = True) -> Snapshot:
    if len(raw) < 128:
        raise SnapshotError(f"snapshot muito curto: {len(raw)} B")
    words = struct.unpack_from("<32I", raw)
    header = dict(zip(HEADER_FIELDS, words[:11]))
    header["trace_count"] = list(words[11:14])
    header["trace_drop"] = list(words[14:17])
    header.update(zip(CONTEXT_FIELDS, words[17:26]))
    header["reserved"] = list(words[26:32])
    if header["magic"] != MAGIC or header["version"] != VERSION:
        raise SnapshotError(f"magic/version inválidos: {header['magic']:#x}/{header['version']}")
    rc, tc = header["row_capacity"], header["trace_capacity"]
    if len(raw) != expected_size(rc, tc):
        raise SnapshotError(f"tamanho {len(raw)} != {expected_size(rc, tc)} (rows={rc}, trace={tc})")
    if header["row_count"] > rc or any(c > tc for c in header["trace_count"]):
        raise SnapshotError("contagem excede capacidade")
    if strict:
        if header["state"] not in (2, 3):
            raise SnapshotError(f"estado não terminal: {STATES.get(header['state'])}")
        if (header["state"] == 2) != (header["error"] == 0):
            raise SnapshotError("estado/erro inconsistentes")
        if any(header["reserved"]):
            raise SnapshotError("campos reservados não nulos")
    rows = [struct.unpack_from("<8I", raw, 128 + 32 * i) for i in range(header["row_count"])]
    base = 128 + 32 * rc
    trace = []
    for w in range(len(WRITERS)):
        for i in range(header["trace_count"][w]):
            t, ev, tr, arg = struct.unpack_from("<4I", raw, base + (w * tc + i) * 16)
            trace.append(TraceEntry(w, i, t, ev, tr, arg))
    if strict:
        # Armazenamento não usado deve continuar zerado (prova de não-corrupção).
        if any(raw[128 + 32 * header["row_count"]:base]):
            raise SnapshotError("linhas não usadas não-zero")
        for w in range(len(WRITERS)):
            start = base + (w * tc + header["trace_count"][w]) * 16
            if any(raw[start:base + (w + 1) * tc * 16]):
                raise SnapshotError(f"trace não usado não-zero no canal {WRITERS[w]}")
    header["error_names"] = [n for b, n in ERRORS.items() if header["error"] & b]
    return Snapshot(header, rows, trace)


def ticks_delta(a: int, b: int) -> int:
    """b − a em aritmética de 32 bits (CYCCNT pode dar a volta)."""
    return (b - a) & 0xFFFFFFFF
