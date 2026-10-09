"""Tipos comuns da avaliação de um run.

Cada cenário (c1..c4.py) transforma um snapshot decodificado em:
  - Check  : observável FUNCIONAL comparado por igualdade exata com o
             oráculo da especificação (valor, flag, ordem, contagem);
  - Metric : observável TEMPORAL (ticks) com a previsão da configuração,
             quando existe, e a RESOLUÇÃO do ponto de observação;
  - problems: falhas do instrumento (layout, plano, trace incompleto) que
             invalidam o que depende delas — nunca viram "divergência".
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Check:
    """expected = None: observação SEM oráculo (o manual não especifica);
    entra na comparação placa × Renode, não na conformidade com o manual."""
    case: str             # rótulo estável do caso, ex. "tim2/apb1/psc_preload"
    item: str             # o que foi comparado
    expected: object
    observed: object

    @property
    def ok(self) -> bool:
        return self.expected is None or self.expected == self.observed


@dataclass(frozen=True)
class Metric:
    case: str
    name: str
    value: float          # ticks do DWT (ou outra unidade em `unit`)
    unit: str = "ticks"
    resolution: float = 1.0
    predicted: float | None = None
    resolution_basis: str = "granularidade do contador; não limita o erro instrumental"


@dataclass
class RunEval:
    firmware: str
    checks: list[Check] = field(default_factory=list)
    metrics: list[Metric] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)       # instrumento
    case_status: dict[str, str] = field(default_factory=dict)
    extra: dict = field(default_factory=dict)                # p/ relatório (ex.: sequências)

    def check(self, case: str, item: str, expected, observed) -> None:
        self.checks.append(Check(case, item, expected, observed))

    def metric(self, case: str, name: str, value: float, *, unit: str = "ticks",
               resolution: float = 1.0, predicted: float | None = None) -> None:
        self.metrics.append(Metric(case, name, float(value), unit, resolution,
                                   None if predicted is None else float(predicted),
                                   "estimativa heurística do polling; limite não demonstrado"
                                   if resolution == RES_POLL else
                                   "granularidade do contador; não limita o erro instrumental"))


# Resolução dos pontos de observação (ticks de 8 MHz).
RES_BRACKET = 1.0     # duas leituras do CYCCNT em ordem fixa (C1)
RES_LOG = 1.0         # timestamp do logger (fid_log), mesmo código nos 2 ambientes
RES_POLL = 16.0       # estimativa heurística; NÃO é limite demonstrado de uma volta do laço
