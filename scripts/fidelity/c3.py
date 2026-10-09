"""C3 — oráculos e métricas (NVIC: arbitragem, preempção, máscaras, encadeamento).

As sequências esperadas abaixo são escritas à mão a partir das regras do
PM0056 (§2.3 e §4.3/§4.4) e do ARMv7-M ARM (B1.5): entre exceções
pendentes vence a de menor prioridade de GRUPO; empate de grupo → menor
subprioridade; empate total → menor número de exceção. Preempção só por
prioridade de grupo estritamente maior. PRIMASK bloqueia todas as IRQs
configuráveis; BASEPRI bloqueia as de prioridade de grupo >= limiar.
Um handler que se pende de novo roda outra vez antes de exceções de
prioridade menor.

Tokens: escritor.evento[entrada]: M = MAIN, A = EXTI0 (IRQ 6), B = EXTI1
(IRQ 7). A sequência observada é a ordem global dos tickets (inc/fidelity.h)
e precisa ser IDÊNTICA à esperada, com todas as ocorrências.
"""
from __future__ import annotations

from statistics import median

from .abi import EV_CASE_BEGIN, EV_CASE_END, EV_FINISH, timeline, SnapshotError
from .model import RES_LOG, RunEval

EV_ENTER, EV_AFTER_PEND, EV_EXIT = 0x300, 0x301, 0x302
EV_REQUEST, EV_RELEASE, EV_BACK = 0x310, 0x311, 0x312
WRITER = {0: "M", 1: "A", 2: "B"}
IPSR = {"A": 16 + 6, "B": 16 + 7}

REQ2 = ["M.REQ", "M.REQ", "M.REL"]
A_ = ["A.ENTER0", "A.EXIT0"]
B_ = ["B.ENTER0", "B.EXIT0"]

CASES = {
    0x01: ("arbitragem: grupo A > grupo B", REQ2 + A_ + B_ + ["M.BACK"]),
    0x02: ("arbitragem: grupo B > grupo A", REQ2 + B_ + A_ + ["M.BACK"]),
    0x03: ("arbitragem: mesmo grupo, sub A < sub B", REQ2 + A_ + B_ + ["M.BACK"]),
    0x04: ("arbitragem: mesmo grupo, sub B < sub A", REQ2 + B_ + A_ + ["M.BACK"]),
    0x05: ("arbitragem: empate, pedido A→B", REQ2 + A_ + B_ + ["M.BACK"]),
    0x06: ("arbitragem: empate, pedido B→A", REQ2 + A_ + B_ + ["M.BACK"]),
    0x11: ("preempção: B (grupo maior) durante A",
           ["M.REQ", "A.ENTER0", "B.ENTER0", "B.EXIT0", "A.AFTER_PEND", "A.EXIT0", "M.BACK"]),
    0x12: ("sem preempção: mesmo grupo, sub maior",
           ["M.REQ", "A.ENTER0", "A.AFTER_PEND", "A.EXIT0"] + B_ + ["M.BACK"]),
    0x13: ("sem preempção: grupo menor",
           ["M.REQ", "A.ENTER0", "A.AFTER_PEND", "A.EXIT0"] + B_ + ["M.BACK"]),
    0x14: ("preempção, papéis invertidos: A durante B",
           ["M.REQ", "B.ENTER0", "A.ENTER0", "A.EXIT0", "B.AFTER_PEND", "B.EXIT0", "M.BACK"]),
    0x15: ("sem preempção: empate total",
           ["M.REQ", "A.ENTER0", "A.AFTER_PEND", "A.EXIT0"] + B_ + ["M.BACK"]),
    0x21: ("PRIMASK: pendente até liberar", ["M.REQ", "M.REL"] + A_ + ["M.BACK"]),
    0x22: ("BASEPRI: A acima do limiar, B abaixo",
           ["M.REQ"] + A_ + ["M.REQ", "M.REL"] + B_ + ["M.BACK"]),
    0x23: ("BASEPRI: prioridade igual ao limiar", REQ2 + A_ + B_ + ["M.BACK"]),
    0x31: ("encadeamento: A pende B (grupo menor)",
           ["M.REQ", "A.ENTER0", "A.AFTER_PEND", "A.EXIT0"] + B_ + ["M.BACK"]),
    0x32: ("controle: A volta à thread, MAIN pende B",
           ["M.REQ"] + A_ + ["M.BACK", "M.REQ"] + B_ + ["M.BACK"]),
    0x41: ("repetição: A se pende de novo (A, A, B)",
           REQ2 + ["A.ENTER0", "A.AFTER_PEND", "A.EXIT0", "A.ENTER1", "A.EXIT1"] + B_ + ["M.BACK"]),
    0x42: ("repetição: B se pende de novo (B, B, A)",
           REQ2 + ["B.ENTER0", "B.AFTER_PEND", "B.EXIT0", "B.ENTER1", "B.EXIT1"] + A_ + ["M.BACK"]),
}
PLANNED = list(CASES)

# Palavras finais esperadas: [entradas A, entradas B, pending A, pending B].
FINAL = {cid: (seq.count("A.ENTER0") + seq.count("A.ENTER1"),
               seq.count("B.ENTER0") + seq.count("B.ENTER1"), 0, 0)
         for cid, (_, seq) in CASES.items()}

