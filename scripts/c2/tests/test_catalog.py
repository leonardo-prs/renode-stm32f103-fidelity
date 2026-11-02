"""Testes do catálogo, do gerador e do leiaute dos parâmetros (sem toolchain).

  PYTHONPATH=scripts python3 -m unittest discover -s scripts/c2/tests -t scripts
"""
import unittest

from c2 import catalog as K
from c2 import collect, gen


class Catalog(unittest.TestCase):
    def test_c2_09_varredura_completa(self):
        pts = K.c2_09_points()
        self.assertEqual(len(pts), len(K.FREE_LINES) * len(K.MECH))
        self.assertEqual({(p.line, p.mech) for p in pts},
                         {(n, m) for n in K.FREE_LINES for m in K.MECH})
        # As duas palavras do NVIC (linhas 0–31 e 32–42) estão cobertas.
        self.assertTrue(any(p.line < 32 for p in pts) and any(p.line >= 32 for p in pts))

    def test_linhas_livres_sem_fonte_na_plataforma(self):
        """Nenhuma linha livre aparece como destino `nvic@N` no .repl do projeto."""
        repl = (collect.ROOT / collect.PLATFORM).read_text()
        import re
        used = set()
        for m in re.finditer(r"nvic@\[?([\d\-, ]+)\]?", repl):
            for part in m[1].split(","):
                a, _, b = part.strip().partition("-")
                used |= set(range(int(a), int(b or a) + 1))
        self.assertFalse(used & set(K.FREE_LINES), sorted(used & set(K.FREE_LINES)))


class Gen(unittest.TestCase):
    def test_header(self):
        h = gen.header()
        self.assertIn(f"0x{K.MAGIC:08X}UL", h)
        self.assertEqual(h.count("c2_irq_handler, /* IRQ"), len(K.FREE_LINES))
        self.assertEqual(h.count("/* IRQ"), K.N_IRQ)
        self.assertIn(f'C2_CATALOG_HASH "{K.catalog_hash()}"', h)


class Params(unittest.TestCase):
    def test_leiaute(self):
        pts = K.c2_09_points()
        w = dict(collect.param_words("C2-09", pts))
        self.assertEqual((w[0], w[4], w[8]), (K.MAGIC, 9, len(pts)))
        last = pts[-1]
        off = 16 + 4 * (K.N_ARGS * last.index)
        self.assertEqual((w[off], w[off + 4]), (last.line, K.MECH[last.mech]))


if __name__ == "__main__":
    unittest.main()
