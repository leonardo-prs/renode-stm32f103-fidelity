"""Exportação para o Perfetto (Chrome Trace Event JSON) e validação da importação.

Formato: JSON "traceEvents" (aceito oficialmente pelo Perfetto). `ts` e
`dur` em MICROSSEGUNDOS (float): µs = ticks / (core_hz / 1e6); com HCLK
nominal de 8 MHz, 1 tick = 0,125 µs (exato em ponto flutuante). A
frequência vem do header do snapshot, nunca de uma constante escondida.

Convenções (README, "Traces"):
  - um processo (pid) por run; trilhas (tid) por CONTEXTO ESCRITOR: MAIN e
    cada handler — trilhas paralelas não significam execução simultânea;
  - ts = 0 no valor inicial do CYCCNT (FID_DWT_START) de cada run. Placa e
    Renode não compartilham origem absoluta: no comparativo, ambos começam
    em 0 (alinhamento declarado; nenhuma duração é reescalada);
  - slices (X) = intervalos com início E fim registrados; instantes (i) =
    pontos registrados; counters (C) = valores por evento; assíncronos
    (b/e) = intervalos que podem se sobrepor (bytes em trânsito na USART);
  - eventos PREVISTOS/INFERIDOS (ex.: instante do update reconstruído por
    CNT) ficam na categoria "inferido" e em trilha própria;
  - handlers do C3: duração INCLUSIVA (inclui preempção) no slice e
    exclusiva nos args; pareamento ENTER/EXIT pelo número da entrada, nunca
    por heurística; par incompleto vira instante "par incompleto";
  - trace com perdas (anel sobrescrito) recebe aviso no instante de
    metadados e nos args do processo.
"""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path
from statistics import median

from . import abi, c1, c2, c3, c4

TRACK_NAMES = {
    "c2": {0: "MAIN", 1: "TIM2 ISR", 2: "TIM3 ISR", 3: "TIM1_UP ISR"},
    "c3": {0: "MAIN", 1: "EXTI0 (A)", 2: "EXTI1 (B)"},
}
TID_BRACKET, TID_UART, TID_INFERRED = 10, 11, 12


class TraceBuilder:
    """Acumula eventos de UM processo (run). O importador JSON do Perfetto trata
    `tid` como identificador GLOBAL (e tid 0 como especial): cada trilha local
    (0 = MAIN, 1..3 = handlers, 10.. = trilhas auxiliares) vira um tid único
    pid·1000 + local + 1."""

    def __init__(self, pid: int, core_hz: int):
        self.pid = pid
        self.us_per_tick = 1e6 / core_hz
        self.events: list[dict] = []
        self.count = defaultdict(int)
        self.per_thread = defaultdict(int)     # tid global → slices esperados na trilha

    def tid(self, local: int) -> int:
        return self.pid * 1000 + local + 1

    def us(self, ticks: float) -> float:
        return ticks * self.us_per_tick

    def meta(self, kind: str, tid: int, name: str, args=None) -> None:
        self.events.append({"ph": "M", "pid": self.pid, "tid": self.tid(tid), "name": kind,
                            "args": {"name": name, **(args or {})}})

    def slice(self, tid: int, name: str, t0: float, dur: float, cat="registrado", args=None):
        self.events.append({"ph": "X", "pid": self.pid, "tid": self.tid(tid), "name": name, "cat": cat,
                            "ts": self.us(t0), "dur": self.us(dur), "args": args or {}})
        self.count["slice"] += 1
        self.per_thread[self.tid(tid)] += 1

    def instant(self, tid: int, name: str, t: float, cat="registrado", args=None):
        self.events.append({"ph": "i", "s": "t", "pid": self.pid, "tid": self.tid(tid), "name": name,
                            "cat": cat, "ts": self.us(t), "args": args or {}})
        self.count["slice"] += 1
        self.per_thread[self.tid(tid)] += 1

    def counter(self, name: str, t: float, value: float):
        self.events.append({"ph": "C", "pid": self.pid, "tid": self.tid(0), "name": name,
                            "ts": self.us(t), "args": {"ticks": value}})
        self.count["counter"] += 1

    def async_span(self, tid: int, name: str, ident: str, t0: float, t1: float, args=None):
        for ph, t in (("b", t0), ("e", t1)):
            self.events.append({"ph": ph, "pid": self.pid, "tid": self.tid(tid), "cat": "transito",
                                "id": ident, "name": name, "ts": self.us(t), "args": args or {}})
        self.count["slice"] += 1

    def flow(self, ident: int, tid0: int, t0: float, tid1: int, t1: float, name="atendimento"):
        self.events.append({"ph": "s", "pid": self.pid, "tid": self.tid(tid0), "cat": "fluxo",
                            "id": self.pid * 1_000_000 + ident, "name": name, "ts": self.us(t0)})
        self.events.append({"ph": "f", "bp": "e", "pid": self.pid, "tid": self.tid(tid1), "cat": "fluxo",
                            "id": self.pid * 1_000_000 + ident, "name": name, "ts": self.us(t1)})
        self.count["flow"] += 1


