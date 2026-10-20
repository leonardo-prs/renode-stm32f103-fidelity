"""Avaliação de um run funcional: snapshot → vetores com oráculo.

Para cada registro do snapshot (um trecho de uma forma), reconstrói as
entradas de cada vetor pela mesma ordem do firmware, aplica o oráculo e
compara campo a campo, sob a máscara declarada. O resultado é uma lista de
`VectorResult`, a unidade de comparação entre ambientes na análise.
"""
from __future__ import annotations

from dataclasses import dataclass

import re

from . import abi
from .catalog import Alt, Batch, Form


def matches(observed: int, exp) -> bool:
    value, mask = exp if isinstance(exp, tuple) else (exp, 0xFFFF_FFFF)
    return (observed & mask) == (value & mask)


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
        if isinstance(exp, Alt):
            return any(matches(self.observed[k], o) for o in exp.options)
        return matches(self.observed[k], exp)

    def alt_label(self, k: int) -> str | None:
        """Qual leitura de um conflito documental o valor observado confirma."""
        exp = self.expected[k]
        if not isinstance(exp, Alt):
            return None
        hits = [lab for o, lab in zip(exp.options, exp.labels) if matches(self.observed[k], o)]
        return "/".join(hits) if hits else None

    @property
    def ok(self) -> bool:
        return all(self.field_ok(k) is not False for k in range(len(self.observed)))


def resolve(value, syms: dict[str, int]):
    """Valor esperado simbólico ("rótulo", "rótulo+N", "rótulo-N") → endereço do ELF."""
    if isinstance(value, str):
        m = re.fullmatch(r"([A-Za-z_][\w.]*)([+-]\d+)?", value)
        if not m or m[1] not in syms:
            raise ValueError(f"símbolo {value} ausente no ELF")
        return ((syms[m[1]] & ~1) + int(m[2] or 0)) & 0xFFFF_FFFF
    if isinstance(value, Alt):
        return Alt(tuple(resolve(o, syms) for o in value.options), value.labels)
    if isinstance(value, tuple) and isinstance(value[0], str):
        return (resolve(value[0], syms), value[1])
    return value


def expected_fields(form: Form, inputs, syms: dict[str, int]) -> tuple:
    exp = form.oracle(inputs)
    unknown = set(exp) - set(form.fields)
    if unknown:
        raise ValueError(f"{form.name}: oráculo devolveu campos inexistentes {unknown}")
    return tuple(resolve(exp.get(name), syms) for name in form.fields)


def functional(snap: abi.Snapshot, forms: list[Form], batch: Batch, syms: dict[str, int],
               trace: bool = False) -> tuple[list[VectorResult], list[str]]:
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
                                        expected_fields(form, inputs, syms)))
    return results, problems
