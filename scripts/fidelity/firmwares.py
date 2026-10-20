"""Firmwares finais: preset → id na ABI, plano de casos, oráculo, timeout."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import abi, c1, c2, c3, c4
from .targets import ROOT


@dataclass(frozen=True)
class Firmware:
    name: str                     # preset CMake = build/<name>/firmware.elf
    firmware_id: int              # header.firmware_id gravado pelo firmware
    scenario: str                 # C1..C4 (ordem do plano de trabalho)
    planned_cases: list[int]
    evaluate: Callable            # snapshot → model.RunEval
    timeout_s: float              # limite do host para um run (inclui GDB)
    question: str

    @property
    def elf(self) -> Path:
        return ROOT / "build" / self.name / "firmware.elf"

    def validate(self, snap: abi.Snapshot, nonce: int | None) -> list[str]:
        """Problemas que invalidam o run como INSTRUMENTO (lista vazia = íntegro).

        Divergência funcional é dado científico, não aparece aqui."""
        problems = abi.run_checks(snap, self.firmware_id, nonce, self.planned_cases)
        if snap.header["core_hz"] != 8_000_000:
            problems.append("clock diferente do protocolo HSI 8 MHz")
        problems += [f"caso {c.case_id:#x}: {c.status}" for c in snap.cases if c.status != "OK"]
        problems += self.evaluate(snap).problems
        return problems


FIRMWARES = {
    # C1: substituído pelo pacote scripts/c1 (presets c1-func, c1-layout, c1-cycle).
    "c2": Firmware(
        "c2", 0x0201, "C2", c2.PLANNED, c2.evaluate, 120,
        "contagem, update, flags e IRQ de TIM2/TIM3/TIM1 sob perfis APB"),
    "c3": Firmware(
        "c3", 0x0301, "C3", c3.PLANNED, c3.evaluate, 60,
        "arbitragem, preempção, máscaras, encadeamento e repetição no NVIC"),
    "c4": Firmware(
        "c4", 0x0401, "C4", c4.PLANNED, c4.evaluate, 120,
        "integridade, quadro, baud, flags e sobrecarga da USART1 em loopback"),
}