def _times(snap: abi.Snapshot) -> tuple[dict, list[str]]:
    """Tempo (ticks desde dwt_start) de cada evento + avisos."""
    warnings = []
    try:
        return abi.timeline(snap), warnings
    except abi.SnapshotError as exc:
        warnings.append(f"ordem global indisponível ({exc}); tempos por evento a partir de dwt_start")
        start = snap.header["dwt_start"]
        return {(e.writer, e.index): abi.unwrap_from(start, e.ticks)
                for w in snap.events for e in w}, warnings


def build_run(run, pid: int, process_label: str) -> TraceBuilder:
    snap = run.snapshot
    h = snap.header
    tb = TraceBuilder(pid, h["core_hz"])
    times, warnings = _times(snap)
    if not snap.complete_trace:
        warnings.append(f"anel sobrescrito: registros perdidos por escritor {snap.lost}")
    start = h["dwt_start"]
    rel = lambda raw: abi.unwrap_from(start, raw)  # noqa: E731
    names = TRACK_NAMES.get(run.firmware, {0: "MAIN"})
    tb.meta("process_name", 0, process_label)
    for tid, name in names.items():
        tb.meta("thread_name", tid, name)
    cfg = run.record.get("config", {})
    tb.instant(0, "metadados do run", 0, cat="metadados", args={
        "ambiente": run.env, "firmware": run.firmware, "run": run.name,
        "nonce": run.record.get("nonce"), "elf_sha256": run.record.get("snapshot_sha256"),
        "core_hz": h["core_hz"], "us_por_tick": tb.us_per_tick,
        "mips": cfg.get("performance_in_mips"), "quantum_s": cfg.get("quantum_s"),
        "trace_completo": snap.complete_trace, "perdas": snap.lost, "avisos": warnings})

    main = [e for e in snap.events[0]]
    open_case = None
    for e in main:
        t = times[(e.writer, e.index)]
        if e.event == abi.EV_CASE_BEGIN:
            open_case = (e.arg, t)
        elif e.event == abi.EV_CASE_END and open_case:
            tb.slice(0, _case_name(run.firmware, open_case[0]), open_case[1], t - open_case[1],
                     args={"case_id": open_case[0], "status": e.arg})
            open_case = None
    if open_case:
        tb.instant(0, "caso sem fim registrado", open_case[1], cat="aviso")

    if run.firmware == "c1-timing":
        tb.meta("thread_name", TID_BRACKET, "bracket (fid_measure)")
        for case in snap.cases:
            w = case.words
            load, n = c1.LOADS[w[0]], w[1]
            for r in range(w[3]):
                ticks, t0, _ = w[4 + 3 * r: 7 + 3 * r]
                tb.slice(TID_BRACKET, f"{load}/{n} rep{r}", rel(t0), ticks,
                         args={"ticks": ticks, "rep": r})
    elif run.firmware == "c2":
        _c2(tb, snap, times, rel)
    elif run.firmware == "c3":
        _c3(tb, snap, times)
    elif run.firmware == "c4":
        _c4(tb, snap, rel)
    return tb


def _case_name(fw: str, case_id: int) -> str:
    if fw == "c1-functional":
        return c1.CASES.get(case_id, f"caso {case_id}")
    if fw == "c1-timing":
        return f"{c1.LOADS[case_id >> 4]}/{0 if case_id == 0 else c1.SIZES[case_id & 0xF]}"
    if fw == "c2":
        return c2.label(case_id)
    if fw == "c3":
        return c3.CASES.get(case_id, ("?",))[0]
    if fw == "c4":
        return c4.CASES.get(case_id, f"caso {case_id:#x}")
    return str(case_id)


