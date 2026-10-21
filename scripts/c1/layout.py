"""Catálogo do preset c1-layout (src/c1/layout): FID-* e LAY-*.

Cada ITEM é um registro produzido pelo main.c do layout, na ordem desta
lista. O oráculo usa as mesmas convenções do catálogo funcional (valores,
máscaras, símbolos do ELF, Alt para conflito documental; None = classe C:
a placa é o oráculo e o Renode é comparado com ela).
"""
from __future__ import annotations

from .catalog import F_FAULT, Alt, Form
from .func.common import EXC_HANDLER, HFSR_FORCED, INVSTATE, IPSR_HARD, IPSR_USAGE, fault
from .vectors import rows

ONE = (rows((0,)),)
PROBE = ("value", "faulted", "cfsr", "bfar")
NO_APSR = 0x0700_FFFF


def item(name, outs, oracle, *, batch=0, klass="B", level="N2", source="", note="", flags=0):
    form = Form(name, name.split(".")[0].replace("R", "") if name.endswith("R") else name.split(".")[0],
                name.lower().replace("-", "_").replace(".", "_"), ONE, tuple(outs),
                lambda vec: oracle(), (), flags=flags, level=level, klass=klass, source=source, note=note)
    form.batch = batch
    return form


def probes(prefix, n):
    return tuple(f"{prefix}{k}_{f}" for k in range(n) for f in PROBE)


FID02 = ("pfr0", "pfr1", "dfr0", "afr0", "mmfr0", "mmfr1", "mmfr2", "mmfr3",
         "isar0", "isar1", "isar2", "isar3", "isar4")
FID02_TRM = (0x30, 0x200, 0x0010_0000, 0, 0x30, 0, 0, 0,
             0x0114_1110, 0x0211_1000, 0x2111_2231, 0x0111_1110, 0x0131_0102)
FID03 = ("vtor", "aircr", "scr", "ccr", "shpr1", "shpr2", "shpr3", "shcsr", "cfsr", "hfsr")
FID04 = ("lr", "sp", "control", "primask", "faultmask", "basepri", "ipsr")
LAY03 = ("isr_vector", "sidata", "sdata", "edata", "sbss", "ebss", "siramfunc", "sramfunc",
         "eramfunc", "snoinit", "enoinit", "estack")
LAY03_SYMS = ("c1_vectors", "_sidata", "_sdata", "_edata", "_sbss", "_ebss", "_siramfunc",
              "_sramfunc", "_eramfunc", "_snoinit", "_enoinit", "_estack")
LAY04 = ("d8", "d16", "d32", "s_a", "s_b", "s_c", "bss_nonzero")
LAY04_EXP = {"d8": 0xA5, "d16": 0xBEEF, "d32": 0x1234_5678, "s_a": 0x11, "s_b": 0x2233_4455,
             "s_c": 0x6677, "bss_nonzero": 0}
VTOR_IN = (0xFFFF_FF80, 0x0800_0280, 0x4000_0000, 0x2000_0200, 0)


def _vtor(value):
    trm, pm = value & 0x3FFF_FF80, value & 0x3FFF_FE00
    if trm == pm:
        return trm
    return Alt((trm, pm), ("TRM r1p1 Tab. 8-15: TBLOFF[29:7]", "PM0056 §4.4.4: TBLOFF[29:9]"))


def _lay08(ipsr, hfsr):
    return {"marker": 0x5AFE, **fault(INVSTATE, "lay_svc_sram", hfsr=hfsr, ipsr=ipsr,
                                      exc_return=EXC_HANDLER, xpsr=(11, NO_APSR))}


