"""FBB — bit-band (src/c1/func/fbb.S). Classe B, nível N3."""
from __future__ import annotations

from .. import arm
from ..catalog import F_FAULT, F_MEM, Form
from ..vectors import rows, table
from .common import Mem, ins, no_fault

SRC = "@armlimited2007[§4.2.1]"
BIT1 = (0x0000_0001, 0x0000_00FF, 0xFFFF_FFFF)      # bit 0 = 1
BIT0 = (0x0000_0000, 0x0000_000E, 0xFFFF_FFFE)      # bit 0 = 0


def _fbb01(vec):
    init, bit, value = vec
    m = Mem()
    byte = (init | (1 << bit)) if value & 1 else (init & ~(1 << bit))
    m.b[13] = byte
    return {"byte": byte, **m.fields(), **no_fault("v_fbb01_land")}


FORMS = [
    Form("FBB-01", "FBB-01", "v_fbb01", (rows((0x00, 0xFF)), rows((0, 3, 7)), rows(BIT1 + BIT0)),
         ("byte",), _fbb01, (ins("str r3, [r4, #0]", 16),), flags=F_MEM | F_FAULT, level="N3",
         klass="B", source=SRC, note="só o bit-alvo muda; vizinhos intactos"),
    Form("FBB-02", "FBB-02", "v_fbb02", (rows((0x00, 0xFF, 0x5A)), rows(tuple(range(8)))), ("value",),
         lambda vec: {"value": (vec[0] >> vec[1]) & 1, **no_fault("v_fbb02_land")},
         (ins("ldr r3, [r4, #0]", 16),), flags=F_FAULT, level="N3", klass="B", source=SRC),
]

_FBB3 = ((0x2000_0300, 2), (0x2000_0000, 0), (0x2000_4FFF, 7))
FORMS.append(Form(
    "FBB-03", "FBB-03", "v_fbb03", (table(*[(a, arm.bitband_alias(a, b)) for a, b in _FBB3]),),
    ("set", "clear"),
    lambda vec: {"set": 0x5A | (1 << _bit(vec)), "clear": 0x5A & ~(1 << _bit(vec)),
                 **no_fault("v_fbb03_land")},
    (ins("str r3, [r4, #0]", 16, 0), ins("str r3, [r4, #0]", 16, 1)), flags=F_FAULT, level="N3",
    klass="B", source="@stmicroelectronics2021[§3.3.2]",
    note="0x22006008 ↔ bit 2 de 0x20000300 (exemplo do RM0008) e os extremos da SRAM"))


def _bit(vec) -> int:
    addr, alias = vec
    return ((alias - 0x2200_0000) - (addr - 0x2000_0000) * 32) // 4


FORMS += [
    Form("FBB-04", "FBB-04", "v_fbb04", (rows((0,)),), ("apb2_set", "odr_set", "odr_clear", "apb2_clear"),
         lambda vec: {"apb2_set": (0x08, 0x08), "odr_set": (0x20, 0x20), "odr_clear": (0, 0x20),
                      "apb2_clear": (0, 0x08), **no_fault("v_fbb04_land")},
         (ins("str r3, [r2, #0]", 16, 0), ins("str r3, [r6, #0]", 16, 1)), flags=F_FAULT, level="N3",
         klass="B", source="@stmicroelectronics2021[§3.3.2, §7.3.7] @armlimited2007[§4.2]",
         note="compara só IOPBEN e ODR[5]; os demais bits são gravados (ex.: PB4/NJTRST sai do "
              "reset como entrada com pull-up, ODR[4] = 1)"),
    Form("FBB-05", "FBB-05", "v_fbb05", (rows((0x1122_3344, 0xFFFF_FFFF, 0)),), ("value",),
         lambda vec: {"value": vec[0]}, (ins("str r3, [r2, #0]", 16),), level="N3", klass="B",
         source="@armlimited2007[§4.2.2]", note="a região de bit-band é SRAM comum"),
]
