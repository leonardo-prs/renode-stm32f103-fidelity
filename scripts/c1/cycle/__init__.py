"""Catálogo temporal do C1 (preset c1-cycle): src/c1/cycle/*.S.

Cada VARIANTE é um caso do material-base num conjunto de operandos: um
conjunto de três blocos (K = 8, 2K = 16, 3K = 24 unidades), os
registradores de entrada, a preparação de memória (setup em main.c) e as
duas previsões, registradas ANTES da medição:

  trm     custo por unidade inteira previsto pelo TRM r1p1 (Tab. 18-1, §18.3):
          intervalo [lo, hi] (hi = None: "pelo menos lo"), com a marca
          "ambíguo" quando o próprio TRM admite duas leituras;
  renode  a hipótese H-T1 (um tick por instrução executada): número de
          instruções executadas por unidade.

Nenhuma das duas é oráculo de veredito: a métrica de fidelidade é placa ×
Renode; placa × TRM confirma ou corrige o modelo documentado; Renode × H-T1
testa a hipótese tirada do código.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from importlib import import_module

from ..catalog import Insn

SIZES = (8, 16, 24)
R_MAX = 30                    # iterações quentes máximas por execução (piloto)
REG_NAMES = ("r0", "r1", "r2", "r3", "r4", "r8", "r9", "r10", "r11", "r12", "apsr")

# Preparações de memória (switch em src/c1/cycle/main.c).
SETUPS = ("none", "cell", "self", "walk", "ls08a", "ls08b", "ls08c", "ls08d", "ldrpc", "pairs",
          "rom", "alias", "bb3_alias", "bb3_plain", "copy")
# Setups cujas tabelas/buffers no firmware têm o tamanho de K = 8/16/24.
TABLE_SETUPS = ("walk", "ldrpc", "pairs", "copy")
# Flags de variante.
V_PRIMASK0, V_CYCOFF, V_PREFOFF, V_RAW = 1, 2, 4, 8


@dataclass(frozen=True)
class Pred:
    lo: Fraction | None               # None = sem previsão (caracterização)
    hi: Fraction | None = None        # None com lo definido = "pelo menos lo"
    ambiguous: bool = False
    text: str = ""

    def contains(self, value: Fraction) -> bool | None:
        if self.lo is None:
            return None
        return value >= self.lo and (self.hi is None or value <= self.hi)

    def __str__(self) -> str:
        if self.lo is None:
            return "—"
        if self.hi is None:
            return f"≥ {self.lo}"
        s = f"{self.lo}" if self.lo == self.hi else f"{self.lo}–{self.hi}"
        return s + (" (ambíguo)" if self.ambiguous else "")


def P(lo, hi=..., ambiguous=False, text="") -> Pred:
    """P(1) = exatamente 1; P(3, 5) = intervalo; P(5, None) = pelo menos 5."""
    if lo is None:
        return Pred(None, None, False, text)
    hi = lo if hi is ... else hi
    return Pred(Fraction(lo), None if hi is None else Fraction(hi), ambiguous, text)


NOPRED = Pred(None)


def R(**regs) -> tuple[int, ...]:
    """Registradores de entrada na ordem de regs[] (blocks.inc)."""
    unknown = set(regs) - set(REG_NAMES)
    if unknown:
        raise ValueError(f"registradores desconhecidos {unknown}")
    return tuple(regs.get(n, 0) & 0xFFFF_FFFF for n in REG_NAMES)


@dataclass
class Variant:
    name: str                         # "T-DIV-01.a16.b8"
    case: str                         # "T-DIV-01"
    blockset: str                     # "t_div01" → t_div01_8/_16/_24 (ou 3 nomes)
    unit: str                         # a unidade em assembly (relatório)
    trm: Pred
    renode: Fraction                  # H-T1: instruções por unidade
    regs: tuple | tuple[tuple, tuple, tuple] = R()
    setup: str = "none"
    arg: int = 0
    flags: int = 0
    obj: str = "custo marginal"       # | "latência" | "sequência isolada" | "total"
    level: str = "N2"
    source: str = "@armlimited2007[Tab. 18-1]"
    note: str = ""
    first: Insn | None = None         # 1ª instrução da unidade (gate)
    ua: int = 4                       # alinhamento da 1ª unidade (4 ou 2)
    sizes: tuple[int, int, int] = SIZES
    blocks: tuple[str, str, str] | None = None

    def __post_init__(self):
        if self.blocks is None:
            self.blocks = tuple(f"{self.blockset}_{n}" for n in self.sizes)
        # Os buffers do firmware (c1_cyc_tab, c1_src/c1_dst, c1_cell) e
        # first_unit() (src/c1/cycle/main.c) só conhecem os blocos K = 8/16/24.
        if self.setup in TABLE_SETUPS and max(self.sizes) > max(SIZES):
            raise ValueError(f"{self.name}: setup {self.setup} limitado a {max(SIZES)} unidades")
        if self.setup in ("ldrpc", "pairs") and self.blocks != tuple(
                f"{self.blockset}_{n}" for n in SIZES):
            raise ValueError(f"{self.name}: setup {self.setup} exige os blocos padrão {SIZES}")
        if len(self.regs) == len(REG_NAMES):
            self.regs = (self.regs,) * 3
        if self.setup not in SETUPS:
            raise ValueError(f"{self.name}: setup {self.setup}")
        if self.level not in ("N1", "N2", "N3"):
            raise ValueError(f"{self.name}: nível {self.level}")

    @property
    def words(self) -> int:
        """Palavras por iteração-máxima: 3 blocos × (1 + R_MAX) Δ, mais t0/t1
        em RAW, mais o bloco de perfil (Δ + 5 contadores)."""
        per_call = 3 if self.flags & V_RAW else 1
        return 3 * (1 + R_MAX) * per_call + 6


GROUPS = ("dwt", "alu", "ls", "br", "fe")
VARIANTS: list[Variant] = []
for _g in GROUPS:
    VARIANTS += import_module(f".{_g}", __name__).VARIANTS
_names = [v.name for v in VARIANTS]
if len(set(_names)) != len(_names):
    raise ValueError("nomes de variante repetidos no catálogo temporal")


def points(variants) -> list:
    """Pontos do gate: a 1ª unidade de cada bloco (instrução e alinhamento)."""
    seen, out = set(), []
    for v in variants:
        if v.first is None:
            continue
        for b, n in zip(v.blocks, v.sizes):
            if b in seen:
                continue
            seen.add(b)
            ins = Insn(v.first.mnemonic, v.first.width, v.first.operands, 0, (4, v.ua % 4))
            out.append((v.name, f"{b}_x0", ins))
    return out


@dataclass
class CycleBatch:
    level: str
    variants: list[int] = field(default_factory=list)


def make_batches(variants, max_words: int, max_records: int) -> list[CycleBatch]:
    out = []
    for level in ("N1", "N2", "N3"):
        cur, used = CycleBatch(level), 0
        for i, v in enumerate(variants):
            if v.level != level:
                continue
            if used + v.words > max_words or len(cur.variants) >= max_records:
                out.append(cur)
                cur, used = CycleBatch(level), 0
            cur.variants.append(i)
            used += v.words
        if cur.variants:
            out.append(cur)
    return out
