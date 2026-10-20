"""Gera os headers do firmware a partir do catálogo (chamado pelo CMake).

    python -m c1 gen --preset c1-func --out build/c1-func/gen

Saídas: c1_config.h (capacidades, hash do catálogo) e c1_catalog.h
(tabelas). O hash do catálogo vai para o header do snapshot; o host
regenera as tabelas e recusa um snapshot cujo hash não confere (o ELF foi
gerado de outro catálogo).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .catalog import F_FAULT, F_MEM, F_TERMINAL, MEM_FILL, MEM_WORDS, Batch, make_batches, short_hash
from .presets import PRESETS, Preset

HEADER = "/* GERADO por scripts/c1 (python -m c1 gen) a partir do catálogo — não editar. */\n"


@dataclass
class Generated:
    preset: Preset
    catalog_hash: int
    config_h: str
    catalog_h: str
    forms: list = field(default_factory=list)       # func: Form; cycle: Variant; layout: Item
    batches: list = field(default_factory=list)


def _words(values, per_line=6) -> str:
    out, line = [], []
    for v in values:
        line.append(f"0x{v:08x}u")
        if len(line) == per_line:
            out.append("    " + ", ".join(line) + ",")
            line = []
    if line:
        out.append("    " + ", ".join(line) + ",")
    return "\n".join(out)


def _config(preset: Preset, catalog_hash: int, extra: str = "") -> str:
    return (HEADER + "#ifndef C1_CONFIG_H\n#define C1_CONFIG_H\n"
            f"#define C1_PRESET_ID {preset.preset_id}U\n"
            f"#define C1_MAX_RECORDS {preset.max_records}U\n"
            f"#define C1_MAX_WORDS {preset.max_words}U\n"
            f"#define C1_CATALOG_HASH 0x{catalog_hash:08x}U\n{extra}"
            "#endif\n")


def _batches_c(batches: list[Batch], entries_name: str = "c1_entries") -> tuple[str, list]:
    """Tabela de lotes: cada lote é um intervalo contíguo de c1_entries."""
    flat, rows = [], []
    for b in batches:
        rows.append(f"    {{ {len(flat)}U, {len(b.entries)}U, {int(b.terminal)}U, "
                    f"{int(b.level[1])}U }},")
        flat += b.entries
    return "\n".join(rows), flat


def gen_func(preset: Preset) -> Generated:
    from .func import FORMS
    batches = make_batches(FORMS, preset.max_words, preset.max_records)
    pool: list[int] = []
    axis_index: dict = {}
    axes_rows = []
    form_rows = []
    for idx, form in enumerate(FORMS):
        first_axis = len(axes_rows)
        for axis in form.axes:
            key = tuple(axis)
            if key not in axis_index:
                axis_index[key] = len(pool)
                for row in axis:
                    pool.extend(row)
            axes_rows.append(f"    {{ {axis_index[key]}U, {len(axis)}U, {len(axis[0])}U }},")
        flags = (form.flags & (F_FAULT | F_MEM | F_TERMINAL))
        form_rows.append(f"    {{ {form.routine}, {first_axis}U, {len(form.axes)}U, {form.n_in}U, "
                         f"{len(form.outs)}U, {flags}U }},   /* {idx}: {form.name} */")
    routines = sorted({f.routine for f in FORMS})
    batch_rows, flat = _batches_c(batches)
    entry_rows = [f"    {{ {e.form}U, {e.first}U, {e.count}U }}," for e in flat]
    catalog = (
        HEADER + "#ifndef C1_CATALOG_H\n#define C1_CATALOG_H\n#include <stdint.h>\n\n"
        f"#define C1_FORM_FAULT {F_FAULT}U\n#define C1_FORM_MEM {F_MEM}U\n"
        f"#define C1_FORM_TERMINAL {F_TERMINAL}U\n"
        f"#define C1_MEM_WORDS {MEM_WORDS}U\n#define C1_MEM_FILL 0x{MEM_FILL:08x}U\n\n"
        "typedef void (*C1Vec)(const uint32_t *in, volatile uint32_t *out);\n"
        "typedef struct { uint32_t offset; uint16_t rows; uint16_t width; } C1Axis;\n"
        "typedef struct { C1Vec fn; uint16_t axis0; uint8_t naxes; uint8_t nin;\n"
        "                 uint8_t nout; uint8_t flags; } C1Form;\n"
        "typedef struct { uint16_t form; uint32_t first; uint32_t count; } C1Entry;\n"
        "typedef struct { uint16_t first; uint16_t count; uint16_t terminal; uint16_t level; } C1Batch;\n\n"
        + "".join(f"void {r}(const uint32_t *in, volatile uint32_t *out);\n" for r in routines)
        + f"\nstatic const uint32_t c1_pool[{len(pool)}] = {{\n{_words(pool)}\n}};\n"
        f"static const C1Axis c1_axes[{len(axes_rows)}] = {{\n" + "\n".join(axes_rows) + "\n};\n"
        f"static const C1Form c1_forms[{len(FORMS)}] = {{\n" + "\n".join(form_rows) + "\n};\n"
        f"static const C1Entry c1_entries[{len(flat)}] = {{\n" + "\n".join(entry_rows) + "\n};\n"
        f"static const C1Batch c1_batches[{len(batches)}] = {{\n{batch_rows}\n}};\n"
        f"#define C1_N_FORMS {len(FORMS)}U\n#define C1_N_BATCHES {len(batches)}U\n"
        "#endif\n")
    h = short_hash(catalog + repr((preset.max_records, preset.max_words)))
    return Generated(preset, h, _config(preset, h), catalog, list(FORMS), batches)


def gen_layout(preset: Preset) -> Generated:
    catalog = HEADER + "#ifndef C1_CATALOG_H\n#define C1_CATALOG_H\n#define C1_N_BATCHES 1U\n#endif\n"
    h = short_hash(catalog + repr((preset.max_records, preset.max_words)))
    return Generated(preset, h, _config(preset, h), catalog, [], [])


def gen_cycle(preset: Preset) -> Generated:
    catalog = HEADER + "#ifndef C1_CATALOG_H\n#define C1_CATALOG_H\n#define C1_N_BATCHES 1U\n#endif\n"
    h = short_hash(catalog + repr((preset.max_records, preset.max_words)))
    return Generated(preset, h, _config(preset, h), catalog, [], [])


GENERATORS = {"c1-func": gen_func, "c1-layout": gen_layout, "c1-cycle": gen_cycle}
_CACHE: dict[str, Generated] = {}


def generate(preset_name: str) -> Generated:
    if preset_name not in _CACHE:
        _CACHE[preset_name] = GENERATORS[preset_name](PRESETS[preset_name])
    return _CACHE[preset_name]


def write(preset_name: str, out: Path) -> Generated:
    g = generate(preset_name)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in (("c1_config.h", g.config_h), ("c1_catalog.h", g.catalog_h)):
        path = out / name
        if not path.exists() or path.read_text() != text:   # não força recompilação à toa
            path.write_text(text)
    return g
