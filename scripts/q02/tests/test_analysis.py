"""Testes de sensibilidade da análise do Q-02 sobre dados reais.

  PYTHONPATH=scripts python3 -m unittest discover -s scripts/q02/tests -t scripts

A fixture (tests/fixture/) é uma execução de cada variante da campanha de
`piloto-01` (Renode 1.17.0, perfil R1), com o leiaute do ELF
dela. Cada teste altera um aspecto do registro e confere que o veredito
muda para o esperado e pelo instrumento certo; o caso sem alteração é
IGUAL. Se spec.py mudar, a fixture tem de ser regenerada de uma campanha
nova (o teste test_fixture_spec avisa).
"""
import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path

from q02 import analysis as A
from q02 import campaign, spec

FIX = Path(__file__).parent / "fixture"
PLAN = json.loads((FIX / "plan.json").read_text())
LAYOUT = campaign.layout_from(PLAN)
VARIANTS = {v: (c["observer"], c["trace"]) for v, c in PLAN["variants"].items()}
BASE = {v: A.read_run(FIX / v, v, 0) for v in VARIANTS}


def runs(mutate=None):
    out = []
    for v in VARIANTS:
        for rep in range(2):
            r = copy.deepcopy(BASE[v])
            r.rep = rep
            if mutate:
                mutate(r)
            out.append(r)
    return out


def failed(res):
    return {c.instrument for c in res.criteria if not c.ok}


def on_events(pred, fn):
    def mut(r):
        r.events = [fn(e) if pred(e) else e for e in r.events if not pred(e) or fn(e) is not None]
    return mut


