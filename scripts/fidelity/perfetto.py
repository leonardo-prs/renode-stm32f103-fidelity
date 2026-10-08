"""Exporta o trace de um snapshot para Chrome Trace Event JSON (Perfetto UI).

Um processo por ambiente (HW, cada config Renode), uma thread por canal
escritor (MAIN/IRQ_A/IRQ_B). BEGIN/END viram spans; demais eventos, instantes.
Eixo: µs = ticks ÷ 8 — no HW são ciclos HCLK a 8 MHz; no Renode, ticks do
DWT virtual. O rótulo do domínio vai em `metadata`; não é tempo de parede.
Abrir em https://ui.perfetto.dev (Open trace file).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import abi

TICKS_PER_US = 8.0


def events_for(snap: abi.Snapshot, pid: int, cond_names: dict[int, str]) -> list[dict]:
    out = []
    for w, name in enumerate(abi.WRITERS):
        out.append({"ph": "M", "pid": pid, "tid": w, "name": "thread_name", "args": {"name": name}})
    entries = sorted(snap.trace, key=lambda e: (e.writer, e.index))
    base = min((e.ticks for e in entries), default=0)
    for e in entries:
        ts = ((e.ticks - base) & 0xFFFFFFFF) / TICKS_PER_US
        common = {"pid": pid, "tid": e.writer, "ts": ts,
                  "args": {"trial": e.trial, "arg": e.arg, "ticks": e.ticks}}
        if e.event == abi_ev("BEGIN"):
            out.append({**common, "ph": "B", "name": cond_names.get(e.arg, f"cond {e.arg}")})
        elif e.event == abi_ev("END"):
            out.append({**common, "ph": "E"})
        else:
            out.append({**common, "ph": "i", "s": "t", "name": f"ev 0x{e.event:x}"})
    return out


def abi_ev(name: str) -> int:
    return {"BOOT": 1, "BEGIN": 2, "END": 3}[name]


def write(path: Path, fw, runs_by_tag: dict) -> None:
    events = []
    for pid, (tag, run) in enumerate(runs_by_tag.items(), start=1):
        events.append({"ph": "M", "pid": pid, "name": "process_name",
                       "args": {"name": f"{fw.name} · {tag}"}})
        events.extend(events_for(run.snap, pid, fw.conditions))
    doc = {"traceEvents": events, "displayTimeUnit": "ns",
           "metadata": {"firmware": fw.name, "time_axis": "µs = ticks / 8",
                        "hw_ticks": "ciclos HCLK (DWT CYCCNT)",
                        "renode_ticks": "DWT derivado do tempo virtual (não ciclos)"}}
    path.write_text(json.dumps(doc))
