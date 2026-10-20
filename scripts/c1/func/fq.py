"""FQ — saturação (src/c1/func/fq.S)."""
from __future__ import annotations

from .. import arm
from ..catalog import Form
from ..vectors import V32, rows
from .common import apsr_out, ins, vun

SRC = "@armlimited2021"
# Q inicial 0 (para ver a saturação ligar Q) com NZCV limpos e ligados.
FLAGS = (0x0000_0000, 0xF000_0000)


def _ssat_values(n: int):
    cand = {1 << (n - 1), -(1 << (n - 1)), (1 << (n - 1)) - 1, -(1 << (n - 1)) - 1}
    vals = {arm.u32(v) for v in cand if -(1 << 31) <= v < (1 << 31)}
    return tuple(sorted(vals | set(V32)))


def _usat_values(n: int):
    vals = {arm.u32(v) for v in (-1, 0, (1 << n) - 1, 1 << n) if -(1 << 31) <= v < (1 << 31)}
    return tuple(sorted(vals | set(V32)))


def _sat(signed: bool, n: int, srtype: str = "LSL", k: int = 0):
    def f(x, ap):
        operand = arm.sint(arm.shift(x, srtype, k, 0)) if k else arm.sint(x)
        r, q = (arm.signed_sat_q if signed else arm.unsigned_sat_q)(operand, n)
        return r, apsr_out(arm.with_q(ap, 1) if q else ap)
    return f


FORMS = []
for n in (1, 8, 16, 31, 32):
    FORMS.append(vun(f"FQ-01.ssat.{n}", "FQ-01", f"v_fq01_ssat_{n}", _sat(True, n),
                     ins(f"ssat r2, #{n}, r3", 32), a=_ssat_values(n), flags=FLAGS,
                     source=f"{SRC}[§A7.7.152]"))
for n in (0, 1, 8, 16, 31):
    FORMS.append(vun(f"FQ-02.usat.{n}", "FQ-02", f"v_fq02_usat_{n}", _sat(False, n),
                     ins(f"usat r2, #{n}, r3", 32), a=_usat_values(n), flags=FLAGS,
                     source=f"{SRC}[§A7.7.213]"))
for k in (1, 4, 31):
    for signed, op in ((True, "ssat"), (False, "usat")):
        for sr, text in (("LSL", "lsl"), ("ASR", "asr")):
            FORMS.append(vun(f"FQ-03.{op}.{text}.{k}", "FQ-03", f"v_fq03_{op}_{text}_{k}",
                             _sat(signed, 8, sr, k), ins(f"{op} r2, #8, r3, {text} #{k}", 32),
                             flags=FLAGS, source="@stmicroelectronics2024[§3.7.1]"))

FORMS.append(Form(
    "FQ-04.sticky", "FQ-04", "v_fq04_sticky", (rows((0,)),), ("apsr_sat", "apsr_nosat", "apsr_msr"),
    lambda vec: {"apsr_sat": 1 << arm.Q_BIT, "apsr_nosat": 1 << arm.Q_BIT, "apsr_msr": 0},
    (ins("ssat r2, #8, r3", 32, 0), ins("ssat r2, #8, r3", 32, 1)),
    source="@armlimited2007[Tab. 2-1]", note="Q só é zerada por escrita explícita no APSR"))

DERIVED = {"FQ-05": {"cases": ("FQ-01", "FQ-02", "FQ-03"), "field": "apsr", "mask": arm.NZCV_MASK,
                     "source": f"{SRC}[§A7.7.152]"}}
