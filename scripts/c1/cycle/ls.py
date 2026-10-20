"""T-LS, T-LSM, T-AL, T-BB (src/c1/cycle/ls.S; TRM r1p1 §18.3)."""
from __future__ import annotations

from fractions import Fraction as F

from ..catalog import Insn
from ..func.common import ins
from . import P, R, Variant

S183 = "@armlimited2007[§18.3]"
ISO = "sequência isolada"
LISTS = {2: "{r1, r2}", 3: "{r1, r2, r3}", 4: "{r1, r2, r3, r4}", 5: "{r1, r2, r3, r4, r8}",
         6: "{r1, r2, r3, r4, r8, r9}", 7: "{r1, r2, r3, r4, r8, r9, sl}",
         8: "{r1, r2, r3, r4, r8, r9, sl, fp}"}


def V(name, bs, unit, trm, renode, first, *, setup="cell", arg=0, regs=None, level="N2", obj="custo marginal",
      source=S183, note="", case=None):
    return Variant(name, case or name.split(".")[0], bs, unit, trm, F(renode), regs=regs or R(),
                   setup=setup, arg=arg, level=level, obj=obj, source=source, first=first, note=note)


VARIANTS = [
    V("T-LS-01", "t_ls01", "ldr r1, [r0]", P(1), 1, ins("ldr r1, [r0, #0]", 16), level="N1",
      note="cargas independentes se sobrepõem: cada uma custa 1 a mais"),
    V("T-LS-02", "t_ls02", "ldr r0, [r0]", P(2), 1, ins("ldr r0, [r0, #0]", 16), setup="self",
      level="N1", obj="latência", note="a memória aponta para si mesma"),
    V("T-LS-03", "t_ls03", "ldr r1, [r0] ; adds r2, r2, #1", P(3), 2, ins("ldr r1, [r0, #0]", 16),
      level="N1", obj=ISO),
    V("T-LS-04.cmp", "t_ls04_cmp", "ldr r1, [r0], #4 ; cmp r7, #0", P(2), 2,
      ins("ldr.w r1, [r0], #4", 32), setup="walk", obj=ISO,
      note="writeback reduzido a 1 se a seguinte não lê registrador do LSU (CMP, TST, NOP)"),
    V("T-LS-04.use", "t_ls04_use", "ldr r1, [r0], #4 ; adds r2, r1, #0", P(3), 2,
      ins("ldr.w r1, [r0], #4", 32), setup="walk", obj=ISO),
    V("T-LS-05", "t_ls05", "ldr r1, =0x12345678 ; adds r2, r2, #1", P(3, 4), 2, Insn("ldr", 16, None),
      setup="none", obj=ISO,
      note="\"might add a cycle because of contention with the fetch unit\""),
    V("T-LS-06", "t_ls06", "str r1, [r0, #0]", P(1, 2, ambiguous=True), 1, ins("str r1, [r0, #0]", 16),
      level="N1", note="\"STR Rx,[Ry,#imm] is always one cycle\" × \"nothing can be pipelined after the store\""),
    V("T-LS-07", "t_ls07", "str r1, [r0, r2] ; adds r4, r4, #1", P(3), 2, ins("str r1, [r0, r2]", 16),
      obj=ISO, source=f"@armlimited2007[Tab. 18-1, nota b; §18.3]",
      note="separadora r4 (o material-base usava r7, que guarda t0)"),
    V("T-LS-08.a", "t_ls08a", "ldr r0,[r1] ; ldr r1,[r2] ; adds r4,r4,#1", P(4), 3,
      ins("ldr r0, [r1, #0]", 16), setup="ls08a", obj=ISO),
    V("T-LS-08.b", "t_ls08b", "ldr r0,[r1,r2] ; str r0,[r3,#20] ; adds r4,r4,#1", P(4), 3,
      ins("ldr r0, [r1, r2]", 16), setup="ls08b", obj=ISO),
    V("T-LS-08.c", "t_ls08c", "ldr r0,[r1,r2] ; str r1,[r3,r2] ; adds r4,r4,#1", P(4), 3,
      ins("ldr r0, [r1, r2]", 16), setup="ls08c", obj=ISO),
    V("T-LS-08.d", "t_ls08d", "ldr r0,[r1,r5] ; ldr r1,[r2] ; ldr r2,[r3,#4] ; adds r4,r4,#1", P(5), 4,
      ins("ldr r0, [r1, r5]", 16), setup="ls08d", obj=ISO),
]
for w, text in (("ldrb", "ldrb r1, [r0, #0]"), ("ldrh", "ldrh r1, [r0, #0]"),
                ("ldrsb", "ldrsb r1, [r0, r2]"), ("ldrsh", "ldrsh r1, [r0, r2]")):
    sep = "adds r3, r3, #1" if w.startswith("ldrs") else "adds r2, r2, #1"
    VARIANTS += [
        V(f"T-LS-09.{w}", f"t_ls09_{w}", text, P(1), 1, ins(text, 16), case="T-LS-09"),
        V(f"T-LS-09.{w}.add", f"t_ls09_{w}_add", f"{text} ; {sep}", P(3), 2, ins(text, 16),
          obj=ISO, case="T-LS-09"),
    ]
