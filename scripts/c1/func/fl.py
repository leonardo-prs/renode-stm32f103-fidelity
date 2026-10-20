"""FL — lógicas, MOV/MVN e constantes modificadas (src/c1/func/fl.S)."""
from __future__ import annotations

from .. import arm
from ..vectors import MOD_CONSTS
from .common import apsr_out, carry, hx, ins, logical, vbin, vflg1, vflg2, vun

SRC = "@armlimited2021"
OPS = {"ands": lambda a, b: a & b, "orrs": lambda a, b: a | b, "eors": lambda a, b: a ^ b,
       "bics": lambda a, b: a & ~b & arm.MASK32, "orns": lambda a, b: a | (~b & arm.MASK32)}
SEC = {"ands": "§A7.7.9", "orrs": "§A7.7.92", "eors": "§A7.7.36", "bics": "§A7.7.16",
       "orns": "§A7.7.90"}
SHIFTS = {"lsl1": ("LSL", 1, "lsl #1"), "lsr32": ("LSR", 32, "lsr #32"),
          "asr32": ("ASR", 32, "asr #32"), "ror1": ("ROR", 1, "ror #1"), "rrx": ("RRX", 1, "rrx")}
FLAGS_VARIED = (0x0000_0000, 0x5000_0000, 0xA800_0000, 0xF800_0000)


def _logic(op, srtype="LSL", amount=0):
    def f(x, y, ap):
        shifted, c = arm.shift_c(y, srtype, amount, carry(ap))
        r = OPS[op](x, shifted) & arm.MASK32
        return r, logical(ap, r, c)
    return f


FORMS = []
for op in ("ands", "orrs", "eors", "bics"):
    FORMS += [
        vbin(f"FL-01.{op}.t1", "FL-01", f"v_fl01_{op}_t1", _logic(op), ins(f"{op} r2, r3", 16),
             level="N1", source=f"{SRC}[{SEC[op]}]"),
        vbin(f"FL-01.{op}.t2", "FL-01", f"v_fl01_{op}_t2", _logic(op),
             ins(f"{op}.w r2, r2, r3", 32), level="N1", source=f"{SRC}[{SEC[op]}]"),
    ]
FORMS.append(vbin("FL-01.orns", "FL-01", "v_fl01_orns_t1", _logic("orns"),
                  ins("orns r2, r2, r3", 32), level="N1", source=f"{SRC}[§A7.7.90]"))

for op in OPS:
    for key, (srtype, amount, text) in SHIFTS.items():
        w = "" if op == "orns" else ".w"
        FORMS.append(vbin(f"FL-02.{op}.{key}", "FL-02", f"v_fl02_{op}_{key}",
                          _logic(op, srtype, amount), ins(f"{op}{w} r2, r2, r3, {text}", 32),
                          source=f"{SRC}[{SEC[op]}, §A7.4.2]"))


def _mov(x, ap):
    return x, logical(ap, x, carry(ap))


def _mvn(x, ap):
    r = ~x & arm.MASK32
    return r, logical(ap, r, carry(ap))


FORMS += [
    vun("FL-03.movs.t2", "FL-03", "v_fl03_movs_t2", _mov, ins("movs r2, r3", 16), level="N1",
        source="@stmicroelectronics2024[§3.5.6]"),
    vun("FL-03.movs.t3", "FL-03", "v_fl03_movs_t3", _mov, ins("movs.w r2, r3", 32), level="N1",
        source="@stmicroelectronics2024[§3.5.6]"),
    vun("FL-03.mvns.t1", "FL-03", "v_fl03_mvns_t1", _mvn, ins("mvns r2, r3", 16), level="N1",
        source="@stmicroelectronics2024[§3.5.6]"),
    vun("FL-03.mvns.t2", "FL-03", "v_fl03_mvns_t2", _mvn, ins("mvns.w r2, r3", 32), level="N1",
        source="@stmicroelectronics2024[§3.5.6]"),
    vflg2("FL-03.tst.t1", "FL-03", "v_fl03_tst_t1", lambda x, y, ap: _logic("ands")(x, y, ap)[1],
          ins("tst r2, r3", 16), level="N1", source="@stmicroelectronics2024[§3.5.9]"),
    vflg2("FL-03.tst.t2", "FL-03", "v_fl03_tst_t2", lambda x, y, ap: _logic("ands")(x, y, ap)[1],
          ins("tst.w r2, r3", 32), level="N1", source="@stmicroelectronics2024[§3.5.9]"),
    vflg2("FL-03.teq", "FL-03", "v_fl03_teq_t1", lambda x, y, ap: _logic("eors")(x, y, ap)[1],
          ins("teq r2, r3", 32), level="N1", source="@stmicroelectronics2024[§3.5.9]"),
]

