"""Análise do Q-01: funções puras sobre os arquivos brutos de cada execução.

Entrada por execução (variant, rep):
  hooks.txt  "pc_hex vt_ns instr" por passagem de gancho (variantes hooks/full)
  mem.txt    q01_count e os valores do DWT_CYCCNT, em ordem de execução
  trace.txt  um PC por instrução executada (variante full)
  fault.txt  presente só se a execução caiu em q01_fault

Ordem das decisões (03-quadro-comum.typ, §Vereditos): primeiro se a
comparação pôde ser feita (EVIDÊNCIA INVÁLIDA), depois o determinismo, por
fim IGUAL/DIVERGE. "IGUAL" aqui = as três medidas concordam em todos os
segmentos e o observador externo não altera o CYCCNT.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

NS_PER_TICK = 125
U32 = 1 << 32

IGUAL, DIVERGE = "IGUAL", "DIVERGE"
NAO_DET, INVALIDA = "NÃO DETERMINÍSTICO", "EVIDÊNCIA INVÁLIDA"

# Conteúdo de cada segmento (pN → pN+1), espelho dos comentários de
# src/q01/q01.S. Só descreve; a contagem vem das medidas.
SEGMENTS = {
    (0, 1): "vazio (STR do ponto anterior)",
    (1, 2): "linha reta: 16 NOPs",
    (2, 3): "laço curto: 10 voltas (SUBS/BNE)",
    (3, 4): "chamada e retorno (BL, BX LR)",
    (4, 5): "memória: SRAM, SCB_CPUID, literal na flash",
    (5, 6): "blocos IT com 2 instruções puladas",
    (6, 7): "SVC → 1ª instrução do tratador",
    (7, 8): "tratador SVC → retorno (EXC_RETURN)",
    (8, 9): "PENDSVSET, DSB, ISB → 1ª instrução do PendSV",
    (9, 10): "tratador PendSV → retorno",
    (10, 11): "laço longo: 100 voltas",
    (11, 0): "fim da passagem → início da seguinte (código C de main)",
}


@dataclass
class Run:
    variant: str
    rep: int
    hooks: list[tuple[int, int, int]] | None    # (pc, vt_ns, instruções)
    cyc: list[int] | None
    trace: list[int] | None
    fault: str | None
    error: str | None = None


@dataclass
class Segment:
    pass_: int
    a: int
    b: int
    d_cyc: int
    d_vt_ns: int
    d_trace: int | None
    d_instr: int

    @property
    def d_vt_ticks(self) -> Fraction:
        return Fraction(self.d_vt_ns, NS_PER_TICK)

    @property
    def agree(self) -> bool:
        return self.d_vt_ticks == self.d_cyc == self.d_trace

    def as_dict(self) -> dict:
        return {"pass": self.pass_, "from": f"p{self.a}", "to": f"p{self.b}",
                "what": SEGMENTS.get((self.a, self.b), "?"), "d_cyccnt": self.d_cyc,
                "d_vt_ns": self.d_vt_ns, "d_vt_ticks": str(self.d_vt_ticks),
                "d_trace": self.d_trace, "d_executed_instructions": self.d_instr,
                "agree": self.agree}


@dataclass
class Result:
    verdict: str
    why: list[str] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    checks: dict = field(default_factory=dict)


# ───────────────────────────── leitura ─────────────────────────────

def read_run(run_dir: Path, variant: str, rep: int, error: str | None = None) -> Run:
    def lines(name):
        p = run_dir / name
        return [l for l in p.read_text().splitlines() if l.strip()] if p.is_file() else None

    hk = lines("hooks.txt")
    mem = lines("mem.txt")
    tr = lines("trace.txt")
    ft = lines("fault.txt")
    hooks = [(int(p, 16), int(t), int(i)) for p, t, i in (l.split() for l in hk)] if hk is not None else None
    cyc = None
    if mem is not None:
        n, vals = int(mem[0]), [int(v) for v in mem[1:]]
        cyc = vals if len(vals) == n else None
        if cyc is None and error is None:
            error = f"mem.txt truncado: q01_count={n}, {len(vals)} valores"
    trace = [int(l, 16) for l in tr] if tr is not None else None
    return Run(variant, rep, hooks, cyc, trace, "\n".join(ft) if ft else None, error)


# ───────────────────────────── validade ─────────────────────────────

def expected_order(points: list[tuple[int, int]], passes: int) -> list[int]:
    return [a for _ in range(passes) for _, a in points]


def validate(run: Run, points: list[tuple[int, int]], passes: int, uses_hooks: bool,
             uses_trace: bool) -> list[str]:
    """Problemas do instrumento nesta execução (lista vazia = válida)."""
    bad = []
    if run.error:
        bad.append(run.error)
    if run.fault:
        bad.append(f"execução caiu em q01_fault ({run.fault.split()[0]})")
    want = expected_order(points, passes)
    if run.cyc is None:
        bad.append("vetor do CYCCNT ausente")
    elif len(run.cyc) != len(want):
        bad.append(f"{len(run.cyc)} valores do CYCCNT, esperados {len(want)}")
    if uses_hooks:
        if run.hooks is None:
            bad.append("registro dos ganchos ausente")
        elif [h[0] for h in run.hooks] != want:
            bad.append("ganchos fora da ordem esperada dos pontos")
    if uses_trace:
        addrs = {a for _, a in points}
        if run.trace is None:
            bad.append("traço ausente")
        elif [p for p in run.trace if p in addrs] != want:
            bad.append("pontos do traço fora da ordem esperada")
    return [f"{run.variant}#{run.rep}: {b}" for b in bad]


# ───────────────────────────── medidas ─────────────────────────────

def trace_positions(trace: list[int], addrs: set[int]) -> list[int]:
    return [i for i, p in enumerate(trace) if p in addrs]


def segments(run: Run, points: list[tuple[int, int]]) -> list[Segment]:
    """Todos os pares de pontos consecutivos na ordem de execução."""
    num = {a: n for n, a in points}
    pos = trace_positions(run.trace, set(num)) if run.trace is not None else None
    out = []
    per_pass = len(points)
    for k in range(len(run.hooks) - 1):
        (pa, ta, ia), (pb, tb, ib) = run.hooks[k], run.hooks[k + 1]
        out.append(Segment(pass_=k // per_pass + 1, a=num[pa], b=num[pb],
                           d_cyc=(run.cyc[k + 1] - run.cyc[k]) % U32, d_vt_ns=tb - ta,
                           d_trace=(pos[k + 1] - pos[k]) if pos is not None else None,
                           d_instr=ib - ia))
    return out


# ───────────────────────────── veredito ─────────────────────────────

def evaluate(runs: list[Run], points: list[tuple[int, int]], passes: int,
             variants: dict[str, tuple[bool, bool]]) -> Result:
    problems = []
    for r in runs:
        problems += validate(r, points, passes, *variants[r.variant])
    if problems:
        return Result(INVALIDA, problems)

    checks: dict = {}
    why: list[str] = []
    # Determinismo: execuções repetidas da mesma variante.
    nondet = []
    for v in variants:
        reps = [r for r in runs if r.variant == v]
        for attr in ("cyc", "hooks", "trace"):
            vals = [getattr(r, attr) for r in reps]
            if any(x != vals[0] for x in vals[1:]):
                nondet.append(f"{v}: {attr} difere entre repetições")
    checks["deterministic"] = not nondet

    # Não intrusão: o CYCCNT visto pelo firmware é o mesmo com e sem observador.
    base = next(r for r in runs if r.variant == "bare").cyc
    intrusive = sorted({r.variant for r in runs if r.cyc != base})
    checks["observer_non_intrusive"] = not intrusive
    if intrusive:
        why.append("o vetor do CYCCNT muda com o observador externo: " + ", ".join(intrusive))

    # Três medidas: execução com ganchos + traço (a 1ª repetição; as demais
    # já foram conferidas iguais acima, ou o caso é NÃO DETERMINÍSTICO).
    full = next(r for r in runs if r.variant == "full")
    segs = segments(full, points)
    hooks_only = next((r for r in runs if r.variant == "hooks"), None)
    checks["hooks_same_with_trace"] = hooks_only is None or hooks_only.hooks == full.hooks
    if not checks["hooks_same_with_trace"]:
        why.append("o tempo virtual nos ganchos muda quando o traço está ligado")
    bad = [s for s in segs if not s.agree]
    checks["segments"] = len(segs)
    checks["segments_agree"] = len(segs) - len(bad)
    checks["vt_multiple_of_tick"] = all(s.d_vt_ns % NS_PER_TICK == 0 for s in segs)
    checks["instr_counter_matches_trace"] = all(s.d_instr == s.d_trace for s in segs)
    for s in bad:
        why.append(f"passagem {s.pass_} p{s.a}→p{s.b}: Δvt/125 ns = {s.d_vt_ticks}, "
                   f"ΔCYCCNT = {s.d_cyc}, traço = {s.d_trace}")

    equal = not bad and not intrusive and checks["hooks_same_with_trace"]
    if nondet:
        return Result(NAO_DET, nondet + why, segs, checks)
    return Result(IGUAL if equal else DIVERGE, why, segs, checks)
