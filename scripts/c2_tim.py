"""C2, etapa 4: o timer como fonte (04-c2.typ), firmware src/c2/tim.c.

Uso (dentro de `nix develop`):
  python3 scripts/c2_tim.py --name piloto-01            build do zero, execuções e resultado
  python3 scripts/c2_tim.py --name piloto-01 --analyze  só refaz o resultado

O instante de um evento de atualização é tomado pela entrada no tratador
(gancho no primeiro endereço de c2_irq); em regime, a latência constante se
cancela nas diferenças. Em C2-11 os contadores são ligados pelo monitor
(escrita de CEN em TIMx_CR1 com a simulação parada).
"""
from __future__ import annotations

from c2_comum import NS, Caso, Execucao, Pausa, main

TIM2, TIM3 = 0x40000000, 0x40000400
CR1, SR = 0x00, 0x10
ARPE, CEN = 0x80, 0x01
EXC2, EXC3 = 44, 45
PARES_10 = [(0, 999), (9, 99), (99, 9)]     # = PARES_10 em tim.c
N_10 = 11
D_11 = [-32, -13, 0, 13, 32]               # d = partida do TIM3 − partida do TIM2, em ticks
T0_NS, RODADA_NS = 200_000, 200_000
P_12, D_MAX_12 = 200, 800                  # = ARR_12 + 1, D_MAX_12


def entradas(run: Execucao, sym: dict[str, int], exc: int) -> list[tuple[int, ...]]:
    return [a for a in run.entradas(sym) if a[3] == exc]


# ── C2-10: período ──────────────────────────────────────────────────

