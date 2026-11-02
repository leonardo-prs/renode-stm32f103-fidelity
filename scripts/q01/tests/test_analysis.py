"""Testes da análise do Q-01 com execuções sintéticas.

  PYTHONPATH=scripts python3 -m unittest discover -s scripts/q01/tests -t scripts
"""
import unittest

from q01 import analysis as A

POINTS = [(0, 0x100), (1, 0x110), (2, 0x120)]
VARIANTS = {"bare": (False, False), "hooks": (True, False), "full": (True, True)}
PASSES = 2
# Instruções entre pontos consecutivos (inclui a volta p2 → p0 da passagem seguinte).
GAPS = [3, 5, 7, 3, 5]


def synthetic(cyc0=10, vt0=1000):
    order = [a for _ in range(PASSES) for _, a in POINTS]
    trace, hooks, cyc = [0x50], [], []
    t, c, i = vt0, cyc0, 40
    for k, pc in enumerate(order):
        hooks.append((pc, t, i))
        cyc.append(c % A.U32)
        trace.append(pc)
        if k < len(GAPS):
            g = GAPS[k]
            trace += [0x200 + j for j in range(g - 1)]
            t, c, i = t + g * A.NS_PER_TICK, c + g, i + g
    return hooks, cyc, trace


def runs(over=None):
    hooks, cyc, trace = synthetic()
    out = []
    for v, (h, t) in VARIANTS.items():
        for rep in range(2):
            out.append(A.Run(v, rep, list(hooks) if h else None, list(cyc), list(trace) if t else None, None))
    for (v, rep), f in (over or {}).items():
        f(next(r for r in out if r.variant == v and r.rep == rep))
    return out


class Evaluate(unittest.TestCase):
    def ev(self, rs):
        return A.evaluate(rs, POINTS, PASSES, VARIANTS)

    def test_igual(self):
        res = self.ev(runs())
        self.assertEqual(res.verdict, A.IGUAL, res.why)
        self.assertEqual(res.checks["segments"], len(GAPS))
        self.assertEqual([s.d_trace for s in res.segments], GAPS)

    def test_cyccnt_wraps(self):
        hooks, cyc, trace = synthetic(cyc0=A.U32 - 4)
        r = A.Run("full", 0, hooks, cyc, trace, None)
        self.assertEqual([s.d_cyc for s in A.segments(r, POINTS)], GAPS)

    def test_vt_diverge(self):
        def bump(r):
            r.hooks[2] = (r.hooks[2][0], r.hooks[2][1] + A.NS_PER_TICK, r.hooks[2][2])
        res = self.ev(runs({("full", 0): bump, ("full", 1): bump, ("hooks", 0): bump, ("hooks", 1): bump}))
        self.assertEqual(res.verdict, A.DIVERGE)
        self.assertFalse(res.segments[1].agree)

    def test_intrusive_observer(self):
        def shift(r):
            r.cyc = [c + 1 for c in r.cyc]
        res = self.ev(runs({("bare", 0): shift, ("bare", 1): shift}))
        self.assertEqual(res.verdict, A.DIVERGE)
        self.assertFalse(res.checks["observer_non_intrusive"])

    def test_nondeterministic(self):
        def shift(r):
            r.cyc = [c + 1 for c in r.cyc]
        res = self.ev(runs({("bare", 1): shift}))
        self.assertEqual(res.verdict, A.NAO_DET)

    def test_invalid_missing_mem(self):
        def drop(r):
            r.cyc = None
        self.assertEqual(self.ev(runs({("hooks", 0): drop})).verdict, A.INVALIDA)

    def test_invalid_order(self):
        def swap(r):
            r.hooks[0], r.hooks[1] = r.hooks[1], r.hooks[0]
        self.assertEqual(self.ev(runs({("full", 0): swap})).verdict, A.INVALIDA)

    def test_invalid_fault(self):
        def fault(r):
            r.fault = "118 5000"
        self.assertEqual(self.ev(runs({("bare", 0): fault})).verdict, A.INVALIDA)


if __name__ == "__main__":
    unittest.main()
