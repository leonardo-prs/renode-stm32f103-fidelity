"""C2, etapas 1 e 2: pedidos por software (04-c2.typ), firmware src/c2/sw.c.

Uso (dentro de `nix develop`):
  python3 scripts/c2_sw.py --name piloto-01            build do zero, execuções e resultado
  python3 scripts/c2_sw.py --name piloto-01 --analyze  só refaz o resultado

Etapa 1 (regras, #qF): o firmware registra a ordem dos atendimentos e as
leituras de volta; a resposta vem das regras do ARM ARM. Etapa 2 (tempo,
#qT): instante do pedido pelo gancho de escrita no STIR, instante do
atendimento e do retorno pelos ganchos de endereço em c2_irq, ausência de
instrução do fluxo principal pelo traço. Ordem dos pontos e leiaute dos
registros: os mesmos de src/c2/sw.c.
"""
from __future__ import annotations

from c2_comum import LIVRES, NS, STIR, Caso, Execucao, main, veredito

TRIO = (0, 20, 42)          # C2-02 (TRIO em sw.c)
PAR = (0, 42)               # C2-03 (PAR em sw.c)
MARCA = 0x100


def ordem(v: int) -> tuple[int, ...]:
    """Desempacota ordem() de sw.c: até 3 exceções de 9 bits e o total."""
    n = v >> 27
    return tuple((v >> (9 * k)) & 0x1FF for k in range(min(n, 3))) + ((n,) if n > 3 else ())


# ── Etapa 1 ──────────────────────────────────────────────────────────

