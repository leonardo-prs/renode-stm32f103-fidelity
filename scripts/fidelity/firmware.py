"""Registro dos firmwares finais (fonte única p/ coletor, análise e relatório).

Cada firmware = (cenário, variante) da ABI v2. As condições espelham os
códigos usados no C; `fields` nomeia v0..v5 das rows dessa condição.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Firmware:
    name: str
    scenario: int
    variant: int
    title: str
    conditions: dict[int, str]
    fields: dict[int, tuple[str, ...]] = field(default_factory=dict)
    uart_loopback: bool = False      # Renode: UARTHub com loopback no usart1
    timeout_s: float = 30.0          # limite de wall-clock de UMA execução
    elf_override: Path | None = None # build de diagnóstico (FINAL_DEFS)

    @property
    def elf(self) -> Path:
        return self.elf_override or ROOT / "build" / self.name / "firmware.elf"

    def field_names(self, condition: int) -> tuple[str, ...]:
        names = self.fields.get(condition) or self.fields.get(-1) or ()
        return tuple(names) + tuple(f"v{i}" for i in range(len(names), 6))


S1A_KERNELS = {
    1: "loop", 2: "alu", 3: "mul", 4: "udiv_fast", 5: "udiv_slow", 6: "ldr",
    7: "ldr_dep", 8: "str", 9: "ldr_flash", 10: "branch", 11: "ldm", 12: "mix",
    13: "alu_ram", 14: "ldr_ram",
}

FIRMWARES: dict[str, Firmware] = {}


def _register(fw: Firmware) -> Firmware:
    FIRMWARES[fw.name] = fw
    return fw


_register(Firmware(
    "s1a", 1, 1, "S1A — custo por classe de instrução",
    {0: "context", **S1A_KERNELS},
    {0: ("w0", "w1", "w2", "w3", "w4", "w5"), -1: ("iterations", "ticks", "signature")},
))


def get(name: str) -> Firmware:
    try:
        return FIRMWARES[name]
    except KeyError:
        raise SystemExit(f"firmware desconhecido: {name} (conhecidos: {', '.join(FIRMWARES)})")
