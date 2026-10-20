"""T-DWT — validação do DWT_CYCCNT como régua (src/c1/cycle/dwt.S). Todos N1."""
from __future__ import annotations

from fractions import Fraction as F

from ..func.common import ins
from . import NOPRED, P, V_CYCOFF, V_PRIMASK0, V_RAW, Variant

ADDS = ins("adds r0, #1", 16)
SRC = "@armlimited2007[§11.5.1] @armlimited2021[§C1.8]"

VARIANTS = [
    Variant("T-DWT-01.on", "T-DWT-01", "t_alu01", "adds r0, r0, #1", P(1), F(1), level="N1",
            source=SRC, first=ADDS, note="CYCCNTENA = 1: a 2ª leitura é maior"),
    Variant("T-DWT-01.off", "T-DWT-01", "t_alu01", "adds r0, r0, #1", P(0), F(0), flags=V_CYCOFF,
            level="N1", source=SRC, first=ADDS, note="CYCCNTENA = 0: Δ = 0"),
    Variant("T-DWT-02", "T-DWT-02", "t_dwt02", "adds r0, r0, #1 (CYCCNT ← 0xFFFFFFF0 antes de t0)",
            P(1), F(1), flags=V_RAW, level="N1", source=SRC, first=ADDS,
            note="t1 < t0 (deu a volta) e Δ módulo 2^32 = Δ sem volta"),
    Variant("T-DWT-03", "T-DWT-03", "t_dwt_empty", "(nenhuma: ldr.w r7,[r6] ; ldr r5,[r6])",
            P(1, 2, text="observer: 2ª carga pode se sobrepor à 1ª (§18.3)"), F(1), level="N1",
            source="@armlimited2007[§18.3]", sizes=(0, 0, 0), first=ins("ldr r5, [r6, #0]", 16),
            blocks=("t_dwt_empty", "t_dwt_empty", "t_dwt_empty"),
            note="o valor é Δ(0) = custo do observador (O do bloco vazio)"),
    Variant("T-DWT-04", "T-DWT-04", "t_alu01", "adds r0, r0, #1", P(1), F(1), level="N1",
            source=SRC, first=ADDS, note="linearidade da régua: c = 1 e Δ(3K)−Δ(2K) = Δ(2K)−Δ(K)"),
    Variant("T-DWT-06", "T-DWT-06", "t_dwt06", "svc #0 (tratador vazio: bx lr)", NOPRED, F(2),
            flags=V_PRIMASK0, level="N1", source="@armlimited2007[§5.5]",
            first=ins("svc 0", 16),
            note="caracterização (latência é objeto do C3); com PRIMASK = 1 o SVC escalaria "
                 "para HardFault, por isso este caso roda com PRIMASK = 0"),
]
# T-DWT-05 (Δ(0) = O de T-DWT-04) é derivado na análise de T-DWT-03 e T-DWT-04.
