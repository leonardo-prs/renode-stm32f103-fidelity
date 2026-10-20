"""FB — manipulação de bits (src/c1/func/fb.S)."""
from __future__ import annotations

from .. import arm
from ..vectors import V32
from .common import apsr_out, ins, vbin, vun

SRC = "@armlimited2021"
FB2 = tuple(sorted(set(V32) | {0x1122_3344, 0x0000_80FF, 0x1234_5678}))
FB3 = tuple(sorted(set(V32) | {0x80, 0x7F, 0x8000, 0x7FFF}))
FB4 = tuple(sorted(set(V32) | {0xF000_0000, 0x80}))
FIELDS = ((0, 1), (0, 8), (0, 32), (4, 8), (28, 4), (31, 1))


def keep(fn):
    return lambda x, ap: (fn(x), apsr_out(ap))


FORMS = [
    vun("FB-01.clz", "FB-01", "v_fb01_clz", keep(arm.clz), ins("clz r2, r3", 32),
        a=tuple(sorted({0} | {1 << k for k in range(32)} | set(V32))), source=f"{SRC}[§A7.7.24]"),
    vun("FB-02.rbit", "FB-02", "v_fb02_rbit", keep(arm.rbit), ins("rbit r2, r3", 32), a=FB2,
        source=f"{SRC}[§A7.7.112]"),
]
for op, fn, sec in (("rev", arm.rev, "§A7.7.113"), ("rev16", arm.rev16, "§A7.7.114"),
                    ("revsh", arm.revsh, "§A7.7.115")):
    FORMS += [vun(f"FB-02.{op}.t1", "FB-02", f"v_fb02_{op}_t1", keep(fn), ins(f"{op} r2, r3", 16),
                  a=FB2, source=f"{SRC}[{sec}]"),
              vun(f"FB-02.{op}.t2", "FB-02", f"v_fb02_{op}_t2", keep(fn), ins(f"{op}.w r2, r3", 32),
                  a=FB2, source=f"{SRC}[{sec}]")]

EXT = {"sxtb": (8, True, "§A7.7.182"), "sxth": (16, True, "§A7.7.184"),
       "uxtb": (8, False, "§A7.7.221"), "uxth": (16, False, "§A7.7.223")}
for op, (bits, signed, sec) in EXT.items():
    def ext(rot, bits=bits, signed=signed):
        def f(x):
            v = arm.ror(x, rot) & ((1 << bits) - 1)
            return arm.sign_extend(v, bits) if signed else v
        return f
    FORMS.append(vun(f"FB-03.{op}.t1", "FB-03", f"v_fb03_{op}_t1", keep(ext(0)),
                     ins(f"{op} r2, r3", 16), a=FB3, source=f"{SRC}[{sec}]"))
    for rot in (0, 8, 16, 24):
        text = f"{op}.w r2, r3" + (f", ror #{rot}" if rot else "")
        FORMS.append(vun(f"FB-03.{op}.t2.{rot}", "FB-03", f"v_fb03_{op}_t2_{rot}", keep(ext(rot)),
                         ins(text, 32), a=FB3, source=f"{SRC}[{sec}]"))

for lsb, w in FIELDS:
    FORMS += [
        vun(f"FB-04.ubfx.{lsb}.{w}", "FB-04", f"v_fb04_ubfx_{lsb}_{w}",
            keep(lambda x, lsb=lsb, w=w: arm.ubfx(x, lsb, w)), ins(f"ubfx r2, r3, #{lsb}, #{w}", 32),
            a=FB4, source=f"{SRC}[§A7.7.193]"),
        vun(f"FB-04.sbfx.{lsb}.{w}", "FB-04", f"v_fb04_sbfx_{lsb}_{w}",
            keep(lambda x, lsb=lsb, w=w: arm.sbfx(x, lsb, w)), ins(f"sbfx r2, r3, #{lsb}, #{w}", 32),
            a=FB4, source=f"{SRC}[§A7.7.126]"),
        vbin(f"FB-05.bfi.{lsb}.{w}", "FB-05", f"v_fb05_bfi_{lsb}_{w}",
             lambda d, s, ap, lsb=lsb, w=w: (arm.bfi(d, s, lsb, w), apsr_out(ap)),
             ins(f"bfi r2, r3, #{lsb}, #{w}", 32), a=(0x0000_0000, 0xFFFF_FFFF), b=V32,
             source=f"{SRC}[§A7.7.14]"),
        vun(f"FB-05.bfc.{lsb}.{w}", "FB-05", f"v_fb05_bfc_{lsb}_{w}",
            keep(lambda x, lsb=lsb, w=w: arm.bfc(x, lsb, w)), ins(f"bfc r2, #{lsb}, #{w}", 32),
            a=tuple(sorted(set(V32) | {0xFFFF_FFFF})), source=f"{SRC}[§A7.7.13]"),
    ]

DERIVED = {"FB-06": {"cases": ("FB-01", "FB-02", "FB-03", "FB-04", "FB-05"), "field": "apsr",
                     "mask": arm.NZCVQ_MASK, "source": "@stmicroelectronics2024[§3.8]"}}
