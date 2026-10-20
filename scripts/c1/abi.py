"""Decodificador do snapshot C1S1, espelho de src/c1/common/c1.h.

O decodificador REJEITA (SnapshotError) qualquer coisa que não seja
exatamente o objeto `c1_snapshot` do preset esperado: magic, versão,
tamanho, capacidades, contagens dentro das capacidades e registros
contíguos. Ele não interpreta resultados (isso é do oráculo/análise).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = 0x31533143            # b"C1S1"
ABI_VERSION = 1
HOST_MAGIC = 0x54534F48       # b"HOST"
HEADER_WORDS = 64
HEADER_BYTES = HEADER_WORDS * 4
RECORD_BYTES = 16
FAULT_WORDS = 10
RESET_WORDS = 24

HEADER_FIELDS = (
    "magic", "abi_version", "snapshot_bytes", "preset", "catalog_hash", "state", "error",
    "nonce", "batch", "iters", "host_flags", "record_capacity", "record_count",
    "word_capacity", "word_count", "record_planned", "observer_ticks", "cpuid", "idcode",
    "flash_kb", "uid0", "uid1", "uid2", "rcc_cr", "rcc_cfgr", "flash_acr", "stack_free",
    "fault_ipsr",
    *(f"fault_{k}" for k in ("cfsr", "hfsr", "mmfar", "bfar", "pc", "xpsr", "exc_return",
                             "landing", "ipsr", "count")),
    *(f"reset_{k}" for k in ("lr", "sp", "control", "primask", "faultmask", "basepri", "ipsr",
                             "vtor", "aircr", "scr", "ccr", "shpr1", "shpr2", "shpr3", "shcsr",
                             "cfsr", "hfsr", "dwt_ctrl", "demcr", "flash_acr", "rcc_cr",
                             "rcc_cfgr", "boots", "magic")),
    "reserved0", "reserved1",
)
assert len(HEADER_FIELDS) == HEADER_WORDS

STATES = {0: "INIT", 1: "RUNNING", 2: "DONE", 3: "FAILED"}
ERROR_BITS = {0: "RECORDS_FULL", 1: "WORDS_FULL", 2: "PROTOCOL", 3: "FAULT", 4: "STACK",
              5: "HOST", 6: "BATCH", 7: "IRQ", 8: "SETUP"}
HOST_TRACE = 1 << 0
RESET_MAGIC = 0x31545352


class SnapshotError(ValueError):
    """Snapshot inválido: o instrumento não produziu um registro confiável."""


@dataclass(frozen=True)
class Record:
    id: int
    status: str
    words: tuple[int, ...]


@dataclass
class Snapshot:
    header: dict
    records: list[Record]
    raw_size: int

    @property
    def state(self) -> str:
        return STATES[self.header["state"]]

    @property
    def errors(self) -> list[str]:
        e = self.header["error"]
        return [name for b, name in ERROR_BITS.items() if e & (1 << b)]

    @property
    def fault(self) -> dict:
        return {k[6:]: v for k, v in self.header.items() if k.startswith("fault_")}

    @property
    def reset(self) -> dict:
        return {k[6:]: v for k, v in self.header.items() if k.startswith("reset_")}


def snapshot_bytes(max_records: int, max_words: int) -> int:
    return HEADER_BYTES + RECORD_BYTES * max_records + 4 * max_words


def decode(raw: bytes) -> Snapshot:
    if len(raw) < HEADER_BYTES:
        raise SnapshotError(f"snapshot truncado: {len(raw)} B < header {HEADER_BYTES} B")
    h = dict(zip(HEADER_FIELDS, struct.unpack_from(f"<{HEADER_WORDS}I", raw, 0)))
    if h["magic"] != MAGIC:
        raise SnapshotError(f"magic 0x{h['magic']:08x} != C1S1 (firmware não inicializou?)")
    if h["abi_version"] != ABI_VERSION:
        raise SnapshotError(f"ABI v{h['abi_version']} incompatível (esperado v{ABI_VERSION})")
    if h["snapshot_bytes"] != len(raw):
        raise SnapshotError(f"tamanho declarado {h['snapshot_bytes']} != lido {len(raw)}")
    if h["state"] not in STATES:
        raise SnapshotError(f"estado inválido {h['state']}")
    if h["reserved0"] or h["reserved1"]:
        raise SnapshotError("campos reservados não zerados (layout incompatível)")
    if h["error"] & ~sum(1 << b for b in ERROR_BITS):
        raise SnapshotError("bits de erro desconhecidos")
    expected = snapshot_bytes(h["record_capacity"], h["word_capacity"])
    if expected != len(raw):
        raise SnapshotError(f"layout derivado ({expected} B) != snapshot ({len(raw)} B)")
    if h["record_count"] > h["record_capacity"] or h["word_count"] > h["word_capacity"]:
        raise SnapshotError("contagem de registros/palavras acima da capacidade")
    if h["state"] == 2 and h["error"]:
        raise SnapshotError("DONE com erro de instrumento")
    if h["state"] == 3 and not h["error"]:
        raise SnapshotError("FAILED sem erro de instrumento")

    rec_off = HEADER_BYTES
    words_off = rec_off + RECORD_BYTES * h["record_capacity"]
    words = struct.unpack_from(f"<{h['word_count']}I", raw, words_off)
    records = []
    expected_first = 0
    for i in range(h["record_count"]):
        rid, status, first, count = struct.unpack_from("<4I", raw, rec_off + i * RECORD_BYTES)
        if status != 1:
            raise SnapshotError(f"registro {i}: status {status} (não encerrado)")
        if first != expected_first or first + count > h["word_count"]:
            raise SnapshotError(f"registro {i} (id {rid}): palavras [{first}, +{count}) fora de ordem")
        expected_first = first + count
        records.append(Record(rid, "OK", tuple(words[first:first + count])))
    # Um registro aberto no fim (FAILED) pode ter palavras além do último fechado.
    if h["state"] == 2 and expected_first != h["word_count"]:
        raise SnapshotError("palavras sem registro (word_count != soma dos registros)")
    return Snapshot(h, records, len(raw))


def run_checks(snap: Snapshot, preset_id: int, catalog_hash: int, nonce: int | None,
               batch: int | None) -> list[str]:
    """Problemas que invalidam o RUN como instrumento (lista vazia = íntegro)."""
    h = snap.header
    problems = []
    if h["preset"] != preset_id:
        problems.append(f"preset {h['preset']} != {preset_id}")
    if h["catalog_hash"] != catalog_hash:
        problems.append(f"catálogo 0x{h['catalog_hash']:08x} != 0x{catalog_hash:08x} "
                        "(ELF gerado de outro catálogo)")
    if nonce is not None and h["nonce"] != nonce:
        problems.append(f"nonce 0x{h['nonce']:08x} != 0x{nonce:08x} (snapshot de outro run?)")
    if batch is not None and h["batch"] != batch:
        problems.append(f"lote {h['batch']} != {batch}")
    if snap.state != "DONE":
        problems.append(f"estado {snap.state} {snap.errors}")
    if snap.state == "DONE" and h["record_count"] != h["record_planned"]:
        problems.append(f"{h['record_count']} registros, {h['record_planned']} planejados")
    if h["reset_magic"] != RESET_MAGIC:
        problems.append("captura do reset incompleta (Reset_Handler do C1 não rodou?)")
    if "FAULT" in snap.errors:
        f = snap.fault
        problems.append(f"falta inesperada: IPSR {h['fault_ipsr']}, CFSR 0x{f['cfsr']:08x}, "
                        f"HFSR 0x{f['hfsr']:08x}, PC 0x{f['pc']:08x}")
    return problems