def _c2(tb, snap, times, rel):
    tb.meta("thread_name", TID_INFERRED, "update (inferido de CNT)")
    core_hz = snap.header["core_hz"]
    for case in snap.cases:
        kind, t, profile, _, psc, _ = case.words[:6]
        div = c2.APB_DIV[profile]
        tpc = (psc + 1) / (c2.timclk(core_hz, div) / core_hz)
        for e in snap.events[c2.TIMER_WRITER[t]]:
            if e.event != c2.EV_ISR_ENTRY or e.case_id != case.case_id:
                continue
            te = times[(e.writer, e.index)]
            lat = e.arg * tpc
            tb.instant(e.writer, "ISR (CNT lido)", te, args={"cnt": e.arg, "latencia_ticks": lat})
            tb.instant(TID_INFERRED, "update (inferido)", te - lat, cat="inferido",
                       args={"base": "CNT × (PSC+1) × HCLK/TIMCLK"})
            tb.counter(f"{c2.TIMERS[t]} latência CNT (ticks)", te, lat)
        if c2.KINDS[kind] in ("update_poll",):
            for k, raw in enumerate(case.words[7:]):
                if raw:
                    tb.instant(0, f"UIF visto (polling) #{k}", rel(raw))


def _c3(tb, snap, times):
    events = [e for e in snap.all_events() if e.event >= 0x300]
    spans = []
    for case in snap.cases:
        mine = [e for e in events if e.case_id == case.case_id]
        enters = {}
        for e in mine:
            t = times[(e.writer, e.index)]
            tok = c3.token(e)
            if e.event == c3.EV_ENTER:
                enters[(e.writer, e.arg & 0xFF)] = t
            elif e.event == c3.EV_EXIT:
                t0 = enters.pop((e.writer, e.arg & 0xFF), None)
                if t0 is None:
                    tb.instant(e.writer, "par incompleto (EXIT sem ENTER)", t, cat="aviso")
                else:
                    spans.append((e.writer, t0, t, f"{c3.WRITER[e.writer]}#{e.arg & 0xFF}"))
            else:
                tb.instant(e.writer, tok, t)
        for (w, k), t0 in enters.items():
            tb.instant(w, "par incompleto (ENTER sem EXIT)", t0, cat="aviso")
        # fluxo: REQ de MAIN → próxima entrada do handler daquela IRQ
        flow_id = case.case_id << 8
        for i, e in enumerate(mine):
            if e.writer == 0 and e.event == c3.EV_REQUEST:
                target = 1 if e.arg == 6 else 2
                nxt = next((x for x in mine[i + 1:] if x.writer == target and x.event == c3.EV_ENTER),
                           None)
                if nxt is not None:
                    flow_id += 1
                    tb.flow(flow_id, 0, times[(e.writer, e.index)], target, times[(nxt.writer, nxt.index)])
    for w, t0, t1, name in spans:
        nested = sum(min(b1, t1) - max(b0, t0) for w2, b0, b1, _ in spans
                     if w2 != w and b0 > t0 and b1 < t1)
        tb.slice(w, name, t0, t1 - t0, args={"inclusiva_ticks": t1 - t0,
                                             "exclusiva_ticks": t1 - t0 - nested})


def _c4(tb, snap, rel):
    tb.meta("thread_name", TID_UART, "USART1 TX→RX (escrita→leitura do byte)")
    for case in snap.cases:
        w = case.words
        if case.case_id == 0x03:                      # rajada: escrita e leitura por byte
            n = w[3]
            words_rx = (n + 3) // 4
            writes = w[5 + words_rx:5 + words_rx + 64]
            reads = w[5 + words_rx + 64:5 + words_rx + 64 + n]
            for i, (a, b) in enumerate(zip(writes, reads)):
                tb.async_span(TID_UART, f"byte {i}", f"c4-{case.case_id}-{i}", rel(a), rel(b))
        elif case.case_id == 0x06:                    # transições de SR
            n = w[5]
            for i in range(n):
                tb.instant(0, f"SR={w[7 + 2 * i]:#04x}", rel(w[6 + 2 * i]), args={"sr": w[7 + 2 * i]})


