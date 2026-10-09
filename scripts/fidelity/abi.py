"""Decodificador do snapshot ABI v3 ("FID3"), espelho de inc/fidelity.h.

O decodificador REJEITA (SnapshotError) qualquer snapshot que não seja
exatamente o objeto `fid_snapshot` de um firmware FID3: magic, versão,
tamanho, layout derivado das capacidades, contagens dentro das
capacidades, casos contíguos, tickets únicos e crescentes por escritor.
Ele não interpreta resultados (isso é dos oráculos c1..c4.py).

Tempo: os eventos guardam o CYCCNT bruto (32 bits). `timeline()` reconstrói
um eixo contínuo percorrendo TODOS os eventos na ordem global dos tickets
(ver inc/fidelity.h): cada passo soma a diferença módulo 2^32 ao anterior.
A reconstrução é aceita só se cada passo for < 2^31 ticks (≈ 268 s a
8 MHz); um passo maior significa tempo andando "para trás" ou uma lacuna
grande demais para descartar estouros múltiplos — o trace é rejeitado.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = 0x33444946            # b"FID3"
ABI_VERSION = 3
HEADER_WORDS = 40
HEADER_BYTES = HEADER_WORDS * 4
CASE_BYTES = 16
EVENT_BYTES = 16
WRAP = 1 << 32
MAX_STEP = 1 << 31

HEADER_FIELDS = (
    "magic", "abi_version", "snapshot_bytes", "firmware_id", "state", "error",
    "run_nonce", "case_planned", "case_capacity", "case_count", "word_capacity",
    "word_count", "ring_capacity", "writer_count",
    "ring_head0", "ring_head1", "ring_head2", "ring_head3",
    "ticket_next", "dwt_start", "dwt_end", "observer_ticks", "log_ticks",
    "core_hz", "cpuid", "idcode", "flash_kb", "uid0", "uid1", "uid2",
    "rcc_cr", "rcc_cfgr", "flash_acr", "dbgmcu_cr", "aircr", "stack_free",
    "fault_pc", "fault_cfsr", "reserved0", "reserved1",
)
assert len(HEADER_FIELDS) == HEADER_WORDS

STATES = {0: "INIT", 1: "RUNNING", 2: "DONE", 3: "FAILED"}
CASE_STATUS = {0: "OPEN", 1: "OK", 2: "TIMEOUT"}
ERROR_BITS = {
    0: "CASES_FULL", 1: "WORDS_FULL", 2: "PROTOCOL", 3: "FAULT",
    4: "STACK", 5: "WRITER", 6: "PLAN",
}

# Eventos genéricos (enum FidEventId); cada cenário define >= 0x100.
EV_BOOT, EV_CALIBRATE, EV_CASE_BEGIN, EV_CASE_END, EV_FINISH = 1, 2, 3, 4, 5
GENERIC_EVENTS = {EV_BOOT: "boot", EV_CALIBRATE: "calibrate",
                  EV_CASE_BEGIN: "case_begin", EV_CASE_END: "case_end",
                  EV_FINISH: "finish"}


class SnapshotError(ValueError):
    """Snapshot inválido: o instrumento não produziu um registro confiável."""


@dataclass(frozen=True)
class Event:
    writer: int
    index: int          # posição absoluta no anel do escritor (0 = 1º escrito)
    ticks: int          # CYCCNT bruto
    ticket: int
    event: int
    case_id: int
    arg: int


@dataclass(frozen=True)
class Case:
    case_id: int
    status: str
    words: tuple[int, ...]


@dataclass
class Snapshot:
    header: dict
    cases: list[Case]
    events: list[list[Event]]          # por escritor, em ordem de escrita
    lost: list[int]                    # registros sobrescritos por escritor
    raw_size: int
    notes: list[str] = field(default_factory=list)

    @property
    def state(self) -> str:
        return STATES[self.header["state"]]

    @property
    def errors(self) -> list[str]:
        e = self.header["error"]
        return [name for bit, name in ERROR_BITS.items() if e & (1 << bit)]

    @property
    def complete_trace(self) -> bool:
        return not any(self.lost)

    def case(self, case_id: int) -> Case | None:
        for c in self.cases:
            if c.case_id == case_id:
                return c
        return None

    def all_events(self) -> list[Event]:
        """Todos os eventos na ordem global (ticket)."""
        return sorted((e for w in self.events for e in w), key=lambda e: e.ticket)


def _u32(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<I", raw, offset)[0]


def layout(case_capacity: int, word_capacity: int, writer_count: int,
           ring_capacity: int) -> tuple[int, int, int, int]:
    """Offsets (cases, words, ring) e tamanho total esperado."""
    cases_off = HEADER_BYTES
    words_off = cases_off + CASE_BYTES * case_capacity
    ring_off = words_off + 4 * word_capacity
    total = ring_off + EVENT_BYTES * writer_count * ring_capacity
    return cases_off, words_off, ring_off, total


def decode(raw: bytes) -> Snapshot:
    if len(raw) < HEADER_BYTES:
        raise SnapshotError(f"snapshot truncado: {len(raw)} B < header {HEADER_BYTES} B")
    h = dict(zip(HEADER_FIELDS, struct.unpack_from(f"<{HEADER_WORDS}I", raw, 0)))
    if h["magic"] != MAGIC:
        raise SnapshotError(f"magic 0x{h['magic']:08x} != FID3 (firmware não inicializou?)")
    if h["abi_version"] != ABI_VERSION:
        raise SnapshotError(f"ABI v{h['abi_version']} incompatível (esperado v{ABI_VERSION})")
    if h["snapshot_bytes"] != len(raw):
        raise SnapshotError(f"tamanho declarado {h['snapshot_bytes']} != lido {len(raw)}")
    if h["state"] not in STATES:
        raise SnapshotError(f"estado inválido {h['state']}")
    ring_cap, writers = h["ring_capacity"], h["writer_count"]
    if writers != 4 or ring_cap == 0 or ring_cap & (ring_cap - 1):
        raise SnapshotError(f"capacidades de anel inválidas: {writers} x {ring_cap}")
    cases_off, words_off, ring_off, total = layout(
        h["case_capacity"], h["word_capacity"], writers, ring_cap)
    if total != len(raw):
        raise SnapshotError(f"layout derivado ({total} B) != snapshot ({len(raw)} B)")
    if h["case_count"] > h["case_capacity"] or h["word_count"] > h["word_capacity"]:
        raise SnapshotError("contagem de casos/palavras acima da capacidade")

    words = struct.unpack_from(f"<{h['word_count']}I", raw, words_off)
    cases: list[Case] = []
    expected_first = 0
    for i in range(h["case_count"]):
        cid, status, first, count = struct.unpack_from("<4I", raw, cases_off + i * CASE_BYTES)
        if status not in CASE_STATUS:
            raise SnapshotError(f"caso {i}: status {status} inválido")
        if first != expected_first or first + count > h["word_count"]:
            raise SnapshotError(f"caso {i} (id {cid}): palavras [{first}, +{count}) fora de ordem")
        expected_first = first + count
        cases.append(Case(cid, CASE_STATUS[status], tuple(words[first:first + count])))
    if expected_first != h["word_count"]:
        raise SnapshotError("palavras sem caso (word_count != soma dos casos)")
    if len({c.case_id for c in cases}) != len(cases):
        raise SnapshotError("case_id repetido")

    events: list[list[Event]] = []
    lost: list[int] = []
    for w in range(writers):
        head = h[f"ring_head{w}"]
        kept = min(head, ring_cap)
        first_index = head - kept
        lst = []
        for k in range(kept):
            index = first_index + k
            off = ring_off + EVENT_BYTES * (w * ring_cap + (index & (ring_cap - 1)))
            ticks, ticket, ev, case_id, arg = struct.unpack_from("<IIHHI", raw, off)
            lst.append(Event(w, index, ticks, ticket, ev, case_id, arg))
        for a, b in zip(lst, lst[1:]):
            if b.ticket <= a.ticket:
                raise SnapshotError(f"escritor {w}: tickets não crescentes ({a.ticket} → {b.ticket})")
        events.append(lst)
        lost.append(first_index)

    tickets = [e.ticket for w in events for e in w]
    if len(set(tickets)) != len(tickets):
        raise SnapshotError("ticket repetido entre escritores (registro concorrente corrompido)")
    if tickets and max(tickets) >= h["ticket_next"]:
        raise SnapshotError("ticket >= ticket_next")
    if not any(lost) and len(tickets) != h["ticket_next"]:
        raise SnapshotError(f"{h['ticket_next']} tickets emitidos, {len(tickets)} registros")

    return Snapshot(h, cases, events, lost, len(raw))


def timeline(snap: Snapshot) -> dict[tuple[int, int], int]:
    """Tempo contínuo (ticks desde dwt_start) de cada evento, chave (writer, index).

    Só é válido com trace completo (sem perdas): com eventos sobrescritos a
    cadeia de tickets tem lacunas e a reconstrução seria um palpite.
    """
    if not snap.complete_trace:
        raise SnapshotError(f"trace incompleto (perdas por escritor: {snap.lost})")
    prev_raw = snap.header["dwt_start"]
    t = 0
    out = {}
    for e in snap.all_events():
        step = (e.ticks - prev_raw) % WRAP
        if step >= MAX_STEP:
            raise SnapshotError(f"passo de tempo inválido no ticket {e.ticket}: {step} ticks")
        t += step
        prev_raw = e.ticks
        out[(e.writer, e.index)] = t
    return out


def unwrap_from(anchor_raw: int, raw: int) -> int:
    """Diferença raw - anchor módulo 2^32 (intervalos curtos dentro de um caso)."""
    d = (raw - anchor_raw) % WRAP
    if d >= MAX_STEP:
        raise SnapshotError(f"intervalo negativo/ambíguo: {anchor_raw:#x} → {raw:#x}")
    return d


def run_checks(snap: Snapshot, firmware_id: int, nonce: int | None,
               planned_cases: list[int]) -> list[str]:
    """Problemas que invalidam o RUN como instrumento (lista vazia = íntegro)."""
    problems = []
    h = snap.header
    if h["firmware_id"] != firmware_id:
        problems.append(f"firmware_id 0x{h['firmware_id']:04x} != 0x{firmware_id:04x}")
    if nonce is not None and h["run_nonce"] != nonce:
        problems.append(f"nonce 0x{h['run_nonce']:08x} != 0x{nonce:08x} (snapshot de outro run?)")
    if snap.state != "DONE":
        problems.append(f"estado {snap.state} {snap.errors}")
    if h["case_planned"] != len(planned_cases):
        problems.append(f"firmware planeja {h['case_planned']} casos, host espera {len(planned_cases)}")
    got = [c.case_id for c in snap.cases]
    if got != planned_cases:
        missing = sorted(set(planned_cases) - set(got))
        extra = sorted(set(got) - set(planned_cases))
        problems.append(f"casos diferentes do plano (faltam {missing[:8]}, sobram {extra[:8]})")
    open_cases = [c.case_id for c in snap.cases if c.status == "OPEN"]
    if open_cases:
        problems.append(f"casos não encerrados: {open_cases}")
    if h["fault_pc"]:
        problems.append(f"falha no PC 0x{h['fault_pc']:08x} CFSR 0x{h['fault_cfsr']:08x}")
    return problems
