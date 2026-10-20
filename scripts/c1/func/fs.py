"""FS — deslocamentos e rotações (src/c1/func/fs.S)."""
from __future__ import annotations

from .. import arm
from ..vectors import SH
from .common import apsr_out, carry, ins, logical, vbin, vun

SRC = "@armlimited2021"
SEC = {"lsl": "§A7.7.67–68", "lsr": "§A7.7.69–70", "asr": "§A7.7.10–11", "ror": "§A7.7.116–117"}
FS3_VALUES = (0x8000_0001, 0x7FFF_FFFF, 0xAAAA_AAAA, 0x0000_0001)
FLAGS_VARIED = (0x0000_0000, 0x5000_0000, 0xA800_0000, 0xF800_0000)


def _imm(srtype, n):
    def f(x, ap):
        r, c = arm.shift_c(x, srtype, n, carry(ap))
        return r, logical(ap, r, c)
    return f


def _reg(srtype, setflags=True):
    def f(x, y, ap):
        r, c = arm.shift_by_register_c(x, srtype, y, carry(ap))
        return r, (logical(ap, r, c) if setflags else apsr_out(ap))
    return f


FORMS = []
for op, kind, amounts in (("lsls", "LSL", (1, 31)), ("lsrs", "LSR", (1, 31, 32)),
                          ("asrs", "ASR", (1, 31, 32))):
    for n in amounts:
        FORMS += [
            vun(f"FS-01.{op}.t1.{n}", "FS-01", f"v_fs01_{op}_t1_{n}", _imm(kind, n),
                ins(f"{op} r2, r3, #{n}", 16), source=f"{SRC}[{SEC[op[:3]]}, §A7.4.2]"),
            vun(f"FS-01.{op}.t2.{n}", "FS-01", f"v_fs01_{op}_t2_{n}", _imm(kind, n),
                ins(f"movs.w r2, r3, {op[:3]} #{n}", 32), source=f"{SRC}[{SEC[op[:3]]}, §A7.4.2]",
                note="o objdump imprime a forma canônica MOVS.W com deslocamento"),
        ]
for n in (1, 31):
    FORMS.append(vun(f"FS-01.rors.t2.{n}", "FS-01", f"v_fs01_rors_t2_{n}", _imm("ROR", n),
                     ins(f"movs.w r2, r3, ror #{n}", 32), source=f"{SRC}[{SEC['ror']}]"))

FORMS.append(vun("FS-02.rrxs", "FS-02", "v_fs02_rrxs", _imm("RRX", 1), ins("movs.w r2, r3, rrx", 32),
                 source=f"{SRC}[§A2.2.1, §A7.7.118]"))

for op, kind in (("lsls", "LSL"), ("lsrs", "LSR"), ("asrs", "ASR"), ("rors", "ROR")):
    FORMS += [
        vbin(f"FS-03.{op}.t1", "FS-03", f"v_fs03_{op}_t1", _reg(kind), ins(f"{op} r2, r3", 16),
             a=FS3_VALUES, b=SH, source=f"{SRC}[{SEC[op[:3]]}]"),
        vbin(f"FS-03.{op}.t2", "FS-03", f"v_fs03_{op}_t2", _reg(kind),
             ins(f"{op}.w r2, r2, r3", 32), a=FS3_VALUES, b=SH, source=f"{SRC}[{SEC[op[:3]]}]"),
    ]
for op, kind in (("lsl", "LSL"), ("lsr", "LSR"), ("asr", "ASR"), ("ror", "ROR")):
    FORMS.append(vbin(f"FS-05.{op}", "FS-05", f"v_fs05_{op}", _reg(kind, setflags=False),
                      ins(f"{op}.w r2, r2, r3", 32), a=(0x8000_0001,), b=SH, flags=FLAGS_VARIED,
                      source=f"{SRC}[{SEC[op]}]"))

# FS-04: deslocamento por 0 (byte baixo de Rm nulo, inclusive 256) preserva C;
# verificado nos vetores de FS-03 com Rm & 0xFF == 0.
DERIVED = {"FS-04": {"cases": ("FS-03",), "field": "apsr", "mask": 1 << arm.C_BIT,
                     "where": lambda inputs: inputs[1] & 0xFF == 0,
                     "source": "@stmicroelectronics2024[§3.3.4]"}}