ITEMS = [
    item("FID-01", ("cpuid",), lambda: {"cpuid": 0x411F_C231},
         source="@armlimited2007[Tab. 3-1] @stmicroelectronics2024[§4.4.2]", note="r1p1"),
    item("FID-02", FID02, lambda: dict(zip(FID02, FID02_TRM)), level="N3",
         source="@armlimited2007[Tab. 3-1] @armlimited2026[616516]",
         note="errata 616516: cinco campos diferem da arquitetura, mas é o que a r1p1 lê"),
    item("FID-03", FID03, lambda: {**dict.fromkeys(FID03, 0), "aircr": 0xFA05_0000},
         source="@armlimited2007[Tab. 3-1] @armlimited2021[§B3.2.6] @stmicroelectronics2024[§4.4.7]",
         note="capturados pelo Reset_Handler antes de qualquer escrita"),
    item("FID-04", FID04, lambda: {**dict.fromkeys(FID04, 0), "lr": 0xFFFF_FFFF, "sp": "_estack"},
         klass="A", source="@armlimited2021[§B1.5.5]"),
    item("FID-05", ("mpu_typer", "ictr", "dwt_ctrl"),
         lambda: {"mpu_typer": 0, "ictr": 1, "dwt_ctrl": (0x4000_0000, 0xF000_0000)}, level="N3",
         source="@stmicroelectronics2024[§4.2.5] @armlimited2007[Tab. 8-2, §11.5.1]",
         note="inferências: sem MPU (o datasheet não lista); 43 linhas → INTLINESNUM = 1; NUMCOMP = 4"),
    item("FID-06", probes("fid06_", 4), lambda: {}, klass="C", level="N3",
         source="@stmicroelectronics2021[§30.1.1, §30.2]",
         note="F_SIZE e UID: endereço e formato documentados; o valor é do exemplar"),
    item("FID-07", probes("actlr_", 1), lambda: {}, klass="C", level="N3",
         source="@stmicroelectronics2024[§4.4.1] @yiu2014[§23.11.3] @armlimited2026[616516]",
         note="ACTLR não existe na r1p1: a placa diz o que se lê ali"),
    item("FID-08", ("flash_acr", "rcc_cr", "rcc_cfgr"),
         lambda: {"flash_acr": 0x30, "rcc_cr": (0x83, 0xFFFF_00FF), "rcc_cfgr": 0}, level="N1",
         source="@stmicroelectronics2021[§3.3.3, §7.3.1, §7.3.2]",
         note="precondição de toda a metade temporal: HSI sem PLL, AHB/APB sem divisão, flash com "
              "0 estados de espera e pré-busca ligada (RCC_CR[15:8] = HSICAL, de fábrica). Na placa "
              "é também gate de todo run (abi.clock_checks)"),
    item("LAY-01", ("equal", *probes("w", 2)),
         lambda: {"equal": 64, "w0_value": "_estack", "w0_faulted": 0, "w1_value": "Reset_Handler+1",
                  "w1_faulted": 0},
         source="@stmicroelectronics2021[§3.4] @stmicroelectronics[Fig. 11]",
         note="as 64 primeiras palavras em 0x0 e em 0x08000000"),
    item("LAY-02", ("word0", "word1", "sp_reset"),
         lambda: {"word0": "_estack", "word1": "Reset_Handler+1", "sp_reset": "_estack"}, klass="A",
         level="N1", source="@armlimited2021[§B1.5.5]"),
    item("LAY-03", (*LAY03, "local"), lambda: {**dict(zip(LAY03, LAY03_SYMS)), "local": None},
         level="N1", source="@armlimited2007[Tab. 5-8]",
         note="endereços vistos pelo firmware × tabela de símbolos do ELF; a variável local fica "
              "abaixo de _estack (gravada, conferida na análise)"),
    item("LAY-04", LAY04, lambda: LAY04_EXP, level="N1", source="@armlimited2007[Tab. 5-8]",
         note="1º boot"),
    item("LAY-05", ("result", "pc", "fn"),
         lambda: {"result": 0x1234 * 3 + 1, "pc": "lay_ramfunc_pc+4", "fn": "lay_ramfunc+1"},
         level="N3", source="@stmicroelectronics2024[§2.2.3]", note="código em .ramfunc na SRAM"),
    item("LAY-06", ("marker", "vtor"), lambda: {"marker": 0x5AFE, "vtor": 0x2000_0000},
         source="@yiu2014[§7.5] @armlimited2007[Tab. 8-15]"),
    item("LAY-07", tuple(f"vtor_{v:08x}" for v in VTOR_IN),
         lambda: {f"vtor_{v:08x}": _vtor(v) for v in VTOR_IN},
         source="@armlimited2007[Tab. 8-15] @stmicroelectronics2024[§4.4.4] @armlimited2021[§B3.2.5]",
         note="conflito documental TRM × PM0056: a placa decide"),
    item("LAY-08.a", ("marker",), lambda: _lay08(IPSR_HARD, HFSR_FORCED), flags=F_FAULT, klass="A",
         source="@armlimited2007[§5.1] @armlimited2021[§B1.5.6, §B1.5.14]",
         note="prioridades do reset: a falta não preempta o SVC → HardFault FORCED"),
    item("LAY-08.b", ("marker",), lambda: _lay08(IPSR_USAGE, 0), flags=F_FAULT, klass="A",
         source="@armlimited2007[§5.1] @armlimited2021[§B1.5.6, §B1.5.14]",
         note="SHPR2.PRI_11 = 0x80 → UsageFault INVSTATE"),
    item("LAY-09", probes("hole", 4), lambda: {}, klass="C", level="N3",
         source="@stmicroelectronics2021[§3.2] @stmicroelectronics[Fig. 11]",
         note="0x20005000, 0x08010000, 0x40008000, 0x60000000"),
    item("LAY-04R", LAY04, lambda: LAY04_EXP, batch=1, level="N1",
         source="@armlimited2007[Tab. 5-8] @armlimited2021[§B3.2.6]",
         note=".data e .bss depois de SYSRESETREQ, com .bss sujada antes"),
    item("LAY-10", ("keep0", "keep1", "keep2", "keep3", "keep_magic"),
         lambda: {}, batch=1, klass="C", level="N3", source="@stmicroelectronics2021[§3.4]",
         note="o RM0008 não define a SRAM depois de um reset de sistema: a placa é o oráculo"),
]
for _f in ITEMS:
    _f.check()
