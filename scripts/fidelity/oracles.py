"""Oráculos do host: valores esperados calculados SEM nenhum dos ambientes.

- S1A: semântica de cada kernel asm (assinatura) e custo nominal por iteração
  segundo ARM DDI 0337G (Cortex-M3 r2p0) Tabela 18-1 / §18.3.
- S1B: as 6 cargas reimplementadas em Python com a mesma sequência xorshift32.
- S2A: custo nominal do laço de fundo (TRM) → trabalho esperado por período.
- S4A: ordem de eventos esperada pelas regras de prioridade do PM0056
  §2.3.5–2.3.7 (grupo preempta; pendentes por grupo, sub, nº de exceção).
"""
from __future__ import annotations

M32 = 0xFFFFFFFF


def u32(x: int) -> int:
    return x & M32


def s32(x: int) -> int:
    x &= M32
    return x - (1 << 32) if x & 0x80000000 else x


def ror(x: int, n: int) -> int:
    n &= 0xFF
    if n == 0:
        return u32(x)
    n %= 32
    return u32((x >> n) | (x << (32 - n))) if n else u32(x)


# ───────────────────────────── S1A ─────────────────────────────

S1A_INSTR_PER_ITER = {k: 18 for k in range(2, 15)} | {1: 2}

# Ciclos nominais por iteração (16 instruções da classe + SUBS 1 + BNE tomado 2),
# DDI0337G Tab. 18-1 (pp. 18-3..18-5) e §18.3 (pp. 18-7..18-8). None = a TRM dá
# só uma faixa/sem valor para o caso (UDIV 2–12; LDR de flash: contenção).
S1A_TRM_CYCLES = {
    1: (3, "SUBS 1 + B<cond> tomado 1+P (P=1)"),
    2: (19, "ADDS 1 ciclo"),
    3: (19, "MUL 1 ciclo"),
    4: (None, "UDIV 2–12 ciclos (mínimo quando divisor > dividendo)"),
    5: (None, "UDIV 2–12 ciclos (quociente grande → perto do máximo)"),
    6: (20, "LDR 2; LDRs seguidas pipelinam (N+1)"),
    7: (35, "LDR 2; destino usado no endereço seguinte → sem pipelining"),
    8: (19, "STR Rx,[Ry,#imm] sempre 1 ciclo"),
    9: (None, "LDR de flash: 2 + possível contenção com o fetch"),
    10: (35, "B tomado com imediato = 2 ciclos"),
    11: (83, "LDM 1+N (N=4)"),
    12: (None, "mix (calibração): soma nominal 23, pipelining LDR→STR pode tirar 1"),
    13: (None, "ALU executando da SRAM (barramento System)"),
    14: (None, "LDR com código na SRAM (contenção no barramento System)"),
}


