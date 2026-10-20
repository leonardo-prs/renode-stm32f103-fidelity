"""Testes do gate da USART1 (fio PA9→PA10 permanente) e do combine sem perfil base."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from c1 import analysis, campaign
from c1.disasm import Decoded


def dump(words: list[int]) -> SimpleNamespace:
    """Saída de objdump -s com as palavras dadas (little-endian)."""
    hexw = " ".join(w.to_bytes(4, "little").hex() for w in words)
    return SimpleNamespace(stdout=f"Contents of section .text:\n 08000000 {hexw}  ................\n")


class UsartGate(unittest.TestCase):
    def check(self, words, insns):
        dis = {i * 4: Decoded(i * 4, 32, m, o) for i, (m, o) in enumerate(insns)}
        with mock.patch.object(campaign.targets, "run_command", return_value=dump(words)), \
                mock.patch.object(campaign.disasm, "disassemble", return_value=dis):
            return campaign.usart_literals(Path("x.elf"), [".text"])

    def test_literal_is_found(self):
        self.assertEqual(self.check([0x1234, 0x4001_3804], []), ["0x40013804"])

    def test_movw_movt_pair_is_found(self):
        found = self.check([], [("movw", "r3, #14336"), ("adds", "r0, #1"), ("movt", "r3, #16385")])
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("0x40013800"))

    def test_other_peripheral_passes(self):
        # GPIOB (0x40010C00) e um MOVT de outro registrador não disparam.
        self.assertEqual(self.check([0x4001_0C00], [("movw", "r3, #14336"), ("movt", "r2, #16385")]),
                         [])


class CombineWithoutBase(unittest.TestCase):
    def test_doc_only_campaign_is_not_diverge(self):
        out = {"renode": {"renode-doc": {"result": analysis.IGUAL}}}
        self.assertEqual(analysis.combine(out, False), analysis.CONFIG)

    def test_no_renode_is_invalid(self):
        self.assertEqual(analysis.combine({"renode": {}}, False), analysis.INVALID)


if __name__ == "__main__":
    unittest.main()
