"""Modelo de referência: pseudocódigo do ARMv7-M ARM transcrito em Python.

Cada função tem o nome e a semântica da função homônima do ARM ARM
(DDI 0403E, citado como @armlimited2021). Este módulo é o ORÁCULO do C1:
ele é independente dos dois ambientes sob teste (placa e Renode) e é
verificado contra os exemplos resolvidos das próprias fontes
(scripts/c1/tests/test_arm.py), antes de qualquer execução.

Convenções: valores de 32 bits são `int` em [0, 2^32); `bit` é 0 ou 1.
"""
from __future__ import annotations

MASK32 = 0xFFFF_FFFF

# Bits do APSR (§A2.3.2).
N_BIT, Z_BIT, C_BIT, V_BIT, Q_BIT = 31, 30, 29, 28, 27
NZCV_MASK = 0xF000_0000
NZCVQ_MASK = 0xF800_0000


def u32(x: int) -> int:
    return x & MASK32


def sint(x: int, n: int = 32) -> int:
    """SInt(): interpretação com sinal de um vetor de n bits."""
    x &= (1 << n) - 1
    return x - (1 << n) if x >> (n - 1) else x


def bit(x: int, i: int) -> int:
    return (x >> i) & 1


# ───────────────────────────── APSR ─────────────────────────────

def apsr(n: int, z: int, c: int, v: int, q: int = 0) -> int:
    return (n << N_BIT) | (z << Z_BIT) | (c << C_BIT) | (v << V_BIT) | (q << Q_BIT)


def flags(x: int) -> tuple[int, int, int, int, int]:
    """(N, Z, C, V, Q) de um valor de APSR."""
    return bit(x, N_BIT), bit(x, Z_BIT), bit(x, C_BIT), bit(x, V_BIT), bit(x, Q_BIT)


def with_nzcv(old: int, n=None, z=None, c=None, v=None) -> int:
    """APSR com os campos dados substituídos (None = inalterado)."""
    out = old
    for value, pos in ((n, N_BIT), (z, Z_BIT), (c, C_BIT), (v, V_BIT)):
        if value is not None:
            out = (out & ~(1 << pos)) | (value << pos)
    return u32(out)


def with_q(old: int, q: int) -> int:
    return u32((old & ~(1 << Q_BIT)) | (q << Q_BIT))


def nz(result: int) -> tuple[int, int]:
    return bit(result, 31), int(u32(result) == 0)


# ───────────────────────────── A2.2.1: aritmética ─────────────────────────────

def add_with_carry(x: int, y: int, carry_in: int) -> tuple[int, int, int]:
    """AddWithCarry(): (resultado, carry_out, overflow)."""
    unsigned_sum = u32(x) + u32(y) + carry_in
    signed_sum = sint(x) + sint(y) + carry_in
    result = unsigned_sum & MASK32
    carry_out = 0 if result == unsigned_sum else 1
    overflow = 0 if sint(result) == signed_sum else 1
    return result, carry_out, overflow


def lsl_c(x: int, shift: int, n: int = 32) -> tuple[int, int]:
    assert shift > 0
    extended = x << shift
    return extended & ((1 << n) - 1), bit(extended, n)


def lsl(x: int, shift: int) -> int:
    return x if shift == 0 else lsl_c(x, shift)[0]


def lsr_c(x: int, shift: int, n: int = 32) -> tuple[int, int]:
    assert shift > 0
    extended = x & ((1 << n) - 1)
    return extended >> shift, bit(extended, shift - 1) if shift - 1 < n else 0


def lsr(x: int, shift: int) -> int:
    return x if shift == 0 else lsr_c(x, shift)[0]


def asr_c(x: int, shift: int, n: int = 32) -> tuple[int, int]:
    assert shift > 0
    extended = sint(x, n)
    result = (extended >> shift) & ((1 << n) - 1)
    carry = (extended >> (shift - 1)) & 1
    return result, carry


def asr(x: int, shift: int) -> int:
    return x if shift == 0 else asr_c(x, shift)[0]


def ror_c(x: int, shift: int, n: int = 32) -> tuple[int, int]:
    assert shift != 0
    m = shift % n
    result = ((x >> m) | (x << (n - m))) & ((1 << n) - 1) if m else x & ((1 << n) - 1)
    return result, bit(result, n - 1)


def ror(x: int, shift: int) -> int:
    return x if shift == 0 else ror_c(x, shift)[0]


def rrx_c(x: int, carry_in: int, n: int = 32) -> tuple[int, int]:
    return (carry_in << (n - 1)) | ((x & ((1 << n) - 1)) >> 1), bit(x, 0)


SRType = str        # "LSL" | "LSR" | "ASR" | "ROR" | "RRX"


def shift_c(value: int, srtype: SRType, amount: int, carry_in: int) -> tuple[int, int]:
    """Shift_C() (§A7.4.2). RRX usa amount = 1."""
    assert not (srtype == "RRX" and amount != 1)
    if amount == 0:
        return u32(value), carry_in
    return {"LSL": lsl_c, "LSR": lsr_c, "ASR": asr_c, "ROR": ror_c}[srtype](value, amount) \
        if srtype != "RRX" else rrx_c(value, carry_in)


