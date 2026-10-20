"""Testes do oráculo contra os exemplos resolvidos das fontes.

O oráculo (scripts/c1/arm.py) precisa estar certo ANTES de qualquer
execução: se ele errasse, placa e Renode "divergiriam da especificação" pelo
motivo errado. Cada teste cita a fonte do exemplo.

    PYTHONPATH=scripts python3 -m unittest discover -s scripts/c1/tests
"""
import unittest

from c1 import arm


def flags_of(result, c, v):
    n, z = arm.nz(result)
    return (n, z, c, v)


class AddWithCarryYiu(unittest.TestCase):
    """Yiu, 3ª ed., Tab. 4.7 — com a linha 2 corrigida (o livro imprime 0x30000000)."""

    ROWS = [  # (op, x, y, resultado, N, Z, C, V)
        ("+", 0x70000000, 0x70000000, 0xE0000000, 1, 0, 0, 1),
        ("+", 0x90000000, 0x90000000, 0x20000000, 0, 0, 1, 1),
        ("+", 0x80000000, 0x80000000, 0x00000000, 0, 1, 1, 1),
        ("-", 0x00001234, 0x00001000, 0x00000234, 0, 0, 1, 0),
        ("-", 0x00000004, 0x00000005, 0xFFFFFFFF, 1, 0, 0, 0),
        ("-", 0xFFFFFFFF, 0xFFFFFFFC, 0x00000003, 0, 0, 1, 0),
        ("-", 0x80000005, 0x80000004, 0x00000001, 0, 0, 1, 0),
        ("-", 0x70000000, 0xF0000000, 0x80000000, 1, 0, 0, 1),
        ("-", 0xA0000000, 0xA0000000, 0x00000000, 0, 1, 1, 0),
    ]

    def test_rows(self):
        for op, x, y, res, n, z, c, v in self.ROWS:
            if op == "+":
                r, co, ov = arm.add_with_carry(x, y, 0)
            else:
                r, co, ov = arm.add_with_carry(x, arm.u32(~y), 1)
            self.assertEqual(r, res, f"{x:#x} {op} {y:#x}")
            self.assertEqual(flags_of(r, co, ov), (n, z, c, v), f"{x:#x} {op} {y:#x}")


class Division(unittest.TestCase):
    def test_sdiv_overflow(self):
        # ARM ARM §A7.7.127: 0x80000000 / 0xFFFFFFFF = 0x80000000.
        self.assertEqual(arm.sdiv(0x80000000, 0xFFFFFFFF), 0x80000000)

    def test_round_towards_zero(self):
        self.assertEqual(arm.sdiv(arm.u32(-7), 2), arm.u32(-3))
        self.assertEqual(arm.sdiv(7, arm.u32(-2)), arm.u32(-3))
        self.assertEqual(arm.sdiv(arm.u32(-7), arm.u32(-2)), 3)

    def test_div_by_zero_returns_zero(self):
        # TRM r1p1 Tab. 18-1 nota e: "A divisor of zero returns zero".
        self.assertEqual(arm.udiv(123, 0), 0)
        self.assertEqual(arm.sdiv(arm.u32(-5), 0), 0)


class Shifts(unittest.TestCase):
    """PM0056 §3.3.4 e a tabela de FS-03/FS-04 do material-base."""

    CASES = [  # (tipo, entrada, Rm, resultado, carry; None = preservado)
        ("LSL", 0x80000001, 32, 0x00000000, 1),
        ("LSL", 0x80000001, 33, 0x00000000, 0),
        ("LSR", 0x80000001, 32, 0x00000000, 1),
        ("LSR", 0x80000001, 33, 0x00000000, 0),
        ("ASR", 0x80000000, 40, 0xFFFFFFFF, 1),
        ("ASR", 0x7FFFFFFF, 40, 0x00000000, 0),
        ("ROR", 0x80000001, 32, 0x80000001, 1),
        ("ROR", 0x80000001, 33, 0xC0000000, 1),
        ("LSL", 0x80000001, 256, 0x80000001, None),
        ("LSL", 0x12345678, 0x120, 0x00000000, 0),
    ]

    def test_by_register(self):
        for kind, x, rm, res, carry in self.CASES:
            for cin in (0, 1):
                r, c = arm.shift_by_register_c(x, kind, rm, cin)
                self.assertEqual(r, res, f"{kind} {x:#x} by {rm}")
                self.assertEqual(c, cin if carry is None else carry, f"{kind} {x:#x} by {rm}")

    def test_rrx(self):
        self.assertEqual(arm.rrx_c(0x00000003, 1), (0x80000001, 1))
        self.assertEqual(arm.rrx_c(0x00000002, 0), (0x00000001, 0))

    def test_decode_imm_shift(self):
        self.assertEqual(arm.decode_imm_shift(1, 0), ("LSR", 32))
        self.assertEqual(arm.decode_imm_shift(2, 0), ("ASR", 32))
        self.assertEqual(arm.decode_imm_shift(3, 0), ("RRX", 1))


class ModifiedImmediates(unittest.TestCase):
    """PM0056 §3.3.3: só a forma rotacionada altera o carry."""

    def test_carry(self):
        for value, cin, carry in ((0x000000AB, 1, 1), (0x00AB00AB, 1, 1), (0xAB00AB00, 1, 1),
                                  (0xABABABAB, 1, 1), (0x80000000, 0, 1), (0x00000FF0, 1, 0)):
            self.assertEqual(arm.modified_imm_carry(value, cin), carry, f"{value:#x}")

    def test_roundtrip(self):
        for value in (0, 1, 0xFF, 0x00AB00AB, 0xAB00AB00, 0xABABABAB, 0x80000000, 0xFF0, 0x3FC00):
            imm12 = arm.encode_modified_imm(value)
            self.assertIsNotNone(imm12)
            self.assertEqual(arm.thumb_expand_imm_c(imm12, 0)[0], value)
        self.assertIsNone(arm.encode_modified_imm(0x12345678))