def c2_01(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """ARM ARM §B3.4.1: desabilitada, fica pendente sem ser atendida; ao
    habilitar, é atendida uma vez; pendência zerada no fim."""
    rec = runs["bare-0"].rec
    erros, pontos = [], [(linha, mec) for linha in LIVRES for mec in (0, 1)]
    if len(rec) != 8 * len(pontos):
        return "EVIDÊNCIA INVÁLIDA", [f"registro com {len(rec)} palavras, esperado {8 * len(pontos)}"]
    for k, (linha, mec) in enumerate(pontos):
        ident, pend1, ativ1, n1, pend2, ativ2, n2, exc = rec[8 * k:8 * k + 8]
        if ident != linha | mec << 8:
            return "EVIDÊNCIA INVÁLIDA", [f"ponto {k}: identificação {ident:#x}"]
        obs = (pend1, ativ1, n1, pend2, ativ2, n2, exc)
        esp = (1, 0, 0, 0, 0, 1, 16 + linha)
        if obs != esp:
            erros.append(f"IRQ{linha} por {'STIR' if mec == 0 else 'ISPR'}: {obs} ≠ {esp}")
    v, linhas = veredito(erros, len(pontos), "pontos (linha × STIR/ISPR)")
    return v, linhas + ["por ponto: (pendente, ativa, atendimentos) depois do pedido e depois da "
                        "habilitação, e a exceção atendida; esperado (1, 0, 0, 0, 0, 1, 16 + linha)"]


def c2_02(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """ARM ARM §B1.5.4: menor número de prioridade primeiro; empate, menor
    número de exceção primeiro."""
    rec = runs["bare-0"].rec
    if len(rec) != 4096:
        return "EVIDÊNCIA INVÁLIDA", [f"registro com {len(rec)} palavras, esperado 4096"]
    erros = []
    for i, v in enumerate(rec):
        prio = ((i >> 8) & 15, (i >> 4) & 15, i & 15)
        esp = tuple(16 + linha for _, linha in sorted(zip(prio, TRIO)))
        if ordem(v) != esp:
            erros.append(f"prioridades {prio} das IRQ{TRIO}: atendidas {ordem(v)}, esperado {esp}")
    v, linhas = veredito(erros, 4096, "combinações de prioridade")
    return v, linhas + [f"linhas IRQ{TRIO}, todas as 16³ combinações das 16 prioridades, pendentes com "
                        "PRIMASK = 1 e liberadas juntas"]


def c2_03(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """ARM ARM §B1.5.4: só o pedido de prioridade maior (número menor) preempta;
    os outros são atendidos na saída."""
    rec = runs["bare-0"].rec
    if len(rec) != 512:
        return "EVIDÊNCIA INVÁLIDA", [f"registro com {len(rec)} palavras, esperado 512"]
    erros, n_pre = [], 0
    for i, v in enumerate(rec):
        a, b = PAR[i >> 8], PAR[1 - (i >> 8)]
        pa, pb = (i >> 4) & 15, i & 15
        ea, eb = 16 + a, 16 + b
        preempta = pb < pa
        n_pre += preempta
        esp = (ea, eb, ea | MARCA) if preempta else (ea, ea | MARCA, eb)
        if ordem(v) != esp:
            erros.append(f"A = IRQ{a} ({pa}), B = IRQ{b} ({pb}): {ordem(v)} ≠ {esp}")
    v, linhas = veredito(erros, 512, "pontos (papel × prioridade de A × prioridade de B)")
    return v, linhas + [f"o tratador de A pede B pelo STIR e depois anota A | 0x100; esperado preempção "
                        f"em {n_pre} pontos (prioridade de B menor em número), espera nos outros "
                        f"(igual ou maior, inclusive com B de número de exceção menor)"]


def c2_04(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """ARM ARM §B1.4.3, §B1.5.4 (Tab. B1-6, ExecutionPriority), §B5.2.3 (MSR);
    RM0008 §10.1 (4 bits): os bits baixos de BASEPRI são lidos como zero e não
    contam; BASEPRI_MAX só grava valor ≠ 0 e menor que o atual (ou atual 0)."""
    rec = runs["bare-0"].rec
    if len(rec) != 16 + 256 + 4096:
        return "EVIDÊNCIA INVÁLIDA", [f"registro com {len(rec)} palavras, esperado {16 + 256 + 4096}"]

    def efeito(base: int) -> int:
        """Bit p = 1 se a prioridade p << 4 é atendida com BASEPRI = base (já com 4 bits)."""
        return sum(1 << p for p in range(16) if base == 0 or (p << 4) < base)

    def max_doc(c: int, v: int) -> int:
        return v & 0xF0 if v != 0 and (v < c or c == 0) else c

    prim = [f"prioridade {p}: {w:#x}" for p, w in enumerate(rec[:16]) if w != 0x110]
    lb, eb, lb8, eb8 = [], [], 0, 0
    for b, w in enumerate(rec[16:272]):
        lb += [b] if w & 0xFF != b & 0xF0 else []
        eb += [b] if w >> 8 != efeito(b & 0xF0) else []
        lb8 += w & 0xFF == b
        eb8 += w >> 8 == sum(1 << p for p in range(16) if b == 0 or (p << 4) < b)
    lm, em = [], []
    for k, w in enumerate(rec[272:]):
        c, v = (k >> 8) << 4, k & 0xFF
        lm += [(c, v)] if w & 0xFF != max_doc(c, v) else []
        em += [(c, v)] if w >> 8 != efeito(max_doc(c, v)) else []

    def faixa(xs: list) -> str:
        return f"{len(xs)}" + (f" (ex.: {', '.join(hex(x) if isinstance(x, int) else f'({x[0]:#x}, {x[1]:#x})' for x in xs[:8])})"
                               if xs else "")

    linhas = [f"PRIMASK (16 prioridades: mascarada, pendente, atendida ao liberar): {16 - len(prim)}/16 iguais"
              + (f"; divergentes: {'; '.join(prim)}" if prim else ""),
              f"BASEPRI, leitura (256 valores; documento: b & 0xF0): divergentes {faixa(lb)}; "
              f"leitura = os 8 bits gravados em {lb8}/256",
              f"BASEPRI, efeito (256 valores × 16 prioridades; documento: mascara p ≥ b & 0xF0): "
              f"valores com efeito divergente {faixa(eb)}; efeito = comparação com os 8 bits em {eb8}/256",
              f"BASEPRI_MAX, leitura (BASEPRI = c, 16 valores × v, 256 valores): divergentes {faixa(lm)}",
              f"BASEPRI_MAX, efeito (idem × 16 prioridades): divergentes {faixa(em)}"]
    ok = not (prim or lb or eb or lm or em)
    return ("IGUAL" if ok else "DIVERGE"), linhas


# ── Etapa 2 ──────────────────────────────────────────────────────────

def c2_05(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """TRM §5.5.1 Fig. 5-2; Yiu §8.3.1: 12 ciclos do pedido à primeira
    instrução do tratador (±1 pela definição do instante do pedido)."""
    rec, full = runs["bare-0"].rec, runs["full-0"]
    erros_f = [f"IRQ{linha}: {ordem(v)}" for linha, v in zip(LIVRES, rec) if ordem(v) != (16 + linha,)]
    pedidos = [w for w in full.W if w[0] == STIR]
    entradas = full.entradas(sym)
    if erros_f or len(pedidos) != 15 or len(entradas) != 15 or [w[1] for w in pedidos] != list(LIVRES):
        return "EVIDÊNCIA INVÁLIDA", [f"pedidos {len(pedidos)}, entradas {len(entradas)}; {erros_f}"]
    lat, erros = [], []
    for (_, linha, tw, _, _), (_, te, _, ipsr) in zip(pedidos, entradas):
        if ipsr != 16 + linha or te < tw:
            return "EVIDÊNCIA INVÁLIDA", [f"IRQ{linha}: entrada {ipsr} em {te} ns, pedido em {tw} ns"]
        lat.append((te - tw) // NS)
        if not 11 <= lat[-1] <= 13:
            erros.append(f"IRQ{linha}: {lat[-1]} ciclos")
    v, linhas = veredito(erros, 15, "latências (STIR → 1ª instrução do tratador) em 12 ± 1 ciclos")
    return v, linhas + [f"latência medida em ciclos (125 ns), por linha {list(LIVRES)}: {lat}"]


def c2_06(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """ARM ARM §B1.5.12; TRM §5.6: o tratador encadeado começa sem instrução
    do fluxo principal, 6 ciclos depois da última instrução do anterior (±1)."""
    rec, full = runs["bare-0"].rec, runs["full-0"]
    esp = [16 + linha for linha in reversed(LIVRES)] + [16 + linha for linha in LIVRES]
    if rec != esp:
        return "DIVERGE", [f"ordem de atendimento {rec}, esperado {esp} (prioridades distintas)"]
    traco = full.traco or []
    ent = full.entradas(sym)
    ret = [a for a in full.A if a[0] != sym["c2_irq"]]
    if len(ent) != 30 or len(ret) != 30:
        return "EVIDÊNCIA INVÁLIDA", [f"{len(ent)} entradas e {len(ret)} retornos observados, esperado 30"]
    func, temp, inter = [], [], []
    for k in range(30):
        if k % 15 == 0:
            continue                                    # 1ª de cada rodada: vem do fluxo principal
        r, e = ret[k - 1], ent[k]
        if not ent[k - 1][2] < r[2] < e[2]:
            return "EVIDÊNCIA INVÁLIDA", [f"retorno {k - 1} depois da entrada {k}"]
        entre = e[2] - r[2] - 1                         # instruções entre o retorno e o tratador seguinte
        if entre != 0 or traco[r[2]] != r[0] or traco[e[2]] != e[0]:
            func.append(f"transição {k}: {entre} instruções entre o retorno e o tratador")
        ciclos = (e[1] - r[1]) // NS
        inter.append(ciclos)
        if not 5 <= ciclos <= 7:
            temp.append(f"transição {k}: {ciclos}")
    vf, lf = veredito(func, 28, "encadeamentos sem instrução do fluxo principal (traço)")
    vt, lt = veredito(temp, 28, "intervalos (última instrução do tratador → 1ª do encadeado) em 6 ± 1 ciclos")
    v = "IGUAL" if vf == vt == "IGUAL" else f"{vf} (#qF), {vt} (#qT)"
    return v, [f"#qF: {x}" for x in lf] + [f"#qT: {x}" for x in lt] + \
        [f"intervalos medidos em ciclos: {sorted(set(inter))}", "ordem de atendimento igual à das prioridades"]


R = 1_000_000           # 1 ms de tempo virtual, em ns
CASOS = [
    Caso("C2-01", 1, 5 * R, c2_01),
    Caso("C2-02", 2, 150 * R, c2_02),
    Caso("C2-03", 3, 30 * R, c2_03),
    Caso("C2-04", 4, 600 * R, c2_04),
    Caso("C2-05", 5, 5 * R, c2_05, ganchos=("c2_irq",), escritas=(STIR,)),
    Caso("C2-06", 6, 5 * R, c2_06, ganchos=("c2_irq",), retornos=("c2_irq",), traco=True),
]

if __name__ == "__main__":
    main("c2-sw", CASOS, (__doc__ or "").splitlines()[0])