def shift(value: int, srtype: SRType, amount: int, carry_in: int) -> int:
    return shift_c(value, srtype, amount, carry_in)[0]


def decode_imm_shift(srtype2: int, imm5: int) -> tuple[SRType, int]:
    """DecodeImmShift() (§A7.4.2)."""
    if srtype2 == 0:
        return "LSL", imm5
    if srtype2 == 1:
        return "LSR", 32 if imm5 == 0 else imm5
    if srtype2 == 2:
        return "ASR", 32 if imm5 == 0 else imm5
    return ("RRX", 1) if imm5 == 0 else ("ROR", imm5)


def shift_by_register_c(value: int, srtype: SRType, rm: int, carry_in: int) -> tuple[int, int]:
    """Deslocamento por registrador: só o byte baixo de Rm conta (§A7.7.69)."""
    return shift_c(value, srtype, rm & 0xFF, carry_in)


# ───────────────────────────── constantes modificadas (§A5.3.2) ─────────────────

def thumb_expand_imm_c(imm12: int, carry_in: int) -> tuple[int, int]:
    """ThumbExpandImm_C()."""
    if (imm12 >> 10) & 3 == 0:
        byte = imm12 & 0xFF
        kind = (imm12 >> 8) & 3
        if kind == 0:
            imm32 = byte
        elif kind == 1:
            assert byte != 0, "UNPREDICTABLE"
            imm32 = (byte << 16) | byte
        elif kind == 2:
            assert byte != 0, "UNPREDICTABLE"
            imm32 = (byte << 24) | (byte << 8)
        else:
            assert byte != 0, "UNPREDICTABLE"
            imm32 = (byte << 24) | (byte << 16) | (byte << 8) | byte
        return imm32, carry_in
    unrotated = 0x80 | (imm12 & 0x7F)
    return ror_c(unrotated, (imm12 >> 7) & 0x1F)


def encode_modified_imm(value: int) -> int | None:
    """imm12 de uma constante modificada (forma canônica do montador) ou None."""
    value = u32(value)
    b = value & 0xFF
    if value == b:
        return b
    if value == (b << 16 | b) and b:
        return 0x100 | b
    b1 = (value >> 8) & 0xFF
    if value == (b1 << 24 | b1 << 8) and b1:
        return 0x200 | b1
    if value == b * 0x01010101 and b:
        return 0x300 | b
    for rot in range(8, 32):
        unrot = ((value << rot) | (value >> (32 - rot))) & MASK32
        if unrot <= 0xFF and unrot & 0x80:
            return (rot << 7) | (unrot & 0x7F)
    return None


def modified_imm_carry(value: int, carry_in: int) -> int:
    """Carry de MOVS/ANDS/... com constante modificada (PM0056 §3.3.3)."""
    imm12 = encode_modified_imm(value)
    assert imm12 is not None, f"0x{value:08x} não é constante modificada"
    return thumb_expand_imm_c(imm12, carry_in)[1]


# ───────────────────────────── saturação (§A2.2.1) ─────────────────────────────

def signed_sat_q(i: int, n: int) -> tuple[int, int]:
    """SignedSatQ(): (resultado de n bits estendido a 32, saturou)."""
    hi, lo = (1 << (n - 1)) - 1, -(1 << (n - 1))
    if i > hi:
        return u32(hi), 1
    if i < lo:
        return u32(lo), 1
    return u32(i), 0


def unsigned_sat_q(i: int, n: int) -> tuple[int, int]:
    hi = (1 << n) - 1
    if i > hi:
        return u32(hi), 1
    if i < 0:
        return 0, 1
    return u32(i), 0


# ───────────────────────────── condições (§A7.3.1) ─────────────────────────────

CONDS = ("eq", "ne", "cs", "cc", "mi", "pl", "vs", "vc",
         "hi", "ls", "ge", "lt", "gt", "le", "al")
COND_CODE = {name: code for code, name in enumerate(CONDS)}
INVERSE = {"eq": "ne", "ne": "eq", "cs": "cc", "cc": "cs", "mi": "pl", "pl": "mi",
           "vs": "vc", "vc": "vs", "hi": "ls", "ls": "hi", "ge": "lt", "lt": "ge",
           "gt": "le", "le": "gt"}


def condition_passed(cond: str | int, apsr_value: int) -> bool:
    """ConditionHolds() para os 4 bits de condição."""
    code = COND_CODE[cond] if isinstance(cond, str) else cond
    n, z, c, v, _ = flags(apsr_value)
    base = code >> 1
    result = (z == 1, c == 1, n == 1, v == 1, c == 1 and z == 0, n == v,
              n == v and z == 0, True)[base]
    if code & 1 and code != 0b1111:
        result = not result
    return result


# ───────────────────────────── bloco IT (§A7.3.3) ─────────────────────────────