def s1a_signature(kernel: int, n: int, ctx: list[int], flash_word: int) -> int:
    """Assinatura (r2+r4+r5+r6+r7) do kernel `kernel` com `n` iterações."""
    c0, a, b = ctx[0], ctx[1], ctx[2]
    if kernel == 1 or kernel == 10:
        return 0
    if kernel in (2, 13):
        return u32(a + 16 * n * b)
    if kernel == 3:
        return u32(a * pow(b, 16 * n, 1 << 32))
    if kernel == 4:
        return u32(ctx[3] + ctx[3] // ctx[4])
    if kernel == 5:
        return u32(ctx[5] + ctx[5] // ctx[6])
    if kernel in (6, 14, 8):
        return a
    if kernel == 7:
        return c0
    if kernel == 9:
        return u32(ctx[7] + flash_word)
    if kernel == 11:
        return u32(ctx[0] + ctx[1] + ctx[2] + ctx[3])
    if kernel == 12:
        r2, r3, r4, r5, r6, r7 = a, b, 0, 0, 0, 0
        for _ in range(n):
            r2 = u32(r2 + r3)
            r4 = a
            r2 ^= r4
            r4 = u32(r3 * r4)
            r5 = u32(r2 << 3)
            r2 = u32(r2 + r5)
            r6 = b
            r2 = u32(r2 - r6)
            r2 = ror(r2, r3)
            r2 |= r4
            r7 = a
            r2 = u32(r2 + r7)
            r2 ^= r3
        return u32(r2 + r4 + r5 + r6 + r7)
    raise ValueError(kernel)


# ───────────────────────────── S1B ─────────────────────────────

class XorShift32:
    def __init__(self, seed: int):
        self.x = seed

    def __call__(self) -> int:
        x = self.x
        x ^= u32(x << 13)
        x ^= x >> 17
        x ^= u32(x << 5)
        self.x = x
        return x


def _i16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def s1b_signatures(seed: int = 0x5EED0002, trials: int = 9) -> dict[tuple[int, int], int]:
    """{(trial, condição): assinatura} replicando app.c (prepare → run)."""
    rng = XorShift32(seed)
    out = {}
    for t in range(trials):
        for cond in range(1, 8):
            if cond == 1:
                data = [rng() & 0xFF for _ in range(256)]
                crc = M32
                for byte in data:
                    crc ^= byte
                    for _ in range(8):
                        crc = (crc >> 1) ^ (0xEDB88320 & u32(-(crc & 1)))
                sig = u32(~crc)
            elif cond == 2:
                arr = sorted(rng() for _ in range(64))
                sig = 0
                for v in arr:
                    sig = u32(sig * 31 + v)
            elif cond == 3:
                ma = [[0] * 8 for _ in range(8)]
                mb = [[0] * 8 for _ in range(8)]
                for i in range(8):
                    for j in range(8):
                        ma[i][j] = (rng() & 0xFFFF) - 0x8000
                        mb[i][j] = (rng() & 0xFFFF) - 0x8000
                sig = 0
                for i in range(8):
                    for j in range(8):
                        acc = s32(sum(ma[i][k] * mb[k][j] for k in range(8)))
                        sig ^= u32(u32(acc) + (i << 8) + j)
            elif cond == 4:
                x = [_i16(rng()) for _ in range(128 + 16)]
                h = [_i16(rng() >> 20) for _ in range(16)]
                sig = 0
                for n in range(128):
                    acc = s32(sum(x[n + k] * h[k] for k in range(16)))
                    y = _i16(acc >> 15)
                    sig = u32(u32(sig << 3) ^ (sig >> 29) ^ (y & 0xFFFF))
            elif cond == 5:
                src = [rng() for _ in range(256)]
                sig = src[0] ^ src[128] ^ src[255]
            elif cond == 6:
                vals = [rng() for _ in range(64)]
                sig = 0
                for i, v in enumerate(vals):
                    r = v
                    if v > 1:
                        y = (r + v // r) >> 1
                        while y < r:
                            r = y
                            y = (r + v // r) >> 1
                    sig = u32(sig + r * (i + 1))
            else:
                sig = 0
            out[(t, cond)] = sig
    return out


# ───────────────────────────── S2A ─────────────────────────────

# Ciclos nominais por iteração do laço de fundo (spin.S): LDR 2 + ADDS 1 +
# STR 1 + corpo + LDR 2 + CMP 1 + BEQ tomado 2 = 9 + corpo. Corpo pela TRM:
# 8×ADDS = 8; 8×UDIV (0xFFFFFFFF/3) = 8×12 (S1A mediu 12); 8×LDM(4) = 8×5.
S2A_SPIN_CYCLES = {1: 9 + 8, 2: 9 + 8 * 12, 3: 9 + 8 * 5}
S2A_SPIN_INSTR = 14


# ───────────────────────────── S4A ─────────────────────────────

# Espelho de s_cases[] em src/s4/nvic.c: (prio TIM2, prio TIM3, L é TIM3?, modo).
def _prio(g: int, s: int) -> int:
    return (g << 1) | s


S4A_CASES = {
    1: (_prio(3, 0), _prio(1, 0), False, "request"),
    2: (_prio(1, 1), _prio(1, 0), False, "request"),
    3: (_prio(1, 0), _prio(1, 0), False, "request"),
    4: (_prio(1, 0), _prio(3, 0), True, "request"),
    5: (_prio(1, 0), _prio(3, 0), False, "request"),
    6: (_prio(3, 0), _prio(1, 0), False, "arb"),
    7: (_prio(1, 1), _prio(1, 0), False, "arb"),
    8: (_prio(1, 0), _prio(1, 0), False, "arb"),
    9: (_prio(1, 0), _prio(1, 0), False, "arb"),
    10: (_prio(3, 0), _prio(1, 0), False, "basepri"),
    11: (_prio(1, 0), _prio(1, 0), False, "self_repend"),
}
S4A_EVENTS = {1: "L_ENTER", 2: "L_REQ", 3: "H_ENTER", 4: "H_EXIT", 5: "L_RESUME",
              6: "L_EXIT", 7: "T2_ENTER", 8: "T2_EXIT", 9: "T3_ENTER", 10: "T3_EXIT",
              11: "BASEPRI_CLEARED"}
TIM2_IRQ, TIM3_IRQ = 28, 29


def order_code(events: list[int]) -> int:
    code = 0
    for i, e in enumerate(events):
        code |= e << (4 * i)
    return code


def decode_order(code: int) -> list[int]:
    out = []
    while code & 0xFFFF:
        out.append(code & 0xF)
        code >>= 4
    return out


def s4a_expected(cond: int) -> list[int]:
    p2, p3, l_is_tim3, mode = S4A_CASES[cond]
    group = lambda p: p >> 1                                  # noqa: E731
    key = lambda p, irq: (p >> 1, p & 1, irq)                # noqa: E731
    if mode == "request":
        pl, ph = (p3, p2) if l_is_tim3 else (p2, p3)
        if group(ph) < group(pl):
            return [1, 2, 3, 4, 5, 6]          # H aninha entre pedido e retomada
        return [1, 2, 5, 6, 3, 4]              # H só depois de L sair
    if mode == "basepri":
        return [9, 10, 11, 7, 8]               # TIM3 (permitido), libera, TIM2
    first_t2 = key(p2, TIM2_IRQ) < key(p3, TIM3_IRQ)
    if mode == "self_repend":
        # TIM2 repende a si mesmo; empate com TIM3 → menor nº (TIM2) de novo.
        return [7, 8, 9, 10] if first_t2 else [9, 10, 7, 8]
    return [7, 8, 9, 10] if first_t2 else [9, 10, 7, 8]