class Saturation(unittest.TestCase):
    def test_examples(self):
        # Exemplos de FQ-01/FQ-02 (material-base, conferidos com §A7.7.152/213).
        self.assertEqual(arm.signed_sat_q(300, 8), (0x7F, 1))
        self.assertEqual(arm.signed_sat_q(-300, 8), (0xFFFFFF80, 1))
        self.assertEqual(arm.signed_sat_q(-32768, 16), (0xFFFF8000, 0))
        self.assertEqual(arm.unsigned_sat_q(-5, 8), (0, 1))
        self.assertEqual(arm.unsigned_sat_q(255, 8), (255, 0))


class Bits(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(arm.clz(0), 32)
        self.assertEqual(arm.clz(1), 31)
        self.assertEqual(arm.clz(0x80000000), 0)
        self.assertEqual(arm.rev(0x11223344), 0x44332211)
        self.assertEqual(arm.rev16(0x11223344), 0x22114433)
        self.assertEqual(arm.revsh(0x000080FF), 0xFFFFFF80)
        self.assertEqual(arm.revsh(0x12345678), 0x00007856)
        self.assertEqual(arm.rbit(1), 0x80000000)
        self.assertEqual(arm.sign_extend(0x80, 8), 0xFFFFFF80)
        self.assertEqual(arm.ubfx(0xF0000000, 28, 4), 0xF)
        self.assertEqual(arm.sbfx(0xF0000000, 28, 4), 0xFFFFFFFF)
        self.assertEqual(arm.sbfx(0x80, 0, 8), 0xFFFFFF80)
        self.assertEqual(arm.ubfx(0x12345678, 0, 32), 0x12345678)


class Multiply(unittest.TestCase):
    def test_examples(self):
        # FM-03 (material-base): (RdLo, RdHi).
        self.assertEqual(arm.umull(0xFFFFFFFF, 0xFFFFFFFF), (0x00000001, 0xFFFFFFFE))
        self.assertEqual(arm.smull(0x80000000, 0x80000000), (0x00000000, 0x40000000))
        self.assertEqual(arm.smull(0x7FFFFFFF, 0x80000000), (0x80000000, 0xC0000000))


class BitBand(unittest.TestCase):
    def test_examples(self):
        # RM0008 §3.3.2: bit 2 do byte em 0x20000300 ↔ 0x22006008.
        self.assertEqual(arm.bitband_alias(0x20000300, 2), 0x22006008)
        self.assertEqual(arm.bitband_alias(0x20000000, 0), 0x22000000)
        self.assertEqual(arm.bitband_alias(0x20004FFF, 7), 0x2209FFFC)
        # FBB-04: RCC_APB2ENR.IOPBEN (0x40021018, bit 3) e GPIOB_ODR bit 5.
        self.assertEqual(arm.bitband_alias(0x40021018, 3), 0x4242030C)
        self.assertEqual(arm.bitband_alias(0x40010C0C, 5), 0x42218194)


class Conditions(unittest.TestCase):
    def test_table(self):
        # ARM ARM Tab. A7-1, conferindo algumas linhas de cada grupo.
        z = arm.apsr(0, 1, 0, 0)
        self.assertTrue(arm.condition_passed("eq", z))
        self.assertFalse(arm.condition_passed("ne", z))
        hi = arm.apsr(0, 0, 1, 0)
        self.assertTrue(arm.condition_passed("hi", hi))
        self.assertFalse(arm.condition_passed("hi", arm.apsr(0, 1, 1, 0)))
        self.assertTrue(arm.condition_passed("ge", arm.apsr(1, 0, 0, 1)))
        self.assertTrue(arm.condition_passed("lt", arm.apsr(1, 0, 0, 0)))
        self.assertFalse(arm.condition_passed("gt", arm.apsr(0, 1, 0, 0)))
        self.assertTrue(arm.condition_passed("le", arm.apsr(0, 1, 0, 0)))
        for value in range(16):
            self.assertTrue(arm.condition_passed("al", value << 28))
            for c in arm.INVERSE:
                self.assertNotEqual(arm.condition_passed(c, value << 28),
                                    arm.condition_passed(arm.INVERSE[c], value << 28))


class ItState(unittest.TestCase):
    def test_fen09(self):
        # FEN-09 (a) ITT EQ e (b) ITTE EQ: ITSTATE depois da 1ª instrução.
        a = arm.it_advance(arm.it_state("eq", "t"))
        b = arm.it_advance(arm.it_state("eq", "te"))
        self.assertEqual(arm.itstate_to_xpsr(a), 0x00000800)
        self.assertEqual(arm.itstate_to_xpsr(b), 0x00000C00)

    def test_lengths(self):
        # O bloco tem 1 + len(pattern) instruções (Tab. A7-2: máscara).
        for pattern in ("", "t", "e", "tt", "te", "et", "ttt", "eee", "tet"):
            for cond in ("eq", "ne", "cs", "gt"):
                self.assertEqual(len(arm.it_executes(cond, pattern, 0)), 1 + len(pattern))

    def test_semantics(self):
        z1 = arm.apsr(0, 1, 0, 0)
        self.assertEqual(arm.it_executes("eq", "te", z1), [True, True, False])
        self.assertEqual(arm.it_executes("eq", "te", 0), [False, False, True])
        self.assertEqual(arm.it_executes("ne", "eee", z1), [False, True, True, True])


if __name__ == "__main__":
    unittest.main()
