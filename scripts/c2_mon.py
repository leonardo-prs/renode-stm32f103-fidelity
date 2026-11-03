"""C2, etapa 3: janelas e WFI, pedidos pelo monitor (04-c2.typ), firmware src/c2/mon.c.

Uso (dentro de `nix develop`):
  python3 scripts/c2_mon.py --name piloto-01            build do zero, execuções e resultado
  python3 scripts/c2_mon.py --name piloto-01 --analyze  só refaz o resultado

Cada pedido é uma escrita no ISPR feita pelo monitor com a simulação parada
(perfil R1; instante e escrita verificados no Q-01). O firmware anuncia a
rodada em c2_pronto e espera num laço ocioso; o monitor confere, na pausa
de cada rodada, que a rodada anterior terminou. Rodadas de RODADA_NS em
RODADA_NS a partir de T0_NS.
"""
from __future__ import annotations

from c2_comum import ISPR, NS, Caso, Execucao, Pausa, main

T0_NS = 200_000
RODADA_NS = 100_000
L7, H7 = 0, 42                  # = L_07, H_07 em mon.c
X8, Y8 = 0, 42                  # = X_08, Y_08
W9 = 20                         # = W_09
K7 = list(range(25))            # C2-07: K em ticks
D8 = [-4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 8, 40]   # C2-08: δ em ticks em relação ao retorno de X
FAIXA_DOC_07 = (2, 14)          # C2-07: a fronteira do documento fica entre K = 2 e K = 12 + 1 + 1


