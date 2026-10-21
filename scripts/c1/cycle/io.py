"""T-IO — acesso a periféricos e buffer de escrita (src/c1/cycle/io.S).

C2 e C4 fazem polling e escrevem em periféricos (TIM2 no APB1, USART1 no
APB2); sem o custo do acesso a periférico no núcleo, uma diferença de tempo
nesses cenários não tem dono (CPU ou modelo do periférico). Cada variante
REUTILIZA o bloco da contraparte na SRAM (T-LS-01, T-LS-03, T-LS-06,
T-SYS-03.str, T-BB-03.plain) com a base num registrador do GPIOB (APB2) ou
do RCC (AHB): o código medido é idêntico, só o endereço muda.

Previsão da placa: classe C. A coleção não documenta os estados de espera da
ponte AHB→APB; o piso é a mesma sequência na SRAM (TRM §14.5) e o RM0008
confirma que um acesso ao APB2 em curso faz esperar o seguinte (RCC_APB2ENR,
§7.3.7). O buffer de escrita só é usado quando o escravo estende a
fase de dados (TRM §14.11): a SRAM nunca o exercita, um periférico sim.

Ambiente (setup "gpio" em main.c): IOPBEN ligado e ODR[5] = 0 antes de cada
chamada; no fim da variante, ODR[5] = 0 e IOPBEN desligado. PB5 continua
entrada (CRL de reset): nenhuma escrita muda pino algum. BSRR ← 0 não tem
efeito; o ODR[4] = 1 de reset (PB4/NJTRST em pull-up) é preservado pelo OR.
"""
from __future__ import annotations

from fractions import Fraction as F

from ..func.common import ins
from . import P, R, Variant

GPIOB, RCC_CR = 0x4001_0C00, 0x4002_1000
IDR, ODR, BSRR = GPIOB + 0x08, GPIOB + 0x0C, GPIOB + 0x10
ODR5_ALIAS = 0x4200_0000 + (ODR - 0x4000_0000) * 32 + 5 * 4      # 0x42218194 (FBB-04)
PB5 = 1 << 5
SRC = "@armlimited2007[§14.5, §14.11] @stmicroelectronics2021[§3.1]"
ISO = "sequência isolada"
LDR, STR = ins("ldr r1, [r0, #0]", 16), ins("str r1, [r0, #0]", 16)


def floor(lo, ref: str):
    """Piso derivado da contraparte na SRAM: "pelo menos" (a ponte não é documentada)."""
    return P(lo, None, text=f"piso: {ref} (mesmo bloco na SRAM); ponte AHB→APB não documentada")


def V(name, case, bs, unit, trm, renode, first, regs, *, setup="gpio", level="N2", obj="custo marginal",
      note=""):
    return Variant(name, case, bs, unit, trm, F(renode), regs=regs, setup=setup, level=level, obj=obj,
                   source=SRC, first=first, note=note)


VARIANTS = [
    V("T-IO-01.apb2", "T-IO-01", "t_ls03", "ldr r1, [GPIOB_IDR] ; adds r2, r2, #1",
      floor(3, "T-LS-03"), 2, LDR, R(r0=IDR), level="N1", obj=ISO,
      note="leitura de registrador APB2 (polling de C4: USART1_SR)"),
    V("T-IO-01.ahb", "T-IO-01", "t_ls03", "ldr r1, [RCC_CR] ; adds r2, r2, #1",
      floor(3, "T-LS-03"), 2, LDR, R(r0=RCC_CR), obj=ISO,
      note="leitura de registrador AHB (RCC): separa o barramento System da ponte APB"),
    V("T-IO-02.apb2", "T-IO-02", "t_ls01", "ldr r1, [GPIOB_IDR] (cargas seguidas)",
      floor(1, "T-LS-01"), 1, LDR, R(r0=IDR),
      note="na SRAM cargas independentes se sobrepõem (§18.3); através da ponte, a placa decide"),
    V("T-IO-03.apb2", "T-IO-03", "t_ls06", "str r1, [GPIOB_BSRR] (r1 = 0: sem efeito)",
      floor(1, "T-LS-06"), 1, STR, R(r0=BSRR), level="N1",
      note="escritas seguidas: o buffer de escrita tem uma entrada (§14.11) e a 2ª espera a 1ª drenar"),
    V("T-IO-03.add.apb2", "T-IO-03", "t_al02_str", "str r1, [GPIOB_BSRR] ; adds r2, r2, #1",
      floor(2, "T-IO-03.add.sram"), 2, STR, R(r0=BSRR), obj=ISO,
      note="uma instrução de dados entre as escritas: quanto o buffer esconde"),
    V("T-IO-03.add.sram", "T-IO-03", "t_al02_str", "str r1, [sram] ; adds r2, r2, #1 (controle)",
      P(2, text="STR com imediato 1 + ALU 1 (Tab. 18-1, §18.3)"), 2, STR, R(), setup="cell", obj=ISO,
      note="contraparte alinhada de T-IO-03.add.apb2 (o mesmo bloco de T-AL-02.str)"),
    V("T-IO-04.apb2", "T-IO-04", "t_sys03_str", "str r1, [GPIOB_BSRR] ; dsb",
      floor(2, "T-SYS-03.str"), 2, STR, R(r0=BSRR), level="N1", obj=ISO,
      note="DSB espera o buffer de escrita drenar (nota g); na SRAM o buffer nunca é usado"),
    V("T-IO-05.apb2", "T-IO-05", "t_bb03", "str r1, [GPIOB_BSRR] ; ldr r2, [GPIOB_IDR]",
      floor(3, "T-BB-03.plain"), 2, STR, R(r0=BSRR, r3=IDR), obj=ISO,
      note="escrita seguida de leitura do mesmo periférico: o idioma \"(void)tim->SR\" de C2 "
           "(src/c2/timers.c) para garantir a escrita antes de seguir"),
    V("T-IO-06.bsrr", "T-IO-06", "t_ls06", "str r1, [GPIOB_BSRR] (r1 = 1 << 5: liga ODR5)",
      floor(1, "T-LS-06"), 1, STR, R(r0=BSRR, r1=PB5),
      note="as três formas de ligar um bit do ODR: (a) BSRR, escrita atômica"),
    V("T-IO-06.rmw", "T-IO-06", "t_io06_rmw", "ldr r1, [GPIOB_ODR] ; orrs r1, r2 ; str r1, [GPIOB_ODR]",
      floor(4, "T-IO-06.rmw.sram"), 3, LDR, R(r0=ODR, r2=PB5),
      note="(b) ler-modificar-escrever no ODR (não atômico)"),
    V("T-IO-06.rmw.sram", "T-IO-06", "t_io06_rmw", "ldr r1, [sram] ; orrs r1, r2 ; str r1, [sram] (controle)",
      P(4, 5, text="LDR 2 + ORRS 1 + STR 1; a carga seguinte pode não se sobrepor ao STR (§18.3)"), 3,
      LDR, R(r2=PB5), setup="cell", note="contraparte na SRAM de T-IO-06.rmw"),
    V("T-IO-06.bb", "T-IO-06", "t_ls06", "str r1, [alias de ODR5] (r1 = 1)",
      P(2, None, text="\"Bit-band writes take two cycles\" (§14.5.2), mais a ponte"), 1, STR,
      R(r0=ODR5_ALIAS, r1=1), note="(c) escrita no alias de bit-band do periférico (FBB-04)"),
]
