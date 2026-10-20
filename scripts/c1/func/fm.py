"""FM — multiplicação (src/c1/func/fm.S)."""
from __future__ import annotations

from .. import arm
from ..catalog import Form
from ..vectors import FLAGS2, V32, rows, table
from .common import apsr_out, ins, vbin

SRC = "@armlimited2021"
ACC = (0x0000_0000, 0xFFFF_FFFF, 0x8000_0000)
ACC64 = ((0x0000_0000, 0x0000_0000), (0xFFFF_FFFF, 0x0000_0000), (0xFFFF_FFFF, 0xFFFF_FFFF))
ONE_FLAGS = (0xF800_0000,)


def _muls(x, y, ap):
    r = arm.u32(x * y)
    n, z = arm.nz(r)
    return r, apsr_out(arm.with_nzcv(ap, n, z))


def _acc(name, case, routine, fn, insn, source):
    def oracle(vec):
        x, y, a, ap = vec
        return {"rd": fn(x, y, a), "apsr": apsr_out(ap)}
    return Form(name, case, routine, (rows(V32), rows(V32), rows(ACC), rows(ONE_FLAGS)),
                ("rd", "apsr"), oracle, (insn,), source=source)


def _long(name, case, routine, fn, insn, acc, flags, source):
    def oracle(vec):
        x, y, lo, hi, ap = vec
        rlo, rhi = fn(x, y, lo, hi)
        return {"lo": rlo, "hi": rhi, "apsr": apsr_out(ap)}
    return Form(name, case, routine, (rows(V32), rows(V32), table(*acc), rows(flags)),
                ("lo", "hi", "apsr"), oracle, (insn,), source=source)


FORMS = [
    vbin("FM-01.muls", "FM-01", "v_fm01_muls", _muls, ins("muls r2, r3", 16),
         source="@stmicroelectronics2024[§3.6.1]", note="C e V inalterados"),
    vbin("FM-02.mul", "FM-02", "v_fm02_mul", lambda x, y, ap: (arm.u32(x * y), apsr_out(ap)),
         ins("mul.w r2, r2, r3", 32), source=f"{SRC}[§A7.7.84]"),
    _acc("FM-02.mla", "FM-02", "v_fm02_mla", lambda x, y, a: arm.u32(a + x * y),
         ins("mla r2, r2, r3, r4", 32), f"{SRC}[§A7.7.74]"),
    _acc("FM-02.mls", "FM-02", "v_fm02_mls", lambda x, y, a: arm.u32(a - x * y),
         ins("mls r2, r2, r3, r4", 32), f"{SRC}[§A7.7.75]"),
    _long("FM-03.umull", "FM-03", "v_fm03_umull", lambda x, y, lo, hi: arm.umull(x, y),
          ins("umull r4, r5, r2, r3", 32), ((0, 0),), FLAGS2, f"{SRC}[§A7.7.204]"),
    _long("FM-03.smull", "FM-03", "v_fm03_smull", lambda x, y, lo, hi: arm.smull(x, y),
          ins("smull r4, r5, r2, r3", 32), ((0, 0),), FLAGS2, f"{SRC}[§A7.7.149]"),
    _long("FM-04.umlal", "FM-04", "v_fm04_umlal", arm.umlal, ins("umlal r4, r5, r2, r3", 32),
          ACC64, ONE_FLAGS, f"{SRC}[§A7.7.203]"),
    _long("FM-04.smlal", "FM-04", "v_fm04_smlal", arm.smlal, ins("smlal r4, r5, r2, r3", 32),
          ACC64, ONE_FLAGS, f"{SRC}[§A7.7.138]"),
]

DERIVED = {"FM-05": {"cases": ("FM-03", "FM-04"), "field": "apsr", "mask": arm.NZCVQ_MASK,
                     "source": "@stmicroelectronics2024[§3.6.2]"}}
