"""Gate de relógio da placa (abi.clock_checks, FID-08)."""
import unittest

from c1 import abi

RESET = {"flash_acr": 0x30, "rcc_cr": 0x0000_6A83, "rcc_cfgr": 0}   # HSICAL de fábrica em [15:8]


def snap(**header) -> abi.Snapshot:
    return abi.Snapshot({**RESET, **header}, [], 0)


class ClockChecks(unittest.TestCase):
    def test_reset_state_passes(self):
        self.assertEqual(abi.clock_checks(snap()), [])

    def test_wait_state_fails(self):
        self.assertEqual(len(abi.clock_checks(snap(flash_acr=0x32))), 1)

    def test_prefetch_off_fails(self):
        self.assertEqual(len(abi.clock_checks(snap(flash_acr=0x00))), 1)

    def test_pll_or_divider_fails(self):
        self.assertEqual(len(abi.clock_checks(snap(rcc_cr=0x0300_6A83))), 1)
        self.assertEqual(len(abi.clock_checks(snap(rcc_cfgr=0x0000_000A))), 1)
        self.assertEqual(len(abi.clock_checks(snap(rcc_cfgr=0x0000_0400))), 1)   # APB1 / 2

    def test_renode_reads_are_not_reset_state(self):
        # Renode 1.17.0: FLASH_ACR não declarado (lê 0), RCC_CR é tag 0x83.
        self.assertEqual(len(abi.clock_checks(snap(flash_acr=0, rcc_cr=0x83))), 1)


if __name__ == "__main__":
    unittest.main()
