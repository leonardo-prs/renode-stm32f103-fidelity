"""FC — controle de fluxo (src/c1/func/fc.S)."""
from __future__ import annotations

from .. import arm
from ..catalog import F_FAULT, Form
from ..vectors import NZCV16, rows, table
from .common import (INVSTATE, T_BIT, UNDEFINSTR, apsr_out, arith, fault, ins, no_fault, vbin)

SRC = "@armlimited2021"
CONDS14 = arm.CONDS[:14]


def _branch(name, routine, cond, insn):
    def oracle(vec):
        (ap,) = vec
        return {"taken": int(cond is None or arm.condition_passed(cond, ap)), "apsr": apsr_out(ap)}
    return Form(name, "FC-01", routine, (rows(NZCV16),), ("taken", "apsr"), oracle, (insn,),
                level="N1", source=f"{SRC}[§A7.3.1, §A7.7.12]")


FORMS = []
for c in CONDS14:
    FORMS.append(_branch(f"FC-01.t1.{c}", f"v_fc01_t1_{c}", c, ins(f"b{c}.n", 16)))
    FORMS.append(_branch(f"FC-01.t3.{c}", f"v_fc01_t3_{c}", c, ins(f"b{c}.w", 32)))
FORMS.append(_branch("FC-01.t2", "v_fc01_t2", None, ins("b.n", 16)))
FORMS.append(_branch("FC-01.t4", "v_fc01_t4", None, ins("b.w", 32)))
for f in FORMS:
    f.insns = tuple(type(i)(i.mnemonic, i.width, None, i.k) for i in f.insns)   # alvo: endereço


def _it(name, routine, cond, pattern):
    def oracle(vec):
        (ap,) = vec
        done = arm.it_executes(cond, pattern, ap) if cond != "al" else [True] * (1 + len(pattern))
        return {"bits": sum(1 << k for k, ran in enumerate(done) if ran), "apsr": apsr_out(ap)}
    return Form(name, "FC-02", routine, (rows(NZCV16),), ("bits", "apsr"), oracle,
                (ins(f"it{pattern} {cond}", 16),), source=f"{SRC}[§A7.7.38, §A7.3.3]")


for pattern in ("", "t", "e", "te", "et", "ttt", "eee"):
    for c in CONDS14:
        FORMS.append(_it(f"FC-02.it{pattern}.{c}", f"v_fc02_it{pattern}_{c}", c, pattern))
FORMS.append(_it("FC-02.it.al", "v_fc02_it_al", "al", ""))
FORMS.append(_it("FC-02.itttt.al", "v_fc02_itttt_al", "al", "ttt"))

# FC-03: a mesma codificação de 16 bits, dentro (sem flags) e fora (com flags) de IT.
_PAIRS3 = ((0xFFFF_FFFF, 1), (0x7FFF_FFFF, 1), (0, 0), (1, 1))
_FLAGS3 = (0x4000_0000, 0x7800_0000, 0x0000_0000, 0xB800_0000)    # Z = 1, 1, 0, 0


def _add_out(x, y, ap):
    r, c, v = arm.add_with_carry(x, y, 0)
    return r, arith(ap, r, c, v)


def _add_in(x, y, ap):
    return (arm.u32(x + y) if arm.condition_passed("eq", ap) else x), apsr_out(ap)


def _mov_out(x, y, ap):
    return 0, apsr_out(arm.with_nzcv(ap, 0, 1))


def _mov_in(x, y, ap):
    return (0 if arm.condition_passed("eq", ap) else x), apsr_out(ap)


for key, fn, insns in (
        ("add.out", _add_out, (ins("adds r2, r2, r3", 16),)),
        ("add.in", _add_in, (ins("it eq", 16, 0), ins("addeq r2, r2, r3", 16, 1))),
        ("mov.out", _mov_out, (ins("movs r2, #0", 16),)),
        ("mov.in", _mov_in, (ins("it eq", 16, 0), ins("moveq r2, #0", 16, 1)))):
    f = vbin(f"FC-03.{key}", "FC-03", f"v_fc03_{key.replace('.', '_')}", fn, insns[0],
             source=f"{SRC}[§A7.7.4, §A7.7.76, encoding T1]")
    f.insns = insns
    f.axes = (table(*_PAIRS3), rows(_FLAGS3))
    FORMS.append(f)


def _fc04(vec):
    x, y, ap = vec
    if not arm.condition_passed("eq", ap):
        return {"marker": 0, "apsr": apsr_out(ap)}
    r, c, v = arm.add_with_carry(x, arm.u32(~y), 1)
    ap2 = arith(ap, r, c, v)
    return {"marker": int(arm.condition_passed("eq", ap2)), "apsr": ap2}


FORMS.append(Form("FC-04", "FC-04", "v_fc04", (table((5, 5), (5, 6), (0x8000_0000, 0x7FFF_FFFF)),
                                               rows((0x4000_0000, 0x0000_0000))),
                  ("marker", "apsr"), _fc04, (ins("itt eq", 16),), source=f"{SRC}[§A7.3.3]"))

