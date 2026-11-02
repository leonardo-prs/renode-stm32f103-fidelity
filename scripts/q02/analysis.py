"""Análise do Q-02: funções puras sobre os arquivos brutos de cada execução.

O Q-02 não tem oráculo de fidelidade: o firmware não é julgado. Cada
instrumento é conferido contra referências independentes dele — o traço de
execução, a visão do próprio firmware (q02_rec) e a especificação dos
estímulos (spec.py) — e o caso responde se eles CONCORDAM.

Ordem das decisões (03-quadro-comum.typ, família Q):
  1. EVIDÊNCIA INVÁLIDA: a execução falhou (tempo esgotado, falta, fim
     anormal, registro ausente); nada foi comparado.
  2. NÃO DETERMINÍSTICO: repetições da mesma variante diferem.
  3. REPROVADO: algum critério de concordância ou de não intrusão falhou;
     o instrumento correspondente não serve aos casos que dependem dele.
  4. IGUAL: todos os critérios valem.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import spec

NS_PER_TICK = 125
IGUAL, REPROVADO = "IGUAL", "REPROVADO"
NAO_DET, INVALIDA = "NÃO DETERMINÍSTICO", "EVIDÊNCIA INVÁLIDA"
EXC_RETURN = frozenset({0xFFFFFFF1, 0xFFFFFFF9, 0xFFFFFFFD})
ACTIVE_BIT = {spec.EXC_PENDSV: 1 << 10, spec.EXC_SYSTICK: 1 << 11}     # SHCSR
INSTRUMENTS = ("escrita", "exceção", "monitor", "não intrusão")


@dataclass(frozen=True)
class Ev:
    kind: str                  # P H B E W F S M
    pc: int
    vt: int                    # ns de tempo virtual
    instr: int                 # instruções executadas pelo núcleo
    data: tuple = ()

    @property
    def off(self) -> int:
        """Tempo virtual em ticks menos instruções executadas (0 ⇔ tick = instrução)."""
        return self.vt // NS_PER_TICK - self.instr

    @property
    def ipsr(self) -> int:
        x = {"H": 0, "B": 1, "E": 1, "F": 0}[self.kind]
        return self.data[x] & 0x1FF


def parse_event(line: str) -> Ev:
    f = line.split()
    k = f[0]
    h = lambda x: int(x, 16)        # noqa: E731
    if k == "P":
        return Ev(k, h(f[1]), int(f[2]), int(f[3]), (h(f[4]),))
    if k == "H":
        return Ev(k, h(f[1]), int(f[2]), int(f[3]), (h(f[4]), h(f[5])))
    if k in ("B", "E"):
        return Ev(k, h(f[4]), int(f[2]), int(f[3]), (int(f[1]), h(f[5]), h(f[6])))
    if k == "W":
        return Ev(k, h(f[6]), int(f[4]), int(f[5]), (h(f[1]), h(f[2]), f[3]))
    if k == "F":
        return Ev(k, h(f[1]), int(f[2]), int(f[3]), (h(f[4]),))
    if k == "S":
        return Ev(k, h(f[3]), int(f[1]), int(f[2]))
    if k == "M":
        return Ev(k, h(f[3]), int(f[1]), int(f[2]), (h(f[4]), h(f[5])))
    raise ValueError(f"evento desconhecido: {line!r}")


@dataclass
class Run:
    variant: str
    rep: int
    events: list[Ev]
    stim: list[Ev]
    rec: dict | None
    trace: list[int] | None
    error: str | None = None


def read_run(run_dir: Path, variant: str, rep: int, error: str | None = None) -> Run:
    def lines(name):
        p = run_dir / name
        return [l for l in p.read_text().splitlines() if l.strip()] if p.is_file() else None

    events = [parse_event(l) for l in lines("events.txt") or []]
    stim = [parse_event(l) for l in lines("stim.txt") or []]
    rec = None
    m = lines("mem.txt")
    if m is not None:
        try:
            words = [int(x) for x in m[0].split()[1:]]
            if len(words) != spec.REC_WORDS:
                raise ValueError
            rec = spec.decode_rec(words)
        except (IndexError, ValueError):
            error = error or "mem.txt malformado"
    tr = lines("trace.txt")
    return Run(variant, rep, events, stim, rec, [int(l, 16) for l in tr] if tr is not None else None, error)


@dataclass(frozen=True)
class Layout:
    """O que a análise precisa do ELF (gravado em plan.json)."""
    point: int
    store: int                         # a instrução de escrita de q02_store
    trigger: int
    handlers: dict[int, range]         # número da exceção → faixa do tratador
    reset: range                       # Reset_Handler (zera .bss)
    wait_loads: frozenset[int]         # leituras de q02_mbox em q02_wait
    returns: frozenset[int]            # instruções que podem fazer retorno de exceção
    sink: int                          # q02_sink[0] (vigiada)
    stores: frozenset[int]             # todas as instruções de escrita


# ─────────────────────────────── validade ───────────────────────────────

def validate_run(run: Run) -> list[str]:
    bad = []
    if run.error:
        bad.append(run.error)
    if run.rec is None:
        bad.append("registro do firmware não lido (mem.txt ausente)")
    elif run.rec["status"] != spec.ST_DONE:
        bad.append(f"status = {run.rec['status']} (esperado {spec.ST_DONE}: fim normal)")
    if any(e.kind == "F" for e in run.events):
        bad.append("execução caiu em q02_fault")
    kinds = Counter(e.kind for e in run.stim)
    if kinds["S"] != 1 or kinds["M"] != len(spec.PAUSES_NS):
        bad.append(f"estímulos registrados: {dict(kinds)} (esperado S=1, M={len(spec.PAUSES_NS)})")
    return [f"{run.variant}#{run.rep}: {b}" for b in bad]


# ─────────────────────────────── critérios ───────────────────────────────

@dataclass
class Criterion:
    instrument: str
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"instrument": self.instrument, "criterion": self.name, "ok": self.ok, "detail": self.detail}


class Checker:
    def __init__(self):
        self.items: list[Criterion] = []

    def add(self, instrument: str, name: str, problems: list[str]):
        self.items.append(Criterion(instrument, name, not problems, "; ".join(problems[:6])))


def _segments(events: list[Ev]) -> dict[str, list[Ev]]:
    """Eventos entre o ponto de início e o de fim de cada segmento."""
    pos = {e.data[0]: k for k, e in enumerate(events) if e.kind == "P"}
    out = {}
    for name, (b, e) in spec.POINT.items():
        if b in pos and e in pos:
            out[name] = events[pos[b] + 1:pos[e]]
    return out


def _p_off(events: list[Ev]) -> int:
    return next(e.off for e in events if e.kind == "P")


def check_writes(ck: Checker, ev: list[Ev], rec: dict, lay: Layout, trace: list[int] | None):
    I = "escrita"
    ws = [e for e in ev if e.kind == "W"]
    first_p = next(k for k, e in enumerate(ev) if e.kind == "P")
    before = [e for e in ev[:first_p] if e.kind == "W"]
    after = [e for e in ev[first_p:] if e.kind == "W"]
    watched = {lay.sink, spec.ICSR}
    ck.add(I, "toda escrita observada é de palavra, num endereço vigiado", [
        f"W 0x{e.data[0]:x} largura {e.data[2]}" for e in ws
        if e.data[0] not in watched or e.data[2] != "DoubleWord"])
    ck.add(I, "antes de main, só a escrita de .bss em q02_sink[0] (zero, no Reset_Handler)", [
        f"W 0x{e.data[0]:x}=0x{e.data[1]:x} pc 0x{e.pc:x}" for e in before
        if e.data[0] != lay.sink or e.data[1] != 0 or e.pc not in lay.reset] +
        ([] if len(before) == 1 else [f"{len(before)} escritas antes de main (esperado 1)"]))
    ck.add(I, "em main e nos tratadores, toda escrita observada vem de q02_store",
           [f"W em pc 0x{e.pc:x}" for e in after if e.pc != lay.store])
    wlog = [tuple(x) for x in zip(rec["wlog"][0::2], rec["wlog"][1::2])][:rec["wlog_n"]]
    sink_fw = [v for a, v in wlog if a == lay.sink]
    sink_obs = [e.data[1] for e in after if e.data[0] == lay.sink]
    ck.add(I, "valores em q02_sink[0] = os que o firmware gravou, na ordem (a vizinha não aparece)",
           [] if sink_obs == sink_fw == list(spec.SINK_VALUES) else
           [f"observado {[hex(v) for v in sink_obs]}, firmware {[hex(v) for v in sink_fw]}"])
    icsr_fw = Counter([v for a, v in wlog if a == spec.ICSR] + [spec.PENDSTSET] * rec["pendsv_icsr"]
                      + [spec.PENDSVSET] * rec["systick_icsr"])
    icsr_obs = Counter(e.data[1] for e in after if e.data[0] == spec.ICSR)
    ck.add(I, "escritas no ICSR = as da thread (registradas) + as contadas pelos tratadores",
           [] if icsr_obs == icsr_fw else [f"observado {dict(icsr_obs)}, firmware {dict(icsr_fw)}"])
    off = _p_off(ev)
    ck.add(I, "tempo virtual = instruções no gancho de escrita (mesmo offset dos pontos)",
           [f"W em instr {e.instr}: offset {e.off} (pontos {off})" for e in ws if e.off != off])
    if trace is not None:
        ck.add(I, "o traço mostra a escrita no PC e na instrução do evento",
               [f"W instr {e.instr}: PC 0x{e.pc:x}, traço 0x{trace[e.instr]:x}" for e in ws
                if not 0 <= e.instr < len(trace) or trace[e.instr] != e.pc])
        n_trace = sum(1 for pc in trace if pc == lay.store)
        ck.add(I, "toda execução de q02_store no traço gerou evento, exceto a da vizinha (uma)",
               [] if n_trace == len(after) + 1 else [f"traço {n_trace} execuções; {len(after)} eventos + 1 vizinha"])


def _match_exceptions(ev: list[Ev]) -> tuple[list[tuple[Ev, Ev, Ev | None]], list[str]]:
    """Pareia B, H e E por pilha (o E fecha o tratador aberto mais recente)."""
    seq = [e for e in ev if e.kind in ("B", "H", "E")]
    bad, out, stack = [], [], []
    k = 0
    while k < len(seq):
        e = seq[k]
        if e.kind == "B":
            nxt = seq[k + 1] if k + 1 < len(seq) else None
            if nxt is None or nxt.kind != "H" or nxt.instr != e.instr:
                bad.append(f"B em instr {e.instr} sem tratador na mesma instrução")
                k += 1
                continue
            stack.append([e, nxt, None])
            k += 2
            continue
        if e.kind == "H":
            bad.append(f"tratador em instr {e.instr} sem início de exceção")
        elif e.kind == "E":
            if not stack or stack[-1][1].ipsr != e.ipsr:
                bad.append(f"E em instr {e.instr} (IPSR {e.ipsr}) sem tratador aberto")
            else:
                b, h, _ = stack.pop()
                out.append((b, h, e))
        k += 1
    bad += [f"tratador IPSR {h.ipsr} (instr {h.instr}) sem fim" for _, h, _ in stack]
    out.sort(key=lambda t: t[1].instr)
    return out, bad


def check_exceptions(ck: Checker, ev: list[Ev], rec: dict, lay: Layout, trace: list[int] | None):
    I = "exceção"
    pairs, bad = _match_exceptions(ev)
    bad += [f"H em 0x{h.pc:x} com IPSR {h.ipsr}" for _, h, _ in pairs
            if h.pc != lay.handlers.get(h.ipsr, range(0)).start]
    bad += [f"E com PC 0x{e.pc:x} (não é EXC_RETURN)" for _, _, e in pairs if e and e.pc not in EXC_RETURN]
    ck.add(I, "estrutura: B e H na mesma instrução; cada E fecha o tratador aberto (pilha por IPSR)", bad)
    hs = [h for _, h, _ in pairs]
    n_obs = {x: sum(1 for h in hs if h.ipsr == x) for x in lay.handlers}
    n_fw = {spec.EXC_PENDSV: rec["n_pendsv"], spec.EXC_SYSTICK: rec["n_systick"]}
    ck.add(I, "entradas por exceção = contadas pelo firmware",
           [] if n_obs == n_fw else [f"observado {n_obs}, firmware {n_fw}"])
    order = []
    for x, other, key in ((spec.EXC_PENDSV, spec.EXC_SYSTICK, "pendsv_saw"),
                          (spec.EXC_SYSTICK, spec.EXC_PENDSV, "systick_saw")):
        mine = [h for h in hs if h.ipsr == x]
        for k, h in enumerate(mine[:spec.N_SAW]):
            before = sum(1 for g in hs if g.ipsr == other and g.instr < h.instr)
            if before != rec[key][k]:
                order.append(f"entrada {k} de IPSR {x}: {before} de IPSR {other} antes; firmware {rec[key][k]}")
    ck.add(I, "ordem das entradas = a vista pelo firmware", order)
    nested = sum(1 for _, h, _ in pairs if h.ipsr == spec.EXC_SYSTICK and any(
        h2.ipsr == spec.EXC_PENDSV and h2.instr < h.instr and e2 is not None and e2.instr > h.instr
        for _, h2, e2 in pairs))
    fw_nested = rec["nest_after"] - rec["nest_before"]
    ck.add(I, "aninhamento (SysTick dentro do PendSV) = o visto pelo firmware",
           [] if nested == fw_nested else [f"observado {nested}, firmware {fw_nested}"])
    off = _p_off(ev)
    ck.add(I, "tempo virtual = instruções na 1ª instrução do tratador (mesmo offset dos pontos)",
           [f"H em instr {h.instr}: offset {h.off}" for h in hs if h.off != off])
    if trace is not None:
        tb = []
        for b, h, e in pairs:
            if not 0 < h.instr < len(trace) or trace[h.instr] != h.pc:
                tb.append(f"H instr {h.instr}: traço 0x{trace[h.instr]:x}")
            if e is not None and (e.instr >= len(trace) or trace[e.instr - 1] not in lay.returns):
                tb.append(f"E instr {e.instr}: instrução anterior 0x{trace[e.instr - 1]:x} não é de retorno")
        for x, r in lay.handlers.items():
            n_tr = sum(1 for pc in trace if pc == r.start)
            if n_tr != n_obs[x]:
                tb.append(f"IPSR {x}: {n_tr} entradas no traço, {n_obs[x]} nos ganchos")
        ck.add(I, "o traço confirma cada entrada (1ª instrução) e cada retorno (instrução de retorno antes do E)", tb)


def check_monitor(ck: Checker, ev: list[Ev], stim: list[Ev], rec: dict, lay: Layout,
                  trace: list[int] | None):
    I = "monitor"
    ms = [e for e in stim if e.kind == "M"]
    s = next(e for e in stim if e.kind == "S")
    expect_mbox = (0,) + spec.PAUSE_VALUES[:-1]
    ck.add(I, "leitura pelo monitor na pausa = o que o firmware gravou", [
        f"pausa {k}: echo 0x{m.data[0]:x}, mbox 0x{m.data[1]:x}" for k, m in enumerate(ms)
        if m.data[0] != spec.ECHO_VALUE or m.data[1] != expect_mbox[k]])
    off = _p_off(ev) if ev else 0
    ck.add(I, "a pausa acontece no instante pedido, com tick = instrução", [
        f"pausa {k}: vt {m.vt} (pedido {t}), instr {m.instr} (esperado {t // NS_PER_TICK - off})"
        for k, (m, t) in enumerate(zip(ms, spec.PAUSES_NS))
        if m.vt != t or m.instr != t // NS_PER_TICK - off])
    ck.add(I, "o firmware vê os valores gravados pelo monitor",
           [] if rec["pause_seen"] == list(spec.PAUSE_VALUES) else [f"visto {rec['pause_seen']}"])
    ck.add(I, "o firmware vê o valor gravado pelo gancho de estímulo na leitura seguinte",
           [] if rec["hook_seen"] == spec.HOOK_VALUE else [f"visto 0x{rec['hook_seen']:x}"])
    ck.add(I, "o gancho de estímulo executa no endereço pedido", [] if s.pc == lay.trigger else [f"PC 0x{s.pc:x}"])
    waits = []
    if ev:
        p = {e.data[0]: e for e in ev if e.kind == "P"}
        waits = [(p[spec.POINT["M_PAUSE"][0]], p[spec.POINT_SEEN1]), (p[spec.POINT_SEEN1], p[spec.POINT["M_PAUSE"][1]])]
        ck.add(I, "o firmware já esperava antes de cada pausa e só seguiu depois dela", [
            f"pausa {k}: espera de instr {a.instr} a {b.instr}, pausa em {m.instr}"
            for k, ((a, b), m) in enumerate(zip(waits, ms)) if not a.instr < m.instr <= b.instr])
    if trace is not None and ev:
        vis = []
        for k, ((a, b), m) in enumerate(zip(waits, ms)):
            loads = [i for i in range(a.instr, b.instr) if trace[i] in lay.wait_loads]
            before = [i for i in loads if i < m.instr]
            after = [i for i in loads if i >= m.instr]
            # A espera termina na 1ª leitura que vê o valor: exatamente uma depois da pausa.
            if not before or len(after) != 1:
                vis.append(f"pausa {k}: {len(before)} leituras antes e {len(after)} depois (esperado ≥1 e 1)")
        ck.add(I, "a escrita na pausa é vista pela 1ª leitura executada depois dela, e por nenhuma antes", vis)
        ck.add(I, "o traço confirma o instante do gancho de estímulo",
               [] if 0 <= s.instr < len(trace) and trace[s.instr] == lay.trigger else [f"S instr {s.instr}"])


# ─────────────────────────── caracterização ───────────────────────────

def characterize(ev: list[Ev], stim: list[Ev], trace: list[int] | None) -> dict:
    """Fatos sobre os ganchos (relatados, fora do critério)."""
    off = _p_off(ev)
    pairs, _ = _match_exceptions(ev)
    out: dict = {"offset_points": off}
    for kind in "PHBEW":
        c = Counter(e.off - off for e in ev if e.kind == kind)
        if c:
            out[f"offset_{kind}"] = {str(k): v for k, v in sorted(c.items())}
    out["B_index"] = sorted({e.data[0] for e in ev if e.kind == "B"})
    out["E_index"] = sorted({e.data[0] for e in ev if e.kind == "E"})
    out["E_pc"] = sorted({f"0x{e.pc:x}" for e in ev if e.kind == "E"})
    segs = _segments(ev)
    out["segments"] = {}
    for name, evs in segs.items():
        xs = [f"{e.kind}{e.ipsr}" if e.kind in "BHE" else f"W:{e.data[1]:x}" if e.kind == "W" else e.kind
              for e in evs if e.kind in "BHEW"]
        out["segments"][name] = " ".join(xs)
    chained = {e1.instr for (_, _, e1), (b2, _, _) in zip(pairs, pairs[1:]) if e1 is not None and b2.instr == e1.instr}
    b_ipsr, b_act, e_act, b_pc_ret = Counter(), Counter(), Counter(), Counter()
    for b, h, e in pairs:
        x = h.ipsr
        b_ipsr[f"{x}: IPSR no B = {b.ipsr}"] += 1
        b_act[f"{x}: ativa no B = {bool(b.data[2] & ACTIVE_BIT[x])}, no H = {bool(h.data[1] & ACTIVE_BIT[x])}"] += 1
        if e is not None:
            e_act[f"{x}: ativa no E = {bool(e.data[2] & ACTIVE_BIT[x])}, IPSR no E = {e.ipsr}"] += 1
            if trace is not None and e.instr < len(trace):
                if e.instr in chained:
                    b_pc_ret["o E encadeou outro tratador (B seguinte na mesma instrução)"] += 1
                elif trace[e.instr] == b.pc:
                    b_pc_ret["PC do B = instrução retomada depois do E"] += 1
                else:
                    b_pc_ret["PC do B ≠ instrução retomada depois do E"] += 1
    out["B_ipsr"] = dict(b_ipsr)
    out["active_bits"] = dict(b_act)
    out["E_state"] = dict(e_act)
    if b_pc_ret:
        out["B_pc_vs_resume"] = dict(b_pc_ret)
    chain = []
    for (b1, h1, e1), (b2, h2, e2) in zip(pairs, pairs[1:]):
        if e1 is not None and b2.instr == e1.instr:
            chain.append(f"IPSR {h1.ipsr} → {h2.ipsr}: E e B na mesma instrução ({e1.instr})")
    out["tail_chain"] = chain
    ms = [e for e in stim if e.kind == "M"]
    out["pause_pc"] = [f"0x{m.pc:x}" for m in ms]
    return out


# ─────────────────────────────── veredito ───────────────────────────────

@dataclass
class Result:
    verdict: str
    why: list[str] = field(default_factory=list)
    criteria: list[Criterion] = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    hooks: dict = field(default_factory=dict)


def evaluate(runs: list[Run], layout: Layout, variants: dict[str, tuple[bool, bool]]) -> Result:
    problems = [p for r in runs for p in validate_run(r)]
    if problems:
        return Result(INVALIDA, problems)

    nondet = []
    for v in variants:
        reps = [r for r in runs if r.variant == v]
        for attr in ("rec", "events", "stim", "trace"):
            vals = [getattr(r, attr) for r in reps]
            if any(x != vals[0] for x in vals[1:]):
                nondet.append(f"{v}: {attr} difere entre repetições")
    if nondet:
        return Result(NAO_DET, nondet, checks={"deterministic": False})

    ck = Checker()
    first = {v: next(r for r in runs if r.variant == v) for v in variants}
    base = first["bare"]
    I = "não intrusão"
    ck.add(I, "o registro do firmware é o mesmo sem e com observação",
           [v for v, r in first.items() if r.rec != base.rec])
    ck.add(I, "os estímulos (pausas e gancho de estímulo) ocorrem nos mesmos instantes sem e com observação",
           [v for v, r in first.items() if r.stim != base.stim])
    hooks, full = first["hooks"], first.get("full")
    if full is not None:
        ck.add(I, "o registro do observador é o mesmo sem e com traço", [] if full.events == hooks.events else ["difere"])
    assert hooks.rec is not None
    trace = full.trace if full is not None else None
    check_writes(ck, hooks.events, hooks.rec, layout, trace)
    check_exceptions(ck, hooks.events, hooks.rec, layout, trace)
    check_monitor(ck, hooks.events, hooks.stim, hooks.rec, layout, trace)
    failed = [c for c in ck.items if not c.ok]
    checks = {"deterministic": True,
              "by_instrument": {i: all(c.ok for c in ck.items if c.instrument == i) for i in INSTRUMENTS},
              "criteria": len(ck.items), "failed": len(failed)}
    hk = characterize(hooks.events, hooks.stim, trace)
    why = [f"[{c.instrument}] {c.name}: {c.detail}" for c in failed]
    return Result(REPROVADO if failed else IGUAL, why, ck.items, checks, hk)
