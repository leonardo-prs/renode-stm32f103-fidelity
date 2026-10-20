"""FEX — acesso exclusivo (src/c1/func/fex.S)."""
from __future__ import annotations

from ..catalog import F_MEM, Form
from ..vectors import rows
from .common import Mem, ins

SRC = "@armlimited2021"
OLD, NEW = 0x1111_1111, 0x2222_2222


def _mem(word: int) -> dict:
    m = Mem()
    m.store(12, word, 4)
    return m.fields()


def _form(case, routine, outs, expected, insns, level="N1", source=f"{SRC}[§A3.4.1, Tab. A3-2]",
          old=OLD, new=NEW):
    return Form(case, case.split(".")[0], routine, (rows((old,)), rows((new,))),
                outs, lambda vec: expected(vec), insns, flags=F_MEM, level=level, source=source)


FORMS = [
    _form("FEX-01", "v_fex01", ("loaded", "status", "mem"),
          lambda v: {"loaded": OLD, "status": 0, "mem": NEW, **_mem(NEW)},
          (ins("ldrex r3, [r2]", 32, 0), ins("strex ip, r4, [r2]", 32, 1))),
    _form("FEX-02", "v_fex02", ("loaded", "status", "mem"),
          lambda v: {"loaded": 0, "status": 1, "mem": OLD, **_mem(OLD)},
          (ins("strex ip, r4, [r2]", 32),)),
    _form("FEX-03", "v_fex03", ("loaded", "status", "mem"),
          lambda v: {"loaded": OLD, "status": 1, "mem": OLD, **_mem(OLD)}, (ins("clrex", 32),)),
    _form("FEX-04", "v_fex04", ("loaded", "status", "mem"),
          lambda v: {"loaded": OLD, "status": 1, "mem": OLD, **_mem(OLD)}, (ins("svc 0", 16),),
          source=f"{SRC}[§A3.4.4] @stmicroelectronics2024[§2.2.7]"),
    _form("FEX-05", "v_fex05", ("loaded", "status1", "status2", "mem"),
          lambda v: {"loaded": OLD, "status1": 0, "status2": 1, "mem": NEW, **_mem(NEW)},
          (ins("strex ip, r4, [r2]", 32),)),
    _form("FEX-06.b", "v_fex06_b", ("loaded", "status", "mem"),
          lambda v: {"loaded": 0xF0, "status": 0, "mem": 0xA5A5_A581, **_mem(0xA5A5_A581)},
          (ins("ldrexb r3, [r2]", 32, 0), ins("strexb ip, r4, [r2]", 32, 1)), level="N2",
          source=f"{SRC}[§A7.7.53, §A7.7.168]", old=0xA5A5_A5F0, new=0x0000_0081),
    _form("FEX-06.h", "v_fex06_h", ("loaded", "status", "mem"),
          lambda v: {"loaded": 0x8001, "status": 0, "mem": 0xA5A5_FFFE, **_mem(0xA5A5_FFFE)},
          (ins("ldrexh r3, [r2]", 32, 0), ins("strexh ip, r4, [r2]", 32, 1)), level="N2",
          source=f"{SRC}[§A7.7.54, §A7.7.169]", old=0xA5A5_8001, new=0x0000_FFFE),
]
