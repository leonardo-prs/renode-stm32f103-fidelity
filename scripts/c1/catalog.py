"""Estruturas do catálogo do C1 e divisão em lotes.

O catálogo é a fonte ÚNICA de três coisas que precisam concordar:

  1. o que o firmware executa (tabelas geradas em build/<preset>/gen/);
  2. o que o host espera (oráculo, campos comparados, máscaras);
  3. o que o disassembly deve conter (instrução, largura, operandos).

Um caso do material-base (ex.: FA-02) vira uma ou mais FORMAS (ex.: FA-02.t1
e FA-02.t2, uma por codificação), cada uma com UMA rotina assembly e um
gerador de vetores. O gerador é o produto cartesiano de EIXOS; cada eixo é
uma tabela de linhas, e cada linha preenche uma ou mais palavras de entrada.
O firmware percorre o produto com o último eixo variando mais rápido; o host
reconstrói exatamente a mesma sequência (`Form.vectors`).
"""
from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

MASK32 = 0xFFFF_FFFF

# Flags de forma (espelhadas em c1_catalog.h).
F_FAULT = 1 << 0        # anexa o registro de faltas (10 palavras) a cada vetor
F_MEM = 1 << 1          # pré-enche a janela de memória e a anexa (8 palavras)
F_TERMINAL = 1 << 2     # caso terminal: execução própria, falta sem aterrissagem
F_ISOLATE = 1 << 3      # lote próprio: um travamento num ambiente não leva os outros vetores

FAULT_FIELDS = ("cfsr", "hfsr", "mmfar", "bfar", "pc", "xpsr", "exc_return",
                "landing", "ipsr", "count")
MEM_WORDS = 8
MEM_FIELDS = tuple(f"mem{k}" for k in range(MEM_WORDS))
MEM_FILL = 0xA5A5_A5A5

Row = tuple[int, ...]
# Valor esperado de uma palavra: int (igualdade exata), None (gravado, não
# comparado: o documento não define) ou (valor, máscara).
Expected = int | None | tuple[int, int]


@dataclass(frozen=True)
class Insn:
    """Instrução esperada no rótulo <rotina>_x<k> do ELF."""
    mnemonic: str             # como o objdump imprime (ex.: "adds", "adds.w", "udiv")
    width: int                # 16 ou 32
    operands: str | None = None   # regex sobre os operandos (None = não confere)
    k: int = 0
    align: tuple[int, int] | None = None   # (m, r): endereço da instrução ≡ r (mod m)


@dataclass
class Form:
    name: str                 # "FA-02.t1" (único)
    case: str                 # "FA-02"
    routine: str              # símbolo assembly "v_fa02_t1"
    axes: Sequence[Sequence[Row]]
    outs: Sequence[str]       # nomes das palavras de saída da rotina
    oracle: Callable[[Row], dict[str, Expected]]
    insns: Sequence[Insn] = ()
    flags: int = 0
    level: str = "N2"
    klass: str = "A"
    source: str = ""
    note: str = ""

    @property
    def n_in(self) -> int:
        return sum(len(axis[0]) for axis in self.axes)

    @property
    def fields(self) -> tuple[str, ...]:
        out = tuple(self.outs)
        if self.flags & F_MEM:
            out += MEM_FIELDS
        if self.flags & F_FAULT or self.flags & F_TERMINAL:
            out += FAULT_FIELDS
        return out

    @property
    def n_words(self) -> int:
        """Palavras gravadas por vetor (saídas + janela + faltas)."""
        return len(self.fields)

    @property
    def count(self) -> int:
        n = 1
        for axis in self.axes:
            n *= len(axis)
        return n

    def vectors(self) -> Iterable[Row]:
        """Entradas na ordem do firmware (último eixo varia mais rápido)."""
        for rows in itertools.product(*self.axes):
            yield tuple(w for row in rows for w in row)

    def vector(self, index: int) -> Row:
        rows = []
        for axis in reversed(self.axes):
            index, k = divmod(index, len(axis))
            rows.append(axis[k])
        return tuple(w for row in reversed(rows) for w in row)

    def check(self) -> None:
        if not self.axes:
            raise ValueError(f"{self.name}: sem eixos")
        for axis in self.axes:
            widths = {len(r) for r in axis}
            if len(widths) != 1 or not axis:
                raise ValueError(f"{self.name}: eixo vazio ou com larguras {widths}")
            for row in axis:
                if any(not 0 <= w <= MASK32 for w in row):
                    raise ValueError(f"{self.name}: palavra fora de 32 bits em {row}")
        if self.n_in > 8:
            raise ValueError(f"{self.name}: {self.n_in} palavras de entrada (máx. 8)")
        if self.level not in ("N1", "N2", "N3"):
            raise ValueError(f"{self.name}: nível {self.level}")
        if self.klass not in ("A", "B", "C"):
            raise ValueError(f"{self.name}: classe {self.klass}")


@dataclass(frozen=True)
class Entry:
    """Um trecho de uma forma dentro de um lote."""
    form: int                 # índice da forma no catálogo
    first: int                # primeiro vetor
    count: int


@dataclass
class Batch:
    level: str
    entries: list[Entry] = field(default_factory=list)
    terminal: bool = False

    def words(self, forms: Sequence[Form]) -> int:
        return sum(e.count * forms[e.form].n_words for e in self.entries)


def make_batches(forms: Sequence[Form], max_words: int, max_records: int) -> list[Batch]:
    """Divide as formas em lotes que cabem no snapshot.

    Lotes são formados por NÍVEL (N1 primeiro), para que o piloto e uma
    campanha reduzida possam executar só os lotes N1. Uma forma maior que
    um lote é dividida em trechos contíguos de vetores. Casos terminais e
    formas isoladas (que podem travar um dos ambientes, ex.: executar em
    região XN) ocupam um lote (uma execução) cada.
    """
    batches: list[Batch] = []
    for level in ("N1", "N2", "N3"):
        cur = Batch(level)
        for idx, form in enumerate(forms):
            if form.level != level:
                continue
            if form.flags & F_TERMINAL:
                batches.append(Batch(level, [Entry(idx, 0, form.count)], terminal=True))
                continue
            if form.flags & F_ISOLATE:
                batches.append(Batch(level, [Entry(idx, 0, form.count)]))
                continue
            per = form.n_words
            remaining, first = form.count, 0
            while remaining:
                room = (max_words - cur.words(forms)) // per
                if room == 0 or len(cur.entries) >= max_records:
                    batches.append(cur)
                    cur = Batch(level)
                    continue
                take = min(room, remaining)
                cur.entries.append(Entry(idx, first, take))
                first += take
                remaining -= take
        if cur.entries:
            batches.append(cur)
    return batches


def short_hash(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "little")
