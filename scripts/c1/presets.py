"""Os três firmwares do C1: identificação na ABI e capacidade do snapshot.

As capacidades vêm do orçamento de SRAM (20 KiB): tabela de vetores na SRAM
(512 B), pilha principal (≥ 2 KiB), pilha de processo (512 B), .noinit e
variáveis (< 0,5 KiB); o resto é o snapshot (header + registros + palavras).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Preset:
    name: str
    preset_id: int
    max_records: int
    max_words: int
    question: str

    @property
    def elf(self) -> Path:
        return ROOT / "build" / self.name / "firmware.elf"

    @property
    def snapshot_bytes(self) -> int:
        return 256 + 16 * self.max_records + 4 * self.max_words


PRESETS = {
    "c1-func": Preset("c1-func", 1, 96, 3584,
                      "instruções, memória e exceções síncronas: resultados bit a bit"),
    "c1-layout": Preset("c1-layout", 2, 64, 1024,
                        "estado de reset, identidade e layout de memória"),
    "c1-cycle": Preset("c1-cycle", 3, 64, 2600,
                       "DWT_CYCCNT como régua e custo em ciclos por classe de instrução"),
}
