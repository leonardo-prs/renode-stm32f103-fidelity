"""Avaliação de um run funcional: snapshot → vetores com oráculo.

Para cada registro do snapshot (um trecho de uma forma), reconstrói as
entradas de cada vetor pela mesma ordem do firmware, aplica o oráculo e
compara campo a campo, sob a máscara declarada. O resultado é uma lista de
`VectorResult`, a unidade de comparação entre ambientes na análise.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import abi
from .catalog import Batch, Form


@dataclass(frozen=True)
class VectorResult:
    form: str
    index: int                 # índice do vetor na forma
    inputs: tuple[int, ...]
    observed: tuple[int, ...]  # todas as palavras gravadas
    expected: tuple            # por campo: int | None | (valor, máscara)

    def field_ok(self, k: int) -> bool | None:
        exp = self.expected[k]
        if exp is None:
            return None
        value, mask = exp if isinstance(exp, tuple) else (exp, 0xFFFF_FFFF)
        return (self.observed[k] & mask) == (value & mask)

    @property
    def ok(self) -> bool:
        return all(self.field_ok(k) is not False for k in range(len(self.observed)))


def expected_fields(form: Form, inputs) -> tuple:
    exp = form.oracle(inputs)
    unknown = set(exp) - set(form.fields)
    if unknown:
        raise ValueError(f"{form.name}: oráculo devolveu campos inexistentes {unknown}")
    return tuple(exp.get(name) for name in form.fields)


def functional(snap: abi.Snapshot, forms: list[Form], batch: Batch, trace: bool = False
               ) -> tuple[list[VectorResult], list[str]]:
    """(vetores, problemas de instrumento) de um run do c1-func."""
    problems = []
    results: list[VectorResult] = []
    if len(snap.records) != len(batch.entries):
        problems.append(f"{len(snap.records)} registros para {len(batch.entries)} entradas do lote")
    for rec, entry in zip(snap.records, batch.entries):
        form = forms[entry.form]
        if rec.id != entry.form:
            problems.append(f"registro da forma {rec.id}, esperado {entry.form} ({form.name})")
            continue
        count = 1 if trace else entry.count
        per = form.n_words
        if len(rec.words) != count * per:
            problems.append(f"{form.name}: {len(rec.words)} palavras, esperado {count * per}")
            continue
        for k in range(count):
            index = entry.first + k
            inputs = form.vector(index)
            obs = rec.words[k * per:(k + 1) * per]
            results.append(VectorResult(form.name, index, inputs, obs,
                                        expected_fields(form, inputs)))
    return results, problems