# FL-04: C inicial 0 e 1 (com 0x80000000, "C = bit 31" só se distingue de
# "C inalterado" partindo de C = 0).
for c in MOD_CONSTS:
    def _imm(op, c=c):
        def f(x, ap):
            r = OPS[op](x, c) & arm.MASK32
            return r, logical(ap, r, arm.modified_imm_carry(c, carry(ap)))
        return f

    def _movi(c=c, inv=False):
        def f(x, ap):
            r = (~c & arm.MASK32) if inv else c
            return r, logical(ap, r, arm.modified_imm_carry(c, carry(ap)))
        return f
    FORMS += [
        vun(f"FL-04.movs.{hx(c)}", "FL-04", f"v_fl04_movs_{hx(c)}", _movi(), a=(0,),
            insn=ins(f"movs.w r2, #{c}", 32), source="@stmicroelectronics2024[§3.3.3]"),
        vun(f"FL-04.mvns.{hx(c)}", "FL-04", f"v_fl04_mvns_{hx(c)}", _movi(inv=True), a=(0,),
            insn=ins(f"mvns.w r2, #{c}", 32), source="@stmicroelectronics2024[§3.3.3]"),
        *[vun(f"FL-04.{op}.{hx(c)}", "FL-04", f"v_fl04_{op}_{hx(c)}", _imm(op),
              ins(f"{op}.w r2, r3, #{c}", 32), source="@stmicroelectronics2024[§3.3.3]")
          for op in ("ands", "orrs", "eors", "bics")],
        vflg1(f"FL-04.tst.{hx(c)}", "FL-04", f"v_fl04_tst_{hx(c)}",
              lambda x, ap, f=_imm("ands"): f(x, ap)[1], ins(f"tst.w r2, #{c}", 32),
              source="@stmicroelectronics2024[§3.3.3]"),
    ]

_keep = lambda fn: (lambda x, ap: (fn(x), apsr_out(ap)))  # noqa: E731
FORMS += [
    vun("FL-05.mov.t1", "FL-05", "v_fl05_mov_t1", _keep(lambda x: x), ins("mov r2, r3", 16),
        flags=FLAGS_VARIED, level="N1", source=f"{SRC}[§A7.7.77]"),
    vun("FL-05.mov.t3", "FL-05", "v_fl05_mov_t3", _keep(lambda x: x), ins("mov.w r2, r3", 32),
        flags=FLAGS_VARIED, level="N1", source=f"{SRC}[§A7.7.77]"),
    vun("FL-05.mvn", "FL-05", "v_fl05_mvn", _keep(lambda x: ~x & arm.MASK32),
        ins("mvn.w r2, r3", 32), flags=FLAGS_VARIED, level="N1", source=f"{SRC}[§A7.7.86]"),
    vun("FL-05.movw", "FL-05", "v_fl05_movw", _keep(lambda x: 0xABCD), ins("movw r2, #43981", 32),
        flags=FLAGS_VARIED, level="N1", source=f"{SRC}[§A7.7.76]"),
    vun("FL-05.movt", "FL-05", "v_fl05_movt", _keep(lambda x: 0xABCD0000 | (x & 0xFFFF)),
        ins("movt r2, #43981", 32), flags=FLAGS_VARIED, level="N1", source=f"{SRC}[§A7.7.79]",
        note="MOVT preserva a metade baixa"),
]