def pedido(linha: int) -> tuple[int, int]:
    """Escrita no ISPR que torna a linha pendente."""
    return ISPR + 4 * (linha // 32), 1 << (linha % 32)


def vezes(sym: dict[str, int], linha: int) -> int:
    return sym["c2_vezes"] + 4 * (16 + linha)


def t_rodada(r: int) -> int:
    return T0_NS + r * RODADA_NS


def na_rodada(eventos: list[tuple[int, ...]], r: int) -> list[tuple[int, ...]]:
    return [e for e in eventos if t_rodada(r) <= e[1] < t_rodada(r + 1)]


def confere_rodadas(run: Execucao, n: int) -> str | None:
    """Na pausa do início de cada rodada (leituras: c2_pronto e os atendimentos
    das duas linhas): main está na rodada e a rodada anterior terminou."""
    p = [p for p in run.P if p[0] in {t_rodada(r) for r in range(n)} and len(p) == 5]
    for r, x in enumerate(p):
        if x[2:] != [r + 1, r, r]:
            return f"rodada {r}: na pausa, c2_pronto = {x[2]}, atendimentos = {x[3:5]}"
    return None if len(p) == n else f"{len(p)} pausas de rodada, esperado {n}"


# ── C2-07: chegada tardia ────────────────────────────────────────────

def pausas_07(sym: dict[str, int], ref: dict) -> list[Pausa]:
    ler = [sym["c2_pronto"], vezes(sym, L7), vezes(sym, H7)]
    ps = []
    for r, k in enumerate(K7):
        t = t_rodada(r)
        ps.append(Pausa(t, [pedido(L7)] + ([pedido(H7)] if k == 0 else []), ler))
        if k > 0:
            ps.append(Pausa(t + k * NS, [pedido(H7)], ler))
    return ps


def c2_07(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """TRM §5.5.1, §5.7; ARM ARM §B1.5.11: com K = 1 ciclo o pedido de maior
    prioridade chega durante a entrada (12 ciclos) e o tratador de menor não
    executa nenhuma instrução antes; com K > 12 + 1, o de menor começa e é
    preemptado. A fronteira entre os dois fica sem veredito."""
    full = runs["full-0"]
    erro = confere_rodadas(full, len(K7))
    if erro:
        return "EVIDÊNCIA INVÁLIDA", [erro]
    ent = full.entradas(sym)
    ret = [a for a in full.A if a[0] != sym["c2_irq"]]
    m = []                                  # instruções do tratador de L antes da entrada no de H
    for r, k in enumerate(K7):
        e = na_rodada(ent, r)
        el = next((x for x in e if x[3] == 16 + L7), None)
        eh = next((x for x in e if x[3] == 16 + H7), None)
        if el is None or eh is None:
            return "EVIDÊNCIA INVÁLIDA", [f"K = {k}: entradas {[(x[3], x[2]) for x in e]}"]
        if eh[2] < el[2]:
            m.append(0)
            continue
        if any(el[2] < x[2] < eh[2] for x in ret):
            return "EVIDÊNCIA INVÁLIDA", [f"K = {k}: o tratador de L terminou antes do pedido de H"]
        m.append(eh[2] - el[2])
    erros = []
    if m[0] != 0:
        erros.append(f"K = 0 (pedidos juntos): {m[0]} instruções de L antes de H")
    if m[1] != 0:
        erros.append(f"K = 1: {m[1]} instrução(ões) de L antes de H (documento: chegada tardia, nenhuma)")
    erros += [f"K = {k}: L não começou antes de H" for k, x in zip(K7, m) if k >= FAIXA_DOC_07[1] and x == 0]
    kf = next((k for k, x in zip(K7, m) if x > 0), None)
    monotona = kf is not None and all(x > 0 for k, x in zip(K7, m) if k >= kf)
    a, b = FAIXA_DOC_07
    if kf is None:
        leitura = "FRONTEIRA AUSENTE NA FAIXA"
    elif a <= kf <= b:
        leitura = "FRONTEIRA REPRODUZIDA"
    else:
        leitura = f"FRONTEIRA DESLOCADA ({kf - a if kf < a else kf - b:+d} tick em relação à faixa do documento)"
    v = "IGUAL" if not erros else "DIVERGE"
    return f"{v}; {leitura}", [
        f"pontos decididos pelo documento (K = 0, K = 1, K ≥ {b}): "
        + ("todos iguais" if not erros else "; ".join(erros)),
        f"fronteira do Renode: primeiro K em que L executa instrução antes de H = {kf}"
        f"{'' if monotona else ' (regime não monótono depois dela)'}; documento: entre K = {a} e K = {b}",
        f"instruções de L antes de H, por K = 0..{K7[-1]}: {m}",
        f"L = IRQ{L7} (prioridade 12, tratador alongado), H = IRQ{H7} (prioridade 4); pedidos pelo monitor "
        f"no ISPR, H K ticks depois de L"]


# ── C2-08: chegada durante o retorno ─────────────────────────────────

def ref_08(sym: dict[str, int]) -> Caso:
    """Execução de referência, para achar o instante do retorno de X: Y é pedida
    só no meio da rodada, longe de X."""
    return Caso("C2-08", 8, CASO_08.run_ns, c2_08, ganchos=("c2_irq",), retornos=("c2_irq",),
                pausas=lambda s, _: [p for r in range(len(D8)) for p in
                                     (Pausa(t_rodada(r), [pedido(X8)]), Pausa(t_rodada(r) + RODADA_NS // 2, [pedido(Y8)]))])


def retorno_x(run: Execucao, sym: dict[str, int], r: int) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """Entrada de X e o primeiro retorno depois dela, na rodada r."""
    ex = next((x for x in na_rodada(run.entradas(sym), r) if x[3] == 16 + X8), None)
    if ex is None:
        return None
    rx = next((a for a in run.A if a[0] != sym["c2_irq"] and a[2] > ex[2]), None)
    return (ex, rx) if rx is not None else None


def deslocamento_retorno(run: Execucao, sym: dict[str, int]) -> int | None:
    """Ticks entre o pedido de X (início da rodada) e a última instrução do tratador de X."""
    d = set()
    for r in range(len(D8)):
        xr = retorno_x(run, sym, r)
        if xr is None:
            return None
        d.add((xr[1][1] - t_rodada(r)) // NS)
    return d.pop() if len(d) == 1 else None


def pausas_08(sym: dict[str, int], ref: dict) -> list[Pausa]:
    off = deslocamento_retorno(ref["execucao"], sym)
    if off is None:
        raise SystemExit("C2-08: a referência não deu um instante de retorno constante")
    ler = [sym["c2_pronto"], vezes(sym, X8), vezes(sym, Y8)]
    ps = []
    for r, d in enumerate(D8):
        ps += [Pausa(t_rodada(r), [pedido(X8)], ler), Pausa(t_rodada(r) + (off + d) * NS, [pedido(Y8)])]
    return ps


def c2_08(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """Yiu §8.3.5; TRM §5.8 Fig. 5-5; ARM ARM §B1.5.12: um pedido que chega
    durante o desempilhamento leva direto ao novo tratador, sem instrução do
    fluxo principal. Controles: antes do retorno (encadeamento, nenhuma) e
    bem depois (nova entrada, instruções do fluxo principal)."""
    full = runs["full-0"]
    off = deslocamento_retorno(runs["ref"], sym)
    if off is None or deslocamento_retorno(full, sym) != off:
        return "EVIDÊNCIA INVÁLIDA", ["instante do retorno de X diferente da referência"]
    erro = confere_rodadas(full, len(D8))
    if erro:
        return "EVIDÊNCIA INVÁLIDA", [erro]
    traco = full.traco or []
    fluxo = []
    for r, d in enumerate(D8):
        xr = retorno_x(full, sym, r)
        ey = next((x for x in na_rodada(full.entradas(sym), r) if x[3] == 16 + Y8), None)
        if xr is None or ey is None or ey[2] <= xr[1][2] or traco[ey[2]] != sym["c2_irq"]:
            return "EVIDÊNCIA INVÁLIDA", [f"δ = {d}: entradas ou retorno não observados"]
        fluxo.append(ey[2] - xr[1][2] - 1)
    por = dict(zip(D8, fluxo))
    erros = [f"δ = {d} (antes do retorno): {x} instruções" for d, x in por.items() if d <= 0 and x != 0]
    if por[1] != 0:
        erros.append(f"δ = +1 (durante o retorno): {por[1]} instruções do fluxo principal (documento: nenhuma)")
    if por[40] == 0:
        erros.append("δ = +40 (bem depois): nenhuma instrução do fluxo principal (documento: nova entrada)")
    v = "IGUAL" if not erros else "DIVERGE"
    janela = [d for d, x in por.items() if d > 0 and x == 0]
    return v, [("pontos decididos pelo documento (δ ≤ 0, δ = +1, δ = +40): "
                + ("todos iguais" if not erros else "; ".join(erros))),
               f"instruções do fluxo principal entre a última instrução de X e a 1ª de Y, por δ: {por}",
               f"δ > 0 sem instrução do fluxo principal (janela do Renode depois do retorno): {janela}",
               f"X = IRQ{X8} (prioridade 4), Y = IRQ{Y8} (8); δ em ticks a partir do instante da última instrução "
               f"de X (gancho de endereço), que a referência pôs {off} ticks depois do pedido de X"]


# ── C2-09: WFI e PRIMASK ─────────────────────────────────────────────

TA, TB = 200_000, 400_000
ESPERA = 20_000


def pausas_09(sym: dict[str, int], ref: dict) -> list[Pausa]:
    ler = [sym["c2_pronto"], vezes(sym, W9)]
    return [Pausa(TA, [], ler), Pausa(TA + ESPERA, [pedido(W9)], ler),
            Pausa(TB, [], ler), Pausa(TB + ESPERA, [pedido(W9)], ler)]


def c2_09(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """ARM ARM §B1.5.19: o pedido acorda o núcleo do WFI mesmo com PRIMASK = 1.
    (a) PRIMASK = 0: o tratador roda antes da instrução seguinte ao WFI.
    (b) PRIMASK = 1: a execução segue depois do WFI sem o tratador, que roda
    quando PRIMASK volta a 0."""
    run = runs["bare-0"]
    p = run.P
    if len(p) != 4 or [x[2] for x in p] != [1, 1, 2, 2]:
        return "EVIDÊNCIA INVÁLIDA", [f"o firmware não estava no WFI de cada parte nas pausas: {p}"]
    dorme = [p[0][1] == p[1][1], p[2][1] == p[3][1]]
    esp = [1, 1, 2]
    erros = []
    if not all(dorme):
        erros.append(f"núcleo não ficou parado no WFI (instruções nas pausas: {[x[1] for x in p]})")
    if run.rec != esp:
        erros.append(f"atendimentos de W (depois do WFI em a; depois do WFI em b; depois de PRIMASK = 0): "
                     f"{run.rec}, esperado {esp}")
    return ("IGUAL" if not erros else "DIVERGE"), erros or [
        f"(a) e (b) iguais ao documento: atendimentos {run.rec}; núcleo parado no WFI nas duas partes "
        f"(instruções nas pausas {[x[1] for x in p]}); W = IRQ{W9}, pedido pelo monitor {ESPERA // 1000} µs "
        "depois de o núcleo entrar no WFI"]


R = 1_000_000
CASO_08 = Caso("C2-08", 8, T0_NS + (len(D8) + 1) * RODADA_NS, c2_08, ganchos=("c2_irq",),
               retornos=("c2_irq",), traco=True, pausas=pausas_08, referencia=ref_08)
CASOS = [
    Caso("C2-07", 7, T0_NS + (len(K7) + 1) * RODADA_NS, c2_07, ganchos=("c2_irq",),
         retornos=("c2_irq", "c2_espera"), traco=True, pausas=pausas_07),
    CASO_08,
    Caso("C2-09", 9, TB + 2 * ESPERA + RODADA_NS, c2_09, pausas=pausas_09),
]

if __name__ == "__main__":
    main("c2-mon", CASOS, (__doc__ or "").splitlines()[0])