def c2_10(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """RM0008 §15.3.1–15.3.2: (PSC + 1)(ARR + 1) ticks entre eventos em regime.
    Sem tolerância: os dois instantes de cada diferença são entradas no
    tratador, quantizadas na mesma grade de 1 tick, e o período é inteiro."""
    full = runs["full-0"]
    if runs["bare-0"].rec != [N_10] * 3:
        return "EVIDÊNCIA INVÁLIDA", [f"atendimentos por par {runs['bare-0'].rec}"]
    partidas = [w for w in full.W if w[0] == TIM2 + CR1 and w[1] == ARPE | CEN]
    ent = entradas(full, sym, EXC2)
    if len(partidas) != 3 or len(ent) != 3 * N_10:
        return "EVIDÊNCIA INVÁLIDA", [f"{len(partidas)} partidas e {len(ent)} entradas"]
    erros, linhas = [], []
    for k, ((psc, arr), w) in enumerate(zip(PARES_10, partidas)):
        e = [x[1] // NS for x in ent[N_10 * k:N_10 * (k + 1)]]
        p = (psc + 1) * (arr + 1)
        reg = [b - a for a, b in zip(e, e[1:])]
        primeiro = e[0] - w[2] // NS
        erros += [f"(PSC, ARR) = ({psc}, {arr}): período {x}" for x in reg if x != p]
        linhas.append(f"(PSC, ARR) = ({psc}, {arr}), esperado {p}: em regime {sorted(set(reg))} ticks "
                      f"({len(reg)} períodos); primeiro (escrita de CEN → 1ª entrada) {primeiro} ticks")
    v, l0 = veredito_periodo(erros, 3 * (N_10 - 1))
    return v, l0 + linhas


def veredito_periodo(erros: list[str], total: int) -> tuple[str, list[str]]:
    if not erros:
        return "IGUAL", [f"{total}/{total} períodos em regime iguais ao documento"]
    return "DIVERGE", [f"{total - len(erros)}/{total} períodos em regime iguais ao documento"]


# ── C2-11: empate entre timers ──────────────────────────────────────

def pausas_11(sym: dict[str, int], ref: dict) -> list[Pausa]:
    ler = [sym["c2_pronto"], sym["c2_vezes"] + 4 * EXC2, sym["c2_vezes"] + 4 * EXC3]
    ps = []
    for r, d in enumerate(D_11):
        t = T0_NS + r * RODADA_NS
        a, b = ((TIM2, 0), (TIM3, d)) if d >= 0 else ((TIM3, 0), (TIM2, -d))
        ps.append(Pausa(t, [(a[0] + CR1, ARPE | CEN)] + ([(b[0] + CR1, ARPE | CEN)] if b[1] == 0 else []), ler))
        if b[1] > 0:
            ps.append(Pausa(t + b[1] * NS, [(b[0] + CR1, ARPE | CEN)]))
    return ps


def c2_11(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """ARM ARM §B1.5.4; TRM §5.5.1: d = 0, os dois pendentes juntos, atende o
    de menor número de exceção (TIM2); |d| maior que a entrada (12 ciclos),
    o primeiro já está ativo e não é preemptado: atende o que chegou antes."""
    run = runs["bare-0"]
    t = [T0_NS + r * RODADA_NS for r in range(len(D_11))]
    p = [x for x in run.P if x[0] in t and len(x) == 5]
    if [x[2:] for x in p] != [[r + 1, r, r] for r in range(len(D_11))]:
        return "EVIDÊNCIA INVÁLIDA", [f"rodadas não conferem nas pausas: {[x[2:] for x in p]}"]
    erros, obs = [], {}
    for d, w in zip(D_11, run.rec):
        ordem = (w & 0xFFFF, w >> 16)
        esp = (EXC2, EXC3) if d >= 0 else (EXC3, EXC2)
        obs[d] = "TIM2, TIM3" if ordem == (EXC2, EXC3) else "TIM3, TIM2" if ordem == (EXC3, EXC2) else str(ordem)
        if ordem != esp:
            erros.append(f"d = {d}: {obs[d]}")
    return ("IGUAL" if not erros else "DIVERGE"), [
        f"{len(D_11) - len(erros)}/{len(D_11)} defasagens com a ordem do documento"
        + (f"; divergentes: {'; '.join(erros)}" if erros else ""),
        f"ordem de atendimento por d (ticks, partida do TIM3 − partida do TIM2): {obs}",
        "prioridades iguais (8), PSC = 0, ARR = 999; partidas por escrita de CEN pelo monitor"]


# ── C2-12: coalescência ─────────────────────────────────────────────

def c2_12(runs: dict[str, Execucao], sym: dict[str, int]) -> tuple[str, list[str]]:
    """ARM ARM §B3.4.1; RM0008 §15.3.1: a pendência guarda um evento só.
    Perdidos = max(N − 1, 0), N = eventos cuja entrada, sem máscara, cairia
    na janela entre o gancho de c2_mascara e o de c2_libera; os que caem
    depois da liberação mas antes de o tratador da liberação limpar a flag
    também se fundem. A ±1 tick de uma borda, os dois lados são aceitos."""
    full = runs["full-0"]
    ent = [a[1] // NS for a in entradas(full, sym, EXC2)]
    mas = [a[1] // NS for a in full.A if a[0] == sym["c2_mascara"]]
    lib = [a[1] // NS for a in full.A if a[0] == sym["c2_libera"]]
    clr = [w[2] // NS for w in full.W if w[0] == TIM2 + SR]
    n = D_MAX_12 + 1
    if len(mas) != n or len(lib) != n:
        return "EVIDÊNCIA INVÁLIDA", [f"{len(mas)} máscaras e {len(lib)} liberações, esperado {n}"]
    p = ent[2] - ent[1]
    erros, perdas, janelas, borda = [], [], [], 0
    for i in range(n):
        e0 = max(e for e in ent if e < mas[i])
        ek = max(e for e in ent if e < (mas[i + 1] if i + 1 < n else 10 ** 18))
        ate = [e for e in ent if e <= ek]
        if (ek - e0) % p or ate[-1] - ate[-2] != p:
            return "EVIDÊNCIA INVÁLIDA", [f"ponto {i}: entradas fora da fase do período {p}"]
        k = (ek - e0) // p
        atendidos = sum(1 for e in ent if e0 < e <= ek)
        perdidos = k - atendidos
        ev = [e0 + j * p for j in range(1, k + 1)]
        m, u = mas[i], lib[i]
        c = next((x for x in clr if x > u), u)          # limpeza da flag no 1º tratador depois de liberar

        def conta(folga: int) -> int:
            """Eventos fundidos; folga = −1 exclui e +1 inclui os que estão a 1 tick de uma borda."""
            dentro = sum(1 for e in ev if m - folga < e <= u + folga)
            if dentro:
                dentro += sum(1 for e in ev if u + folga < e <= c + folga)
            return dentro

        esperado = {max(conta(f) - 1, 0) for f in (-1, 0, 1)}
        borda += len(esperado) > 1 and perdidos != max(conta(0) - 1, 0)
        perdas.append(perdidos)
        janelas.append(u - m)
        if perdidos not in esperado:
            erros.append(f"D = {i}: {perdidos} perdidos, esperado {sorted(esperado)} (janela {u - m} ticks)")
    mudancas = [i for i in range(1, n) if perdas[i] != perdas[i - 1]]
    v = "IGUAL; FRONTEIRA REPRODUZIDA" if not erros else "DIVERGE; FRONTEIRA DESLOCADA"
    return v, [f"{n - len(erros)}/{n} valores de D com o número de perdas do documento"
               + (f"; divergentes (até 12): {'; '.join(erros[:12])}" if erros else ""),
               f"pontos aceitos só pela folga de ±1 tick numa borda: {borda}",
               f"período observado {p} ticks (usado para situar os eventos dentro da janela); janela observada (c2_mascara → c2_libera) de {min(janelas)} a "
               f"{max(janelas)} ticks; perdas de {min(perdas)} a {max(perdas)}",
               f"D em que o número de perdas muda: {[(d, perdas[d]) for d in mudancas]}"]


R = 1_000_000
CASOS = [
    Caso("C2-10", 10, 5 * R, c2_10, ganchos=("c2_irq",), escritas=(TIM2 + CR1,)),
    Caso("C2-11", 11, T0_NS + (len(D_11) + 1) * RODADA_NS, c2_11, pausas=pausas_11),
    Caso("C2-12", 12, 200 * R, c2_12, ganchos=("c2_irq", "c2_mascara", "c2_libera"), escritas=(TIM2 + SR,)),
]

if __name__ == "__main__":
    main("c2-tim", CASOS, (__doc__ or "").splitlines()[0])
