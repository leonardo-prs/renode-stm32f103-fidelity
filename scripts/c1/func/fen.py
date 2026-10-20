"""FEN — exceções síncronas e faltas (src/c1/func/fen.S)."""
from __future__ import annotations

from ..catalog import F_FAULT, F_ISOLATE, F_TERMINAL, Alt, Form
from ..vectors import rows, table
from .common import (DIVBYZERO, EXC_HANDLER, EXC_THREAD_MSP, EXC_THREAD_PSP, HFSR_FORCED, IACCVIOL,
                     INVPC, IPSR_HARD, IPSR_MEM, IPSR_USAGE, NOCP, T_BIT, UNDEFINSTR, XPSR_MASK,
                     fault, ins)

SRC = "@armlimited2021"
FLAGS = (0x0000_0000, 0xF800_0000)
PATTERNS = (0xA0A0_A0A0, 0xA1A1_A1A1, 0xA2A2_A2A2, 0xA3A3_A3A3, 0xACAC_ACAC, 0xAEAE_AEAE)
NO_APSR = 0x0700_FFFF        # T, ITSTATE, bit 9 e exceção (APSR do tratador é UNKNOWN)
FRAME_OUTS = (*(f"f{k}" for k in range(8)), "exc_return", "ipsr", "frame_delta",
              "a0", "a1", "a2", "a3", "a12", "alr")


def _svcframe(routine, exc):
    def oracle(vec):
        regs = dict(zip(("f0", "f1", "f2", "f3", "f4", "f5"), PATTERNS))
        after = dict(zip(("a0", "a1", "a2", "a3", "a12", "alr"), PATTERNS))
        return {**regs, "f6": f"{routine}_x0+2", "f7": (0x9000_0000 | T_BIT, XPSR_MASK),
                "exc_return": exc, "ipsr": 11, "frame_delta": 32, **after}
    return oracle


FORMS = [
    Form("FEN-01", "FEN-01", "v_fen01", (rows((0,)),), FRAME_OUTS, _svcframe("v_fen01", EXC_THREAD_MSP),
         (ins("svc 0", 16),), level="N1", source="@stmicroelectronics2024[§2.3.7] " + SRC + "[§B1.5.6]",
         note="PC empilhado = instrução após o SVC; registradores restaurados no retorno"),
    Form("FEN-02", "FEN-02", "v_fen02", (rows((0,)),), FRAME_OUTS, _svcframe("v_fen02", EXC_THREAD_PSP),
         (ins("svc 0", 16),), level="N1", source=f"{SRC}[Tab. B1-8]"),
    Form("FEN-03", "FEN-03", "v_fen03", (rows((0,)),), ("marker",),
         lambda v: {"marker": 1, **fault(0, "v_fen03_x1+2", hfsr=HFSR_FORCED, ipsr=IPSR_HARD,
                                         exc_return=EXC_HANDLER, xpsr=(11 | T_BIT, NO_APSR))},
         (ins("svc 0", 16, 0), ins("svc 1", 16, 1)), flags=F_FAULT,
         source=f"{SRC}[§B1.5.4, §B1.5.6] @armlimited2007[Tab. 5-10]",
         note="escala para HardFault; o PC empilhado segue o ReturnAddress() do SVC "
              "(instrução seguinte); Yiu §12.2.3 lista o caso como UsageFault"),
    Form("FEN-04", "FEN-04", "v_fen04", (rows((0, 1)), rows((0, 4))), ("delta", "bit9", "restored"),
         lambda v: ({"delta": 36, "bit9": 0x200, "restored": 0} if v == (1, 4)
                    else {"delta": 32, "bit9": 0, "restored": 0}),
         (ins("svc 0", 16),), klass="B", source=f"@armlimited2007[Tab. 8-18] {SRC}[§B1.5.7]",
         note="STKALIGN × SP mod 8"),
]

