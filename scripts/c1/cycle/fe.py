"""T-FE (busca e sistema de memória) e T-COMP (composição) — src/c1/cycle/fe.S."""
from __future__ import annotations

from fractions import Fraction as F

from ..catalog import Insn
from ..func.common import ins
from . import NOPRED, P, R, V_PREFOFF, Variant

VARIANTS = [
    Variant("T-FE-01.w", "T-FE-01", "t_fe01_w", "add.w r0, r1, r2 (1ª unidade alinhada à palavra)",
            P(1), F(1), level="N3", source="@armlimited2007[Tab. 14-1]", first=ins("add.w r0, r1, r2", 32),
            note="O é caracterização (a fila de busca pode ter buscado antes de t0)"),
    Variant("T-FE-01.h", "T-FE-01", "t_fe01_h", "add.w r0, r1, r2 (1ª unidade em meia palavra)",
            P(1), F(1), level="N3", source="@armlimited2007[Tab. 14-1]", first=ins("add.w r0, r1, r2", 32),
            ua=2),
    Variant("T-FE-02.alu01", "T-FE-02", "t_fe02_alu01", "adds r0, r0, #1 (na SRAM)", P(1), F(1),
            level="N1", source="@armlimited2007[§14.5.6]", first=ins("adds r0, #1", 16),
            note="busca pelo barramento System: 2 ciclos, sem buscas consecutivas"),
    Variant("T-FE-02.alu02", "T-FE-02", "t_fe02_alu02", "add.w r0, r1, r2, lsl #3 (na SRAM)", P(2),
            F(1), level="N1", source="@armlimited2007[§14.5.6]", first=ins("add.w r0, r1, r2, lsl #3", 32)),
    Variant("T-FE-02.ls03", "T-FE-02", "t_fe02_ls03", "ldr r1, [r0] ; adds (na SRAM)",
            P(3, None, ambiguous=True, text="derivado: dados têm prioridade sobre buscas (§14.5)"),
            F(2), setup="cell", level="N1", source="@armlimited2007[§14.5, §14.5.6]",
            first=ins("ldr r1, [r0, #0]", 16), obj="sequência isolada"),
    Variant("T-FE-02.br01", "T-FE-02", "t_fe02_br01", "b.n <seguinte> (na SRAM)",
            P(2, None, ambiguous=True), F(1), level="N1", source="@armlimited2007[§14.5.6]",
            first=Insn(r"b\.n", 16, None)),
    Variant("T-FE-03.alu02", "T-FE-03", "t_alu02", "add.w r0, r1, r2, lsl #3 (pré-busca desligada)",
            NOPRED, F(1), regs=R(r1=0x1234, r2=3), flags=V_PREFOFF, level="N3",
            source="@stmicroelectronics2021[§3.3.3]", first=ins("add.w r0, r1, r2, lsl #3", 32),
            note="FLASH_ACR.PRFTBE = 0 (permitido com SYSCLK < 24 MHz); caracterização"),
    Variant("T-FE-03.br02", "T-FE-03", "t_br02_w", "b.w <seguinte> (pré-busca desligada)", NOPRED, F(1),
            flags=V_PREFOFF, level="N3", source="@stmicroelectronics2021[§3.3.3]",
            first=Insn(r"b\.w", 32, None)),
    # T-COMP: o laço inteiro é chamado com n = 8, 16 e 24 iterações (regs por tamanho).
    Variant("T-COMP-01", "T-COMP-01", "t_comp01",
            "1: ldr.w r3,[r1],#4 ; str.w r3,[r0],#4 ; subs r2,r2,#1 ; bne 1b",
            P(6, 8, ambiguous=True, text="2+1+1+2 por iteração tomada (7 se o STR pós-indexado "
                                         "custar 2; +1 se o desvio tomado custar 3)"),
            F(4), regs=tuple(R(r2=n) for n in (8, 16, 24)), setup="copy", obj="total", level="N1",
            source="@armlimited2007[Tab. 18-1, §18.3]", first=ins("ldr.w r3, [r1], #4", 32),
            blocks=("t_comp01",) * 3,
            note="c = custo por iteração; a última (não tomada) entra em O (placa 6n − 1, Renode 4n)"),
    Variant("T-COMP-02", "T-COMP-02", "t_comp02",
            "1: lsrs r3,r2,#1 ; it cs ; eorcs r3,r4 ; mov r2,r3 ; subs r1,#1 ; bne 1b",
            P(6, 8, ambiguous=True, text="1+0+1+1+1+2 com IT dobrado (7 sem dobrar; +1 se desvio = 3)"),
            F(6), regs=tuple(R(r1=n, r2=0xFFFF_FFFF, r4=0xEDB8_8320) for n in (8, 16, 24)), obj="total",
            level="N2", source="@armlimited2007[Tab. 18-1]", first=ins("lsrs r3, r2, #1", 16),
            blocks=("t_comp02",) * 3,
            note="placa e Renode podem coincidir por compensação de erros (Cebrian 2020)"),
]
