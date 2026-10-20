"""Avaliação de um run temporal: snapshot → Δ, c, O e linearidade por variante.

Modelo da medida (material-base, "Três tamanhos e o teste de linearidade"):

    Δ(n) = O + n·c,   c = (Δ(3K) − Δ(K)) / (3K − K),   O = Δ(K) − K·c,
    linear  ⇔  (Δ(3K) − Δ(2K))·(2K − K) = (Δ(2K) − Δ(K))·(3K − 2K).

Como os Δ são inteiros, o teste é exato; c é uma FRAÇÃO exata (pode não
ser inteiro mesmo com a medida linear e determinística). Se o teste falha,
c não é publicado como custo (EVIDÊNCIA INVÁLIDA para c).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from . import abi

PROFILE_FIELDS = ("profile_delta", "cpicnt", "exccnt", "sleepcnt", "lsucnt", "foldcnt")


@dataclass(frozen=True)
class Fit:
    deltas: tuple[int, int, int]
    c: Fraction | None
    o: Fraction
    linear: bool


def fit(deltas: tuple[int, int, int], sizes: tuple[int, int, int]) -> Fit:
    d1, d2, d3 = deltas
    s1, s2, s3 = sizes
    if s3 == s1:                                    # bloco vazio (T-DWT-03/05)
        return Fit(deltas, None, Fraction(d1), d1 == d2 == d3)
    c = Fraction(d3 - d1, s3 - s1)
    o = d1 - s1 * c
    linear = (d3 - d2) * (s2 - s1) == (d2 - d1) * (s3 - s2)
    return Fit(deltas, c, o, linear)


@dataclass
class VariantRun:
    name: str
    deltas: list[list[int]]           # [bloco K/2K/3K][iteração 0 = fria, 1.. = quentes]
    raw: list[list[tuple[int, int]]]  # (t0, t1) por chamada (só variantes RAW)
    profile: dict | None              # Δ do bloco de perfil e os 5 contadores

    def fits(self, sizes) -> list[Fit]:
        """Um ajuste por iteração (a mesma iteração dos três blocos)."""
        n = min(len(d) for d in self.deltas)
        return [fit((self.deltas[0][i], self.deltas[1][i], self.deltas[2][i]), sizes) for i in range(n)]


def parse(snap: abi.Snapshot, variants, batch, iters: int, trace: bool = False
          ) -> tuple[list[VariantRun], list[str]]:
    from .cycle import V_RAW
    problems, out = [], []
    if len(snap.records) != len(batch.variants):
        problems.append(f"{len(snap.records)} registros para {len(batch.variants)} variantes do lote")
    for rec, idx in zip(snap.records, batch.variants):
        v = variants[idx]
        if rec.id != idx:
            problems.append(f"registro da variante {rec.id}, esperado {idx} ({v.name})")
            continue
        per_call = 3 if v.flags & V_RAW else 1
        calls = 1 if trace else 3 * (1 + iters)
        expected = calls * per_call + (0 if trace else len(PROFILE_FIELDS))
        if len(rec.words) != expected:
            problems.append(f"{v.name}: {len(rec.words)} palavras, esperado {expected}")
            continue
        words = list(rec.words)
        deltas, raw = [[], [], []], [[], [], []]
        for call in range(calls):
            k = 0 if trace else call // (1 + iters)
            chunk = words[call * per_call:(call + 1) * per_call]
            deltas[k].append(chunk[0])
            if per_call == 3:
                raw[k].append((chunk[1], chunk[2]))
        profile = None if trace else dict(zip(PROFILE_FIELDS, words[calls * per_call:]))
        out.append(VariantRun(v.name, deltas, raw, profile))
    return out, problems