_FLAGS5 = (0x0000_0000, 0xF800_0000, 0x4000_0000, 0x5000_0000)
for op, taken in (("cbz", lambda r: r == 0), ("cbnz", lambda r: r != 0)):
    FORMS.append(Form(
        f"FC-05.{op}", "FC-05", f"v_fc05_{op}", (rows((0, 1, 0x8000_0000)), rows(_FLAGS5)),
        ("taken", "apsr"),
        lambda vec, taken=taken: {"taken": int(taken(vec[0])), "apsr": apsr_out(vec[1])},
        (type(ins("cbz", 16))(op, 16, None),), level="N1",
        source="@stmicroelectronics2024[§3.8.6]"))

for op, where, text in (("tbb", "flash", "tbb [pc, r2]"), ("tbh", "flash", "tbh [pc, r2, lsl #1]"),
                        ("tbb", "sram", "tbb [r4, r2]"), ("tbh", "sram", "tbh [r4, r2, lsl #1]")):
    FORMS.append(Form(f"FC-06.{op}.{where}", "FC-06", f"v_fc06_{op}_{where}", (rows((0, 1, 2)),),
                      ("target",), lambda vec: {"target": vec[0] + 1}, (ins(text, 32),),
                      source="@stmicroelectronics2024[§3.8.8]"))

FORMS += [
    Form("FC-07.bl", "FC-07", "v_fc07_bl", (rows((0,)),), ("lr", "marker"),
         lambda vec: {"lr": "v_fc07_bl_x0+5", "marker": 7},
         (type(ins("bl", 32))("bl", 32, None),), level="N1", source=f"{SRC}[§A7.7.18]",
         note="LR = endereço de retorno com bit 0 = 1"),
    Form("FC-07.blx", "FC-07", "v_fc07_blx", (rows((0,)),), ("lr", "marker"),
         lambda vec: {"lr": "v_fc07_blx_x0+3", "marker": 7}, (ins("blx r2", 16),), level="N1",
         source=f"{SRC}[§A7.7.19]"),
]

for op in ("bx", "blx"):
    FORMS.append(Form(
        f"FC-08.{op}", "FC-08", f"v_fc08_{op}", (rows((0x0000_0000, 0xF800_0000)),), ("marker",),
        lambda vec, op=op: {"marker": 0, **fault(INVSTATE, f"v_fc08_{op}_x1", apsr=vec[0],
                                                  xpsr_extra=0)},
        (ins(f"{op} r2", 16, 0), ins("mov.w r3, #1", 32, 1)), flags=F_FAULT,
        source=f"{SRC}[§A3.2.1] @armlimited2007[Tab. 5-10]",
        note="PC empilhado = alvo; T empilhado = 0"))

for op, text in (("mov", "mov pc, r2"), ("add", "add pc, r2")):
    FORMS.append(Form(
        f"FC-09.{op}", "FC-09", f"v_fc09_{op}", (rows((0, 1)),), ("marker",),
        lambda vec, op=op: {"marker": 1, **no_fault(f"v_fc09_{op}_land")}, (ins(text, 16),),
        flags=F_FAULT, source=f"{SRC}[§A3.2.1, §A7.7.4, §A7.7.77]",
        note="ALUWritePC ignora o bit 0"))


def _fc10(kind):
    def oracle(vec):
        bit, ap = vec
        if bit:
            return {"marker": 1, **no_fault(f"v_fc10_{kind}_land")}
        return {"marker": 0, **fault(INVSTATE, f"v_fc10_{kind}_x1", apsr=ap, xpsr_extra=0)}
    return oracle


for kind, text, width in (("ldr", "ldr.w pc, [ip]", 32), ("pop", "pop {r4, pc}", 16),
                          ("ldm", "ldmia.w ip, {r4, pc}", 32)):
    FORMS.append(Form(f"FC-10.{kind}", "FC-10", f"v_fc10_{kind}",
                      (rows((1, 0)), rows((0x0000_0000, 0xF800_0000))), ("marker",), _fc10(kind),
                      (ins(text, width, 0), ins("mov.w r3, #1", 32, 1)), flags=F_FAULT,
                      source=f"{SRC}[§A3.2.1]"))


def _fc11(vec):
    (ap,) = vec
    if not arm.condition_passed("ne", ap):
        return {"marker": 1, **no_fault("v_fc11_land")}
    it = arm.itstate_to_xpsr(arm.it_state("ne", ""))
    return {"marker": 1, **fault(UNDEFINSTR, "v_fc11_x1", apsr=ap, xpsr_extra=T_BIT | it)}


FORMS.append(Form("FC-11", "FC-11", "v_fc11", (rows((0x4000_0000, 0x0000_0000)),), ("marker",),
                  _fc11, (ins("it ne", 16, 0), ins("qaddne r0, r0, r1", 32, 1)), flags=F_FAULT,
                  source=f"{SRC}[§A7.3.2]",
                  note="QADD (DSP) é indefinida no M3; com a condição falsa vira NOP"))
