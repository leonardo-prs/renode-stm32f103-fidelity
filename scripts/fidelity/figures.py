"""Figuras estáticas (PNG) do relatório. Cada figura tem a tabela equivalente
em analysis/*.csv (os valores exatos ficam lá, não só na imagem).

Cores: paleta categórica validada (ordem fixa, entidade → cor, nunca posto):
placa = azul, Renode nominal = laranja, Renode calibrado = verde-água.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = {"hw": "#2a78d6", "renode-nominal": "#eb6834", "renode-calibrated": "#1baf7a"}
LABELS = {"hw": "placa", "renode-nominal": "Renode 8 MIPS", "renode-calibrated": "Renode calibrado"}
SURFACE, INK, MUTED = "#fcfcfb", "#0b0b0b", "#52514e"


def _style(ax, title: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=11, loc="left")
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#b9b8b2")
    ax.tick_params(colors=MUTED)


def _grouped_bars(path: Path, title: str, ylabel: str, categories: list[str],
                  series: dict[str, list[float | None]]) -> str:
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=130)
    fig.patch.set_facecolor(SURFACE)
    width = 0.8 / max(len(series), 1)
    for k, (env, values) in enumerate(series.items()):
        xs = [i + (k - (len(series) - 1) / 2) * width for i in range(len(categories))]
        ax.bar([x for x, v in zip(xs, values) if v is not None],
               [v for v in values if v is not None], width=width * 0.92,
               color=COLORS.get(env, MUTED), label=LABELS.get(env, env))
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=30, ha="right", fontsize=8)
    _style(ax, title, ylabel)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path.name


def _ecdf(path: Path, title: str, xlabel: str, samples: dict[str, list[float]]) -> str:
    fig, ax = plt.subplots(figsize=(6.5, 3.8), dpi=130)
    fig.patch.set_facecolor(SURFACE)
    for env, vals in samples.items():
        vals = sorted(vals)
        if not vals:
            continue
        ys = [(i + 1) / len(vals) for i in range(len(vals))]
        ax.step([vals[0], *vals], [0, *ys], where="post", color=COLORS.get(env, MUTED), linewidth=2,
                label=f"{LABELS.get(env, env)} (n={len(vals)})")
    _style(ax, title, "fração acumulada")
    ax.set_xlabel(xlabel, color=MUTED)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path.name


def make_all(out: Path, stats: list[dict], metrics: list[dict], instr_rows: list[dict],
             cal: dict | None) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    made = []
    st = {(s["firmware"], s["case"], s["metric"], s["environment"]): s for s in stats}
    envs = [e for e in ("hw", "renode-nominal", "renode-calibrated")
            if any(s["environment"] == e for s in stats)]

    # C1: ticks (mediana warm) por carga no maior tamanho.
    loads = sorted({s["case"] for s in stats if s["firmware"] == "c1-timing"
                    and s["metric"] == "warm" and s["case"].endswith("/256")})
    if loads:
        series = {e: [st.get(("c1-timing", c, "warm", e), {}).get("median") for c in loads]
                  for e in envs}
        made.append(_grouped_bars(out / "c1_ticks_n256.png",
                                  "C1-timing: duração por carga (n = 256, mediana entre runs)",
                                  "ticks (8 MHz)", loads, series))
    if instr_rows:
        rows = [r for r in instr_rows if r["n"] == 256 and r["cpi_hw"]]
        if rows:
            fig_series = {"hw": [r["cpi_hw"] for r in rows],
                          "renode-nominal": [r["ticks_renode_warm"] / r["instructions_renode"]
                                             if r["ticks_renode_warm"] is not None and r["instructions_renode"] else None
                                             for r in rows]}
            made.append(_grouped_bars(out / "c1_cpi_n256.png",
                                      "C1-timing: ticks por instrução executada (stepi), n = 256",
                                      "ticks / instrução", [r["case"] for r in rows], fig_series))

    # Distribuições entre runs de métricas temporais selecionadas.
    by_run = defaultdict(list)
    for m in metrics:
        by_run[(m["firmware"], m["case"], m["metric"], m["environment"], m["run"])].append(m["value"])
    per_run = defaultdict(lambda: defaultdict(list))
    for (fw, case, metric, env, run), vals in by_run.items():
        per_run[(fw, case, metric)][env].append(median(vals))
    selected = [
        ("c2", "tim2/apb1/irq_idle", "phase_cnt_median", "C2: fase CNT observada na ISR (TIM2)"),
        ("c2", "tim2/apb1/irq_load", "phase_cnt_median", "C2: fase CNT com MAIN em carga (TIM2)"),
        ("c3", "c3/31", "a_exit_to_b_entry", "C3: saída de A → entrada de B (encadeado)"),
        ("c3", "c3/32", "a_exit_to_b_entry", "C3: saída de A → entrada de B (via thread)"),
        ("c4", "c4/44", "producer_time", "C4: tempo do produtor, 64 bytes por TXE"),
    ]
    for fw, case, metric, title in selected:
        samples = per_run.get((fw, case, metric))
        if samples:
            name = f"{fw}_{case.replace('/', '_')}_{metric}.png"
            made.append(_ecdf(out / name, title, "ticks (8 MHz)", dict(samples)))

    if cal and cal.get("per_case"):
        rows = [r for r in cal["per_case"] if r["case"].endswith("/256")]
        series = {"renode-nominal": [abs(r["err_nominal"]) * 100 if r["err_nominal"] is not None else None for r in rows],
                  "renode-calibrated": [abs(r["err_calibrated"]) * 100 if r["err_calibrated"] is not None else None for r in rows]}
        made.append(_grouped_bars(out / "c1_calibration_error.png",
                                  "C1: erro relativo |Renode − placa| (n = 256), nominal × calibrado",
                                  "% do tempo na placa",
                                  [f"{r['case']} ({r['role']})" for r in rows], series))
    return made
