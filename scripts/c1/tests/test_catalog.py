"""Consistência do catálogo: todo oráculo roda em todo vetor e os lotes cabem."""
import unittest

from c1 import gen
from c1.catalog import Alt


class Catalog(unittest.TestCase):
    def test_oracles_cover_every_vector(self):
        for preset in ("c1-func", "c1-layout"):
            g = gen.generate(preset)
            for form in g.forms:
                for vec in form.vectors():
                    exp = form.oracle(vec)
                    self.assertTrue(set(exp) <= set(form.fields), form.name)
                    for value in exp.values():
                        self.assertTrue(value is None or isinstance(value, (int, str, tuple, Alt)),
                                        f"{form.name}: {value!r}")

    def test_batches_fit_the_snapshot(self):
        for preset in ("c1-func", "c1-cycle"):
            g = gen.generate(preset)
            p = g.preset
            for b in g.batches:
                if preset == "c1-func":
                    self.assertLessEqual(b.words(g.forms), p.max_words)
                    self.assertLessEqual(len(b.entries), p.max_records)
                else:
                    self.assertLessEqual(sum(g.forms[i].words for i in b.variants), p.max_words)
                    self.assertLessEqual(len(b.variants), p.max_records)

    def test_every_form_is_in_exactly_one_place(self):
        g = gen.generate("c1-func")
        covered = {}
        for b in g.batches:
            for e in b.entries:
                covered.setdefault(e.form, []).append((e.first, e.count))
        for idx, form in enumerate(g.forms):
            spans = sorted(covered[idx])
            self.assertEqual(spans[0][0], 0, form.name)
            self.assertEqual(sum(c for _, c in spans), form.count, form.name)


if __name__ == "__main__":
    unittest.main()
