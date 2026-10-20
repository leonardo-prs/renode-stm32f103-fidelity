"""Conjuntos de vetores do C1 (material-base, §"Como os vetores são escolhidos").

Os vetores cobrem (1) cada ramo do pseudocódigo da instrução e (2) as
bordas numéricas onde as flags mudam: zero (Z), bit 31 (N), a fronteira
0x7FFFFFFF/0x80000000 (V) e 0xFFFFFFFF/0x00000000 (C).
"""
from __future__ import annotations

from . import arm

# V32: 13 valores (tabela "O conjunto V32").
V32 = (
    0x0000_0000, 0x0000_0001, 0x0000_0002,      # neutro, menor positivo, Z
    0x0000_FFFF, 0x0001_0000,                   # fronteira de 16 bits (nota c)
    0x7FFF_FFFE, 0x7FFF_FFFF,                   # maior positivo: +1 gera V
    0x8000_0000, 0x8000_0001,                   # menor negativo: -1 gera V
    0xFFFF_FFFE, 0xFFFF_FFFF,                   # maior sem sinal: +1 gera C
    0x5555_5555, 0xAAAA_AAAA,                   # bits alternados
)

# SH: quantidades de deslocamento por registrador (só o byte baixo vale).
SH = (0, 1, 7, 16, 31, 32, 33, 63, 255, 256, 0xFFFF_FF20)

# Flags iniciais. A instrução não lê o carry: dois estados, todas as flags
# limpas ou ligadas (Q incluído, para FA-10/FQ: Q é preservado). A instrução
# lê o carry: C × Q completos, com as demais flags variando.
FLAGS2 = (0x0000_0000, 0xF800_0000)
FLAGS_C = (0x0000_0000, 0x2000_0000, 0xD800_0000, 0xF800_0000)
NZCV16 = tuple(k << 28 for k in range(16))
NZCVQ32 = tuple(k << 27 for k in range(32))

# Constantes modificadas: uma de cada forma codificável (PM0056 §3.3.3).
MOD_CONSTS = (0x0000_00AB, 0x00AB_00AB, 0xAB00_AB00, 0xABAB_ABAB, 0x8000_0000, 0x0000_0FF0)
for _c in MOD_CONSTS:
    assert arm.encode_modified_imm(_c) is not None


def rows(values, *more) -> tuple[tuple[int, ...], ...]:
    """Eixo de uma palavra (ou várias, zipadas)."""
    if more:
        return tuple(zip(values, *more))
    return tuple((v,) for v in values)


def table(*rows_):
    """Eixo de linhas explícitas."""
    return tuple(tuple(r) for r in rows_)


def hexname(value: int) -> str:
    return f"{value:x}"