# Palavras extras de casos de máscara (depois das 4 de configuração).
EXTRA = {
    0x21: [("pending durante PRIMASK", 1), ("entradas logo após pender", 0),
           ("entradas após 1000 ticks mascarado", 0)],
    0x22: [("BASEPRI lido", 0x40), ("entradas A antes de liberar", 1),
           ("entradas B antes de liberar", 0), ("pending A antes de liberar", 0),
           ("pending B antes de liberar", 1)],
    0x23: [("BASEPRI lido", 0x40), ("entradas A antes de liberar", 0),
           ("entradas B antes de liberar", 0), ("pending A antes de liberar", 1),
           ("pending B antes de liberar", 1)],
}

GROUP = {**{c: "arbitragem entre pendentes" for c in range(0x01, 0x07)},
         **{c: "preempção por prioridade de grupo" for c in range(0x11, 0x16)},
         0x21: "PRIMASK", 0x22: "BASEPRI", 0x23: "BASEPRI",
         0x31: "encadeamento (tail-chaining)", 0x32: "encadeamento (tail-chaining)",
         0x41: "repetição (auto-repending)", 0x42: "repetição (auto-repending)"}


def label(case_id: int) -> str:
    return f"c3/{case_id:02x}"


def token(e) -> str:
    names = {EV_ENTER: "ENTER", EV_AFTER_PEND: "AFTER_PEND", EV_EXIT: "EXIT",
             EV_REQUEST: "REQ", EV_RELEASE: "REL", EV_BACK: "BACK"}
    name = names.get(e.event, f"EV{e.event:#x}")
    if e.event in (EV_ENTER, EV_EXIT):
        name += str(e.arg & 0xFF)
    return f"{WRITER.get(e.writer, '?')}.{name}"


def evaluate(snap) -> RunEval:
    ev = RunEval("c3")
    try:
        times = timeline(snap)
    except SnapshotError as exc:
        ev.problems.append(f"trace inválido ({exc}): ordem e tempos do C3 não avaliáveis")
        times = None
    events = [e for e in snap.all_events()
              if e.event not in (EV_CASE_BEGIN, EV_CASE_END, EV_FINISH) and e.event >= 0x300]
    ev.extra["sequences"] = {}
    for case_id, (title, expected) in CASES.items():
        name = label(case_id)
        c = snap.case(case_id)
        if c is None:
            ev.problems.append(f"{name}: caso ausente")
            continue
        ev.case_status[name] = c.status
        mine = [e for e in events if e.case_id == case_id]
        observed = [token(e) for e in mine]
        ev.extra["sequences"][name] = observed
        if times is not None:
            ev.check(name, "sequência completa de eventos", " ".join(expected), " ".join(observed))
        for e in mine:
            if e.event == EV_ENTER:
                who = WRITER[e.writer]
                ev.check(name, f"IPSR na entrada de {who}{e.arg & 0xFF}", IPSR[who], e.arg >> 8)
        w = list(c.words)
        tail = w[-4:]
        for item, exp, obs in zip(["entradas A", "entradas B", "pending A no fim",
                                   "pending B no fim"], FINAL[case_id], tail):
            ev.check(name, item, exp, obs)
        for (item, exp), obs in zip(EXTRA.get(case_id, []), w[4:-4]):
            ev.check(name, item, exp, obs)
        if times is not None and observed == expected:
            _timing(ev, name, case_id, mine, times)
    return ev


def _timing(ev, name, case_id, mine, times):
    """Intervalos entre pontos instrumentados (ticks), só com sequência correta."""
    t = {}
    for e in mine:
        t.setdefault(token(e), []).append(times[(e.writer, e.index)])

    def first(tok):
        return t[tok][0]

    def span(a, b, metric):
        ev.metric(name, metric, first(b) - first(a), resolution=RES_LOG)

    if "M.REL" in t:
        released = [x for k, v in t.items() if k.endswith("ENTER0") for x in v if x > first("M.REL")]
        if released:
            ev.metric(name, "release_to_first_entry", min(released) - first("M.REL"),
                      resolution=RES_LOG)
    if case_id in (0x11, 0x14):
        low, high = ("A", "B") if case_id == 0x11 else ("B", "A")
        span(f"{low}.ENTER0", f"{high}.ENTER0", "preempting_entry_after_low_entry")
        span(f"{high}.EXIT0", f"{low}.AFTER_PEND", "resume_after_preemption")
    if case_id in (0x31, 0x32):
        span("A.EXIT0", "B.ENTER0", "a_exit_to_b_entry")
        span("M.REQ", "A.ENTER0", "request_to_entry")
    if case_id in (0x41, 0x42):
        r = "A" if case_id == 0x41 else "B"
        span(f"{r}.EXIT0", f"{r}.ENTER1", "repend_exit_to_reentry")
    for h in ("A", "B"):
        if f"{h}.ENTER0" in t and f"{h}.EXIT0" in t:
            span(f"{h}.ENTER0", f"{h}.EXIT0", f"{h.lower()}_inclusive_duration")
