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
  - C2 mantém fase CNT como inferência nos args/counters; não desenha uma
    borda de update em timestamp corrigido por um atraso de logger desconhecido;
  - handlers do C3: duração INCLUSIVA (inclui preempção) no slice e
    exclusiva nos args; pareamento ENTER/EXIT pelo número da entrada, nunca
    por heurística; par incompleto vira instante "par incompleto";
  - trace com perdas/tempo ambíguo é recusado com diagnóstico em validation/
    summary; dados tabulares independentes podem permanecer na análise.
"""
from __future__ import annotations

import json
import csv
import math
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
        if core_hz <= 0:
            raise abi.SnapshotError("frequência de trace inválida")
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
        if not math.isfinite(t0) or not math.isfinite(dur) or dur < 0:
            raise abi.SnapshotError(f"slice inválido: {name}")
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
        if t1 < t0:
            raise abi.SnapshotError(f"span assíncrono negativo: {name}")
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
    # Não há fallback: ordenar timestamps módulo 2^32 com lacunas inventa tempo.
    return abi.timeline(snap), []


def _relative(snap, times, raw, case_id):
    """Localiza timestamp tabular no intervalo registrado do seu caso.

    A âncora global resolve runs longos; um caso com mais de um wrap é
    ambíguo para dados que contêm somente o timestamp de 32 bits.
    """
    bounds = [e for e in snap.events[0] if e.case_id == case_id and
              e.event in (abi.EV_CASE_BEGIN, abi.EV_CASE_END)]
    if len(bounds) != 2 or bounds[0].event != abi.EV_CASE_BEGIN or bounds[1].event != abi.EV_CASE_END:
        raise abi.SnapshotError(f"caso {case_id}: âncoras incompletas")
    begin, end = (times[(e.writer, e.index)] for e in bounds)
    t = begin + (raw - bounds[0].ticks) % abi.WRAP
    if t > end or t + abi.WRAP <= end:
        raise abi.SnapshotError(f"caso {case_id}: timestamp fora da janela/ambíguo")
    return t


def build_run(run, pid: int, process_label: str) -> TraceBuilder:
    snap = run.snapshot
    h = snap.header
    tb = TraceBuilder(pid, h["core_hz"])
    times, warnings = _times(snap)
    if not snap.complete_trace:
        warnings.append(f"anel sobrescrito: registros perdidos por escritor {snap.lost}")
    rel = lambda raw, cid: _relative(snap, times, raw, cid)  # noqa: E731
    names = TRACK_NAMES.get(run.firmware, {0: "MAIN"})
    tb.meta("process_name", 0, process_label)
    for tid, name in names.items():
        tb.meta("thread_name", tid, name)
    cfg = run.record.get("config", {})
    tb.instant(0, "metadados do run", 0, cat="metadados", args={
        "ambiente": run.env, "firmware": run.firmware, "run": run.name,
        "nonce": run.record.get("nonce"), "snapshot_sha256": run.record.get("snapshot_sha256"),
        "elf_sha256": run.record.get("elf_sha256"),
        "core_hz": h["core_hz"], "us_por_tick": tb.us_per_tick,
        "mips": cfg.get("performance_in_mips"), "quantum_s": cfg.get("quantum_s"),
        "trace_completo": snap.complete_trace, "perdas": snap.lost, "avisos": warnings})

    main = [e for e in snap.events[0]]
    open_case = None
    for e in main:
        t = times[(e.writer, e.index)]
        if e.event == abi.EV_CASE_BEGIN:
            if open_case:
                raise abi.SnapshotError("CASE_BEGIN antes do fim do caso anterior")
            open_case = (e.arg, t)
        elif e.event == abi.EV_CASE_END and open_case:
            if e.case_id != open_case[0]:
                raise abi.SnapshotError("CASE_END de outro caso")
            tb.slice(0, _case_name(run.firmware, open_case[0]), open_case[1], t - open_case[1],
                     args={"case_id": open_case[0], "status": e.arg})
            open_case = None
    if open_case:
        tb.instant(0, "caso sem fim registrado", open_case[1], cat="aviso")

    if run.firmware == "c1-timing":
        tb.meta("thread_name", TID_BRACKET, "bracket (fid_measure)")
        reps, problems = c1.parse_timing(snap)
        if problems:
            raise abi.SnapshotError("; ".join(problems))
        for rep in reps:
            cid = 0 if rep.load == "empty" else (c1.LOADS.index(rep.load) << 4) | c1.SIZES.index(rep.n)
            t0 = rel(rep.t0, cid)
            end = next(times[(e.writer, e.index)] for e in snap.events[0]
                       if e.case_id == cid and e.event == abi.EV_CASE_END)
            if t0 + rep.ticks > end:
                raise abi.SnapshotError(f"bracket {rep.load}/{rep.n} fora da janela do caso")
            tb.slice(TID_BRACKET, f"{rep.load}/{rep.n} rep{rep.rep}", t0, rep.ticks,
                     args={"ticks": rep.ticks, "rep": rep.rep})
    elif run.firmware == "c2":
        _c2(tb, snap, times, rel)
    elif run.firmware == "c3":
        _c3(tb, snap, times)
    elif run.firmware == "c4":
        _c4(tb, snap, rel)
    # Todos os registros originais permanecem visíveis, inclusive eventos
    # repetidos e calibração. Trilhas próprias evitam interferir no nesting.
    for writer, events in enumerate(snap.events):
        if events:
            tb.meta("thread_name", 20 + writer, f"registros brutos writer {writer}")
        for e in events:
            tb.instant(20 + writer, abi.GENERIC_EVENTS.get(e.event, f"evento {e.event:#x}"),
                       times[(e.writer, e.index)], cat="registro bruto",
                       args={"ticket": e.ticket, "case_id": e.case_id, "arg": e.arg,
                             "raw_ticks": e.ticks, "index": e.index})
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
    core_hz = snap.header["core_hz"]
    for case in snap.cases:
        kind, t, profile, cfgr, psc, arr = case.words[:6]
        if len(case.words) != 10 + c2.DATA_WORDS[kind]:
            raise abi.SnapshotError("payload C2 incompatível para exportação")
        div = c2.APB_DIV[profile]
        code = c2.PPRE_CODE[div]
        expected_psc = 7 if 3 <= kind <= 9 else 0
        expected_arr = 65535 if kind <= 2 else (999 if kind <= 9 else 7999)
        applied = ((cfgr & 0x3FFF) == ((code << 8) | (code << 11))
                   and psc == expected_psc and arr == expected_arr)
        tpc = (psc + 1) / (c2.timclk(core_hz, div) / core_hz)
        isr = [e for e in snap.events[c2.TIMER_WRITER[t]]
               if e.event == c2.EV_ISR_ENTRY and e.case_id == case.case_id]
        periodic = (kind in (10, 11) and applied and case.status == "OK"
                    and case.words[7] == c2.N_IRQS and len(isr) == c2.N_IRQS
                    and all(e.arg <= arr for e in isr))
        for e in isr:
            te = times[(e.writer, e.index)]
            args = {"cnt": e.arg, "config_aplicada": applied,
                    "observacao": "timestamp do logger posterior à leitura de CNT"}
            if periodic:
                phase = e.arg * tpc
                args.update(fase_periodica_ticks=phase,
                            inferencia="fase módulo período; pressupõe ausência de períodos perdidos",
                            erro_logger="offset entre CNT e logger não medido; limite não estabelecido")
                tb.counter(f"{c2.TIMERS[t]} fase CNT periódica (ticks)", te, phase)
            elif kind in (12, 13):
                args["observacao"] += "; CNT congelado antes da liberação, não mede latência"
            tb.instant(e.writer, "ISR (logger após CNT)", te, args=args)
        # Nenhuma borda sintética em te-CNT: o atraso do logger não foi medido.
        if kind == 3:
            for k, raw in enumerate(case.words[7:-4]):
                if raw:
                    tb.instant(0, f"UIF visto (polling) #{k}", rel(raw, case.case_id))


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
                key = (e.writer, e.arg & 0xFF)
                if key in enters:
                    raise abi.SnapshotError("ENTER repetido sem EXIT")
                enters[key] = (t, e.ticket)
            elif e.event == c3.EV_EXIT:
                begin = enters.pop((e.writer, e.arg & 0xFF), None)
                if begin is None:
                    tb.instant(e.writer, "par incompleto (EXIT sem ENTER)", t, cat="aviso")
                else:
                    t0, ticket0 = begin
                    spans.append((e.writer, t0, t, f"{c3.WRITER[e.writer]}#{e.arg & 0xFF}", ticket0, e.ticket))
            else:
                tb.instant(e.writer, tok, t)
        for (w, k), (t0, _) in enters.items():
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
    for w, t0, t1, name, ticket0, ticket1 in spans:
        # União dos intervalos internos: evita contar duas vezes preempções
        # aninhadas; igualdade de timestamps é possível por quantização.
        if any(ticket0 < a < ticket1 < b for _, _, _, _, a, b in spans):
            raise abi.SnapshotError("intervalos de handlers cruzados: nesting inválido")
        intervals = sorted((b0, b1) for w2, b0, b1, _, a, b in spans
                           if w2 != w and ticket0 < a and b < ticket1)
        nested, end = 0, t0
        for b0, b1 in intervals:
            nested += max(0, b1 - max(end, b0))
            end = max(end, b1)
        tb.slice(w, name, t0, t1 - t0, args={"inclusiva_ticks": t1 - t0,
                                             "exclusiva_ticks": t1 - t0 - nested})


def _c4(tb, snap, rel):
    tb.meta("thread_name", TID_UART, "USART1 TX→RX (escrita→leitura do byte)")
    for case in snap.cases:
        w = case.words
        # Payload versionado do C4: metadados/config efetiva + corpo + estado final.
        if not w or w[0] != c4.PAYLOAD_VERSION:
            raise abi.SnapshotError("payload C4 incompatível para exportação")
        d = w[5:-3]
        if case.case_id == 0x03:
            sent, n = d[:2]
            nw = (n + 3) // 4
            writes = d[3 + nw:3 + nw + sent]
            reads = d[3 + nw + sent:]
            received = c4.unpack_bytes(d[3:3 + nw], n)
            content_ok = received == [c4.pattern(i) for i in range(sent)]
            if sent != n or not content_ok:
                tb.instant(TID_UART, "pareamento TX→RX indisponível: contagem ou conteúdo divergente", 0,
                           cat="aviso", args={"escritos": sent, "recebidos": n,
                                              "conteudo_e_ordem_validos": content_ok})
                continue
            for i, (a, b) in enumerate(zip(writes, reads)):
                tb.async_span(TID_UART, f"byte {i}", f"c4-{case.case_id}-{i}",
                              rel(a, case.case_id), rel(b, case.case_id))
        elif case.case_id == 0x06:
            n = d[2]
            for i in range(n):
                raw, sr = d[5 + 2 * i:7 + 2 * i]
                tb.instant(0, f"SR={sr:#04x}", rel(raw, case.case_id), args={"sr": sr})


def write_trace(path: Path, builders: list[TraceBuilder], metadata: dict) -> dict:
    events = [e for b in builders for e in b.events]
    # X externos antes dos internos quando o início coincide; empates restantes
    # preservam ordem de registro (sort estável). M antecede dados.
    events.sort(key=lambda e: (0 if e["ph"] == "M" else 1, e.get("ts", 0),
                               -e.get("dur", 0) if e["ph"] == "X" else 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"traceEvents": events, "displayTimeUnit": "ns",
                                "otherData": metadata}, ensure_ascii=False, allow_nan=False))
    path.with_suffix(".meta.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False))
    expected = defaultdict(int)
    per_thread = {}
    for b in builders:
        for k, v in b.count.items():
            expected[k] += v
        per_thread.update({str(t): n for t, n in b.per_thread.items()})
    return {**expected, "per_thread": per_thread}


def median_run(runs):
    """Run cuja duração total (dwt_end − dwt_start) é a mediana; empate → menor nome."""
    durations = [(r, abi.run_duration(r.snapshot)) for r in runs]
    m = median(d for _, d in durations)
    return min(durations, key=lambda pair: (abs(pair[1] - m), pair[0].name))[0]


def export_campaign(root: Path, runs, out: Path, log=print) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    results = {"per_run": 0, "comparisons": [], "validation": [], "errors": []}
    valid = [r for r in runs if r.valid]
    expected_by_file = {}
    for r in valid:
        path = out / "runs" / r.env / r.firmware / f"{r.name}.json"
        try:
            tb = build_run(r, 1, f"{r.env} · {r.firmware} · {r.name}")
        except (abi.SnapshotError, ValueError, IndexError, KeyError) as exc:
            results["errors"].append({"environment": r.env, "firmware": r.firmware,
                                      "run": r.name, "error": str(exc)})
            path.unlink(missing_ok=True)
            path.with_suffix(".meta.json").unlink(missing_ok=True)
            continue
        expected_by_file[path] = write_trace(path, [tb], {"environment": r.env, "firmware": r.firmware,
                                                           "run": r.name})
        results["per_run"] += 1
    by = defaultdict(list)
    for r in valid:
        if not any(e["environment"] == r.env and e["firmware"] == r.firmware and e["run"] == r.name
                   for e in results["errors"]):
            by[(r.firmware, r.env)].append(r)
    for fw in sorted({fw for fw, _ in by}):
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
    (out / "validation.json").write_text(json.dumps(results["validation"], indent=2, ensure_ascii=False, allow_nan=False))
    bad = [v for v in results["validation"] if not v["ok"]]
    log(f"perfetto: {results['per_run']} traces de run, {len(results['comparisons'])} comparativos, "
        f"{len(results['validation']) - len(bad)}/{len(results['validation'])} importações conferidas")
    return results


QUERIES = ("select count(*) as n from slice;\n"
           "select count(*) as n from counter;\n"
           "select count(*) as n from flow;\n"
           "select name, ts, dur from slice where dur > 0 order by ts, name limit 1;\n"
           "select t.tid as tid, count(*) as n from slice s join thread_track tt on s.track_id = tt.id "
           "join thread t using(utid) group by t.tid order by t.tid;\n"
           "select name, ts, dur from slice order by ts, dur desc, name;\n")


def validate(path: Path, expected: dict, root: Path) -> dict:
    """Confere contagens, trilhas e TODOS os nomes/tempos/durações importados."""
    q = path.with_suffix(".sql")
    q.write_text(QUERIES)
    res = {"file": str(path.relative_to(root)), "expected": expected}
    try:
        out = subprocess.run(["trace_processor_shell", "-q", str(q), str(path)], capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        res.update(ok=False, error=f"trace_processor_shell indisponível: {exc}")
        return res
    finally:
        q.unlink(missing_ok=True)
    if out.returncode:
        res.update(ok=False, error=f"trace_processor exit {out.returncode}: {out.stderr[-500:]}")
        return res
    blocks = [b.strip().splitlines() for b in out.stdout.strip().split("\n\n")]
    try:
        n_slice, n_counter, n_flow = (int(b[1]) for b in blocks[:3])
        first = next(csv.reader([blocks[3][1]])) if len(blocks) > 3 and len(blocks[3]) > 1 else None
    except (ValueError, IndexError):
        res.update(ok=False, error=out.stdout[-300:] + out.stderr[-300:])
        return res
    doc = json.loads(path.read_text())
    per_thread = {}
    for line in (blocks[4][1:] if len(blocks) > 4 else []):
        tid, n = next(csv.reader([line]))
        per_thread[tid.strip('"')] = int(n)
    threads_ok = per_thread == expected.get("per_thread", {})
    wanted = [(e["name"], round(e["ts"] * 1000), round(e.get("dur", 0) * 1000))
              for e in doc["traceEvents"] if e["ph"] in ("X", "i")]
    async_starts = {}
    for e in doc["traceEvents"]:
        if e["ph"] == "b":
            async_starts[(e["pid"], e["cat"], e["id"])] = e
        elif e["ph"] == "e":
            begin = async_starts.pop((e["pid"], e["cat"], e["id"]), None)
            if begin is not None:
                wanted.append((begin["name"], round(begin["ts"] * 1000),
                               round(e["ts"] * 1000) - round(begin["ts"] * 1000)))
    positives = sorted((v for v in wanted if v[2] > 0), key=lambda v: (v[1], v[0]))
    slice_ok = bool(first) == bool(positives)
    if first and positives:
        candidate = (first[0], int(first[1]), int(first[2]))
        slice_ok = candidate in [v for v in positives if (v[1], v[0]) == (positives[0][1], positives[0][0])]
    try:
        actual = [(name, int(ts), int(dur)) for name, ts, dur in
                  csv.reader(blocks[5][1:] if len(blocks) > 5 else [])]
        all_slices_ok = sorted(actual) == sorted(wanted)
    except (ValueError, IndexError):
        all_slices_ok = False
    res.update(imported={"slice": n_slice, "counter": n_counter, "flow": n_flow,
                         "per_thread": per_thread},
               first_slice_ns=first, first_slice_matches=slice_ok, threads_match=threads_ok,
               all_slices_match=all_slices_ok,
               ok=(n_slice == expected.get("slice", 0) and n_counter == expected.get("counter", 0)
                   and n_flow == expected.get("flow", 0) and slice_ok and threads_ok and all_slices_ok))
    return res
