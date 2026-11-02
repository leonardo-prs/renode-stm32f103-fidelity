"""Especificação do Q-02: fonte única do firmware (gera q02_spec.h) e da análise.

O firmware executa segmentos em sequência, cada um delimitado por pontos
marcados (q02_point(id): o gancho lê o id em R0). Nenhum segmento usa
periférico do chip: só instruções do núcleo, SRAM e registradores do SCS
(ICSR, SHPR, VTOR). O Q-02 não pergunta se o núcleo é fiel (isso é do C1 e
do C2); pergunta se os instrumentos concordam entre si e com o firmware.
"""
from __future__ import annotations

import hashlib
import json

MAGIC = 0xC0DE0002                       # gravado pelo monitor antes da partida (.noinit)
ST_RUNNING, ST_DONE, ST_BAD_PARAM = 0, 1, 2
MODE_NONE, MODE_TAIL, MODE_NEST = 0, 1, 2

# Segmentos: (nome, o que exercita). Ponto de início = 2k+1, de fim = 2k+2.
SEGMENTS = (
    ("W", "escritas de palavra na SRAM vigiada (e numa vizinha não vigiada)"),
    ("X_PENDSV", "PendSV pedido pela thread (escrita no ICSR)"),
    ("X_SYSTICK", "exceção SysTick pedida pela thread (PENDSTSET; o timer SysTick não é usado)"),
    ("X_TAIL", "o tratador do SysTick pede o PendSV (menor prioridade)"),
    ("X_NEST", "o tratador do PendSV pede o SysTick (maior prioridade)"),
    ("X_MASKED", "PendSV e SysTick pedidos com PRIMASK = 1; depois PRIMASK = 0"),
    ("M_HOOK", "um gancho de endereço grava na SRAM; o firmware lê logo depois"),
    ("M_PAUSE", "o monitor lê e grava a SRAM com a simulação parada, em dois instantes"),
)
POINT = {name: (2 * k + 1, 2 * k + 2) for k, (name, _) in enumerate(SEGMENTS)}
POINT_SEEN1 = 0x20                       # dentro de M_PAUSE: primeiro valor visto
POINT_IDS = tuple(i for name, _ in SEGMENTS for i in
                  ((POINT[name][0], POINT_SEEN1, POINT[name][1]) if name == "M_PAUSE" else POINT[name]))

SINK_VALUES = (0x11111111, 0xA5A5A5A5, 0x0000FFFF, 0x00000000)
NEIGHBOR_VALUE = 0x77777777              # q02_sink[1]: não vigiada; não pode gerar evento
HOOK_VALUE = 0xC0FFEE02                  # gravado em q02_mbox2 pelo gancho em q02_trigger
ECHO_VALUE = 0xEC40EC40                  # gravado pelo firmware; lido pelo monitor na pausa
PAUSE_VALUES = (0x0BAD0001, 0x0BAD0002)  # gravados pelo monitor em q02_mbox nas pausas
# Instantes das pausas (ns de tempo virtual, múltiplos de 125 ns) e duração total.
# O 2º difere do 1º por um número de instruções que não é múltiplo da volta
# de espera, para a escrita cair em fases diferentes do laço.
PAUSES_NS = (200_000, 250_125)
RUN_NS = 300_000
PRIO_SYSTICK, PRIO_PENDSV = 8, 15        # 4 bits implementados; SysTick preempta PendSV

ICSR = 0xE000ED04
PENDSVSET, PENDSTSET = 1 << 28, 1 << 26
SHCSR = 0xE000ED24
EXC_PENDSV, EXC_SYSTICK = 14, 15
N_WLOG, N_SAW = 12, 8

# Registro do firmware (struct q02_rec_t, gerada daqui): (campo, palavras).
# Cada campo tem um único escritor: main, o tratador do PendSV ou o do SysTick.
REC_FIELDS = (
    ("status", 1),                 # main
    ("wlog_n", 1),                 # main: escritas vigiadas feitas pela thread
    ("wlog", 2 * N_WLOG),          # main: (endereço, valor) de cada uma, em ordem
    ("n_pendsv", 1),               # PendSV: entradas
    ("n_systick", 1),              # SysTick: entradas
    ("pendsv_icsr", 1),            # PendSV: escritas no ICSR feitas por ele
    ("systick_icsr", 1),           # SysTick: idem
    ("pendsv_saw", N_SAW),         # PendSV: n_systick na k-ésima entrada
    ("systick_saw", N_SAW),        # SysTick: n_pendsv na k-ésima entrada
    ("nest_before", 1),            # PendSV (X_NEST): n_systick antes de pedir o SysTick
    ("nest_after", 1),             # PendSV (X_NEST): n_systick depois
    ("hook_seen", 1),              # main: q02_mbox2 lido logo depois de q02_trigger
    ("wait_iters", 2),             # main: voltas de espera até ver cada valor da pausa
    ("pause_seen", 2),             # main: valor visto em q02_mbox
)
REC_WORDS = sum(n for _, n in REC_FIELDS)


