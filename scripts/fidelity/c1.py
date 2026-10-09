"""C1 — oráculos e métricas (núcleo e memória).

c1-functional: cada caso grava ENTRADAS e SAÍDAS. O oráculo:
  1. confere se as entradas gravadas são exatamente as do plano abaixo
     (cópia das tabelas de src/c1/functional.c — se divergirem, o caso é
     inválido como instrumento, não "errado");
  2. recalcula as saídas com aritmética de largura explícita (máscara 32/64
     bits, divisão truncada em direção a zero), sem reaproveitar o C.
Casos cujo resultado depende da IMPLEMENTAÇÃO (C17 6.3.1.3 e 6.5.7: conversão
para tipo com sinal menor, >> de negativo) seguem a convenção documentada
do GCC (módulo 2^N, deslocamento aritmético) e são marcados em IMPL_DEFINED.

c1-timing: cada caso = carga × tamanho, REPS execuções com entradas
idênticas. O oráculo confere o resultado de cada execução (recalculado em
Python a partir da mesma semente) e extrai os ticks.
"""
from __future__ import annotations

from dataclasses import dataclass, field

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1


def s32(u: int) -> int:
    u &= M32
    return u - (1 << 32) if u & 0x80000000 else u


def u32(v: int) -> int:
    return v & M32