VARIANTS += [
    V("T-LS-10.01", "t_ls01", "ldr r1, [r0] (base na flash)", P(1, text="hipótese: igual à SRAM"), 1,
      ins("ldr r1, [r0, #0]", 16), setup="rom", case="T-LS-10",
      source="@stmicroelectronics2021[§3.3.3]", note="disputa DCode × ICode na interface da flash"),
    V("T-LS-10.03", "t_ls03", "ldr r1, [r0] ; adds (base na flash)", P(3, text="hipótese: igual à SRAM"),
      2, ins("ldr r1, [r0, #0]", 16), setup="rom", case="T-LS-10", obj=ISO,
      source="@stmicroelectronics2021[§3.3.3]"),
]
for n in range(2, 9):
    amb = n == 3
    VARIANTS.append(V(f"T-LSM-01.n{n}", f"t_lsm01_{n}", f"ldm.w r0, {LISTS[n]}",
                      P(1 + n, 1 + n + (1 if amb else 0), ambiguous=amb,
                        text="§18.3: \"2+1+1 or 5\"" if amb else "1+N"), 1,
                      ins(f"ldmia.w r0, {LISTS[n]}", 32), level="N1", case="T-LSM-01",
                      source=f"@armlimited2007[Tab. 18-1, §18.3]",
                      note="para N ≥ 5 a lista pula r5–r7 (instrumento)"))
    VARIANTS.append(V(f"T-LSM-02.n{n}", f"t_lsm02_{n}", f"stm.w r0, {LISTS[n]}", P(1 + n), 1,
                      ins(f"stmia.w r0, {LISTS[n]}", 32), level="N1", case="T-LSM-02",
                      note="\"an eight element store takes nine cycles\""))
_PP = {1: "{r4}", 2: "{r4, r5}", 3: "{r4, r5, r6}", 4: "{r4, r5, r6, r7}", 5: "{r4, r5, r6, r7, r8}",
       6: "{r4, r5, r6, r7, r8, r9}", 7: "{r4, r5, r6, r7, r8, r9, sl}",
       8: "{r4, r5, r6, r7, r8, r9, sl, fp}"}
for n in range(1, 9):
    text = f"push {_PP[n]}" if n <= 4 else f"stmdb sp!, {_PP[n]}"
    VARIANTS.append(V(f"T-LSM-03.n{n}", f"t_lsm03_{n}", f"push {_PP[n]} ; pop {_PP[n]}",
                      P(2 * (1 + n)), 2, ins(text, 16 if n <= 4 else 32), setup="none",
                      case="T-LSM-03", note="a pilha volta ao ponto inicial a cada unidade"))
