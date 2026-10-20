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
    from . import cycle
    variants = cycle.VARIANTS
    batches = cycle.make_batches(variants, preset.max_words, preset.max_records)
    sets: dict[tuple, int] = {}
    regs_pool: dict[tuple, int] = {}
    var_rows = []
    for idx, v in enumerate(variants):
        key = tuple(v.blocks)
        sets.setdefault(key, len(sets))
        rix = []
        for regs in v.regs:
            regs_pool.setdefault(tuple(regs), len(regs_pool))
            rix.append(regs_pool[tuple(regs)])
        var_rows.append(f"    {{ {sets[key]}U, {{ {rix[0]}U, {rix[1]}U, {rix[2]}U }}, "
                        f"{{ {v.sizes[0]}U, {v.sizes[1]}U, {v.sizes[2]}U }}, "
                        f"C1_SETUP_{v.setup.upper()}, {v.arg}U, {v.flags}U }},   /* {idx}: {v.name} */")
    blocks = sorted({b for key in sets for b in key})
    set_rows = [f"    {{ {{ {', '.join(key)} }} }}," for key in sets]
    pool_rows = ["    { " + ", ".join(f"0x{w:08x}u" for w in regs) + " }," for regs in regs_pool]
    items, batch_rows = [], []
    for b in batches:
        batch_rows.append(f"    {{ {len(items)}U, {len(b.variants)}U, 0U, {int(b.level[1])}U }},")
        items += b.variants
    x0 = sorted({f"{b}_x0" for key in sets for b, n in zip(key, (1, 1, 1)) if b.startswith(("t_br09", "t_br10"))})
    catalog = (
        HEADER + "#ifndef C1_CATALOG_H\n#define C1_CATALOG_H\n#include <stdint.h>\n\n"
        f"#define C1_R_MAX {cycle.R_MAX}U\n"
        + "".join(f"#define C1_SETUP_{name.upper()} {k}U\n" for k, name in enumerate(cycle.SETUPS))
        + f"#define C1_V_PRIMASK0 {cycle.V_PRIMASK0}U\n#define C1_V_CYCOFF {cycle.V_CYCOFF}U\n"
        f"#define C1_V_PREFOFF {cycle.V_PREFOFF}U\n#define C1_V_RAW {cycle.V_RAW}U\n\n"
        "typedef uint32_t (*C1Block)(uint32_t *regs);\n"
        "typedef struct { C1Block fn[3]; } C1BlockSet;\n"
        "typedef struct { uint16_t set; uint16_t regs[3]; uint8_t units[3]; uint8_t setup;\n"
        "                 uint8_t arg; uint8_t flags; } C1Variant;\n"
        "typedef struct { uint16_t first; uint16_t count; uint16_t terminal; uint16_t level; } C1Batch;\n\n"
        + "".join(f"uint32_t {b}(uint32_t *regs);\n" for b in blocks)
        + "".join(f"extern const char {s}[];\n" for s in x0)
        + f"\nstatic const C1BlockSet c1_sets[{len(sets)}] = {{\n" + "\n".join(set_rows) + "\n};\n"
        f"static const uint32_t c1_regs_pool[{len(regs_pool)}][11] = {{\n" + "\n".join(pool_rows) + "\n};\n"
        f"static const C1Variant c1_variants[{len(variants)}] = {{\n" + "\n".join(var_rows) + "\n};\n"
        f"static const uint16_t c1_items[{len(items)}] = {{ " + ", ".join(f"{i}U" for i in items) + " };\n"
        f"static const C1Batch c1_batches[{len(batches)}] = {{\n" + "\n".join(batch_rows) + "\n};\n"
        f"#define C1_N_VARIANTS {len(variants)}U\n#define C1_N_BATCHES {len(batches)}U\n"
        "#endif\n")
    h = short_hash(catalog + repr((preset.max_records, preset.max_words)))
    return Generated(preset, h, _config(preset, h), catalog, list(variants), batches)


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