def rec_offsets() -> dict[str, int]:
    out, off = {}, 0
    for name, n in REC_FIELDS:
        out[name] = off
        off += n
    return out


def decode_rec(words: list[int]) -> dict[str, int | list[int]]:
    off, out = 0, {}
    for name, n in REC_FIELDS:
        out[name] = words[off] if n == 1 else list(words[off:off + n])
        off += n
    return out


def spec_hash() -> str:
    blob = json.dumps([MAGIC, SEGMENTS, POINT_IDS, SINK_VALUES, NEIGHBOR_VALUE, HOOK_VALUE, ECHO_VALUE,
                       PAUSE_VALUES, PAUSES_NS, RUN_NS, PRIO_SYSTICK, PRIO_PENDSV, REC_FIELDS])
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def header() -> str:
    L = ["/* Gerado por scripts/q02/spec.py — não editar. */", "#ifndef Q02_SPEC_H", "#define Q02_SPEC_H", "",
         "#include <stdint.h>", "",
         f'#define Q02_SPEC_HASH "{spec_hash()}"',
         f"#define Q02_MAGIC 0x{MAGIC:08X}UL",
         f"#define Q02_ST_RUNNING {ST_RUNNING}U", f"#define Q02_ST_DONE {ST_DONE}U",
         f"#define Q02_ST_BAD_PARAM {ST_BAD_PARAM}U",
         f"#define Q02_MODE_NONE {MODE_NONE}U", f"#define Q02_MODE_TAIL {MODE_TAIL}U",
         f"#define Q02_MODE_NEST {MODE_NEST}U", ""]
    for name, _ in SEGMENTS:
        L += [f"#define Q02_P_{name}_BEGIN {POINT[name][0]}U", f"#define Q02_P_{name}_END {POINT[name][1]}U"]
    L += [f"#define Q02_P_SEEN1 0x{POINT_SEEN1:02X}U", ""]
    L += [f"#define Q02_N_SINK_VALUES {len(SINK_VALUES)}U",
          "#define Q02_SINK_VALUES {" + ", ".join(f"0x{v:08X}UL" for v in SINK_VALUES) + "}",
          f"#define Q02_NEIGHBOR_VALUE 0x{NEIGHBOR_VALUE:08X}UL",
          f"#define Q02_HOOK_VALUE 0x{HOOK_VALUE:08X}UL", f"#define Q02_ECHO_VALUE 0x{ECHO_VALUE:08X}UL",
          f"#define Q02_PAUSE_VALUE0 0x{PAUSE_VALUES[0]:08X}UL",
          f"#define Q02_PAUSE_VALUE1 0x{PAUSE_VALUES[1]:08X}UL",
          f"#define Q02_PRIO_SYSTICK {PRIO_SYSTICK}U", f"#define Q02_PRIO_PENDSV {PRIO_PENDSV}U",
          f"#define Q02_N_WLOG {N_WLOG}U", f"#define Q02_N_SAW {N_SAW}U", "",
          "typedef struct {"]
    for name, n in REC_FIELDS:
        L.append(f"    uint32_t {name};" if n == 1 else
                 f"    uint32_t {name}[{n}];" if name != "wlog" else f"    uint32_t {name}[{N_WLOG}][2];")
    L += ["} q02_rec_t;", "", "#endif", ""]
    return "\n".join(L)


def check() -> None:
    assert all(t % 125 == 0 for t in (*PAUSES_NS, RUN_NS)), "instantes em múltiplos de 125 ns"
    assert PAUSES_NS[0] < PAUSES_NS[1] < RUN_NS
    assert len(set(POINT_IDS)) == len(POINT_IDS)
    assert len(SINK_VALUES) + 6 <= N_WLOG, "wlog cabe as escritas vigiadas da thread"
    assert PRIO_SYSTICK < PRIO_PENDSV < 16
    # Nenhum valor de teste cai em faixa que o gate proíbe como literal.
    for v in (MAGIC, NEIGHBOR_VALUE, HOOK_VALUE, ECHO_VALUE, *SINK_VALUES, *PAUSE_VALUES):
        assert not (0x40000000 <= v < 0x60000000 or 0x22000000 <= v < 0x24000000), hex(v)


check()
