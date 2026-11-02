"""Gate estático do ELF do c2-od: o binário é o que o catálogo e as regras dizem?

Confere, sem executar (03-quadro-comum.typ §Regras de projeto; padrão do C1):
  - tabela de vetores: MSP inicial, Reset_Handler, linhas livres → c2_irq_handler,
    toda outra exceção → c2_fault (nenhuma fonte inesperada é tratada em silêncio);
  - VTOR gravado explicitamente (main referencia SCB e o endereço de c2_vectors);
  - c2_param em .noinit (o Reset_Handler não o zera);
  - c2_point é chamada, não foi expandida e tem corpo vazio (o gancho lê R0);
  - sem exclusivos (LDREX/STREX/CLREX) nem BKPT; sem literal de bit-band nem
    da USART1 (a USART é objeto do C4, não instrumento; J0 não é usado).
Retorna a lista de problemas (vazia = aprovado).
"""
from __future__ import annotations

from . import catalog as K
from obs.elf import Elf

THUMB = 1
SCB_BASE = 0xE000ED00
BITBAND = ((0x22000000, 0x24000000), (0x42000000, 0x44000000))
USART1 = (0x40013800, 0x40013C00)
FORBIDDEN_MNEMONICS = ("ldrex", "strex", "clrex", "bkpt")
NEED = ("c2_vectors", "Reset_Handler", "c2_irq_handler", "c2_fault", "c2_point", "c2_done",
        "c2_param", "c2_rec", "c2_served", "c2_status", "main", "_ebss", "_estack")


def check(elf: Elf) -> list[str]:
    bad = [f"símbolo {n} ausente" for n in NEED if n not in elf.symbols]
    if bad:
        return bad
    s = elf.symbols
    vt = s["c2_vectors"]
    w = elf.words

    # Tabela de vetores.
    want = {0: s["_estack"], 1: s["Reset_Handler"] | THUMB}
    for exc in range(2, 16):
        want[exc] = s["c2_fault"] | THUMB
    for n in range(K.N_IRQ):
        want[16 + n] = (s["c2_irq_handler"] if n in K.FREE_LINES else s["c2_fault"]) | THUMB
    for exc, value in want.items():
        got = w.get(vt + 4 * exc)
        if got != value:
            bad.append(f"vetor {exc}: 0x{got or 0:08x}, esperado 0x{value:08x}")

    # VTOR explícito: main carrega o endereço da tabela e a base do SCB.
    main_lits = {v for a, v in elf.literals.items() if a in elf.function_range("main")}
    if vt not in main_lits or SCB_BASE not in main_lits:
        bad.append("main não grava o VTOR explicitamente (literais de c2_vectors/SCB ausentes)")

    # ABI host ↔ firmware: os tamanhos batem com o leiaute do catálogo
    # (collect.param_words e o gancho de fim calculam endereços com eles).
    abi = {"c2_param": 16 + 4 * K.MAX_POINTS * K.N_ARGS, "c2_rec": 4 * K.MAX_POINTS * K.N_REC,
           "c2_served": 4 * K.N_IRQ, "c2_status": 4}
    for name, size in abi.items():
        if elf.sizes.get(name) != size:
            bad.append(f"{name}: {elf.sizes.get(name)} bytes, catálogo espera {size}")

    if s["c2_param"] < s["_ebss"]:
        bad.append("c2_param não está em .noinit (seria zerado pelo Reset_Handler)")

    # c2_point: corpo vazio (só o retorno) e chamada por BL nos casos.
    body = elf.function_insns("c2_point")
    if [i.mnemonic for i in body] != ["bx"]:
        bad.append(f"c2_point não é só 'bx lr': {[i.mnemonic for i in body]}")
    calls = [i for i in elf.disasm.values() if i.mnemonic == "bl"
             and i.operands.startswith(f"{s['c2_point']:x}")]
    if len(calls) < len(K.C2_09_PHASES):
        bad.append(f"c2_point chamada {len(calls)} vezes (o C2-09 marca {len(K.C2_09_PHASES)} fases)")

    for i in elf.disasm.values():
        if i.mnemonic.startswith(FORBIDDEN_MNEMONICS):
            bad.append(f"instrução proibida em 0x{i.addr:08x}: {i.mnemonic}")
    for a, v in elf.literals.items():
        if any(lo <= v < hi for lo, hi in BITBAND):
            bad.append(f"literal de bit-band em 0x{a:08x}: 0x{v:08x}")
        if USART1[0] <= v < USART1[1]:
            bad.append(f"literal da USART1 em 0x{a:08x}: 0x{v:08x}")
    return bad
