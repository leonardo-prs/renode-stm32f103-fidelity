"""Relatório técnico (Markdown) gerado pela análise — produto do software, não
a monografia. Todos os números vêm das tabelas CSV ao lado."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ENV = {"hw": "placa", "renode-nominal": "Renode 8 MIPS", "renode-calibrated": "Renode calibrado"}


def _table(headers: list[str], rows: list[list]) -> str:
    def cell(v):
        if isinstance(v, float):
            return f"{v:.8g}" if math.isfinite(v) else "—"
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
        if _zero_uid(i.get("UID")):
            L.append("  - **UID todo zero**: atípico para um STM32 genuíno — dados desta placa "
                     "devem ser tratados como de um exemplar possivelmente compatível/clone.")
    rn = plan["renode_nominal"]
    L.append(f"- Renode: `{plan['tools'].get('renode')}`, PerformanceInMips {rn['performance_in_mips']}, "
             f"quantum {rn['quantum_s']} s, plataforma sha256 `{rn['platform_sha256'][:12]}…`, "
             f"processo novo por run: {rn.get('fresh_process_per_run')}, "
             f"AutoUpdateDelay: {rn.get('uart_auto_update_delay')}.")
    L.append(f"- Revisão base: `{plan['revision']}`; fontes da aquisição sha256 `{plan['sources']['sha256'][:12]}…`.")
    L.append("- Cada run válido foi produzido pelo ELF congelado (SHA-256 no `run.json`) e "
             "revalidado por esta análise; reanálise não altera snapshots nem o plano.")
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
    L.append("Funcional HW×Renode: igualdade de todos os valores constantes observados. "
             "Conformidade com especificação: eixo separado; valores iguais mas errados nos "
             "dois ambientes não sustentam fidelidade ao contrato e recebem classe 3. "
             "Falhas ocasionais contam. Instrução: caminho observado de PCs por stepi "
             "(só C1), sem validação do estado após cada instrução. Tempo: comparação descritiva "
             "das medianas entre resets, sem margem de aceitação. Igualdade observada não prova "
             "precisão universal de ciclo. Adequação temporal a uma aplicação não estabelecida. "
             "A resolução declarada pelos oráculos (incluindo RES_POLL=16) não tem bound "
             "instrumental validado e não é usada para declarar concordância.\n")
    L.append(_table(["recurso", "casos", "funcional HW×Renode", "instrução", "tempo observado", "placa × espec.",
                     "Renode × espec."],
                    [[r["resource"], r["cases"], r["functional"], r["instruction"], r["cycle"],
                      r["hw_vs_spec"], r["sim_vs_spec"]] for r in resources]))
    L.append("")
    counts = Counter(c["class_name"] for c in cases)
    L.append("Linhas por carga sem tamanho são ajustes derivados dos mesmos resets; "
             "linhas de configuração são leituras de contexto. Não são novos "
             "experimentos funcionais nem aumentam o tamanho da amostra.\n")
    L.append("Classes por caso tabular: " + "; ".join(f"{k}: {v}" for k, v in counts.most_common()) + ".\n")

    L.append("## Observações funcionais e falhas por tentativa\n")
    observed = defaultdict(lambda: defaultdict(Counter))
    failed = defaultdict(Counter)
    expected = {}
    for c in checks:
        key = (c["firmware"], c["case"], c["item"])
        observed[key][c["environment"]][c["observed"]] += 1
        failed[key][c["environment"]] += not c["ok"]
        expected[key] = c["expected"]
    rows = []
    for key, envs in sorted(observed.items()):
        hw, sim = envs.get("hw", {}), envs.get("renode-nominal", {})
        if failed[key] and any(failed[key].values()) or set(hw) != set(sim) or len(hw) > 1 or len(sim) > 1:
            def counts(env):
                return "; ".join(f"{v} (×{n})" for v, n in envs.get(env, {}).items()) or "sem dados"
            rows.append([*key, expected[key], counts("hw"), counts("renode-nominal"),
                         failed[key].get("hw", 0), failed[key].get("renode-nominal", 0)])
    L.append(_table(["firmware", "caso", "item", "especificação", "placa: valor (contagem)",
                     "Renode: valor (contagem)", "falhas placa", "falhas Renode"], rows)
             if rows else "Nenhuma falha ou variação observada nos itens disponíveis.")
    L.append("\nEvidência integral, inclusive buffers, em checks.csv; nenhum valor modal decide a classe.\n")
    unstable = [[c["firmware"], c["case"], c["variable_across_runs"]] for c in cases
                if c["variable_across_runs"]]
    if unstable:
        L.append("### Observáveis funcionais que variam entre runs\n")
        L.append(_table(["firmware", "caso", "itens"], unstable))
        L.append("")

    L.append("## Métricas temporais (mediana por reset; unidades por métrica)\n")
    st = defaultdict(dict)
    for s in stats:
        st[(s["firmware"], s["case"], s["metric"])][s["environment"]] = s
    rows = []
    for (fw, case, metric), envs in sorted(st.items()):
        hw, sim = envs.get("hw"), envs.get("renode-nominal")
        if not hw or not sim or hw["unit"] == "bytes":
            continue
        agree = hw["unit"] == sim["unit"] and hw["median"] == sim["median"]
        if hw["unit"] != sim["unit"]:
            continue
        err = sim["median"] - hw["median"]
        rows.append([fw, case, metric, hw["unit"], hw["n"], sim["n"], hw["predicted"], f"{hw['median']:.6g} [{hw['min']:.6g}, {hw['max']:.6g}]",
                     f"{sim['median']:.6g} [{sim['min']:.6g}, {sim['max']:.6g}]", f"{err:+.6g}",
                     f"{err / hw['median']:+.1%}" if hw["median"] else "—", f"{hw['resolution']} / {sim['resolution']} (não validada)",
                     "sim" if agree else "não"])
    L.append(_table(["firmware", "caso", "métrica", "unidade", "N placa", "N Renode", "previsto", "placa med [mín, máx]",
                     "Renode med [mín, máx]", "Δ", "Δ rel.", "resolução placa / Renode", "mesma mediana"], rows))
    L.append("")

    L.append("N = resets com métrica disponível; múltiplos eventos por run são reduzidos à "
             "mediana antes de calcular média, desvio padrão amostral, mediana e extremos "
             "(stats.csv). Não se presume independência entre resets: podem existir drift e "
             "efeitos de sessão; não se calculam intervalos de confiança. Falhas/omissões "
             "permanecem em checks.csv/accounting.csv e não viram tempos de sucesso.\n")
    if instr_rows:
        L.append("## C1: instruções executadas (stepi) × ticks\n")
        L.append("`ticks/instr. placa` é o CPI físico do intervalo medido (contagem dinâmica medida "
                 "por stepi, não inferida; a contagem de rep0 é confrontada com warm, portanto essa "
                 "razão é diagnóstica, não prova do CPI por instrução). `Renode − instr.` caracteriza "
                 "a diferença observada, sem demonstrar a regra universal tempo = instruções.\n")
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
        L.append(f"Agregado apenas no tamanho pré-registrado n={cal.get('aggregate_size')}; "
                 "conjunto incompleto não recebe média agregada.\n")
        L.append(_table(["conjunto", "erro médio nominal", "erro médio calibrado"],
                        [["treino", agg.get("treino_err_nominal"), agg.get("treino_err_calibrated")],
                         ["avaliação", agg.get("avaliação_err_nominal"), agg.get("avaliação_err_calibrated")]]))
        L.append("\nMelhorar a média não demonstra custo correto por instrução nem validade geral; "
                 "o valor calibrado nunca é usado em C2–C4. O quantum pode mudar junto "
                 "com MIPS para representar instruções em ns inteiros: compara-se a "
                 "configuração calibrada, sem isolar o efeito causal de MIPS. Um controle "
                 "8 MIPS com o mesmo quantum seria necessário para essa atribuição.\n")

    L.append("## Repetibilidade\n")
    L.append(_table(["ambiente", "observáveis", "elegíveis (N≥2)", "insuficientes", "idênticos em todos os runs", "fração"],
                    [[ENV.get(d["environment"], d["environment"]), d["observables"],
                      d["eligible"], d["insufficient"], d["identical_in_all_runs"], d["fraction"]] for d in det]))
    L.append("\nIdentidade entre N runs = determinismo OBSERVADO nestas condições, não prova geral.\n")

    L.append("## Integridade da análise e dos traces\n")
    L.append(f"Aquisição planejada completa: {summary.get('acquisition_complete', False)}; "
             f"comparação placa × Renode planejada: {summary.get('comparison_available', False)}.")
    for problem in summary.get("analysis_problems", []):
        L.append(f"- {problem}")
    traces = summary.get("perfetto", {})
    for error in traces.get("errors", []):
        L.append(f"- Trace recusado {error['environment']}/{error['firmware']}/{error['run']}: {error['error']}")
    validations = traces.get("validation", [])
    L.append(f"Importações Perfetto conferidas: {sum(v['ok'] for v in validations)}/{len(validations)}. "
             "Ausência de validação ou falha de importação impede declarar entrega completa.")
    L.append("")
    L += _duration(root, plan)
    L.append("## Limites desta campanha\n")
    lim = []
    if not summary["complete"]:
        lim.append("Campanha incompleta: ver contabilidade; condições sem runs válidos nos dois "
                   "ambientes ficam como 'evidência insuficiente'.")
    if plan["mode"] == "piloto":
        lim.append("Modo piloto: serve para medir dispersão e duração, não para conclusão final.")
    if any(_zero_uid(i.get("UID")) for i in ids):
        lim.append("Exemplar com UID zerado (provável compatível/clone): conclusões valem para ESTE "
                   "exemplar; a campanha final deve ser repetida no STM32F103 genuíno.")
    lim.append("O traço por stepi só é usado se for do ELF congelado; o caminho de PCs não "
               "comprova estado arquitetural correto após cada instrução.")
    lim.append("Repetições em uma placa não representam uma amostra de placas; reset não é "
               "power-cycle; o debugger permanece conectado durante os runs (sem polling de SRAM).")
    lim.append("Tempos do Renode são tempo virtual; o CYCCNT do Renode não é contador de ciclos.")
    L += [f"- {x}" for x in lim]
    L.append("")
    L.append("## Arquivos\n")
    L.append("`exclusions.csv`, `accounting.csv`, `checks.csv`, `metrics.csv`, `stats.csv`, `cases.csv`, `resources.csv`, "
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


def _zero_uid(uid) -> bool:
    if isinstance(uid, (list, tuple)):
        return bool(uid) and all(_zero_uid(x) for x in uid)
    if isinstance(uid, int):
        return uid == 0
    if isinstance(uid, str) and uid.strip():
        try:
            return all(int(x.removeprefix("0x"), 16) == 0 for x in uid.replace(",", " ").split())
        except ValueError:
            return False
    return False


def _duration(root: Path, plan: dict) -> list[str]:
    """Tempos host de tentativas; nenhum intervalo entre mensagens é uma etapa."""
    stages = defaultdict(list)
    for p in root.glob("*/**/run-*/run.json"):
        try:
            rec = json.loads(p.read_text())
            elapsed = rec.get("host_elapsed_s")
            if isinstance(elapsed, (int, float)) and math.isfinite(elapsed) and elapsed >= 0:
                stages[(rec["environment"], rec["firmware"])].append(elapsed)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not stages:
        return []
    rows = [[f"{env}/{fw}", len(v), sum(v) / 60, sum(v) / len(v),
             sum(v) / len(v) * 50 / 60, sum(v) / len(v) * 100 / 60]
            for (env, fw), v in sorted(stages.items())]
    return ["## Duração host das tentativas\n",
            "Soma dos tempos host registrados (não é duração de parede com jobs paralelos). "
            "Estimativas lineares por tentativa, excluindo build, stepi, análise e tentativas "
            "sem tempo registrado; retries podem aumentar o custo por run válido.\n",
            _table(["etapa", "tentativas cronometradas", "min somados", "s/tentativa",
                    "min para 50 tentativas", "min para 100 tentativas"], rows), ""]
