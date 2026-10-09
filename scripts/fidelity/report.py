"""Relatório técnico (Markdown) gerado pela análise — produto do software, não
a monografia. Todos os números vêm das tabelas CSV ao lado."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ENV = {"hw": "placa", "renode-nominal": "Renode 8 MIPS", "renode-calibrated": "Renode calibrado"}


def _table(headers: list[str], rows: list[list]) -> str:
    def cell(v):
        if isinstance(v, float):
            return f"{v:.4g}"
        return str(v).replace("|", "\\|").replace("\n", " ") if v is not None else "—"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def _identity(root: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((root / "hw" / "sessions").glob("*/identify.json"))]


def write(path: Path, plan: dict, summary: dict, acc, cases, resources, stats, instr_rows,
          cal, det, checks, root: Path) -> None:
    L = []
    L.append(f"# Relatório da campanha `{plan['campaign']}`\n")
    L.append(f"Gerado por `scripts/fidelity.py analyze`. Modo **{plan['mode']}**; "
             f"repetições planejadas por firmware e ambiente: **{plan['repetitions']}**. "
             f"Campanha **{'completa' if summary['complete'] else 'INCOMPLETA'}** "
             "(todas as tentativas e motivos em `accounting.csv`).\n")
    ids = _identity(root)
    L.append("## Identidade\n")
    L.append(f"- Exemplar informado: **{plan['board']}** {plan.get('board_note') or ''}")
    for i in ids:
        L.append(f"- Identificação lida pelo SWD (metadado, não autenticação): CPUID {i.get('CPUID')}, "
                 f"IDCODE {i.get('IDCODE')}, F_SIZE {i.get('FLASH_KB')} KiB, UID {i.get('UID')}, "
                 f"ST-Link {i.get('stlink')}, alvo {i.get('target_voltage')} V")
        if i.get("UID", "").strip("0") == "":
            L.append("  - **UID todo zero**: atípico para um STM32 genuíno — dados desta placa "
                     "devem ser tratados como de um exemplar possivelmente compatível/clone.")
    rn = plan["renode_nominal"]
    L.append(f"- Renode: `{plan['tools'].get('renode')}`, PerformanceInMips {rn['performance_in_mips']}, "
             f"quantum {rn['quantum_s']} s, plataforma sha256 `{rn['platform_sha256'][:12]}…`, "
             "processo novo por run, AutoUpdateDelay desligado.")
    L.append(f"- Revisão do código: `{plan['revision']}`; fontes sha256 `{plan['sources']['sha256'][:12]}…`.")
    L.append(f"- Toolchain: {plan['tools'].get('arm-none-eabi-gcc')}; OpenOCD: {plan['tools'].get('openocd')}.")
    for name, fw in plan["firmwares"].items():
        L.append(f"- `{name}` ({fw['scenario']}): ELF `{fw['elf_sha256'][:12]}…`, RAM {fw['ram_bytes']} B "
                 f"+ {fw['stack_heap_reserved']} B pilha/heap reservados, flags {' '.join(fw['compile_flags'])}")
    L.append("")

    L.append("## Contabilidade\n")
    L.append(_table(["ambiente", "firmware", "planejado", "tentativas", "válidos", "inválidos",
                     "falha infra", "completo", "motivos"],
                    [[ENV.get(a["environment"], a["environment"]), a["firmware"], a["planned"],
                      a["attempts"], a["valid"], a["invalid"], a["infra_error"],
                      "sim" if a["complete"] else "NÃO", a["reasons"]] for a in acc]))
    L.append("")

    L.append("## Mapa de limites por recurso (Renode 8 MIPS × placa)\n")
    L.append("Funcional = igualdade dos valores observados; Instrução = mesma sequência de PCs "
             "por stepi (só C1); Ciclo = mediana do Renode dentro da faixa da placa ± resolução. "
             "As colunas 'placa × especificação' e 'Renode × especificação' mostram a conformidade "
             "de cada ambiente com o oráculo do manual.\n")
    L.append(_table(["recurso", "casos", "funcional", "instrução", "ciclo", "placa × espec.",
                     "Renode × espec."],
                    [[r["resource"], r["cases"], r["functional"], r["instruction"], r["cycle"],
                      r["hw_vs_spec"], r["sim_vs_spec"]] for r in resources]))
    L.append("")
    counts = Counter(c["class_name"] for c in cases)
    L.append("Classes por caso: " + "; ".join(f"{k}: {v}" for k, v in counts.most_common()) + ".\n")

    L.append("## Divergências funcionais (valor modal por ambiente)\n")
    modal = defaultdict(lambda: defaultdict(Counter))
    expected = {}
    for c in checks:
        modal[(c["firmware"], c["case"], c["item"])][c["environment"]][c["observed"]] += 1
        expected[(c["firmware"], c["case"], c["item"])] = c["expected"]
    rows = []
    for key, envs in sorted(modal.items()):
        hw, sim = envs.get("hw"), envs.get("renode-nominal")
        if hw and sim and hw.most_common(1)[0][0] != sim.most_common(1)[0][0]:
            rows.append([key[0], key[1], key[2], _short(expected[key]), _short(hw.most_common(1)[0][0]),
                         _short(sim.most_common(1)[0][0])])
    L.append(_table(["firmware", "caso", "item", "especificação", "placa", "Renode"], rows)
             if rows else "Nenhuma.")
    L.append("")
    unstable = [[c["firmware"], c["case"], c["variable_across_runs"]] for c in cases
                if c["variable_across_runs"]]
    if unstable:
        L.append("### Observáveis funcionais que variam entre runs\n")
        L.append(_table(["firmware", "caso", "itens"], unstable))
        L.append("")

    L.append("## Métricas temporais (mediana entre runs; ticks de 8 MHz)\n")
    st = defaultdict(dict)
    for s in stats:
        st[(s["firmware"], s["case"], s["metric"])][s["environment"]] = s
    rows = []
    for (fw, case, metric), envs in sorted(st.items()):
        hw, sim = envs.get("hw"), envs.get("renode-nominal")
        if not hw or not sim or hw["unit"] == "bytes":
            continue
        agree = hw["min"] - hw["resolution"] <= sim["median"] <= hw["max"] + hw["resolution"]
        err = sim["median"] - hw["median"]
        rows.append([fw, case, metric, hw["predicted"], f"{hw['median']:.6g} [{hw['min']:.6g}, {hw['max']:.6g}]",
                     f"{sim['median']:.6g} [{sim['min']:.6g}, {sim['max']:.6g}]", f"{err:+.6g}",
                     f"{err / hw['median']:+.1%}" if hw["median"] else "—", hw["resolution"],
                     "sim" if agree else "não"])
    L.append(_table(["firmware", "caso", "métrica", "previsto", "placa med [mín, máx]",
                     "Renode med [mín, máx]", "Δ", "Δ rel.", "resolução", "ciclo ok"], rows))
    L.append("")

    if instr_rows:
        L.append("## C1: instruções executadas (stepi) × ticks\n")
        L.append("`ticks/instr. placa` é o CPI físico do intervalo medido (contagem dinâmica medida "
                 "por stepi, não inferida). `Renode − instr.` constante indica tempo = instruções.\n")
        L.append(_table(["carga/n", "instr. placa", "instr. Renode", "mesma sequência de PCs",
                         "ticks placa", "ticks Renode", "ticks/instr. placa", "Renode − instr."],
                        [[r["case"], r["instructions_hw"], r["instructions_renode"],
                          "sim" if r["same_pc_sequence"] else "NÃO", r["ticks_hw_warm"],
                          r["ticks_renode_warm"], r["cpi_hw"], r["renode_ticks_minus_instructions"]]
                         for r in instr_rows]))
        L.append("")
    else:
        L.append("## C1: instruções executadas\n\nTraço por stepi ausente nesta campanha: o nível "
                 "'instrução' fica sem evidência.\n")

    if cal:
        L.append("## C1: complemento de calibração (separado da referência nominal)\n")
        L.append(f"Regra pré-registrada: {cal['rule']['objective']}; treino {cal['rule']['training_loads']}, "
                 f"avaliação {cal['rule']['evaluation_loads']}. Valor escolhido: **{cal['chosen_mips']}** "
                 f"MIPS (inteiro; efetivo lido do Renode: {cal.get('effective_mips')}). "
                 f"Erro médio no treino previsto: {cal['training_mare']:.1%}.\n")
        agg = cal.get("aggregate", {})
        L.append(_table(["conjunto", "erro médio nominal", "erro médio calibrado"],
                        [["treino", agg.get("treino_err_nominal"), agg.get("treino_err_calibrated")],
                         ["avaliação", agg.get("avaliação_err_nominal"), agg.get("avaliação_err_calibrated")]]))
        L.append("\nMelhorar a média não demonstra custo correto por instrução nem validade geral; "
                 "o valor calibrado nunca é usado em C2–C4.\n")

    L.append("## Repetibilidade\n")
    L.append(_table(["ambiente", "observáveis", "idênticos em todos os runs", "fração"],
                    [[ENV.get(d["environment"], d["environment"]), d["observables"],
                      d["identical_in_all_runs"], d["fraction"]] for d in det]))
    L.append("\nIdentidade entre N runs = determinismo OBSERVADO nestas condições, não prova geral.\n")

    L.append("## Limites desta campanha\n")
    lim = []
    if not summary["complete"]:
        lim.append("Campanha incompleta: ver contabilidade; condições sem runs válidos nos dois "
                   "ambientes ficam como 'evidência insuficiente'.")
    if plan["mode"] == "piloto":
        lim.append("Modo piloto: serve para medir dispersão e duração, não para conclusão final.")
    if any(i.get("UID", "").strip("0") == "" for i in ids):
        lim.append("Exemplar com UID zerado (provável compatível/clone): conclusões valem para ESTE "
                   "exemplar; a campanha final deve ser repetida no STM32F103 genuíno.")
    lim.append("Repetições em uma placa não representam uma amostra de placas; reset não é "
               "power-cycle; o debugger permanece conectado durante os runs (sem polling de SRAM).")
    lim.append("Tempos do Renode são tempo virtual; o CYCCNT do Renode não é contador de ciclos.")
    L += [f"- {x}" for x in lim]
    L.append("")
    L.append("## Arquivos\n")
    L.append("`accounting.csv`, `checks.csv`, `metrics.csv`, `stats.csv`, `cases.csv`, `resources.csv`, "
             "`c1_instructions.csv`, `determinism.csv`, `figures/`, `perfetto/` (um trace por run, "
             "`compare-<firmware>.json` com o run mediano de cada ambiente, `validation.json`).")
    figs = summary.get("figures") or []
    if figs:
        L.append("")
        L += [f"![{f}](figures/{f})" for f in figs]
    path.write_text("\n".join(L) + "\n")


def _short(v, n=80) -> str:
    s = str(v)
    return s if len(s) <= n else s[:n] + "…"
