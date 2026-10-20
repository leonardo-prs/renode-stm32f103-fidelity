"""FD — divisão (src/c1/func/fd.S)."""
from __future__ import annotations

from .. import arm
from ..catalog import F_FAULT, Form
from ..vectors import rows, table
from .common import DIVBYZERO, apsr_out, fault, ins, vbin

SRC = "@armlimited2021"
ONE_FLAGS = (0xF800_0000,)
ROUND = ((arm.u32(-7), 2), (7, arm.u32(-2)), (arm.u32(-7), arm.u32(-2)))

FORMS = [
    vbin("FD-01.udiv", "FD-01", "v_fd01_udiv", lambda x, y, ap: (arm.udiv(x, y), apsr_out(ap)),
         ins("udiv r2, r2, r3", 32), flags=ONE_FLAGS, source=f"{SRC}[§A7.7.195]"),
    vbin("FD-02.sdiv", "FD-02", "v_fd02_sdiv", lambda x, y, ap: (arm.sdiv(x, y), apsr_out(ap)),
         ins("sdiv r2, r2, r3", 32), flags=ONE_FLAGS, source=f"{SRC}[§A7.7.127]"),
]
_round = vbin("FD-02.round", "FD-02", "v_fd02_sdiv",
              lambda x, y, ap: (arm.sdiv(x, y), apsr_out(ap)), ins("sdiv r2, r2, r3", 32),
              source=f"{SRC}[§A7.7.127]", note="arredondamento em direção a zero")
_round.axes = (table(*ROUND), rows(ONE_FLAGS))
FORMS.append(_round)

for op in ("udiv", "sdiv"):
    def oracle(vec, op=op):
        x, ap = vec
        return {"rd": 0xDEADBEEF, **fault(DIVBYZERO, f"v_fd03_{op}_x0", apsr=ap)}
    FORMS.append(Form(f"FD-03.{op}", "FD-03", f"v_fd03_{op}",
                      (rows((0, 1, 0x8000_0000, 0xFFFF_FFFF)), rows((0x0000_0000, 0xF800_0000))),
                      ("rd",), oracle, (ins(f"{op} r2, r3, r4", 32),), flags=F_FAULT,
                      source="@armlimited2007[Tab. 5-10] @stmicroelectronics2024[§4.4.7, §4.4.10]",
                      note="CCR.DIV_0_TRP = 1 é precondição do caso"))

DERIVED = {"FD-04": {"cases": ("FD-01", "FD-02"), "field": "apsr", "mask": arm.NZCVQ_MASK,
                     "source": "@stmicroelectronics2024[§3.6.3]"}}
