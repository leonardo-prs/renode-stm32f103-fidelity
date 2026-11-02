"""Testes da análise do C2 #oD com execuções sintéticas (sensibilidade do veredito).

  PYTHONPATH=scripts python3 -m unittest discover -s scripts/c2/tests -t scripts

O gerador imita o registro real do Renode 1.17.0 (piloto do C2-09): pontos
e tratador com tick = instrução, B e E um tick atrás, escrita no instante
da instrução de escrita. Cada teste altera um aspecto e confere que o
veredito muda para o esperado.
"""
import unittest
from dataclasses import replace

from c2 import analysis as A
from c2 import catalog as K

POINT, HANDLER, HANDLER_END = 0x80000EC, 0x80000F4, 0x800010C
STORE_REQ, STORE_ENA = 0x80002AE, 0x80002E4
LAYOUT = A.Layout(POINT, range(HANDLER, HANDLER_END), frozenset({STORE_REQ, STORE_ENA}))
VARIANTS = {"bare": (False, False), "hooks": (True, False), "full": (True, True)}
PTS = [K.Point(0, 0, "STIR"), K.Point(1, 35, "ISPR")]
T = A.NS_PER_TICK


class Gen:
    """Gera eventos, traço e memória de uma execução do C2-09 conforme o documento."""

    def __init__(self, points=PTS):
        self.ev, self.trace, self.served = [], [0x8000184] * 10, [0] * K.N_IRQ
        self.rec = []
        self.state = {}                      # line -> (enabled, pending, active)
        for p in points:
            self.point(p)

    def _pc(self, pc, n=1):
        self.trace += [pc] * n

    def _words(self, field_):
        w = [0, 0]
        for line, st in self.state.items():
            if st[field_]:
                w[line >> 5] |= 1 << (line & 31)
        return w

    def mark(self, ident):
        i = len(self.trace)
        e, p, a = self._words(0), self._words(1), self._words(2)
        self.ev.append(A.Ev("P", POINT, i * T, i, (ident, e[0], e[1], p[0], p[1], a[0], a[1], 0x800, 0, 0)))
        self._pc(POINT)
        self._pc(0x8000300, 3)

    def write(self, pc, addr, value):
        i = len(self.trace)
        self.ev.append(A.Ev("W", pc, i * T, i, (addr, value)))
        self._pc(pc)

    def irq(self, line):
        i = len(self.trace)
        self.ev.append(A.Ev("B", 0x8000300, (i - 1) * T, i, (5, 0x1000000)))
        self.ev.append(A.Ev("H", HANDLER, i * T, i, (0x1000000 | (16 + line), 0, 0, 0, 0)))
        self._pc(HANDLER, 9)
        self.served[line] += 1
        i = len(self.trace)
        self.ev.append(A.Ev("E", 0xFFFFFFF9, (i - 1) * T, i, (2**64 - 1, 0x1000000 | (16 + line))))
        self._pc(0x8000300)

    def point(self, p):
        line, w, b = p.line, 4 * (p.line >> 5), 1 << (p.line & 31)
        self.state[line] = [0, 0, 0]
        base = self.served[line]
        rec = [0, base]
        self.mark(p.index << 8 | 1)
        if p.mech == "STIR":
            self.write(STORE_REQ, A.STIR, line)
        else:
            self.write(STORE_REQ, A.ISPR + w, b)
        self.state[line][1] = 1
        self._pc(0x8000300, 5)
        rec += [1, self.served[line]]
        self.mark(p.index << 8 | 2)
        self.write(STORE_ENA, A.ISER + w, b)
        self.state[line][0] = 1
        self.state[line][1] = 0
        self.irq(line)
        rec += [0, self.served[line]]
        self.mark(p.index << 8 | 3)
        self.state[line] = [0, 0, 0]
        self.rec.append(rec + [0, 0])

    def mem(self):
        return A.Mem(K.ST_DONE, [list(r) for r in self.rec], list(self.served))


def runs(gen=None, mutate=None):
    g = gen or Gen()
    out = []
    for v, (obs, tr) in VARIANTS.items():
        for rep in range(2):
            out.append(A.Run(v, rep, list(g.ev) if obs else [], g.mem(), list(g.trace) if tr else None))
    for r in out:
        if mutate:
            mutate(r)
    return out


def ev_replace(r, pred, fn):
    r.events = [fn(e) if pred(e) else e for e in r.events]