def tdiv(a: int, b: int) -> int:
    """Divisão inteira truncada em direção a zero (C17 6.5.5)."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def trem(a: int, b: int) -> int:
    return a - b * tdiv(a, b)


@dataclass
class CaseCheck:
    """Resultado de um caso funcional em um run."""
    case_id: int
    name: str
    status: str                      # status do firmware (OK/TIMEOUT/...)
    inputs_ok: bool
    mismatches: list = field(default_factory=list)   # (rótulo, esperado, observado)
    checked: int = 0                 # nº de valores comparados

    @property
    def ok(self) -> bool:
        return self.status == "OK" and self.inputs_ok and not self.mismatches


# ───────────────────────── plano (cópia das entradas) ─────────────────────────

INT32_MAX, INT32_MIN = 0x7FFFFFFF, -0x80000000

U32_PAIRS = [(0x00000000, 0x00000000), (0x00000001, 0xFFFFFFFF), (0xFFFFFFFF, 0xFFFFFFFF),
             (0x80000000, 0x80000000), (0x7FFFFFFF, 0x00000001), (0x12345678, 0x9ABCDEF0),
             (0xDEADBEEF, 0x00010001), (0x0000FFFF, 0x00010001)]
U32_DIV_PAIRS = [(0xFFFFFFFF, 1), (0xFFFFFFFF, 0xFFFFFFFF), (7, 3), (0x80000000, 2), (100, 7),
                 (0x12345678, 0x1000), (1, 0xFFFFFFFF), (0xDEADBEEF, 0x10001), (0, 7)]
S32_ADDSUB_PAIRS = [(INT32_MAX, 0), (INT32_MIN, 0), (-1, 1), (100, -200), (INT32_MIN + 5, -5),
                    (INT32_MAX - 5, 5), (-123456789, 987654321)]
S32_MUL_PAIRS = [(-3, 7), (46340, 46340), (-46341, 46340), (INT32_MIN, 1), (-1, INT32_MAX),
                 (0, INT32_MIN), (-65536, 32767)]
S32_DIV_PAIRS = [(7, 2), (-7, 2), (7, -2), (-7, -2), (INT32_MIN, 1), (INT32_MIN, 2),
                 (INT32_MAX, -1), (-1, INT32_MAX), (INT32_MIN, INT32_MAX), (0, -5)]
SHIFT_VALUES = [0x80000001, 0xFFFFFFFF, 0x12345678, 0x00000001]
SHIFT_AMOUNTS = [0, 1, 15, 31]
ROTATE_VALUES = [0x80000001, 0x12345678]
ROTATE_AMOUNTS = [1, 8, 31]
FIELDS = [(0, 1), (4, 8), (31, 1), (16, 16), (3, 5)]
FIELD_SOURCE, FIELD_VALUE = 0xDEADBEEF, 0x5A
BITCOUNT_VALUES = [0x00000001, 0x80000000, 0x00010000, 0xFFFFFFFF, 0x0F0F0000, 0x00000300]
CONVERSION_VALUES = [0x00000080, 0x0000FF7F, 0xFFFF8000, 0x12345678, 0x7FFFFFFF]
U64_PAIRS = [(0x00000000FFFFFFFF, 0x0000000000000001),
             (0xFFFFFFFFFFFFFFFF, 0x0000000000000002),
             (0x123456789ABCDEF0, 0x0FEDCBA987654321)]
SORT_INPUT = [0xFFFFFFFF, 0, 5, 0x80000000, 5, 0x7FFFFFFF, 1, 0xFFFFFFFE,
              42, 0, 1000, 3, 0x80000001, 7, 42, 2]
GCD_PAIRS = [(48, 18), (17, 5), (0, 9), (1071, 462), (0xFFFFFFFF, 0xFFFF), (0x80000000, 0x00100000)]
RECURSION_INPUTS = [0, 1, 10, 18]
TABLE = [((i * 0x9E3779B9) ^ 0xA5A5A5A5) & M32 for i in range(64)]   # src/c1/table.h
TABLE_BYTES = b"".join(v.to_bytes(4, "little") for v in TABLE)
FLASH_RANGE = (0x08000000, 0x08010000)

CASES = {
    1: "u32_add", 2: "u32_sub", 3: "u32_mul", 4: "u32_mul_wide", 5: "u32_divrem",
    6: "s32_addsub", 7: "s32_mul", 8: "s32_divrem", 9: "compare", 10: "bit_logic",
    11: "shifts", 12: "rotate", 13: "bitfield", 14: "bitcount", 15: "promotion",
    16: "conversion", 17: "u64_ops", 18: "sram_byte_order", 19: "sram_widths",
    20: "sram_patterns", 21: "sram_walking", 22: "flash_words", 23: "flash_narrow",
    24: "copy_unaligned", 25: "fill_region", 26: "sort16", 27: "gcd", 28: "switch",
    29: "recursion",
}
# Área de cada caso (para a tabela de limites por recurso).
CASE_GROUP = {**{i: "aritmética inteira" for i in range(1, 10)},
              **{i: "bits e conversões" for i in range(10, 18)},
              **{i: "SRAM (larguras, ordem de bytes, padrões)" for i in range(18, 22)},
              22: "flash (.rodata)", 23: "flash (.rodata)",
              24: "cópia/preenchimento", 25: "cópia/preenchimento",
              26: "controle/algoritmo", 27: "controle/algoritmo", 28: "controle/algoritmo",
              29: "controle/algoritmo"}
IMPL_DEFINED = {"shifts": "asr de negativo (GCC: aritmético)",
                "conversion": "conversão para int8/int16 fora da faixa (GCC: módulo 2^N)",
                "flash_narrow": "conversão uint8/16 → int8/16 via LDRSB/LDRSH"}
PLANNED_FUNCTIONAL = list(CASES)


# ───────────────────────── expectativas por caso ─────────────────────────

def _chunks(words, n):
    if len(words) % n:
        raise ValueError(f"{len(words)} palavras não divisíveis em grupos de {n}")
    return [words[i:i + n] for i in range(0, len(words), n)]


def _sx(v: int, bits: int) -> int:
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def _binary(words, pairs, fn, labels, n_out):
    """Grupos [a, b, out...]; devolve (entradas_ok, checks)."""
    groups = _chunks(words, 2 + n_out)
    inputs_ok = [tuple(g[:2]) for g in groups] == [(u32(a), u32(b)) for a, b in pairs]
    checks = []
    for (a, b), g in zip(pairs, groups):
        for label, exp, obs in zip(labels, fn(a, b), g[2:]):
            checks.append((f"{label}({a:#x},{b:#x})", u32(exp), obs))
    return inputs_ok, checks


def expected_functional(case_id: int, words: tuple[int, ...]):
    """(entradas_ok, [(rótulo, esperado, observado)]) para um caso."""
    w = list(words)
    name = CASES[case_id]
    if name == "u32_add":
        return _binary(w, U32_PAIRS, lambda a, b: [a + b], ["add"], 1)
    if name == "u32_sub":
        return _binary(w, U32_PAIRS, lambda a, b: [a - b], ["sub"], 1)
    if name == "u32_mul":
        return _binary(w, U32_PAIRS, lambda a, b: [a * b], ["mul"], 1)
    if name == "u32_mul_wide":
        return _binary(w, U32_PAIRS, lambda a, b: [a * b, (a * b) >> 32], ["lo", "hi"], 2)
    if name == "u32_divrem":
        return _binary(w, U32_DIV_PAIRS, lambda a, b: [a // b, a % b], ["div", "rem"], 2)
    if name == "s32_addsub":
        return _binary(w, S32_ADDSUB_PAIRS, lambda a, b: [a + b, a - b], ["add", "sub"], 2)
    if name == "s32_mul":
        return _binary(w, S32_MUL_PAIRS, lambda a, b: [a * b], ["mul"], 1)
    if name == "s32_divrem":
        return _binary(w, S32_DIV_PAIRS, lambda a, b: [tdiv(a, b), trem(a, b)], ["div", "rem"], 2)
    if name == "compare":
        def flags(a, b):
            sa, sb = s32(a), s32(b)
            return [(a < b) | (sa < sb) << 1 | (a == b) << 2 | (a >= b) << 3 | (sa >= sb) << 4]
        return _binary(w, U32_PAIRS, flags, ["flags"], 1)
    if name == "bit_logic":
        return _binary(w, U32_PAIRS, lambda a, b: [a & b, a | b, a ^ b, ~a, a & ~b],
                       ["and", "or", "xor", "not", "andn"], 5)
    if name == "shifts":
        groups = _chunks(w, 5)
        plan = [(v, n) for v in SHIFT_VALUES for n in SHIFT_AMOUNTS]
        checks = []
        for (v, n), g in zip(plan, groups):
            exp = [v << n, v >> n, s32(v) >> n]       # >> em int Python = aritmético
            checks += [(f"{k}({v:#x},{n})", u32(e), o) for k, e, o in zip(("lsl", "lsr", "asr"), exp, g[2:])]
        return [tuple(g[:2]) for g in groups] == plan, checks
    if name == "rotate":
        groups = _chunks(w, 4)
        plan = [(v, n) for v in ROTATE_VALUES for n in ROTATE_AMOUNTS]
        checks = []
        for (v, n), g in zip(plan, groups):
            exp = [(v >> n) | (v << (32 - n)), (v << n) | (v >> (32 - n))]
            checks += [(f"{k}({v:#x},{n})", u32(e), o) for k, e, o in zip(("ror", "rol"), exp, g[2:])]
        return [tuple(g[:2]) for g in groups] == plan, checks
    if name == "bitfield":
        head, groups = w[:2], _chunks(w[2:], 5)
        checks = []
        for (lsb, width), g in zip(FIELDS, groups):
            field_v = (FIELD_SOURCE >> lsb) & ((1 << width) - 1)
            mask = ((1 << width) - 1) << lsb
            exp = [field_v, u32(_sx(field_v, width)),
                   (FIELD_SOURCE & ~mask) | ((FIELD_VALUE << lsb) & mask)]
            checks += [(f"{k}({lsb},{width})", u32(e), o)
                       for k, e, o in zip(("ubfx", "sbfx", "bfi"), exp, g[2:])]
        ok = head == [FIELD_SOURCE, FIELD_VALUE] and [tuple(g[:2]) for g in groups] == FIELDS
        return ok, checks
    if name == "bitcount":
        groups = _chunks(w, 4)
        checks = []
        for v, g in zip(BITCOUNT_VALUES, groups):
            exp = [32 - v.bit_length(), (v & -v).bit_length() - 1, bin(v).count("1")]
            checks += [(f"{k}({v:#x})", e, o) for k, e, o in zip(("clz", "ctz", "popcount"), exp, g[1:])]
        return [g[0] for g in groups] == BITCOUNT_VALUES, checks
    if name == "promotion":
        a, b, c, e, f = 200, 100, 0xFFFF, -128, -32768
        exp = [(a + b) & 0xFF, a + b, int(a + b > 255), (c + 1) & 0xFFFF, (c * c) & M32,
               u32(e), u32(e * 2), u32(f)]
        labels = ["u8(a+b)", "a+b", "a+b>255", "u16(c+1)", "c*c", "i32(i8)", "i8*2", "i32(i16)"]
        return True, [(k, u32(x), o) for k, x, o in zip(labels, exp, w)]
    if name == "conversion":
        groups = _chunks(w, 8)
        checks = []
        for v, g in zip(CONVERSION_VALUES, groups):
            exp = [_sx(v, 8), v & 0xFF, _sx(v, 16), v & 0xFFFF,
                   M32 if s32(v) < 0 else 0, 0, -v]
            checks += [(f"{k}({v:#x})", u32(x), o) for k, x, o in
                       zip(("sx8", "zx8", "sx16", "zx16", "s64hi", "u64hi", "neg"), exp, g[1:])]
        return [g[0] for g in groups] == CONVERSION_VALUES, checks
    if name == "u64_ops":
        groups = _chunks(w, 12)
        checks = []
        ok = True
        for (a, b), g in zip(U64_PAIRS, groups):
            ok &= (g[0] | g[1] << 32, g[2] | g[3] << 32) == (a, b)
            for k, x, lo, hi in (("add", a + b, g[4], g[5]), ("sub", a - b, g[6], g[7]),
                                 ("mul", a * b, g[8], g[9]), ("div", a // b, g[10], g[11])):
                checks.append((f"{k}({a:#x},{b:#x})", x & M64, lo | hi << 32))
        return ok, checks
    if name == "sram_byte_order":
        return True, list(zip(["b0", "b1", "b2", "b3", "h0", "h1"],
                              [0x44, 0x33, 0x22, 0x11, 0x3344, 0x1122], w))
    if name == "sram_widths":
        block = bytearray([0xEE] * 16)
        block[1] = 0xA1
        block[6:8] = (0xB2C3).to_bytes(2, "little")
        block[8:12] = (0xD4E5F607).to_bytes(4, "little")
        block[15] = 0x08
        exp = [int.from_bytes(block[i:i + 4], "little") for i in range(0, 16, 4)] + [0xA1, 0xB2C3, 0x08]
        labels = [f"w{i}" for i in range(4)] + ["byte1", "half3", "byte15"]
        return True, list(zip(labels, exp, w))
    if name == "sram_patterns":
        exp = [p for p in (0, M32, 0xAAAAAAAA, 0x55555555) for _ in range(16)]
        return True, [(f"pat{i // 16}[{i % 16}]", e, o) for i, (e, o) in enumerate(zip(exp, w))] \
            + _length_check(w, exp)
    if name == "sram_walking":
        exp = [1 << i for i in range(32)] + [M32 ^ (1 << i) for i in range(32)]
        return True, [(f"walk[{i}]", e, o) for i, (e, o) in enumerate(zip(exp, w))] + _length_check(w, exp)
    if name == "flash_words":
        addr_ok = FLASH_RANGE[0] <= w[0] < FLASH_RANGE[1]
        checks = [("addr_in_flash", 1, int(addr_ok))]
        checks += [(f"T[{i}]", e, o) for i, (e, o) in enumerate(zip(TABLE, w[1:]))]
        return True, checks + _length_check(w[1:], TABLE)
    if name == "flash_narrow":
        exp = []
        for i in range(8):
            exp += [TABLE_BYTES[i], u32(_sx(TABLE_BYTES[i], 8))]
        for i in range(4):
            h = int.from_bytes(TABLE_BYTES[2 * i:2 * i + 2], "little")
            exp += [h, u32(_sx(h, 16))]
        labels = [f"{k}[{i}]" for i in range(8) for k in ("u8", "s8")] + \
                 [f"{k}[{i}]" for i in range(4) for k in ("u16", "s16")]
        return True, list(zip(labels, exp, w)) + _length_check(w, exp)
    if name in ("copy_unaligned", "fill_region"):
        block = bytearray([0xEE] * 64)
        if name == "copy_unaligned":
            block[3:40] = TABLE_BYTES[1:38]
        else:
            block[5:43] = bytes([0x3C] * 38)
        exp = [int.from_bytes(block[i:i + 4], "little") for i in range(0, 64, 4)]
        return True, [(f"block[{4 * i}:{4 * i + 4}]", e, o) for i, (e, o) in enumerate(zip(exp, w))] \
            + _length_check(w, exp)
    if name == "sort16":
        exp = sorted(SORT_INPUT)
        return True, [(f"sorted[{i}]", e, o) for i, (e, o) in enumerate(zip(exp, w))] + _length_check(w, exp)
    if name == "gcd":
        import math
        return _binary(w, GCD_PAIRS, lambda a, b: [math.gcd(a, b)], ["gcd"], 1)
    if name == "switch":
        groups = _chunks(w, 2)
        table = {k: 0x10 + 0x11 * k for k in range(10)}
        checks = [(f"dispatch({k})", table.get(k, M32), g[1]) for k, g in zip(range(12), groups)]
        return [g[0] for g in groups] == list(range(12)), checks
    if name == "recursion":
        groups = _chunks(w, 2)

        def fib(n):
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            return a
        checks = [(f"fib({n})", fib(n), g[1]) for n, g in zip(RECURSION_INPUTS, groups)]
        return [g[0] for g in groups] == RECURSION_INPUTS, checks
    raise KeyError(name)


def _length_check(observed, expected):
    return [] if len(observed) == len(expected) else [("n_words", len(expected), len(observed))]


def check_functional(snap) -> list[CaseCheck]:
    out = []
    for case_id, name in CASES.items():
        c = snap.case(case_id)
        if c is None:
            out.append(CaseCheck(case_id, name, "MISSING", False, [("present", 1, 0)]))
            continue
        try:
            inputs_ok, checks = expected_functional(case_id, c.words)
        except (ValueError, IndexError) as exc:
            out.append(CaseCheck(case_id, name, c.status, False, [("layout", "ok", str(exc))]))
            continue
        bad = [(k, e, o) for k, e, o in checks if e != o]
        if len(checks) == 0:
            bad.append(("no_values", ">0", 0))
        out.append(CaseCheck(case_id, name, c.status, inputs_ok, bad, len(checks)))
    return out


# ───────────────────────────── C1-timing ─────────────────────────────

LOADS = ["empty", "alu", "mul", "div_small", "div_large", "sram_copy", "flash_sum", "branch", "crc"]
LOAD_DESCRIPTION = {
    "empty": "só chamada + retorno (custo fixo do bracket)",
    "alu": "xorshift32 em registradores (LSL/LSR/EOR)",
    "mul": "x = x*0x01000193 + i (MLA)",
    "div_small": "UDIV, quociente 1 (dividendo ~ divisor)",
    "div_large": "UDIV, dividendo 32 bits / 3 (quociente grande)",
    "sram_copy": "dst[i] = src[i] + 1 (LDR/STR SRAM)",
    "flash_sum": "soma de palavras da tabela em flash (LDR flash)",
    "branch": "desvios dependentes de dados (if/else if/else)",
    "crc": "CRC-32 bit a bit sobre bytes da flash (carga mista)",
}
SIZES = [16, 64, 256]
REPS = 4
SEED = 0x2545F491
LOAD_ARGS = {"empty": 0x5A5A5A5A, "alu": SEED, "mul": 0x811C9DC5, "div_small": 0x00F00000,
             "div_large": 3, "sram_copy": 0, "flash_sum": 0, "branch": 0, "crc": 0}
PLANNED_TIMING = [0] + [(li << 4) | s for li in range(1, len(LOADS)) for s in range(len(SIZES))]


def timing_inputs(load: str) -> list[int]:
    """Mesma geração de src/c1/timing.c: prepare_inputs()."""
    x = SEED
    out = []
    for _ in range(256):
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        out.append(0x00F00000 + (x & 0x00FFFFFF) % 0x00F00000 if load == "div_small" else x)
    return out


def expected_timing_result(load: str, n: int) -> int:
    arg = LOAD_ARGS[load]
    src = timing_inputs(load)
    if load == "empty":
        return n ^ arg
    if load == "alu":
        x = arg
        for _ in range(n):
            x ^= (x << 13) & M32
            x ^= x >> 17
            x ^= (x << 5) & M32
        return x
    if load == "mul":
        x = arg
        for i in range(n):
            x = (x * 0x01000193 + i) & M32
        return x
    if load in ("div_small", "div_large"):
        return sum(v // arg for v in src[:n]) & M32
    if load == "sram_copy":
        return (src[n - 1] + 1) & M32
    if load == "flash_sum":
        return sum(TABLE[i & 63] for i in range(n)) & M32
    if load == "branch":
        a = b = c = 0
        for v in src[:n]:
            if v & 1:
                a = (a + v) & M32
            elif v & 2:
                b ^= v
            else:
                c = (c - v) & M32
        return a ^ b ^ c
    if load == "crc":
        crc = M32
        for byte in TABLE_BYTES[:n]:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ (0xEDB88320 & (M32 if crc & 1 else 0))
        return crc ^ M32
    raise KeyError(load)


@dataclass
class TimingRep:
    load: str
    n: int
    rep: int
    ticks: int
    t0: int
    result_ok: bool


def parse_timing(snap) -> tuple[list[TimingRep], list[str]]:
    """Execuções medidas + problemas de layout/entrada (instrumento)."""
    reps, problems = [], []
    for case_id in PLANNED_TIMING:
        c = snap.case(case_id)
        if c is None:
            problems.append(f"caso {case_id:#x} ausente")
            continue
        w = c.words
        li, si = case_id >> 4, case_id & 0xF
        load = LOADS[li]
        n = 0 if load == "empty" else SIZES[si]
        if len(w) != 4 + 3 * REPS or tuple(w[:4]) != (li, n, LOAD_ARGS[load], REPS):
            problems.append(f"caso {load}/{n}: cabeçalho {w[:4]} diferente do plano")
            continue
        expected = expected_timing_result(load, n)
        for r in range(REPS):
            ticks, t0, result = w[4 + 3 * r: 7 + 3 * r]
            reps.append(TimingRep(load, n, r, ticks, t0, result == expected))
    return reps, problems


# ───────────────────────── avaliação de um run ─────────────────────────

def evaluate_functional(snap):
    from .model import RunEval
    ev = RunEval("c1-functional")
    for r in check_functional(snap):
        ev.case_status[r.name] = r.status
        if not r.inputs_ok:
            ev.problems.append(f"{r.name}: entradas gravadas diferem do plano (instrumento)")
        c = snap.case(r.case_id)
        if c is None:
            continue
        _, checks = expected_functional(r.case_id, c.words)
        for label, exp, obs in checks:
            ev.check(r.name, label, exp, obs)
    return ev


def linear_fit(xs, ys):
    """Mínimos quadrados y = a + b·x; devolve (a, b, maior |resíduo|)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    return a, b, max(abs(y - (a + b * x)) for x, y in zip(xs, ys))