def it_state(firstcond: str, pattern: str) -> int:
    """ITSTATE de `IT<pattern> <firstcond>`; pattern = 'x y z' em 'T'/'E' (sem o 1º T)."""
    fc = COND_CODE[firstcond]
    mask = 0
    for k, ch in enumerate(pattern):
        b = (fc & 1) if ch == "t" else (fc & 1) ^ 1
        mask |= b << (3 - k)
    mask |= 1 << (3 - len(pattern))
    return (fc << 4) | mask


def it_advance(itstate: int) -> int:
    """ITAdvance()."""
    if itstate & 0b111 == 0:
        return 0
    return (itstate & 0xE0) | ((itstate << 1) & 0x1F)


def it_cond(itstate: int) -> int:
    """Condição corrente do bloco: ITSTATE[7:4]."""
    return itstate >> 4


def in_it_block(itstate: int) -> bool:
    return itstate & 0xF != 0


def itstate_to_xpsr(itstate: int) -> int:
    """Posição do ITSTATE no xPSR: IT[1:0] → [26:25], IT[7:2] → [15:10]."""
    return ((itstate & 3) << 25) | ((itstate >> 2) << 10)


ITSTATE_XPSR_MASK = 0x0600_FC00


def it_executes(firstcond: str, pattern: str, apsr_value: int) -> list[bool]:
    """Quais instruções de um bloco IT executam (flags constantes no bloco)."""
    state = it_state(firstcond, pattern)
    out = []
    while in_it_block(state):
        out.append(condition_passed(it_cond(state), apsr_value))
        state = it_advance(state)
    return out


# ───────────────────────────── divisão (§A7.7.127, §A7.7.195) ─────────────────────

def udiv(n: int, m: int) -> int:
    return 0 if u32(m) == 0 else u32(n) // u32(m)


def sdiv(n: int, m: int) -> int:
    """RoundTowardsZero(SInt(n) / SInt(m)); 0x80000000 / -1 = 0x80000000."""
    a, b = sint(n), sint(m)
    if b == 0:
        return 0
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return u32(q)


# ───────────────────────────── bits (§A7.7) ─────────────────────────────

def clz(x: int) -> int:
    x = u32(x)
    return 32 - x.bit_length()


def rbit(x: int) -> int:
    return int(f"{u32(x):032b}"[::-1], 2)


def rev(x: int) -> int:
    return int.from_bytes(u32(x).to_bytes(4, "little"), "big")


def rev16(x: int) -> int:
    x = u32(x)
    return ((x & 0x00FF00FF) << 8 | (x >> 8) & 0x00FF00FF) & MASK32


def revsh(x: int) -> int:
    lo = ((x & 0xFF) << 8) | ((x >> 8) & 0xFF)
    return u32(sint(lo, 16))


def sign_extend(x: int, n: int) -> int:
    return u32(sint(x, n))


def ubfx(x: int, lsb: int, width: int) -> int:
    return (u32(x) >> lsb) & ((1 << width) - 1)


def sbfx(x: int, lsb: int, width: int) -> int:
    return sign_extend(ubfx(x, lsb, width), width)


def bfi(dst: int, src: int, lsb: int, width: int) -> int:
    mask = ((1 << width) - 1) << lsb
    return u32((dst & ~mask) | ((src << lsb) & mask))


def bfc(dst: int, lsb: int, width: int) -> int:
    return u32(dst & ~(((1 << width) - 1) << lsb))


# ───────────────────────────── multiplicação ─────────────────────────────

def umull(a: int, b: int) -> tuple[int, int]:
    """(RdLo, RdHi) do produto sem sinal de 64 bits."""
    p = u32(a) * u32(b)
    return p & MASK32, (p >> 32) & MASK32


def smull(a: int, b: int) -> tuple[int, int]:
    p = (sint(a) * sint(b)) & ((1 << 64) - 1)
    return p & MASK32, p >> 32


def umlal(a: int, b: int, lo: int, hi: int) -> tuple[int, int]:
    p = (u32(a) * u32(b) + ((hi << 32) | lo)) & ((1 << 64) - 1)
    return p & MASK32, p >> 32


def smlal(a: int, b: int, lo: int, hi: int) -> tuple[int, int]:
    p = (sint(a) * sint(b) + sint((hi << 32) | lo, 64)) & ((1 << 64) - 1)
    return p & MASK32, p >> 32


# ───────────────────────────── bit-band (TRM §4.2) ─────────────────────────────

SRAM_BASE, SRAM_ALIAS = 0x2000_0000, 0x2200_0000
PERIPH_BASE, PERIPH_ALIAS = 0x4000_0000, 0x4200_0000


def bitband_alias(addr: int, bit_number: int) -> int:
    """bit_word_addr = bit_band_base + (byte_offset × 32) + (bit_number × 4)."""
    if SRAM_BASE <= addr < SRAM_BASE + 0x10_0000:
        return SRAM_ALIAS + (addr - SRAM_BASE) * 32 + bit_number * 4
    if PERIPH_BASE <= addr < PERIPH_BASE + 0x10_0000:
        return PERIPH_ALIAS + (addr - PERIPH_BASE) * 32 + bit_number * 4
    raise ValueError(f"0x{addr:08x} fora das regiões de bit-band")
