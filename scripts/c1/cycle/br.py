"""T-BR, T-IT, T-SYS (src/c1/cycle/br.S; TRM r1p1 Tab. 18-1, nota a)."""
from __future__ import annotations

from fractions import Fraction as F

from .. import arm
from ..catalog import Insn
from ..func.common import ins
from . import P, R, Variant

NOTA_A = "@armlimited2007[Tab. 18-1, nota a]"
Z1 = R(apsr=arm.apsr(0, 1, 0, 0))
BR = lambda m, w: Insn(m, w, None)   # noqa: E731 — o operando de desvio é um endereço

VARIANTS = [
    Variant("T-BR-01", "T-BR-01", "t_br01", "b.n <seguinte>",
            P(2, 3, ambiguous=True, text="nota a: \"two cycles are added\" × \"2 cycles total\""), F(1),
            level="N1", source=NOTA_A, first=BR(r"b\.n", 16)),
    Variant("T-BR-02.w", "T-BR-02", "t_br02_w", "b.w <seguinte> (alinhado à palavra)",
            P(2, 3, ambiguous=True), F(1), source=NOTA_A, first=BR(r"b\.w", 32)),
    Variant("T-BR-02.h", "T-BR-02", "t_br02_h", "b.w <seguinte> (alinhado à meia palavra)",
            P(3, None, text="\"Pipeline reload is longer when branching to unaligned 32-bit\""),
            F(1), source=NOTA_A, first=BR(r"b\.w", 32), ua=2),
    Variant("T-BR-03", "T-BR-03", "t_br03", "bne.n <seguinte> (Z = 1: nunca tomado)", P(1), F(1),
            regs=Z1, level="N1", source=NOTA_A, first=BR(r"bne\.n", 16),
            note="\"Non-taken branches are 1 cycle total\""),
    Variant("T-BR-04", "T-BR-04", "t_br04", "beq.n <seguinte> (Z = 1: sempre tomado)",
            P(2, 3, ambiguous=True), F(1), regs=Z1, source=NOTA_A, first=BR(r"beq\.n", 16)),
    Variant("T-BR-05.cbz", "T-BR-05", "t_br05_cbz", "cbz r0, 1f ; nop ; 1: (r0 = 0, tomado)",
            P(2, 3, ambiguous=True), F(1), source=NOTA_A, first=BR("cbz", 16),
            note="CBZ só desvia para a frente e pelo menos uma instrução adiante"),
    Variant("T-BR-05.cbnz", "T-BR-05", "t_br05_cbnz", "cbnz r0, 1f ; nop ; 1: (r0 = 0, não tomado)",
            P(1, 2, text="1 + NOP (0 ou 1)"), F(2), source=NOTA_A, first=BR("cbnz", 16)),
    Variant("T-BR-06", "T-BR-06", "t_br06", "adr.w r1, 1f+1 ; bx r1 ; 1:",
            P(4, text="1 + 3 (por registrador: P normalmente 2)"), F(2), level="N1", source=NOTA_A,
            first=Insn(r"addw", 32, None),
            note="o +1 é correto: BX exige bit 0 = 1"),
    Variant("T-BR-07", "T-BR-07", "t_br07", "bl f ; f: bx lr",
            P(4, 5, text="BL 1+P e BX LR 1+P"), F(2), source=NOTA_A, first=BR("bl", 32)),
    Variant("T-BR-08.add", "T-BR-08", "t_br08_add", "add pc, r1 (r1 = −2)", P(2, 4, text="1+P"), F(1),
            regs=R(r1=arm.u32(-2)), source=NOTA_A, first=ins("add pc, r1", 16)),
    Variant("T-BR-08.mov", "T-BR-08", "t_br08_mov", "adr.w r1, 1f ; mov pc, r1 ; 1:",
            P(3, 5, text="1 + (1+P)"), F(2), source=NOTA_A, first=Insn(r"addw", 32, None)),
    Variant("T-BR-09", "T-BR-09", "t_br09", "ldr pc, [r0], #4 (tabela dos alvos)",
            P(5, None, text="\"at least five cycles\""), F(1), setup="ldrpc",
            source="@armlimited2007[§18.3]", first=ins("ldr.w pc, [r0], #4", 32)),
    Variant("T-BR-10", "T-BR-10", "t_br10", "pop {r4, pc} (pares empilhados antes de t0)",
            P(4, 6, text="1 + 2 + P"), F(1), setup="pairs", source=NOTA_A, first=ins("pop {r4, pc}", 16)),
    Variant("T-BR-11", "T-BR-11", "t_br11", "tbb [pc, r0] (r0 = 0; tabela de 1 byte em seguida)",
            P(6, None, text="\"at least six cycles\""), F(1), source="@armlimited2007[§18.3]",
            first=ins("tbb [pc, r0]", 32), note="a tabela não é executada: o Renode conta uma instrução"),
    Variant("T-IT-01", "T-IT-01", "t_it01", "mov r1, r4 ; it eq ; moveq r2, r3 (Z = 1)",
            P(2, 3, text="IT dobrado: 0; senão 1 (nota d)"), F(3), regs=Z1, level="N1",
            source="@armlimited2007[Tab. 18-1, nota d]", first=ins("mov r1, r4", 16)),
    Variant("T-IT-02", "T-IT-02", "t_it02", "mov.w r1, r4 ; it eq ; moveq r2, r3 (Z = 1)",
            P(2, 3), F(3), regs=Z1, source="@armlimited2007[Tab. 18-1, nota d]",
            first=ins("mov.w r1, r4", 32), note="a largura da vizinha muda o dobramento?"),
    Variant("T-IT-03", "T-IT-03", "t_it03", "it ne ; movne r2, r3 (Z = 1: pulada)", P(1, 2), F(2),
            regs=Z1, source="@armlimited2007[Tab. 18-1, nota d]", first=ins("it ne", 16),
            note="H-T1, ponto aberto (a): a instrução pulada conta como executada?"),
    Variant("T-IT-04.br.taken", "T-IT-04", "t_it04_br", "cmp ; bne L ; movs ×4 ; L: (r0 ≠ r1)",
            P(3, text="Yiu §23.2 (ilustração)"), F(2), regs=R(r0=1, r1=2), source="@yiu2014[§23.2]",
            first=ins("cmp r0, r1", 16)),
    Variant("T-IT-04.br.nottaken", "T-IT-04", "t_it04_br", "cmp ; bne L ; movs ×4 ; L: (r0 = r1)",
            P(6), F(6), regs=R(r0=1, r1=1), source="@yiu2014[§23.2]", first=ins("cmp r0, r1", 16)),
    Variant("T-IT-04.it.true", "T-IT-04", "t_it04_it", "cmp ; itttt eq ; moveq ×4 (r0 = r1)",
            P(5, 6, text="6 sem dobrar, 5 dobrado"), F(6), regs=R(r0=1, r1=1),
            source="@yiu2014[§23.2]", first=ins("cmp r0, r1", 16)),
    Variant("T-IT-04.it.false", "T-IT-04", "t_it04_it", "cmp ; itttt eq ; moveq ×4 (r0 ≠ r1)",
            P(5, 6), F(6), regs=R(r0=1, r1=2), source="@yiu2014[§23.2]", first=ins("cmp r0, r1", 16),
            note="\"If no IT folding, both paths take 6 cycles\""),
    Variant("T-IT-05", "T-IT-05", "t_it05", "nop", P(0, 1), F(1), first=ins("nop", 16)),
    Variant("T-SYS-01.mrs", "T-SYS-01", "t_sys01_mrs", "mrs r0, primask", P(1, 2), F(1),
            first=ins("mrs r0, PRIMASK", 32)),
    Variant("T-SYS-01.msr", "T-SYS-01", "t_sys01_msr", "msr primask, r0 (r0 = 1)", P(1, 2), F(1),
            regs=R(r0=1), first=ins("msr PRIMASK, r0", 32),
            note="PRIMASK já é 1: nenhuma das três muda o estado das interrupções"),
    Variant("T-SYS-01.cpsid", "T-SYS-01", "t_sys01_cpsid", "cpsid i", P(1, 2), F(1),
            first=ins("cpsid i", 16)),
    Variant("T-SYS-02", "T-SYS-02", "t_sys02", "isb", P(2, None, text="\"acts as branch\" (nota g)"),
            F(1), first=ins("isb sy", 32)),
    Variant("T-SYS-03.dmb", "T-SYS-03", "t_sys03_dmb", "dmb", P(1), F(1), first=ins("dmb sy", 32)),
    Variant("T-SYS-03.dsb", "T-SYS-03", "t_sys03_dsb", "dsb", P(1), F(1), first=ins("dsb sy", 32)),
    Variant("T-SYS-03.str", "T-SYS-03", "t_sys03_str", "str r1, [r0] ; dsb", P(2, None), F(2),
            setup="cell", first=ins("str r1, [r0, #0]", 16),
            note="\"take one cycle unless data is pending in the write buffer\""),
    Variant("T-SYS-04", "T-SYS-04", "t_sys04", "sev", P(1), F(1), first=ins("sev", 16)),
]

# Diagnóstico de T-BR-03 e T-BR-06 (fora do intervalo do TRM na placa): as
# mesmas unidades com a 1ª unidade em ≡ 2 (mod 4), para separar o efeito de
# alinhamento da busca.
VARIANTS += [
    Variant("T-BR-03.h", "T-BR-03", "t_br03_h", "bne.n <seguinte> (Z = 1; 1ª unidade em meia palavra)",
            P(1), F(1), regs=Z1, level="N3", source=NOTA_A, first=BR(r"bne\.n", 16), ua=2,
            note="diagnóstico do alinhamento"),
    Variant("T-BR-06.h", "T-BR-06", "t_br06_h", "adr.w r1, 1f+1 ; bx r1 ; 1: (1ª unidade em meia palavra)",
            P(4), F(2), level="N3", source=NOTA_A, first=Insn(r"addw", 32, None), ua=2,
            note="diagnóstico do alinhamento"),
]