def evaluate_timing(snap):
    from statistics import median

    from .model import RES_BRACKET, RunEval
    ev = RunEval("c1-timing")
    reps, problems = parse_timing(snap)
    ev.problems += problems
    by_case: dict[tuple[str, int], list[TimingRep]] = {}
    for r in reps:
        by_case.setdefault((r.load, r.n), []).append(r)
    warm_by_load: dict[str, list[tuple[int, float]]] = {}
    for (load, n), rs in by_case.items():
        case = f"{load}/{n}"
        ev.case_status[case] = "OK"
        ev.check(case, "resultado correto em todas as repetições", True, all(r.result_ok for r in rs))
        rs.sort(key=lambda r: r.rep)
        warm = [r.ticks for r in rs[1:]]
        ev.metric(case, "first", rs[0].ticks, resolution=RES_BRACKET)
        ev.metric(case, "warm", median(warm), resolution=RES_BRACKET)
        ev.metric(case, "warm_spread", max(warm) - min(warm), resolution=RES_BRACKET)
        if load != "empty":
            warm_by_load.setdefault(load, []).append((n, median(warm)))
    for load, pts in warm_by_load.items():
        if len(pts) >= 3:
            a, b, worst = linear_fit([p[0] for p in pts], [p[1] for p in pts])
            ev.metric(load, "per_iteration", b, unit="ticks/iter", resolution=RES_BRACKET)
            ev.metric(load, "fixed_cost", a, resolution=RES_BRACKET)
            ev.metric(load, "nonlinearity", worst, resolution=RES_BRACKET)
    return ev