def write_trace(path: Path, builders: list[TraceBuilder], metadata: dict) -> dict:
    events = [e for b in builders for e in b.events]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"traceEvents": events, "displayTimeUnit": "ns",
                                "otherData": metadata}, ensure_ascii=False))
    path.with_suffix(".meta.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    expected = defaultdict(int)
    per_thread = {}
    for b in builders:
        for k, v in b.count.items():
            expected[k] += v
        per_thread.update({str(t): n for t, n in b.per_thread.items()})
    return {**expected, "per_thread": per_thread}


def median_run(runs):
    """Run cuja duração total (dwt_end − dwt_start) é a mediana; empate → menor nome."""
    dur = {r.name: abi.unwrap_from(r.snapshot.header["dwt_start"], r.snapshot.header["dwt_end"])
           for r in runs}
    m = median(dur.values())
    return min(runs, key=lambda r: (abs(dur[r.name] - m), r.name))


def export_campaign(root: Path, runs, out: Path, log=print) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    results = {"per_run": 0, "comparisons": [], "validation": []}
    valid = [r for r in runs if r.valid]
    expected_by_file = {}
    for r in valid:
        path = out / "runs" / r.env / r.firmware / f"{r.name}.json"
        tb = build_run(r, 1, f"{r.env} · {r.firmware} · {r.name}")
        expected_by_file[path] = write_trace(path, [tb], {"environment": r.env, "firmware": r.firmware,
                                                           "run": r.name})
        results["per_run"] += 1
    by = defaultdict(list)
    for r in valid:
        by[(r.firmware, r.env)].append(r)
    for fw in sorted({r.firmware for r in valid}):
        chosen = [median_run(by[(fw, env)]) for env in ("hw", "renode-nominal", "renode-calibrated")
                  if by.get((fw, env))]
        builders = [build_run(r, pid, f"{r.env} · {r.firmware} · {r.name} (run mediano)")
                    for pid, r in enumerate(chosen, start=1)]
        path = out / f"compare-{fw}.json"
        meta = {"firmware": fw, "selection": "run de duração total mediana em cada ambiente",
                "alignment": "ts = 0 no início (FID_DWT_START) de cada run; durações não reescaladas",
                "runs": {r.env: r.name for r in chosen}}
        expected_by_file[path] = write_trace(path, builders, meta)
        results["comparisons"].append(str(path.relative_to(root)))
    # Validação: todos os comparativos + o primeiro run de cada (ambiente, firmware).
    sample = [p for p in expected_by_file if p.name.startswith("compare-")]
    seen = set()
    for p in sorted(expected_by_file):
        key = p.parent
        if "runs" in p.parts and key not in seen:
            seen.add(key)
            sample.append(p)
    for p in sample:
        results["validation"].append(validate(p, expected_by_file[p], root))
    (out / "validation.json").write_text(json.dumps(results["validation"], indent=2, ensure_ascii=False))
    bad = [v for v in results["validation"] if not v["ok"]]
    log(f"perfetto: {results['per_run']} traces de run, {len(results['comparisons'])} comparativos, "
        f"{len(results['validation']) - len(bad)}/{len(results['validation'])} importações conferidas")
    return results


QUERIES = ("select count(*) as n from slice;\n"
           "select count(*) as n from counter;\n"
           "select count(*) as n from flow;\n"
           "select name, ts, dur from slice where dur > 0 order by ts, name limit 1;\n"
           "select t.tid as tid, count(*) as n from slice s join thread_track tt on s.track_id = tt.id "
           "join thread t using(utid) group by t.tid order by t.tid;\n")


def validate(path: Path, expected: dict, root: Path) -> dict:
    """Importa com o trace_processor_shell e confere contagens e um slice."""
    q = path.with_suffix(".sql")
    q.write_text(QUERIES)
    res = {"file": str(path.relative_to(root)), "expected": expected}
    try:
        out = subprocess.run(["trace_processor_shell", "-q", str(q), str(path)], capture_output=True,
                             text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        res.update(ok=False, error=f"trace_processor_shell indisponível: {exc}")
        return res
    finally:
        q.unlink(missing_ok=True)
    blocks = [b.strip().splitlines() for b in out.stdout.strip().split("\n\n")]
    try:
        n_slice, n_counter, n_flow = (int(b[1]) for b in blocks[:3])
        first = blocks[3][1].split(",") if len(blocks) > 3 and len(blocks[3]) > 1 else None
    except (ValueError, IndexError):
        res.update(ok=False, error=out.stdout[-300:] + out.stderr[-300:])
        return res
    doc = json.loads(path.read_text())
    xs = sorted((e for e in doc["traceEvents"] if e["ph"] == "X" and e["dur"] > 0),
                key=lambda e: (e["ts"], e["name"]))
    slice_ok = True
    if first and xs:
        slice_ok = (int(first[1]) == round(xs[0]["ts"] * 1000)
                    and int(first[2]) == round(xs[0]["dur"] * 1000))
    per_thread = {}
    for line in (blocks[4][1:] if len(blocks) > 4 else []):
        tid, n = line.split(",")
        per_thread[tid.strip('"')] = int(n)
    threads_ok = per_thread == expected.get("per_thread", {})
    res.update(imported={"slice": n_slice, "counter": n_counter, "flow": n_flow,
                         "per_thread": per_thread},
               first_slice_ns=first, first_slice_matches=slice_ok, threads_match=threads_ok,
               ok=(n_slice == expected.get("slice", 0) and n_counter == expected.get("counter", 0)
                   and n_flow == expected.get("flow", 0) and slice_ok and threads_ok))
    return res
