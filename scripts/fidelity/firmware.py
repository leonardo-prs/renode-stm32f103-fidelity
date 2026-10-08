"""Registro dos firmwares finais (fonte única p/ coletor, análise e relatório).

Cada firmware = (cenário, variante) da ABI v2. As condições espelham os
códigos usados no C; `fields` nomeia v0..v5 das rows dessa condição.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Firmware:
    name: str
    scenario: int
    variant: int
    title: str
    conditions: dict[int, str]
    fields: dict[int, tuple[str, ...]] = field(default_factory=dict)
    uart_loopback: bool = False      # Renode: UARTHub com loopback no usart1
    timeout_s: float = 30.0          # limite de wall-clock de UMA execução
    elf_override: Path | None = None # build de diagnóstico (FINAL_DEFS)

    @property
    def elf(self) -> Path:
        return self.elf_override or ROOT / "build" / self.name / "firmware.elf"

    def field_names(self, condition: int) -> tuple[str, ...]:
        names = self.fields.get(condition) or self.fields.get(-1) or ()
        return tuple(names) + tuple(f"v{i}" for i in range(len(names), 6))


S1A_KERNELS = {
    1: "loop", 2: "alu", 3: "mul", 4: "udiv_fast", 5: "udiv_slow", 6: "ldr",
    7: "ldr_dep", 8: "str", 9: "ldr_flash", 10: "branch", 11: "ldm", 12: "mix",
    13: "alu_ram", 14: "ldr_ram",
}

FIRMWARES: dict[str, Firmware] = {}


def _register(fw: Firmware) -> Firmware:
    FIRMWARES[fw.name] = fw
    return fw


_register(Firmware(
    "s1a", 1, 1, "S1A — custo por classe de instrução",
    {0: "context", **S1A_KERNELS},
    {0: ("w0", "w1", "w2", "w3", "w4", "w5"), -1: ("iterations", "ticks", "signature")},
))


_register(Firmware(
    "s1b", 1, 2, "S1B — cargas de aplicação em C (-O2)",
    {1: "crc32", 2: "isort", 3: "matmul", 4: "fir", 5: "memcpy", 6: "isqrt", 7: "empty"},
    {-1: ("ticks", "signature")},
))


_register(Firmware(
    "s2a", 2, 1, "S2A — latência de IRQ periódica e razão CPU/periférico",
    {1: "alu", 2: "div", 3: "ldm", 4: "wfi", 5: "masked", 6: "wfi_nodbg"},
    {-1: ("latency", "dwt_entry", "work", "dbgmcu_cr")},
))


_register(Firmware(
    "s2b", 2, 2, "S2B — semântica de eventos TIM2 → NVIC",
    {1: "uif_no_uie", 2: "coalesce", 3: "clear_both", 4: "stale_pending",
     5: "late_clear", 6: "late_clear_apb2", 7: "late_clear_dsb",
     8: "psc_buffered", 9: "ug_uif", 10: "arr_preload", 11: "late_clear_rb"},
    {1: ("uif", "nvic_pending"),
     2: ("uif", "pending_after_run", "pending_at_enable", "isr_entries", "first_sr", "spurious"),
     3: ("uif", "pending_after_run", "pending_at_enable", "isr_entries", "first_sr", "spurious"),
     4: ("uif", "pending_after_run", "pending_at_enable", "isr_entries", "first_sr", "spurious"),
     5: ("isr_entries", "spurious", "ppre1"),
     6: ("isr_entries", "spurious", "ppre1"),
     7: ("isr_entries", "spurious", "ppre1"),
     8: ("base_period", "write_to_update", "next_period", "ref_to_write"),
     9: ("uif_before", "uif_after_ug", "cnt_after_ug"),
     10: ("base_period", "write_to_update", "next_period", "ref_to_write"),
     11: ("isr_entries", "spurious", "ppre1")},
))


_register(Firmware(
    "s3a", 3, 1, "S3A — USART1 em loopback: integridade e flags",
    {0: "context", 1: "ping_pong", 2: "full_duplex", 3: "overrun", 4: "rxne_irq",
     5: "txe_irq", 6: "idle", 7: "tc", 8: "te_off"},
    {0: ("brr", "cr1", "cr2", "cr3"),
     1: ("received", "mismatches", "timeouts"),
     2: ("received", "mismatches", "tx_ahead_max", "ore_seen", "sent"),
     3: ("sr_after_burst", "dr_byte_index", "sr_after_dr", "drained_more", "dr_value", "drained_in_order"),
     4: ("received", "mismatches", "isr_entries", "stranded_after", "nvic_pending_after"),
     5: ("received", "mismatches", "isr_entries", "tx_by_isr"),
     6: ("rxne_seen", "idle_seen", "sr_before", "sr_after"),
     7: ("tc_after_clear", "tc_right_after_write", "tc_after_2_frames"),
     8: ("rx_seen", "byte")},
    uart_loopback=True,
))


_register(Firmware(
    "s3b", 3, 2, "S3B — temporização de quadro da USART1",
    {0: "context", 1: "single", 2: "burst", 3: "tc_8"},
    {0: ("brr", "cr1"),
     1: ("t_txe", "t_tc", "t_rxne", "t_idle", "byte_ok"),
     2: ("t_write", "t_rxne", "byte_ok"),
     3: ("t_tc_final",)},
    uart_loopback=True,
))


_register(Firmware(
    "s4a", 4, 1, "S4A — preempção × arbitragem no NVIC",
    {1: "preempt", 2: "same_group_sub", 3: "equal", 4: "preempt_swapped",
     5: "lower_requested", 6: "arb_group", 7: "arb_sub", 8: "arb_number",
     9: "arb_number_rev", 10: "basepri", 11: "self_repend"},
    {-1: ("order", "ipsr", "icsr", "iabr", "msp_delta", "delta_ticks")},
))


_register(Firmware(
    "s4b", 4, 2, "S4B — late-arrival × preempção × sequencial (TIM1 UP/CC1)",
    {1: "race"},
    {-1: ("delta", "l_cnt", "h_cnt", "order_iabr", "tL_minus_tH", "tL_minus_tHexit")},
))


def get(name: str) -> Firmware:
    try:
        return FIRMWARES[name]
    except KeyError:
        raise SystemExit(f"firmware desconhecido: {name} (conhecidos: {', '.join(FIRMWARES)})")
