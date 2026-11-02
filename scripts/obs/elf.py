"""Leitura de ELF: símbolos (com tamanho), disassembly e palavras da flash.

Comum aos firmwares observados de fora no Renode (família Q a partir do
Q-02, C2 #oD). Usa só as binutils do toolchain (arm-none-eabi-nm/objdump).
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def elf_path(preset: str) -> Path:
    return ROOT / "build" / preset / "firmware.elf"


class ElfError(RuntimeError):
    pass


@dataclass(frozen=True)
class Insn:
    addr: int
    mnemonic: str          # como o objdump escreve (com sufixos de condição e largura)
    operands: str


@dataclass
class Elf:
    path: Path
    sha256: str
    symbols: dict[str, int]                  # nome → endereço (bit Thumb removido)
    sizes: dict[str, int] = field(default_factory=dict)

    @cached_property
    def disasm(self) -> dict[int, Insn]:
        out = subprocess.run(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", str(self.path)],
                             check=True, capture_output=True, text=True).stdout
        insns = {}
        for line in out.splitlines():
            m = re.match(r"^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$", line)
            if m and not m[2].startswith("."):
                insns[int(m[1], 16)] = Insn(int(m[1], 16), m[2], m[3].split("@")[0].split(";")[0].strip())
        return insns

    @cached_property
    def literals(self) -> dict[int, int]:
        """Palavras de pool de literais (linhas `.word` do objdump -d): endereço → valor."""
        out = subprocess.run(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", str(self.path)],
                             check=True, capture_output=True, text=True).stdout
        lits = {}
        for line in out.splitlines():
            m = re.match(r"^\s*([0-9a-f]+):\s+\.word\s+0x([0-9a-f]+)", line)
            if m:
                lits[int(m[1], 16)] = int(m[2], 16)
        return lits

    @cached_property
    def words(self) -> dict[int, int]:
        """Palavras de 32 bits das seções carregáveis da flash (objdump -s)."""
        out = subprocess.run(["arm-none-eabi-objdump", "-s", "-j", ".isr_vector", "-j", ".text",
                              "-j", ".rodata", str(self.path)], check=True, capture_output=True,
                             text=True).stdout
        data = {}
        for line in out.splitlines():
            m = re.match(r"^ ([0-9a-f]+) ((?:[0-9a-f]{2,8} ){1,4})", line)
            if not m:
                continue
            base = int(m[1], 16)
            for k, w in enumerate(m[2].split()):
                if len(w) == 8:
                    data[base + 4 * k] = int.from_bytes(bytes.fromhex(w), "little")
        return data

    def function_range(self, name: str) -> range:
        a = self.symbols[name]
        return range(a, a + self.sizes.get(name, 2))

    def function_insns(self, name: str) -> list[Insn]:
        r = self.function_range(name)
        return [i for a, i in sorted(self.disasm.items()) if a in r]

    def is_load(self, addr: int) -> bool:
        """Leitura de memória por registrador base (exclui o pool de literais, [pc, #…])."""
        i = self.disasm.get(addr)
        return (i is not None and re.match(r"^ldr(?!ex)", i.mnemonic) is not None
                and "[pc" not in i.operands and "[" in i.operands)

    def is_store(self, addr: int) -> bool:
        i = self.disasm.get(addr)
        return i is not None and re.match(r"^(str|stm|push)", i.mnemonic) is not None


def load(path: Path, need: tuple[str, ...] = ()) -> Elf:
    if not path.is_file():
        raise ElfError(f"ELF ausente: {path}")
    out = subprocess.run(["arm-none-eabi-nm", "-S", str(path)], check=True, capture_output=True,
                         text=True).stdout
    sym, size = {}, {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4:
            sym[parts[3]] = int(parts[0], 16) & ~1
            size[parts[3]] = int(parts[1], 16)
        elif len(parts) == 3:
            sym[parts[2]] = int(parts[0], 16) & ~1
    for n in need:
        if n not in sym:
            raise ElfError(f"símbolo {n} ausente em {path}")
    return Elf(path, hashlib.sha256(path.read_bytes()).hexdigest(), sym, size)