VARIANTS += [
    V("T-LSM-04.ldrd", "t_lsm04_ldrd", "ldrd r2, r3, [r0]", P(3), 1, ins("ldrd r2, r3, [r0]", 32),
      case="T-LSM-04", note="\"three cycles when not stalled\""),
    V("T-LSM-04.strd", "t_lsm04_strd", "strd r2, r3, [r0]", P(3), 1, ins("strd r2, r3, [r0]", 32),
      case="T-LSM-04"),
    V("T-LSM-05.a", "t_lsm05a", "ldrex r1, [r0]", P(1, 2), 1, ins("ldrex r1, [r0]", 32), case="T-LSM-05",
      note="\"LDREX and STREX can be pipelined exactly as LDR\""),
    V("T-LSM-05.b", "t_lsm05b", "ldrex r1, [r0] ; adds r4, r4, #1", P(3), 2, ins("ldrex r1, [r0]", 32),
      case="T-LSM-05", obj=ISO),
    V("T-LSM-05.c", "t_lsm05c", "ldrex r1, [r0] ; strex r2, r1, [r0]", P(3, 4), 2,
      ins("ldrex r1, [r0]", 32), case="T-LSM-05", obj=ISO,
      note="o par do registrador de eventos (custo do ticket FID3, que o C3 precisa conhecer)"),
    # Desalinhado: blocos de T-LS-03 / T-LS-09 com a base deslocada (setup cell + arg).
    V("T-AL-01.ldrh.odd", "t_ls09_ldrh_add", "ldrh r1, [r0] ; adds (r0 ímpar)", P(4), 2,
      ins("ldrh r1, [r0, #0]", 16), arg=1, case="T-AL-01", obj=ISO,
      note="+1: meia palavra em endereço de byte"),
    V("T-AL-01.ldr.m2", "t_ls03", "ldr r1, [r0] ; adds (r0 ≡ 2 mod 4)", P(4), 2,
      ins("ldr r1, [r0, #0]", 16), arg=2, case="T-AL-01", obj=ISO),
    V("T-AL-01.ldr.m1", "t_ls03", "ldr r1, [r0] ; adds (r0 ≡ 1 mod 4)", P(5), 2,
      ins("ldr r1, [r0, #0]", 16), arg=1, case="T-AL-01", obj=ISO),
    V("T-AL-01.ldr.m3", "t_ls03", "ldr r1, [r0] ; adds (r0 ≡ 3 mod 4)", P(5), 2,
      ins("ldr r1, [r0, #0]", 16), arg=3, case="T-AL-01", obj=ISO),
    V("T-AL-01.ldrh.aligned", "t_ls09_ldrh_add", "ldrh r1, [r0] ; adds (alinhado, controle)", P(3), 2,
      ins("ldrh r1, [r0, #0]", 16), case="T-AL-01", obj=ISO),
    V("T-AL-02.str", "t_al02_str", "str r1, [r0] ; adds (r0 ≡ 1 mod 4)", P(2, ambiguous=True), 2,
      ins("str r1, [r0, #0]", 16), arg=1, case="T-AL-02", obj=ISO,
      note="\"A STR or STRH cannot delay the processor because of the store buffer\""),
    V("T-AL-02.strh", "t_al02_strh", "strh r1, [r0] ; adds (r0 ímpar)", P(2, ambiguous=True), 2,
      ins("strh r1, [r0, #0]", 16), arg=1, case="T-AL-02", obj=ISO),
    V("T-BB-01", "t_ls03", "ldr r1, [alias] ; adds", P(3, text="derivado (§14.10)"), 2,
      ins("ldr r1, [r0, #0]", 16), setup="alias", level="N3", obj=ISO,
      source="@armlimited2007[§14.10]"),
    V("T-BB-02", "t_al02_str", "str r1, [alias] ; adds", P(2, text="derivado (§14.10)"), 2,
      ins("str r1, [r0, #0]", 16), setup="alias", level="N3", obj=ISO,
      source="@armlimited2007[§14.10]"),
    V("T-BB-03.alias", "t_bb03", "str r1, [alias] ; ldr r2, [sram]", P(4, text="derivado (§14.5.2)"), 2,
      ins("str r1, [r0, #0]", 16), setup="bb3_alias", level="N3", obj=ISO, case="T-BB-03",
      source="@armlimited2007[§14.5.2]", note="\"Bit-band writes take two cycles [...] stall\""),
    V("T-BB-03.plain", "t_bb03", "str r1, [sram] ; ldr r2, [sram]", P(3, text="derivado"), 2,
      ins("str r1, [r0, #0]", 16), setup="bb3_plain", level="N3", obj=ISO, case="T-BB-03",
      source="@armlimited2007[§14.5.2]"),
]

# Diagnóstico de T-LS-10.01 (material-base: se a linearidade falha, investigar
# com K = 16 e 32): a mesma unidade com a base na flash, em tamanhos maiores.
for k in (16, 32):
    VARIANTS.append(Variant(
        f"T-LS-10.01.k{k}", "T-LS-10", "t_ls01k", "ldr r1, [r0] (base na flash)",
        P(1, text="hipótese: igual à SRAM"), F(1), setup="rom", level="N3",
        source="@stmicroelectronics2021[§3.3.3]", first=ins("ldr r1, [r0, #0]", 16),
        sizes=(k, 2 * k, 3 * k), blocks=(f"t_ls01k_{k}", f"t_ls01k_{k}x2", f"t_ls01k_{k}x3"),
        note=f"diagnóstico da não linearidade com K = 8: mesmo bloco com K = {k}"))