for key, width, text, cfsr in (("udf", 16, "udf #0", UNDEFINSTR),
                               ("qadd", 32, "qadd r0, r0, r1", UNDEFINSTR),
                               ("sel", 32, "sel r0, r1, r2", UNDEFINSTR),
                               ("setend", 16, "setend le", UNDEFINSTR),
                               ("mrc", 32, "mrc 15, 0, r0, cr0, cr0, {0}", NOCP)):
    FORMS.append(Form(f"FEN-05.{key}", "FEN-05", f"v_fen05_{key}", (rows(FLAGS),), (),
                      lambda v, key=key, cfsr=cfsr: fault(cfsr, f"v_fen05_{key}_x0", apsr=v[0]),
                      (ins(text, width),), flags=F_FAULT,
                      source="@armlimited2007[Tab. 2-4, 2-5, 5-10]"))

FORMS.append(Form(
    "FEN-05.invpc", "FEN-05", "v_fen05_invpc", (rows((0,)),), (),
    lambda v: {"cfsr": INVPC, "hfsr": 0, "mmfar": None, "bfar": None,
               "pc": Alt(("v_fen05_invpc_x0+2", "v_fen05_invpc_x1"),
                         ("ARM ARM §B1.5.8: sem quadro novo (quadro do Thread)",
                          "TRM Tab. 8-23: a instrução que tentou o retorno")),
               "xpsr": None, "exc_return": 0xFFFF_FFF5, "landing": 0, "ipsr": IPSR_USAGE, "count": 1},
    (ins("svc 0", 16, 0), ins("bx lr", 16, 1)), flags=F_TERMINAL,
    source=f"{SRC}[§B1.5.8] @armlimited2007[Tab. 8-23]",
    note="caso terminal; SHPR2.PRI_11 = 0x80; o conteúdo do quadro é conflito documental"))

for key, text, width, cfsr in (("udf", "udf #0", 16, UNDEFINSTR),
                               ("div", "udiv r2, r2, r3", 32, DIVBYZERO)):
    FORMS.append(Form(f"FEN-06.{key}", "FEN-06", f"v_fen06_{key}", (rows(FLAGS),), (),
                      lambda v, key=key, cfsr=cfsr: fault(cfsr, f"v_fen06_{key}_x0", apsr=v[0],
                                                          hfsr=HFSR_FORCED, ipsr=IPSR_HARD),
                      (ins(text, width),), flags=F_FAULT,
                      source=f"{SRC}[§B1.5.4] @stmicroelectronics2024[§2.4.2, §4.4.11]",
                      note="USGFAULTENA = 0: escala para HardFault"))


def _xn(vec):
    target, ena, ap = vec
    if ena:
        return fault(IACCVIOL, target & ~1, apsr=ap, ipsr=IPSR_MEM)
    return fault(IACCVIOL, target & ~1, apsr=ap, ipsr=IPSR_HARD, hfsr=HFSR_FORCED)


for key, target in (("periph", 0x4000_0001), ("ppb", 0xE000_0001)):
    FORMS.append(Form(f"FEN-07.{key}", "FEN-07", "v_fen07", (table((target, 1), (target, 0)), rows((0,))),
                      (), _xn, (ins("blx r2", 16),), flags=F_FAULT | F_ISOLATE, klass="B",
                      source="@armlimited2007[Tab. 4-2] @stmicroelectronics2024[§2.2.1, §2.4.1]",
                      note="XN mesmo sem MPU; MMARVALID = 0"))

for key, bits in (("a", 0x800), ("b", 0xC00)):
    FORMS.append(Form(f"FEN-09.{key}", "FEN-09", f"v_fen09_{key}", (rows((0,)),), ("xpsr", "marker"),
                      lambda v, bits=bits: {"xpsr": (0x4000_0000 | T_BIT | bits, XPSR_MASK), "marker": 1},
                      (ins("itt eq" if key == "a" else "itte eq", 16),),
                      source=f"{SRC}[§A7.3.3, §B1.5.6, §A7.7.178]",
                      note="ITSTATE empilhado = ITAdvance() depois do SVC; o bloco continua"))

DERIVED = {"FEN-08": {"cases": ("FSY-08",), "field": None, "mask": None,
                      "source": f"{SRC}[§B3.1.1]", "note": "mesmo caso que FSY-08"}}
