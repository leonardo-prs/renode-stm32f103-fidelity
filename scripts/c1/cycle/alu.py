"""T-ALU, T-MUL, T-DIV (src/c1/cycle/alu.S; TRM r1p1 Tab. 18-1)."""
from __future__ import annotations

from fractions import Fraction as F

from .. import arm
from ..func.common import ins
from . import P, R, Variant

T181 = "@armlimited2007[Tab. 18-1]"


def one(name, case, bs, unit, first, *, level="N2", n=1, obj="custo marginal", note="", regs=None):
    return Variant(name, case, bs, unit, P(n), F(n), regs=regs or R(r1=0x1234, r2=3, r3=0x55),
                   level=level, source=T181, first=first, obj=obj, note=note)


VARIANTS = [
    one("T-ALU-01", "T-ALU-01", "t_alu01", "adds r0, r0, #1", ins("adds r0, #1", 16), level="N1"),
    one("T-ALU-02", "T-ALU-02", "t_alu02", "add.w r0, r1, r2, lsl #3",
        ins("add.w r0, r1, r2, lsl #3", 32), level="N1"),
    Variant("T-ALU-03", "T-ALU-03", "t_alu03", "movw r0, #0x1234 ; movt r0, #0x5678", P(2), F(2),
            source=T181, first=ins("movw r0, #4660", 32)),
    one("T-ALU-04", "T-ALU-04", "t_alu04", "lsl.w r0, r1, r2", ins("lsl.w r0, r1, r2", 32),
        note="sem custo extra pela quantidade"),
]
for key, unit, text in (("clz", "clz r0, r1", "clz r0, r1"), ("rbit", "rbit r0, r1", "rbit r0, r1"),
                        ("rev", "rev r0, r1", "rev r0, r1"), ("uxtb", "uxtb.w r0, r1", "uxtb.w r0, r1"),
                        ("ubfx", "ubfx r0, r1, #4, #8", "ubfx r0, r1, #4, #8"),
                        ("bfi", "bfi r0, r1, #4, #8", "bfi r0, r1, #4, #8")):
    VARIANTS.append(one(f"T-ALU-05.{key}", "T-ALU-05", f"t_alu05_{key}", unit,
                        ins(text, 16 if key == "rev" else 32)))
VARIANTS += [
    one("T-ALU-06", "T-ALU-06", "t_alu06", "ssat r0, #8, r1", ins("ssat r0, #8, r1", 32)),
    one("T-ALU-07.dep", "T-ALU-07", "t_alu07_dep", "adds r0, r0, r1", ins("adds r0, r0, r1", 16),
        obj="latência", note="encaminhamento: a dependência não custa"),
    one("T-ALU-07.ind", "T-ALU-07", "t_alu07_ind", "adds r2, r0, r1", ins("adds r2, r0, r1", 16)),
    one("T-MUL-01", "T-MUL-01", "t_mul01", "mul r2, r0, r1", ins("mul.w r2, r0, r1", 32),
        regs=R(r0=0x1234, r1=0x5678)),
]
for op in ("mla", "mls"):
    VARIANTS.append(Variant(f"T-MUL-02.{op}", "T-MUL-02", f"t_mul02_{op}", f"{op} r2, r0, r1, r3",
                            P(2), F(1), regs=R(r0=0x1234, r1=0x5678, r3=7), level="N1",
                            source=T181, first=ins(f"{op} r2, r0, r1, r3", 32)))

# Classes de operandos por MAGNITUDE (nota c: "ABS(inputs) < 64K terminates early").
_UMULL = (("pequenos", 0x1234, 0x5678), ("fronteira_ffff", 0xFFFF, 0xFFFF),
          ("fronteira_10000", 0x1_0000, 0x1_0000), ("grandes", 0xFFFF_FFFF, 0xFFFF_FFFF))
_SMULL = _UMULL[:3] + (("menos1", arm.u32(-1), 0x1234), ("grandes", 0x7FFF_FFFF, 0x8000_0000))
for op, classes, lo, hi, case, level in (("umull", _UMULL, 3, 5, "T-MUL-03", "N1"),
                                         ("smull", _SMULL, 3, 5, "T-MUL-03", "N1"),
                                         ("umlal", _UMULL, 4, 7, "T-MUL-04", "N2"),
                                         ("smlal", _SMULL, 4, 7, "T-MUL-04", "N2")):
    for cls, a, b in classes:
        VARIANTS.append(Variant(
            f"{case}.{op}.{cls}", case, f"t_{case[2:].lower().replace('-', '')}_{op}",
            f"{op} r2, r3, r0, r1", P(lo, hi, text="término antecipado se ABS(inputs) < 64K"),
            F(1), regs=R(r0=a, r1=b), level=level, source=f"{T181}, nota c",
            obj="latência" if case == "T-MUL-04" else "custo marginal",
            first=ins(f"{op} r2, r3, r0, r1", 32),
            note="SMLAL = UMLAL + 1" if op.endswith("lal") else ""))

# A grade da divisão: dividendo 2^a − 1, divisor 2^b − 1, mais divisor 0 e
# divisor maior que o dividendo (72 pontos).
A_BITS = (1, 2, 4, 8, 12, 16, 20, 24, 28, 32)
B_BITS = (1, 2, 4, 8, 16, 24, 32)
for a in A_BITS:
    for b in B_BITS:
        VARIANTS.append(Variant(
            f"T-DIV-01.a{a}.b{b}", "T-DIV-01", "t_div01", "udiv r2, r0, r1",
            P(2, 12, text="mínimo com divisor > dividendo ou 0"), F(1),
            regs=R(r0=(1 << a) - 1, r1=(1 << b) - 1), level="N1", source=f"{T181}, nota e",
            first=ins("udiv r2, r0, r1", 32)))
VARIANTS += [
    Variant("T-DIV-01.div0", "T-DIV-01", "t_div01", "udiv r2, r0, r1", P(2, 12), F(1),
            regs=R(r0=0xFFFF_FFFF, r1=0), level="N1", source=f"{T181}, nota e",
            first=ins("udiv r2, r0, r1", 32), note="divisor 0 (sem trap): resultado 0"),
    Variant("T-DIV-01.bgta", "T-DIV-01", "t_div01", "udiv r2, r0, r1", P(2, 12), F(1),
            regs=R(r0=0xF, r1=0xFF), level="N1", source=f"{T181}, nota e",
            first=ins("udiv r2, r0, r1", 32), note="divisor maior que o dividendo"),
]
for a, b in ((8, 4), (16, 8), (31, 16), (31, 1), (16, 16)):
    for sa, sb, tag in ((-1, 1, "nm"), (1, -1, "mn"), (-1, -1, "nn")):
        VARIANTS.append(Variant(
            f"T-DIV-02.a{a}.b{b}.{tag}", "T-DIV-02", "t_div02", "sdiv r2, r0, r1",
            P(2, 12, text="o TRM não fala de sinal: caracterização"), F(1),
            regs=R(r0=arm.u32(sa * ((1 << a) - 1)), r1=arm.u32(sb * ((1 << b) - 1))),
            source=f"{T181}, nota e", first=ins("sdiv r2, r0, r1", 32)))
