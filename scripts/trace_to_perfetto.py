#!/usr/bin/env python3
"""CSV do tracer DWT (inc/trace.h) -> Chrome Trace Events (ui.perfetto.dev).

Entrada: CSV com `cycles,event_id` (event_id decimal ou 0x..; linhas `#`
sao comentarios; primeira linha nao-numerica tratada como header e ignorada).
As linhas devem estar em ordem cronologica (mais antigo -> mais novo;
reconstruir a ordem do ring via trace_w antes de gerar o CSV). O script
desenrola apenas o wrap de 32 bits do CYCCNT, nao a ordem do ring.

Pares enter/exit viram spans (ph=X com dur); demais IDs viram instantes
(ph=I). Lanes: tid 10=TIM2, 11=HIGH/EXTI-TIM3, 12=USART, 1=main/marks.

Exemplo:
    scripts/trace_to_perfetto.py build/c2/trace.csv --cpu-mhz 8 --out build/c2/trace.perfetto.json
    # upload do JSON em https://ui.perfetto.dev ("Open trace file")
"""

import argparse
import json
import sys

MASK32 = 0xFFFFFFFF

# enter_id: (exit_id, nome do span, tid). IDs de inc/trace.h.
# S1 usa 7 pares enter/exit (B1..B8); S3 mapeado por ISR (TIM2=HIGH prio2,
# TIM3=LOW prio12) — ver nota L/H em inc/trace.h.
PAIRS = {
    0x01: (0x02, "B1", 1),
    0x03: (0x04, "B23", 1),
    0x05: (0x06, "B4", 1),
    0x07: (0x08, "B5", 1),
    0x09: (0x0A, "B6", 1),
    0x0B: (0x0C, "B7", 1),
    0x0D: (0x0E, "B8", 1),
    0x10: (0x11, "TIM2", 10),
    0x12: (0x13, "WFI", 1),
    0x20: (0x21, "TIM2", 10),
    0x22: (0x23, "TIM3", 11),
}

EXIT = {exit_id: (enter_id, name, tid) for enter_id, (exit_id, name, tid) in PAIRS.items()}

# id: (nome, tid) — eventos sem par viram instantes na lane indicada.
MARKS = {
    0x00: ("BOOT", 1),
    0xFE: ("ERROR", 1),
    0xFF: ("WRAP_RESYNC", 1),
    0x24: ("SWEEP", 1),
    0x30: ("USART_TX", 12),
    0x31: ("USART_RX", 12),
    0x32: ("USART_UIF_POLL", 12),
    0x33: ("USART_TIM2_BG", 12),
}

TID_NAMES = {
    1: "main/marks",
    10: "TIM2",
    11: "TIM3",
    12: "USART",
}


def parse_rows(path):
    """Le CSV -> [(cycles, event_id)]; header/comentarios/blank ignorados."""
    rows = []
    with open(path, newline="") as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(",")
            if len(parts) != 2:
                sys.exit(f"erro: linha {lineno}: esperado `cycles,event_id`: {s!r}")
            try:
                cyc = int(parts[0].strip(), 0)
                eid = int(parts[1].strip(), 0)
            except ValueError:
                if not rows:
                    continue  # header na primeira linha de dados: ignora
                sys.exit(f"erro: linha {lineno}: valores invalidos: {s!r}")
            if not 0 <= eid <= 0xFF:
                sys.exit(f"erro: linha {lineno}: event_id fora de 0..255: {eid}")
            rows.append((cyc & MASK32, eid))
    if not rows:
        sys.exit(f"erro: {path}: nenhum dado (CSV vazio ou so header?)")
    return rows


def convert(rows, cpu_mhz, c0):
    """Desenrola CYCCNT e monta eventos; retorna (events, n_spans, n_instants, t_max_us)."""
    events = []
    open_stacks = {}  # enter_id -> [ts_us, ...]
    used_tids = set()
    n_spans = 0
    for cyc, eid in rows:
        ts_us = round(((cyc - c0) & MASK32) / cpu_mhz, 3)
        if eid in PAIRS:
            _, name, tid = PAIRS[eid]
            open_stacks.setdefault(eid, []).append(ts_us)
            used_tids.add(tid)
        elif eid in EXIT:
            enter_id, name, tid = EXIT[eid]
            used_tids.add(tid)
            stack = open_stacks.get(enter_id, [])
            if stack:
                t0 = stack.pop()
                events.append({"name": name, "ph": "X", "ts": t0,
                               "dur": round(ts_us - t0, 3), "pid": 1, "tid": tid})
                n_spans += 1
            else:
                events.append({"name": name + "_UNMATCHED", "ph": "I",
                               "ts": ts_us, "pid": 1, "tid": tid})
        else:
            if eid in MARKS:
                name, tid = MARKS[eid]
            elif 0x01 <= eid <= 0x0F:
                name, tid = (f"BLOCK_{eid:02X}", 1)  # S1 reservados
            else:
                name, tid = (f"ID_{eid:02X}", 1)  # id desconhecido: nao perde dado
            used_tids.add(tid)
            events.append({"name": name, "ph": "I", "ts": ts_us, "pid": 1, "tid": tid})
    for enter_id, stack in open_stacks.items():
        _, name, tid = PAIRS[enter_id]
        for t0 in stack:  # enter sem exit: degrada p/ instante (evita span infinito)
            events.append({"name": name + "_UNCLOSED", "ph": "I", "ts": t0, "pid": 1, "tid": tid})
    events.sort(key=lambda e: (e["ts"], e["tid"]))
    meta = [{"name": "process_name", "ph": "M", "pid": 1, "args": {"name": "stm32f103-hsi8"}}]
    meta += [{"name": "thread_name", "ph": "M", "pid": 1, "tid": t,
              "args": {"name": TID_NAMES[t]}} for t in sorted(used_tids)]
    t_max = events[-1]["ts"] if events else 0.0
    return meta + events, n_spans, len(events) - n_spans, t_max


def main():
    ap = argparse.ArgumentParser(description="CSV do tracer DWT -> JSON p/ ui.perfetto.dev.")
    ap.add_argument("csv", help="entrada `cycles,event_id` em ordem cronologica")
    ap.add_argument("--cpu-mhz", type=float, default=8.0, help="clock p/ ciclos->us (padrao: 8)")
    ap.add_argument("--c0", default="auto",
                    help="ciclo de referencia (decimal/0x..) ou 'auto'=1a amostra (padrao: auto)")
    ap.add_argument("--out", default="trace.perfetto.json", help="JSON de saida (padrao: trace.perfetto.json)")
    args = ap.parse_args()
    if args.cpu_mhz <= 0:
        sys.exit("erro: --cpu-mhz deve ser > 0")
    rows = parse_rows(args.csv)
    try:
        c0 = rows[0][0] if args.c0 == "auto" else int(args.c0, 0) & MASK32
    except ValueError:
        sys.exit(f"erro: --c0 invalido: {args.c0!r} (use decimal, 0x.. ou 'auto')")
    events, n_spans, n_inst, t_max = convert(rows, args.cpu_mhz, c0)
    with open(args.out, "w") as f:
        json.dump(events, f, indent=1)
        f.write("\n")
    print(f"{args.csv}: {len(rows)} amostras, {n_spans} spans, {n_inst} instantes, "
          f"t_max={t_max:.3f} us -> {args.out}")


if __name__ == "__main__":
    main()