class C2_09(unittest.TestCase):
    def ev(self, rs, pts=PTS):
        return A.evaluate("C2-09", rs, pts, LAYOUT, VARIANTS)

    def test_igual(self):
        res = self.ev(runs())
        self.assertEqual(res.verdict, A.IGUAL, res.why)
        self.assertEqual(res.checks["points_by_verdict"], {A.IGUAL: 2})
        self.assertEqual(res.hooks["B"], {"-1": 2})

    def test_atendida_desabilitada_diverge(self):
        """A linha é atendida logo após o pedido, ainda desabilitada."""
        g = Gen([])
        p = PTS[0]
        g.state[0] = [0, 0, 0]
        g.mark(0 << 8 | 1)
        g.write(STORE_REQ, A.STIR, 0)
        g.irq(0)
        g.mark(0 << 8 | 2)
        g.write(STORE_ENA, A.ISER, 1)
        g.state[0] = [1, 0, 0]
        g.mark(0 << 8 | 3)
        g.rec.append([0, 0, 0, 1, 0, 1, 0, 0])
        res = self.ev(runs(g), [p])
        self.assertEqual(res.verdict, A.DIVERGE, res.why)
        self.assertTrue(any("PENDING: served = 1" in w for w in res.why), res.why)

    def test_atendida_duas_vezes_diverge(self):
        g = Gen([])
        g.state[0] = [0, 0, 0]
        g.mark(1)
        g.write(STORE_REQ, A.STIR, 0)
        g.state[0][1] = 1
        g.mark(2)
        g.write(STORE_ENA, A.ISER, 1)
        g.state[0] = [1, 0, 0]
        g.irq(0)
        g.irq(0)
        g.mark(3)
        g.rec.append([0, 0, 1, 0, 0, 2, 0, 0])
        res = self.ev(runs(g), [PTS[0]])
        self.assertEqual(res.verdict, A.DIVERGE, res.why)

    def test_pendencia_nao_zerada_diverge(self):
        """Pendência continua 1 depois do atendimento (visto de fora e pelo firmware)."""
        g = Gen()

        def mut(r):
            ev_replace(r, lambda e: e.kind == "P" and e.data[0] == (1 << 8 | 3),
                       lambda e: replace(e, data=e.data[:4] + (e.data[4] | 1 << 3,) + e.data[5:]))
            r.mem.rec[1][A.K.C2_09_REC.index("pend_served")] = 1
        res = self.ev(runs(g, mut))
        self.assertEqual(res.verdict, A.DIVERGE, res.why)
        self.assertEqual(res.points[0].verdict, A.IGUAL)

    def test_estimulo_ausente_invalida(self):
        res = self.ev(runs(mutate=lambda r: setattr(r, "events", [e for e in r.events
                                                                  if not (e.kind == "W" and e.data[0] == A.STIR)])))
        self.assertEqual(res.verdict, A.INVALIDA)

    def test_observadores_discordam_invalida(self):
        def mut(r):
            r.mem.rec[0][A.K.C2_09_REC.index("pend_pending")] = 0
        res = self.ev(runs(mutate=mut))
        self.assertEqual(res.verdict, A.INVALIDA, res.why)
        self.assertTrue(any("firmware vê" in w for w in res.why), res.why)

    def test_inicio_sem_tratador_invalida(self):
        res = self.ev(runs(mutate=lambda r: setattr(r, "events", [e for e in r.events if e.kind != "H"])))
        self.assertEqual(res.verdict, A.INVALIDA)

    def test_falta_invalida(self):
        def mut(r):
            r.events = r.events + [A.Ev("F", 0x8000180, 0, 0, (0x1000003,))]
        self.assertEqual(self.ev(runs(mutate=mut)).verdict, A.INVALIDA)

    def test_status_invalida(self):
        def mut(r):
            r.mem.status = K.ST_BAD_PARAM
        self.assertEqual(self.ev(runs(mutate=mut)).verdict, A.INVALIDA)

    def test_traco_incoerente_invalida(self):
        def mut(r):
            if r.trace is not None:
                i = next(e.instr for e in r.events if e.kind == "H")
                r.trace[i] = 0x8000500
        self.assertEqual(self.ev(runs(mutate=mut)).verdict, A.INVALIDA)

    def test_tempo_dos_ganchos_de_endereco_invalida(self):
        def mut(r):
            ev_replace(r, lambda e: e.kind == "H", lambda e: replace(e, vt=e.vt + T))
        self.assertEqual(self.ev(runs(mutate=mut)).verdict, A.INVALIDA)

    def test_nao_determinismo(self):
        def mut(r):
            if r.variant == "hooks" and r.rep == 1:
                ev_replace(r, lambda e: e.kind == "W", lambda e: replace(e, vt=e.vt + 1))
        self.assertEqual(self.ev(runs(mutate=mut)).verdict, A.NAO_DET)

    def test_observador_intrusivo_invalida(self):
        def mut(r):
            if r.variant == "full":
                r.mem.rec[0][1] = 7
        res = self.ev(runs(mutate=mut))
        self.assertEqual(res.verdict, A.INVALIDA)
        self.assertFalse(res.checks["observer_non_intrusive"])


class Parse(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(A.parse_event("B 5 237000 1897 80002e8 1000000"),
                         A.Ev("B", 0x80002E8, 237000, 1897, (5, 0x1000000)))
        self.assertEqual(A.parse_event("W e000ef00 23 222875 1783 80002ae"),
                         A.Ev("W", 0x80002AE, 222875, 1783, (0xE000EF00, 0x23)))
        e = A.parse_event("H 80000f4 237125 1897 1000033 0 8 0 0")
        self.assertEqual((e.ipsr, e.off), (0x33, 0))


if __name__ == "__main__":
    unittest.main()
