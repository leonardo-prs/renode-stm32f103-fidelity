"""Testes da aritmética temporal (timing.fit) e dos estimadores de Kalibera."""
import unittest
from fractions import Fraction

from c1 import timing
from c1.analysis import variance_levels


class Fit(unittest.TestCase):
    def test_linear_integer(self):
        f = timing.fit((10, 18, 26), (8, 16, 24))
        self.assertEqual((f.c, f.o, f.linear), (Fraction(1), Fraction(2), True))

    def test_fractional_cost_is_exact(self):
        # c = 3/2 por unidade (padrão que se repete a cada duas unidades).
        f = timing.fit((14, 26, 38), (8, 16, 24))
        self.assertEqual(f.c, Fraction(3, 2))
        self.assertTrue(f.linear)

    def test_nonlinear_is_flagged(self):
        f = timing.fit((11, 23, 34), (8, 16, 24))
        self.assertFalse(f.linear)

    def test_empty_block(self):
        f = timing.fit((1, 1, 1), (0, 0, 0))
        self.assertIsNone(f.c)
        self.assertEqual(f.o, 1)


class Kalibera(unittest.TestCase):
    def test_no_variation_is_rule_1(self):
        st = variance_levels([[2.0] * 30 for _ in range(30)])
        self.assertEqual((st["T1^2"], st["T2^2"], st["rule"]), (0, 0, 1))

    def test_iteration_noise_only_is_rule_2(self):
        y = [[1.0, 2.0] * 15 for _ in range(30)]
        self.assertEqual(variance_levels(y)["rule"], 2)

    def test_execution_variation_is_rule_3(self):
        y = [[float(j % 3)] * 10 + [float(j % 3) + 0.5] * 10 for j in range(30)]
        st = variance_levels(y)
        self.assertGreater(st["T2^2"], 0)
        self.assertEqual(st["rule"], 3)

    def test_needs_two_levels(self):
        self.assertIsNone(variance_levels([[1.0, 1.0]]))


if __name__ == "__main__":
    unittest.main()
