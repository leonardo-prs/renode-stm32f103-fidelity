"""Gate estático dos ELFs finais (antes de qualquer campanha).

Prova, no binário (não no nome das funções), que o que se mede é o que se
pretende medir: corpo dos kernels, bracket de medição, posição flash/SRAM,
orçamento de RAM, tamanho do snapshot e isolamento do loopback PA9→PA10.
"""
from __future__ import annotations

import re
import subprocess

from . import abi, firmware
from .firmware import ROOT

RAM_BYTES = 20 * 1024
STACK_HEAP = 0x400 + 0x200          # vendor/STM32F103XX_FLASH.ld
USART1_BASE = 0x40013800
INSN = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{4}(?: [0-9a-f]{4})?)\s+(\S+)\s*(.*)$")


def objdump(elf, symbol=None) -> str:
    argv = ["arm-none-eabi-objdump", "-d", str(elf)]
    if symbol:
        argv.append(f"--disassemble={symbol}")
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout


def insns(text: str):
    out = []
    for line in text.splitlines():
        m = INSN.match(line)
        if m and not m[3].startswith("."):
            out.append((int(m[1], 16), m[3], m[4]))
    return out


def symbols(elf) -> dict[str, tuple[int, int]]:
    out = {}
    text = subprocess.run(["arm-none-eabi-nm", "-S", str(elf)], capture_output=True, text=True).stdout
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4:
            out[parts[3]] = (int(parts[0], 16), int(parts[1], 16))
    return out


def loop_body(elf, fn: str) -> int | None:
    """Nº de instruções no laço (alvo do desvio para trás até SUBS/LDR de teste)."""
    code = insns(objdump(elf, fn))
    for i, (addr, op, args) in enumerate(code):
        m = re.match(r"([0-9a-f]+)", args)
        if op.startswith(("bne", "beq")) and m and int(m[1], 16) < addr:
            target = int(m[1], 16)
            start = next(j for j, c in enumerate(code) if c[0] == target)
            return i - start + 1      # inclui o desvio
    return None


def first_load_offset(elf, fn: str, reg_offset: str) -> int | None:
    """Instruções antes do 1º LDR com deslocamento `reg_offset` (ex. '#36')."""
    for i, (_, op, args) in enumerate(insns(objdump(elf, fn))):
        if op.startswith("ldr") and args.split("@")[0].rstrip().endswith(f"{reg_offset}]"):
            return i
    return None


def ram_used(elf) -> int:
    text = subprocess.run(["arm-none-eabi-size", "-A", str(elf)], capture_output=True, text=True).stdout
    total = 0
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in (".data", ".bss") and parts[2].isdigit():
            total += int(parts[1])
    return total


def check(name: str) -> list[dict]:
    fw = firmware.get(name)
    elf = fw.elf
    res = []

    def add(item, ok, detail):
        res.append({"firmware": name, "check": item, "ok": bool(ok), "detail": detail})

    if not elf.is_file():
        add("ELF existe", False, str(elf))
        return res
    syms = symbols(elf)
    used = ram_used(elf) + STACK_HEAP
    add("RAM estática + pilha/heap ≤ 20 KiB", used <= RAM_BYTES, f"{used} B")
    snap = syms.get("fidelity_snapshot")
    if snap:
        size = snap[1]
        rows = (size - 128 - 3 * 16 * 0) // 32
        ok = any(size == abi.expected_size(r, t) for r in (128, 200, 384) for t in (32, 48, 128))
        add("tamanho do snapshot coerente com a ABI v2", ok, f"{size} B")
    add("fidelity_complete presente", "fidelity_complete" in syms, "")
    dis = objdump(elf)
    usart = f"{USART1_BASE:08x}" in dis.replace("0x", "")
    if fw.scenario == 3:
        add("USART1 referenciada (S3)", usart, "")
    else:
        add("USART1 NÃO referenciada (loopback físico PA9→PA10 intocado)", not usart, "")
    if "fidelity_measure" in syms:
        code = [c[1] for c in insns(objdump(elf, "fidelity_measure"))]
        shape = "ldr" in code and "blx" in code and code.index("blx") > 0 and \
            code[code.index("blx") - 1] == "ldr" and code[code.index("blx") + 1] == "ldr"
        add("bracket fidelity_measure = LDR CYCCNT · BLX · LDR CYCCNT", shape, " ".join(code))
    if name == "s1a":
        for k, kname in firmware.S1A_KERNELS.items():
            fn = f"s1k_{kname}"
            body = loop_body(elf, fn)
            want = 2 if kname == "loop" else 18
            add(f"{fn}: laço = {want} instruções (16 da classe + SUBS + BNE)", body == want, f"{body}")
            addr = syms.get(fn, (0, 0))[0]
            in_ram = 0x20000000 <= addr < 0x20005000
            add(f"{fn}: {'SRAM' if kname.endswith('_ram') else 'flash'}",
                in_ram == kname.endswith("_ram"), f"0x{addr:08x}")
    if name == "s2a":
        for fn in ("s2_spin_alu", "s2_spin_div", "s2_spin_ldm"):
            body = loop_body(elf, fn)
            add(f"{fn}: laço = 14 instruções (contador 3 + corpo 8 + teste 3)", body == 14, f"{body}")
        n = first_load_offset(elf, "TIM2_IRQHandler", "#36")
        add("TIM2_IRQHandler: instruções antes de ler TIM2->CNT (offset fixo)", n is not None, f"{n}")
    if name == "s4b":
        for fn in ("TIM1_UP_IRQHandler", "TIM1_CC_IRQHandler"):
            n = first_load_offset(elf, fn, "#36")
            add(f"{fn}: instruções antes de ler TIM1->CNT", n is not None, f"{n}")
    return res


def main(args) -> int:
    names = args.firmware or list(firmware.FIRMWARES)
    rows = []
    for name in names:
        rows += check(name)
    width = max(len(r["check"]) for r in rows)
    bad = 0
    for r in rows:
        bad += not r["ok"]
        print(f"[{'ok' if r['ok'] else 'FALHA'}] {r['firmware']:4s} {r['check']:<{width}}  {r['detail']}")
    if args.out:
        lines = ["# Gate estático dos ELFs finais", "", "| firmware | verificação | ok | detalhe |", "|---|---|---|---|"]
        lines += [f"| {r['firmware']} | {r['check']} | {'sim' if r['ok'] else '**NÃO**'} | `{r['detail']}` |" for r in rows]
        args.out.write_text("\n".join(lines) + "\n")
    print(f"gate: {len(rows) - bad}/{len(rows)} ok")
    return 1 if bad else 0
