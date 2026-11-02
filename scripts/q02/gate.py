"""Gate estático do ELF do Q-02: o binário só usa núcleo, SRAM e SCS, e os
pontos de observação são os que a análise supõe.

  - tabela de vetores: MSP inicial, Reset_Handler, PendSV_Handler e
    SysTick_Handler; toda outra exceção e linha → q02_fault;
  - VTOR gravado explicitamente (main referencia SCB e q02_vectors);
  - nenhum literal na faixa de periféricos do chip (0x40000000–0x5FFFFFFF)
    nem de bit-band da SRAM: o Q-02 não depende de modelo de periférico;
  - q02_magic em .noinit; tamanho de q02_rec = o da especificação;
  - q02_point e q02_trigger são só `bx lr` e chamadas por BL;
  - q02_store é uma única escrita de palavra seguida de `bx lr` (é a única
    instrução que escreve nos endereços vigiados);
  - q02_wait tem leituras de memória (as de q02_mbox) e nenhuma escrita;
  - sem exclusivos nem BKPT.
"""
from __future__ import annotations

from obs.elf import Elf

from . import spec

THUMB = 1
SCB_BASE = 0xE000ED00
PERIPH = (0x40000000, 0x60000000)
BITBAND_SRAM = (0x22000000, 0x24000000)
FORBIDDEN = ("ldrex", "strex", "clrex", "bkpt")
NEED = ("q02_vectors", "Reset_Handler", "PendSV_Handler", "SysTick_Handler", "q02_fault", "q02_done",
        "q02_point", "q02_store", "q02_trigger", "q02_wait", "q02_magic", "q02_sink", "q02_mbox",
        "q02_mbox2", "q02_echo", "q02_rec", "main", "_ebss", "_estack")
N_IRQ = 43


def check(elf: Elf) -> list[str]:
    bad = [f"símbolo {n} ausente" for n in NEED if n not in elf.symbols]
    if bad:
        return bad
    s, w = elf.symbols, elf.words
    want = {0: s["_estack"], 1: s["Reset_Handler"] | THUMB}
    for exc in range(2, 16 + N_IRQ):
        want[exc] = s["q02_fault"] | THUMB
    want[spec.EXC_PENDSV] = s["PendSV_Handler"] | THUMB
    want[spec.EXC_SYSTICK] = s["SysTick_Handler"] | THUMB
    for exc, value in want.items():
        got = w.get(s["q02_vectors"] + 4 * exc)
        if got != value:
            bad.append(f"vetor {exc}: 0x{got or 0:08x}, esperado 0x{value:08x}")

    main_lits = {v for a, v in elf.literals.items() if a in elf.function_range("main")}
    if s["q02_vectors"] not in main_lits or SCB_BASE not in main_lits:
        bad.append("main não grava o VTOR explicitamente (literais de q02_vectors/SCB ausentes)")
    for a, v in elf.literals.items():
        if PERIPH[0] <= v < PERIPH[1] or BITBAND_SRAM[0] <= v < BITBAND_SRAM[1]:
            bad.append(f"literal fora de núcleo/SRAM/SCS em 0x{a:08x}: 0x{v:08x}")

    if s["q02_magic"] < s["_ebss"]:
        bad.append("q02_magic não está em .noinit (seria zerada pelo Reset_Handler)")
    if elf.sizes.get("q02_rec") != 4 * spec.REC_WORDS:
        bad.append(f"q02_rec: {elf.sizes.get('q02_rec')} bytes, especificação {4 * spec.REC_WORDS}")

    def calls(name):
        return sum(1 for i in elf.disasm.values() if i.mnemonic in ("bl", "b.w")
                   and i.operands.startswith(f"{s[name]:x}"))

    for name, n_min in (("q02_point", len(spec.POINT_IDS)), ("q02_trigger", 1)):
        body = [i.mnemonic for i in elf.function_insns(name)]
        if body != ["bx"]:
            bad.append(f"{name} não é só 'bx lr': {body}")
        if calls(name) < n_min:
            bad.append(f"{name} chamada {calls(name)} vezes (esperado >= {n_min})")
    body = elf.function_insns("q02_store")
    if [i.mnemonic for i in body] != ["str", "bx"]:
        bad.append(f"q02_store não é 'str; bx lr': {[i.mnemonic for i in body]}")
    wait = elf.function_range("q02_wait")
    if not any(elf.is_load(a) for a in wait) or any(elf.is_store(a) for a in wait):
        bad.append("q02_wait sem leitura de q02_mbox ou com escrita")

    for i in elf.disasm.values():
        if i.mnemonic.startswith(FORBIDDEN):
            bad.append(f"instrução proibida em 0x{i.addr:08x}: {i.mnemonic}")
    return bad
