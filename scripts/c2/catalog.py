"""Catálogo do C2 #oD — fonte única do firmware (via gen) e do oráculo (analysis).

Tudo o que o firmware e o host precisam concordar está aqui: o bloco de
parâmetros que o monitor grava antes da partida, os identificadores de caso
e de fase dos pontos marcados, o leiaute dos registros que o firmware grava
e as linhas de interrupção usadas como estímulo por software.

Referências: 04-c2.typ (casos), 03-quadro-comum.typ §Instrumentos e §Regras
de projeto; ARM ARM = armlimited2021; RM0008 = stmicroelectronics2021.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

# ───────────────────────── ABI host ↔ firmware ─────────────────────────
# c2_param fica em .noinit: o Reset_Handler não o zera, e o monitor o grava
# depois do LoadELF e antes da partida (simulação parada).
MAGIC = 0xC20D0001          # muda quando o leiaute de c2_param/c2_rec muda
MAX_POINTS = 64             # pontos por execução
N_ARGS = 4                  # palavras de argumento por ponto
N_REC = 8                   # palavras de registro (visão do firmware) por ponto
N_IRQ = 43                  # IRQ0..IRQ42 da família medium-density (RM0008 Tab. 63)

# Estados de fim de execução gravados em c2_status (único escritor: main).
ST_RUNNING, ST_DONE, ST_BAD_PARAM = 0, 1, 2

# Identificadores de caso: o número do caso na fundamentação.
CASES = {"C2-09": 9}

# ───────────────────────── linhas de estímulo ─────────────────────────
# "Escrita no STIR ou no ISPR de linhas sem periférico" (04-c2.typ, tabela de
# estímulos). Linhas IRQ da família medium-density (RM0008 Tab. 63) às quais
# a plataforma do projeto (renode/stm32f103_hsi8.repl) não liga nenhuma
# fonte, e cujo periférico, no chip, fica sem relógio ou sem configuração
# (nenhum firmware do C2 os liga). Cobrem os dois registradores de 32 linhas
# do NVIC (ISER0/ISPR0 e ISER1/ISPR1), inclusive a primeira e a última linha.
FREE_LINES = {
    0: "WWDG", 1: "PVD", 2: "TAMPER", 3: "RTC", 4: "FLASH", 5: "RCC",
    18: "ADC1_2", 19: "USB_HP_CAN_TX", 20: "USB_LP_CAN_RX0", 21: "CAN_RX1",
    22: "CAN_SCE", 35: "SPI1", 36: "SPI2", 41: "RTCAlarm", 42: "USBWakeUp",
}

# Mecanismo do pedido por software (ARM ARM §B3.4.1, §B3.4.6).
MECH = {"STIR": 1, "ISPR": 2}

# ───────────────────────── C2-09 ─────────────────────────
# Fases (ponto marcado c2_point(id), id = índice do ponto << 8 | fase).
C2_09_PHASES = {"ARMED": 1, "PENDING": 2, "SERVED": 3}
C2_09_PRIO = 8              # campo de prioridade (NVIC_SetPriority) → byte 0x80
C2_09_WINDOW = 32           # voltas de NOP entre o pedido/habilitação e o ponto seguinte
# Registro do firmware por ponto (c2_rec[i][k]).
C2_09_REC = ("pend_armed", "served_armed", "pend_pending", "served_pending",
             "pend_served", "served_served")

POINT_SHIFT = 8


@dataclass(frozen=True)
class Point:
    """Um ponto de um caso: argumentos gravados em c2_param.arg[i]."""
    index: int
    line: int
    mech: str

    @property
    def args(self) -> tuple[int, int, int, int]:
        return (self.line, MECH[self.mech], 0, 0)

    @property
    def label(self) -> str:
        return f"IRQ{self.line} ({FREE_LINES[self.line]}) via {self.mech}"


def c2_09_points() -> list[Point]:
    """Varredura completa do C2-09: todas as linhas livres × os dois mecanismos."""
    pts = [(line, mech) for line in sorted(FREE_LINES) for mech in MECH]
    return [Point(i, line, mech) for i, (line, mech) in enumerate(pts)]


# Oráculo do C2-09 (ARM ARM §B3.4.1): estado do NVIC da linha em cada fase,
# visto de fora (ganchos) e pelo firmware, e atendimentos em cada janela.
#   ARMED   desabilitada, não pendente, não ativa (estado inicial do ponto)
#   PENDING pedido feito com a linha desabilitada: pendente, não atendida
#   SERVED  depois de habilitar: atendida exatamente uma vez; pendência zerada
C2_09_EXPECT = {
    "ARMED":   {"enabled": 0, "pending": 0, "active": 0, "served": 0},
    "PENDING": {"enabled": 0, "pending": 1, "active": 0, "served": 0},
    "SERVED":  {"enabled": 1, "pending": 0, "active": 0, "served": 1},
}

CASE_POINTS = {"C2-09": c2_09_points}


def catalog_hash() -> str:
    """Hash do conteúdo do catálogo (vai para o header e para o plano)."""
    blob = json.dumps({"magic": MAGIC, "max": MAX_POINTS, "args": N_ARGS, "rec": N_REC,
                       "cases": CASES, "lines": FREE_LINES, "mech": MECH,
                       "c2_09": [asdict(p) for p in c2_09_points()],
                       "c2_09_phases": C2_09_PHASES, "c2_09_prio": C2_09_PRIO,
                       "c2_09_window": C2_09_WINDOW, "c2_09_expect": C2_09_EXPECT},
                      sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def check() -> None:
    for name, fn in CASE_POINTS.items():
        pts = fn()
        assert 0 < len(pts) <= MAX_POINTS, name
        assert [p.index for p in pts] == list(range(len(pts))), name
    assert all(0 <= n < N_IRQ for n in FREE_LINES)
    assert len(C2_09_REC) <= N_REC
    assert len(c2_09_points()) << POINT_SHIFT < 1 << 16


check()