class Q02(unittest.TestCase):
    def ev(self, mutate=None):
        return A.evaluate(runs(mutate), LAYOUT, VARIANTS)

    def test_fixture_spec(self):
        self.assertEqual(PLAN["spec_hash"], spec.spec_hash(), "regenerar a fixture (spec.py mudou)")

    def test_igual(self):
        res = self.ev()
        self.assertEqual(res.verdict, A.IGUAL, res.why)
        self.assertEqual(res.hooks["offset_B"], {"-1": 8})
        self.assertEqual(len(res.hooks["tail_chain"]), 2)

    # ── escrita ──
    def test_escrita_perdida(self):
        sink = LAYOUT.sink
        drop = lambda e: None                                   # noqa: E731
        res = self.ev(on_events(lambda e: e.kind == "W" and e.data[:2] == (sink, spec.SINK_VALUES[1]), drop))
        self.assertEqual(res.verdict, A.REPROVADO)
        self.assertEqual(failed(res), {"escrita"})

    def test_escrita_na_vizinha_observada(self):
        def mut(r):
            if r.events:
                w = next(e for e in r.events if e.kind == "W" and e.data[0] == LAYOUT.sink and e.data[1])
                r.events.insert(r.events.index(w) + 1, replace(w, data=(LAYOUT.sink + 4, spec.NEIGHBOR_VALUE, "DoubleWord")))
        res = self.ev(mut)
        self.assertEqual(res.verdict, A.REPROVADO)
        self.assertIn("escrita", failed(res))

    def test_escrita_um_tick_depois(self):
        res = self.ev(on_events(lambda e: e.kind == "W", lambda e: replace(e, vt=e.vt + 125)))
        self.assertEqual(failed(res), {"escrita"})

    def test_escrita_valor_errado(self):
        res = self.ev(on_events(lambda e: e.kind == "W" and e.data[0] == spec.ICSR,
                                lambda e: replace(e, data=(e.data[0], e.data[1] | 1, e.data[2]))))
        self.assertEqual(failed(res), {"escrita"})

    # ── exceção ──
    def test_tratador_sem_inicio(self):
        first_b = next(e for e in BASE["hooks"].events if e.kind == "B")
        res = self.ev(on_events(lambda e: e == first_b, lambda e: None))
        self.assertEqual(res.verdict, A.REPROVADO)
        self.assertIn("exceção", failed(res))

    def test_fim_perdido(self):
        last_e = [e for e in BASE["hooks"].events if e.kind == "E"][-1]
        res = self.ev(on_events(lambda e: e == last_e, lambda e: None))
        self.assertIn("exceção", failed(res))

    def test_firmware_conta_diferente(self):
        def mut(r):
            r.rec["n_systick"] += 1
        self.assertIn("exceção", failed(self.ev(mut)))

    def test_aninhamento_nao_visto_pelo_firmware(self):
        def mut(r):
            r.rec["nest_after"] = r.rec["nest_before"]
        self.assertEqual(failed(self.ev(mut)), {"exceção"})

    def test_ordem_trocada(self):
        def mut(r):
            r.rec["systick_saw"][0] += 1
        self.assertEqual(failed(self.ev(mut)), {"exceção"})

    def test_tratador_um_tick_depois(self):
        res = self.ev(on_events(lambda e: e.kind == "H", lambda e: replace(e, vt=e.vt + 125)))
        self.assertEqual(failed(res), {"exceção"})

    def test_entrada_sem_gancho_no_traco(self):
        def mut(r):
            if r.trace is not None:
                h = LAYOUT.handlers[spec.EXC_PENDSV].start
                i = len(r.trace) - 5
                r.trace[i] = h
        self.assertIn("exceção", failed(self.ev(mut)))

    # ── monitor ──
    def test_pausa_fora_do_instante(self):
        def mut(r):
            r.stim = [replace(e, vt=e.vt + 125, instr=e.instr + 1) if e.kind == "M" else e for e in r.stim]
        self.assertEqual(failed(self.ev(mut)), {"monitor"})

    def test_escrita_da_pausa_vista_antes(self):
        """Se a pausa tivesse ocorrido 3 instruções antes do registrado, uma leitura
        anterior à pausa registrada teria visto o valor: o critério de visibilidade acusa."""
        def mut(r):
            r.stim = [replace(e, instr=e.instr + 6, vt=e.vt + 750) if e.kind == "M" else e for e in r.stim]
        res = self.ev(mut)
        self.assertEqual(failed(res), {"monitor"})
        self.assertTrue(any("1ª leitura" in w for w in res.why), res.why)

    def test_leitura_do_monitor_errada(self):
        def mut(r):
            r.stim = [replace(e, data=(0, e.data[1])) if e.kind == "M" else e for e in r.stim]
        self.assertEqual(failed(self.ev(mut)), {"monitor"})

    def test_gancho_de_estimulo_sem_efeito(self):
        def mut(r):
            r.rec["hook_seen"] = 0
        self.assertEqual(failed(self.ev(mut)), {"monitor"})

    # ── não intrusão, determinismo, validade ──
    def test_observador_intrusivo(self):
        def mut(r):
            if r.variant == "full":
                r.rec["wait_iters"][0] += 1
        res = self.ev(mut)
        self.assertEqual(res.verdict, A.REPROVADO)
        self.assertIn("não intrusão", failed(res))

    def test_estimulo_deslocado_pela_observacao(self):
        def mut(r):
            if r.variant == "hooks":
                r.stim = [replace(e, instr=e.instr + 1) if e.kind == "S" else e for e in r.stim]
        self.assertIn("não intrusão", failed(self.ev(mut)))

    def test_nao_deterministico(self):
        def mut(r):
            if r.variant == "bare" and r.rep == 1:
                r.rec["wait_iters"][1] += 1
        self.assertEqual(self.ev(mut).verdict, A.NAO_DET)

    def test_falta_invalida(self):
        def mut(r):
            r.events = r.events + [A.Ev("F", 0x80000EC, 0, 0, (3,))]
        self.assertEqual(self.ev(mut).verdict, A.INVALIDA)

    def test_status_invalida(self):
        def mut(r):
            r.rec["status"] = spec.ST_BAD_PARAM
        self.assertEqual(self.ev(mut).verdict, A.INVALIDA)

    def test_estimulo_ausente_invalida(self):
        def mut(r):
            r.stim = [e for e in r.stim if e.kind != "S"]
        self.assertEqual(self.ev(mut).verdict, A.INVALIDA)


class Parse(unittest.TestCase):
    def test_linhas(self):
        self.assertEqual(A.parse_event("W e000ed04 10000000 DoubleWord 42125 337 80000f8"),
                         A.Ev("W", 0x80000F8, 42125, 337, (0xE000ED04, 0x10000000, "DoubleWord")))
        e = A.parse_event("E 18446744073709551615 64000 513 fffffff1 2100000f 400")
        self.assertEqual((e.ipsr, e.pc, e.off), (15, 0xFFFFFFF1, -1))
        self.assertEqual(A.parse_event("M 200000 1600 80001c4 ec40ec40 0").data, (0xEC40EC40, 0))


class Spec(unittest.TestCase):
    def test_header_e_registro(self):
        h = spec.header()
        self.assertIn(f"0x{spec.MAGIC:08X}UL", h)
        self.assertEqual(sum(n for _, n in spec.REC_FIELDS), spec.REC_WORDS)
        d = spec.decode_rec(list(range(spec.REC_WORDS)))
        self.assertEqual(d["status"], 0)
        self.assertEqual(d["pause_seen"], [spec.REC_WORDS - 2, spec.REC_WORDS - 1])


if __name__ == "__main__":
    unittest.main()
