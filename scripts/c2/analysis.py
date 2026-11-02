"""Análise do C2 #oD: funções puras sobre os arquivos brutos de cada execução.

Entrada por execução (variante, repetição), formato em collect.py:
  events.txt  registro do observador externo (variantes hooks/full; F em todas)
  mem.txt     o que o firmware viu: status, c2_rec por ponto, c2_served
  trace.txt   um PC por instrução executada (variante full)

Ordem das decisões (03-quadro-comum.typ §Vereditos): primeiro se a
comparação pôde ser feita (EVIDÊNCIA INVÁLIDA: execução inválida,
observador incoerente, estímulo não aplicado como declarado, observadores
interno e externo discordando), depois o determinismo entre repetições, por
fim IGUAL/DIVERGE contra o oráculo documental do catálogo.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import catalog as K

NS_PER_TICK = 125
IGUAL, DIVERGE = "IGUAL", "DIVERGE"
NAO_DET, INVALIDA = "NÃO DETERMINÍSTICO", "EVIDÊNCIA INVÁLIDA"

STIR = 0xE000EF00
ISER, ISPR = 0xE000E100, 0xE000E200


@dataclass(frozen=True)
class Ev:
    kind: str                  # P H B E W F
    pc: int
    vt: int                    # ns de tempo virtual
    instr: int                 # instruções executadas pelo núcleo
    data: tuple[int, ...]

    @property
    def ipsr(self) -> int:
        """Número da exceção (H, B, E, F): IPSR = xPSR[8:0]."""
        x = {"H": 0, "B": 1, "E": 1, "F": 0}[self.kind]
        return self.data[x] & 0x1FF

    @property
    def off(self) -> int:
        """Tempo virtual em ticks menos instruções executadas (0 ⇔ tick = instrução)."""
        return self.vt // NS_PER_TICK - self.instr


def parse_event(line: str) -> Ev:
    f = line.split()
    k = f[0]
    if k == "P":
        return Ev(k, int(f[1], 16), int(f[2]), int(f[3]), tuple(int(x, 16) for x in f[4:]))
    if k == "H":
        return Ev(k, int(f[1], 16), int(f[2]), int(f[3]), tuple(int(x, 16) for x in f[4:]))
    if k in ("B", "E"):
        return Ev(k, int(f[4], 16), int(f[2]), int(f[3]), (int(f[1]), int(f[5], 16)))
    if k == "W":
        return Ev(k, int(f[5], 16), int(f[3]), int(f[4]), (int(f[1], 16), int(f[2], 16)))
    if k == "F":
        return Ev(k, int(f[1], 16), int(f[2]), int(f[3]), (int(f[4], 16),))
    raise ValueError(f"evento desconhecido: {line!r}")


@dataclass
class Mem:
    status: int
    rec: list[list[int]]
    served: list[int]


@dataclass
class Run:
    variant: str
    rep: int
    events: list[Ev]           # vazio quando não há registro (variante bare sem falta)
    mem: Mem | None
    trace: list[int] | None
    error: str | None = None


def read_run(run_dir: Path, variant: str, rep: int, error: str | None = None) -> Run:
    def lines(name):
        p = run_dir / name
        return [l for l in p.read_text().splitlines() if l.strip()] if p.is_file() else None

    ev = lines("events.txt")
    events = [parse_event(l) for l in ev] if ev is not None else []
    mem = None
    m = lines("mem.txt")
    if m is not None:
        try:
            status = int(m[0].split()[1])
            rec = [[int(x) for x in l.split()[2:]] for l in m if l.startswith("rec ")]
            served = next([int(x) for x in l.split()[1:]] for l in m if l.startswith("served "))
            mem = Mem(status, rec, served)
        except (IndexError, ValueError, StopIteration):
            error = error or "mem.txt malformado"
    tr = lines("trace.txt")
    trace = [int(l, 16) for l in tr] if tr is not None else None
    return Run(variant, rep, events, mem, trace, error)


# ─────────────────────── observador externo (genérico) ───────────────────────

@dataclass(frozen=True)
class Layout:
    """O que a análise precisa saber do ELF (gravado em plan.json)."""
    point: int                 # endereço de c2_point
    handler: range             # c2_irq_handler (endereço .. fim)
    stores: frozenset[int]     # endereços de instruções de escrita em .text


def validate_run(run: Run, uses_hooks: bool, layout: Layout, want_ids: list[int]) -> list[str]:
    """Problemas de instrumento ou de execução nesta execução (vazia = válida)."""
    bad = []
    if run.error:
        bad.append(run.error)
    if run.mem is None:
        bad.append("memória do firmware não lida (mem.txt ausente)")
    elif run.mem.status != K.ST_DONE:
        bad.append(f"c2_status = {run.mem.status} (esperado {K.ST_DONE}: fim normal)")
    faults = [e for e in run.events if e.kind == "F"]
    if faults:
        bad.append(f"execução caiu em c2_fault (IPSR {faults[0].ipsr})")
    if uses_hooks:
        bad += observer_structure(run.events, want_ids)
        if run.trace is not None:
            bad += observer_vs_trace(run.events, run.trace, layout)
    return [f"{run.variant}#{run.rep}: {b}" for b in bad]


def observer_structure(events: list[Ev], want_ids: list[int]) -> list[str]:
    """Coerência interna do registro: pontos na ordem, B→H no mesmo instante,
    E fecha o tratador aberto, e tick = instrução nos ganchos de endereço."""
    bad = []
    ids = [e.data[0] for e in events if e.kind == "P"]
    if ids != want_ids:
        bad.append(f"pontos marcados fora da sequência esperada ({len(ids)} de {len(want_ids)})")
    seq = [e for e in events if e.kind != "W"]
    stack: list[int] = []
    for k, e in enumerate(seq):
        if e.kind == "B":
            nxt = seq[k + 1] if k + 1 < len(seq) else None
            if nxt is None or nxt.kind not in ("H", "F") or nxt.instr != e.instr:
                bad.append(f"início de interrupção em instr {e.instr} sem tratador na mesma instrução")
        elif e.kind == "H":
            prev = seq[k - 1] if k else None
            if prev is None or prev.kind != "B" or prev.instr != e.instr:
                bad.append(f"tratador em instr {e.instr} sem início de interrupção")
            stack.append(e.ipsr)
        elif e.kind == "E":
            if not stack or stack[-1] != e.ipsr:
                bad.append(f"fim de interrupção em instr {e.instr} (IPSR {e.ipsr}) sem tratador aberto")
            else:
                stack.pop()
    if stack:
        bad.append(f"tratadores sem fim de interrupção: IPSR {stack}")
    offs = {e.off for e in events if e.kind in ("P", "H")}
    if len(offs) > 1:
        bad.append(f"tempo virtual e instruções divergem nos ganchos de endereço (offsets {sorted(offs)})")
    return bad


def observer_vs_trace(events: list[Ev], trace: list[int], layout: Layout) -> list[str]:
    """O contador de instruções de cada evento indexa o traço (Q-01): o PC
    registrado tem de ser a instrução que o traço mostra nessa posição."""
    bad = []
    for e in events:
        i = e.instr
        if not 0 < i < len(trace):
            bad.append(f"{e.kind} em instr {i} fora do traço ({len(trace)})")
            continue
        if e.kind in ("P", "H", "W", "F") and trace[i] != e.pc:
            bad.append(f"{e.kind} em instr {i}: PC 0x{e.pc:x}, traço 0x{trace[i]:x}")
        if e.kind == "W" and e.pc not in layout.stores:
            bad.append(f"escrita observada em 0x{e.pc:x}, que não é instrução de escrita")
        if e.kind == "B" and trace[i] not in layout.handler:
            bad.append(f"início de interrupção em instr {i}: próxima instrução 0x{trace[i]:x} fora do tratador")
        if e.kind == "E" and trace[i - 1] not in layout.handler:
            bad.append(f"fim de interrupção em instr {i}: última instrução 0x{trace[i - 1]:x} fora do tratador")
    return bad


def characterize(events: list[Ev], trace: list[int] | None) -> dict:
    """Caracterização dos ganchos (relatada, fora do critério): offset tempo −
    instruções por tipo de evento, relativo aos pontos marcados."""
    ref = next((e.off for e in events if e.kind == "P"), 0)
    out = {}
    for kind in "PHBEW":
        c = Counter(e.off - ref for e in events if e.kind == kind)
        if c:
            out[kind] = {str(k): v for k, v in sorted(c.items())}
    b = [e for e in events if e.kind == "B"]
    out["B_index_values"] = sorted({e.data[0] for e in b})
    out["B_ipsr_values"] = sorted({e.ipsr for e in b})
    out["E_pc_values"] = sorted({f"0x{e.pc:x}" for e in events if e.kind == "E"})
    if trace is not None:
        out["trace_len"] = len(trace)
    return out


# ─────────────────────────────── C2-09 ───────────────────────────────

def bit(words: tuple[int, int], line: int) -> int:
    return (words[line >> 5] >> (line & 31)) & 1


def nvic_state(p: Ev, line: int) -> dict[str, int]:
    d = p.data
    return {"enabled": bit((d[1], d[2]), line), "pending": bit((d[3], d[4]), line),
            "active": bit((d[5], d[6]), line)}


@dataclass
class PointResult:
    index: int
    label: str
    verdict: str
    observed: dict = field(default_factory=dict)
    firmware: dict = field(default_factory=dict)
    why: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"index": self.index, "point": self.label, "verdict": self.verdict,
                "observed": self.observed, "firmware": self.firmware, "why": self.why}


def c2_09_ids(points: list[K.Point]) -> list[int]:
    return [(p.index << K.POINT_SHIFT) | ph for p in points for ph in K.C2_09_PHASES.values()]


def c2_09_point(p: K.Point, events: list[Ev], mem: Mem) -> PointResult:
    line, exc = p.line, 16 + p.line
    pos = {e.data[0] & 0xFF: k for k, e in enumerate(events)
           if e.kind == "P" and e.data[0] >> K.POINT_SHIFT == p.index}
    a, q, s = pos[K.C2_09_PHASES["ARMED"]], pos[K.C2_09_PHASES["PENDING"]], pos[K.C2_09_PHASES["SERVED"]]
    end = next((k for k in range(s + 1, len(events)) if events[k].kind == "P"), len(events))
    win = {"armed→pending": events[a + 1:q], "pending→served": events[q + 1:s], "served→next": events[s + 1:end]}
    res = PointResult(p.index, p.label, IGUAL)

    def entries(evs, n=exc):
        return sum(1 for e in evs if e.kind == "H" and e.ipsr == n)

    others = [e.ipsr for evs in win.values() for e in evs if e.kind == "H" and e.ipsr != exc]
    # Estímulo exato: a escrita declarada aconteceu uma vez, na janela certa.
    req = (STIR, line) if p.mech == "STIR" else (ISPR + 4 * (line >> 5), 1 << (line & 31))
    ena = (ISER + 4 * (line >> 5), 1 << (line & 31))
    writes = {w: [e.data for e in evs if e.kind == "W"] for w, evs in win.items()}
    if writes["armed→pending"].count(req) != 1:
        res.why.append(f"pedido ({p.mech}) não observado exatamente uma vez entre ARMED e PENDING")
    if writes["pending→served"].count(ena) != 1:
        res.why.append("habilitação (ISER) não observada exatamente uma vez entre PENDING e SERVED")

    n_ap, n_ps, n_sn = entries(win["armed→pending"]), entries(win["pending→served"]), entries(win["served→next"])
    phase_ev = {"ARMED": events[a], "PENDING": events[q], "SERVED": events[s]}
    served = {"ARMED": 0, "PENDING": n_ap, "SERVED": n_ap + n_ps}
    res.observed = {ph: {**nvic_state(e, line), "served": served[ph]} for ph, e in phase_ev.items()}
    res.observed["entries_after_served"] = n_sn
    res.observed["other_exceptions"] = others

    r = dict(zip(K.C2_09_REC, mem.rec[p.index]))
    res.firmware = {"ARMED": {"pending": r["pend_armed"], "served": 0},
                    "PENDING": {"pending": r["pend_pending"], "served": r["served_pending"] - r["served_armed"]},
                    "SERVED": {"pending": r["pend_served"], "served": r["served_served"] - r["served_armed"]}}
    for ph, fw in res.firmware.items():
        for k, v in fw.items():
            if res.observed[ph][k] != v:
                res.why.append(f"{ph}: firmware vê {k}={v}, observador externo {res.observed[ph][k]}")
    if res.observed["ARMED"] != {**K.C2_09_EXPECT["ARMED"]}:
        res.why.append(f"estado inicial não estabelecido: {res.observed['ARMED']}")
    if res.why:
        res.verdict = INVALIDA
        return res

    for ph in ("PENDING", "SERVED"):
        for k, v in K.C2_09_EXPECT[ph].items():
            if res.observed[ph][k] != v:
                res.why.append(f"{ph}: {k} = {res.observed[ph][k]}, documento {v}")
    if n_sn:
        res.why.append(f"{n_sn} atendimento(s) da linha depois de SERVED")
    if others:
        res.why.append(f"exceções inesperadas atendidas: {sorted(set(others))}")
    if res.why:
        res.verdict = DIVERGE
    return res


# ─────────────────────────────── veredito ───────────────────────────────

@dataclass
class Result:
    verdict: str
    why: list[str] = field(default_factory=list)
    points: list[PointResult] = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    hooks: dict = field(default_factory=dict)


def evaluate(case: str, runs: list[Run], points: list[K.Point], layout: Layout,
             variants: dict[str, tuple[bool, bool]]) -> Result:
    if case != "C2-09":
        raise ValueError(f"caso sem análise: {case}")
    want_ids = c2_09_ids(points)
    problems = []
    for r in runs:
        problems += validate_run(r, variants[r.variant][0], layout, want_ids)
    if problems:
        return Result(INVALIDA, problems)

    checks: dict = {}
    why: list[str] = []
    nondet = []
    for v in variants:
        reps = [r for r in runs if r.variant == v]
        for attr in ("mem", "events", "trace"):
            vals = [getattr(r, attr) for r in reps]
            if any(x != vals[0] for x in vals[1:]):
                nondet.append(f"{v}: {attr} difere entre repetições")
    checks["deterministic"] = not nondet

    base = next(r for r in runs if r.variant == "bare").mem
    intrusive = sorted({r.variant for r in runs if r.mem != base})
    checks["observer_non_intrusive"] = not intrusive
    if intrusive:
        why.append("o que o firmware vê muda com o observador externo: " + ", ".join(intrusive))
    hooks_run = next(r for r in runs if r.variant == "hooks")
    full_run = next((r for r in runs if r.variant == "full"), None)
    checks["events_same_with_trace"] = full_run is None or full_run.events == hooks_run.events
    if not checks["events_same_with_trace"]:
        why.append("o registro do observador muda quando o traço está ligado")
    if why:
        return Result(INVALIDA, why, checks=checks)
    if nondet:
        return Result(NAO_DET, nondet, checks=checks)

    assert hooks_run.mem is not None            # validate_run já exigiu
    res = [c2_09_point(p, hooks_run.events, hooks_run.mem) for p in points]
    checks["points"] = len(res)
    checks["points_by_verdict"] = dict(Counter(p.verdict for p in res))
    hk = characterize(hooks_run.events, full_run.trace if full_run else None)
    if any(p.verdict == INVALIDA for p in res):
        verdict = INVALIDA
    elif any(p.verdict == DIVERGE for p in res):
        verdict = DIVERGE
    else:
        verdict = IGUAL
    why = [f"{p.label}: {w}" for p in res for w in p.why]
    return Result(verdict, why, res, checks, hk)
