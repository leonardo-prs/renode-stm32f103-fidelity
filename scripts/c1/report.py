"""Relatório da campanha: analysis/report.md, tabelas CSV e figuras PNG.

O relatório é a saída para a monografia: cada linha leva o identificador do
caso do material-base, a fonte e o veredito, de modo que todo número possa
ser seguido até a linha do manual e até o código que o produziu.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

# Paleta (dataviz, instância de referência): placa = slot 1, Renode = slot 2;
# TRM = faixa neutra. Forma do marcador como codificação secundária.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_HW, C_RN, C_TRM = "#2a78d6", "#eb6834", "#c9c8c2"
SEQ = ["#eaf2fc", "#c4dcf6", "#93bdee", "#5f9be3", "#2a78d6", "#1d5aa6", "#123d73"]

VERDICT_ORDER = ("IGUAL", "IGUAL COM CONFIGURAÇÃO", "DIVERGE", "NÃO DETERMINÍSTICO", "EVIDÊNCIA INVÁLIDA")


def group_of(case: str) -> str:
    return case.split("-")[0] if not case.startswith("T-") else "-".join(case.split("-")[:2])


def fmt_c(x) -> str:
    return "—" if x is None else str(x)


def write(out: Path, results: dict, kal: dict, plan: dict) -> None:
    figs = figures(out, results)
    lines = header(results, plan)
    lines += instrument(results)
    lines += functional_section("Metade funcional: instruções, memória e exceções (c1-func)",
                                results["functional"])
    lines += functional_section("Reset, identidade e layout (c1-layout)", results["layout"])
    lines += cycle_section(results["cycle"], figs)
    lines += trace_section(results.get("trace", {}), results["functional"]["cases"])
    lines += kalibera_section(kal, plan)
    lines += deviations()
    (out / "report.md").write_text("\n".join(lines) + "\n")
    (out / "resumo.md").write_text("\n".join(summary(results, figs)) + "\n")
    tables(out, results)


# ───────────────────────────── seções ─────────────────────────────

def header(results, plan) -> list[str]:
    p = results["plan"]
    ident = p.get("identity") or {}
    rows = [
        f"# C1 — relatório da campanha `{p['campaign']}` ({p['mode']})",
        "",
        "Gerado por `python -m c1 analyze`. Vereditos e campos definidos conforme o "
        "material-base (cap. Método); custos por unidade inteira (cap. Ciclos).",
        "",
        "## Identificação",
        "",
        "| Item | Valor |", "|---|---|",
        f"| Exemplar | {p['board']} — CPUID `{ident.get('CPUID', '?')}`, IDCODE `{ident.get('IDCODE', '?')}` "
        f"(lido pelo depurador), UID `{ident.get('UID', '?')}`, F_SIZE {ident.get('FLASH_KB', '?')} KiB, "
        f"JEP106 `{ident.get('ROM_JEP106', '?')}` |",
        f"| Ambientes | {', '.join(p['environments'])} |",
        f"| Renode | {p['renode'].get('version')}; {p['renode']['mips']} MIPS, quantum {p['renode']['quantum_s']} s; "
        "processo novo por run |",
        f"| Perfis | " + "; ".join(f"`{k}` = `{v['repl']}` (sha256 {v['sha256'][:12]}…)"
                                   for k, v in p["renode"]["profiles"].items()) + " |",
        f"| Repetições | execuções por lote: {p['repetitions']}; iterações quentes no c1-cycle: "
        f"{p['cycle_iters']} (+1 fria) |",
        f"| Decisão de repetições | regra {p['kalibera'].get('rule')}: {p['kalibera'].get('why')} |",
        f"| Revisão | `{p['revision']}` |",
    ]
    for preset, info in results["presets"].items():
        rows.append(f"| ELF `{preset}` | sha256 `{info['elf_sha256'][:16]}…`, catálogo `{info['catalog_hash']}`, "
                    f"lotes {info['batches']} |")
    return rows + [""]


def instrument(results) -> list[str]:
    rows = ["## Validade do instrumento", "",
            "Runs por lote (válidos/tentativas; abortos do simulador contam como observação):", ""]
    for name, part in (("c1-func", results["functional"]), ("c1-layout", results["layout"])):
        agg = defaultdict(lambda: [0, 0, 0])
        for key, r in part["runs"].items():
            env = key.split("/")[0]
            agg[env][0] += r["valid"]
            agg[env][1] += r["aborts"]
            agg[env][2] += r["attempts"]
        rows.append(f"- `{name}`: " + "; ".join(f"{e} {v[0]} válidos + {v[1]} abortos em {v[2]} tentativas"
                                                for e, v in agg.items()))
    dwt = results["cycle"]["variants"].get("_dwt", {})
    rows += ["", "Verificações do `DWT_CYCCNT` como régua (T-DWT):", "",
             "| Verificação | " + " | ".join(dwt) + " |", "|---|" + "---|" * len(dwt)]
    checks = sorted({c for env in dwt.values() for c in env if not c.startswith("_")})
    for c in checks:
        rows.append(f"| {c} | " + " | ".join("ok" if dwt[e].get(c) else "**não**" for e in dwt) + " |")
    o = {e: d.get("_O") for e, d in dwt.items() if d.get("_O")}
    if o:
        rows += ["", "Bordas da janela: " + "; ".join(f"{e}: Δ(0) = {v['delta0']}, O(T-DWT-04) = {v['O_T-DWT-04']}"
                                                      for e, v in o.items()) + ".",
                 "Quando Δ(0) ≠ O, as bordas dependem do conteúdo: na placa, com a janela vazia a carga de "
                 "t1 se sobrepõe à de t0 (cargas vizinhas se sobrepõem, TRM §18.3); com qualquer instrução "
                 "entre elas, não. O não entra no veredito de instrução alguma e c é diferencial "
                 "(Δ(3K) − Δ(K)), com linearidade exata verificada caso a caso: a régua continua válida "
                 "para c; O é reportado como caracterização."]
    return rows + [""]


def functional_section(title, part) -> list[str]:
    cases = part["cases"]
    rows = [f"## {title}", "", f"{part['vectors']} vetores avaliados."
            + (f" Casos não planejados neste modo: {', '.join(part['not_planned'])}." if part.get("not_planned") else ""),
            "",
            "| Grupo | Casos | " + " | ".join(VERDICT_ORDER) + " | placa ≠ espec. / conflito |",
            "|---|---|" + "---|" * (len(VERDICT_ORDER) + 1)]
    by_group = defaultdict(list)
    for c in cases.values():
        by_group[group_of(c["case"])].append(c)
    for grp, cs in by_group.items():
        cnt = Counter(c["verdict"] for c in cs)
        odd = sum(1 for c in cs if c.get("board") and c["board"].startswith(("PLACA", "CONFLITO")))
        rows.append(f"| {grp} | {len(cs)} | " + " | ".join(str(cnt.get(v, "")) for v in VERDICT_ORDER)
                    + f" | {odd or ''} |")
    rows += ["", "| Caso | Cl. | Nível | Vetores | Placa × especificação | Renode | renode-doc | Veredito |",
             "|---|---|---|---|---|---|---|---|"]
    for c in cases.values():
        r = c.get("renode", {})
        cell = lambda e: (r.get(e, {}).get("result", "—") +  # noqa: E731
                          (f" ({r[e]['vectors_diverging']})" if r.get(e, {}).get("vectors_diverging") else ""))
        rows.append(f"| {c['case']}{' (derivado)' if c.get('derived_from') else ''} | {c['klass']} | "
                    f"{c['level']} | {c['vectors']} | {c.get('board') or c.get('why', '')} | {cell('renode')} | "
                    f"{cell('renode-doc')} | **{c['verdict']}** |")
    detail = [c for c in cases.values() if c["verdict"] != "IGUAL"]
    if detail:
        rows += ["", "### Diferenças, caso a caso", ""]
    from .renode_notes import NOTES
    for c in detail:
        rows.append(f"**{c['case']}** — {c['verdict']}. Fonte: {c['source']}. {c.get('note', '')}")
        if c["case"] in NOTES:
            rows.append(f"- *Explicação no código do Renode 1.17.0 (hipótese, não oráculo):* {NOTES[c['case']]}")
        for env, r in c.get("renode", {}).items():
            if r.get("result") == "IGUAL":
                continue
            if r.get("why"):
                rows.append(f"- {env}: {r['why']}")
                continue
            rows.append(f"- {env}: {r.get('vectors_diverging')} vetores; campos {', '.join(r.get('fields', []))}")
            for ex in r.get("examples", [])[:2]:
                fields = "; ".join(f"{k}: placa {v['placa']}, Renode {v['renode']}" for k, v in ex["fields"].items())
                rows.append(f"  - `{ex['vector']}` entradas {ex['inputs']}: {fields}")
        rows.append("")
    return rows + [""]


def cycle_section(cyc, figs) -> list[str]:
    vs = {k: v for k, v in cyc["variants"].items() if not k.startswith("_")}
    rows = ["## Metade temporal: custo por unidade (c1-cycle)", "",
            "c = (Δ(3K) − Δ(K)) / 2K por unidade inteira (fração exata), com o teste de linearidade "
            "exato; O fora do veredito. TRM = TRM r1p1 Tab. 18-1/§18.3; H-T1 = um tick por instrução.", ""]
    for f in figs:
        rows += [f"![{f}]({f})", ""]
    cnt = Counter(v["verdict"] for v in vs.values())
    rows += [f"Variantes: {len(vs)} — " + ", ".join(f"{k}: {n}" for k, n in cnt.items()) + ".", "",
             "| Variante | Unidade | Objeto | TRM | Placa c | Renode c | Δ placa − Renode | Placa × TRM | "
             "Renode × H-T1 | Fria = quente | Veredito |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for v in vs.values():
        cw = v.get("cold_eq_warm", {})
        rows.append(f"| {v['variant']} | `{v['unit']}` | {v['obj']} | {v['trm']} | {fmt_c(v.get('c_hw'))} | "
                    f"{fmt_c(v.get('c_renode'))} | {fmt_c(v.get('delta'))} | {v.get('board_vs_trm', '—')} | "
                    f"{v.get('renode_vs_h_t1', '—')} | {'sim' if cw and all(cw.values()) else ('não' if cw else '—')} | "
                    f"**{v['verdict']}**{(' — ' + v['why']) if v.get('why') else ''} |")
    rows += ["", "Contadores de perfil do DWT na placa (diagnóstico, nunca veredito): valores do bloco K "
             "menos a linha de base do bloco vazio (T-DWT-03), módulo 256; \"volta?\" quando passa de 200.", "",
             "| Variante | CPICNT | LSUCNT | FOLDCNT | EXCCNT | Observação |", "|---|---|---|---|---|---|"]
    for v in vs.values():
        net = v.get("profile_net")
        if net:
            rows.append(f"| {v['variant']} | {net['cpicnt']} | {net['lsucnt']} | {net['foldcnt']} | "
                        f"{net['exccnt']} | {'volta? ' + ', '.join(v['profile_overflow']) if v.get('profile_overflow') else ''} |")
    return rows + [""]


def trace_section(trc, func_cases=None) -> list[str]:
    if not trc:
        return ["## Nível de instrução", "", "Traço por stepi não executado nesta campanha.", ""]
    rows = ["## Nível de instrução (traço por stepi)", ""]
    for preset, items in trc.items():
        same = sum(1 for r in items if r.get("same_path"))
        compared = sum(1 for r in items if "same_path" in r)
        rows.append(f"- `{preset}`: {same} de {compared} chamadas com a MESMA sequência de PCs na placa "
                    f"e no Renode ({len(items)} chamadas no total).")
        stat = [r for r in items if "static" in r]
        if stat:
            for env in ("hw", "renode"):
                ok = sum(1 for r in stat if r.get(f"static_ok_{env}"))
                rows.append(f"  - contagem estática (rotinas em linha reta): {env} confere em {ok} de {len(stat)}")
        diff = [r for r in items if r.get("same_path") is False]
        for r in diff[:30]:
            case = r["name"].split(".")[0]
            why = ""
            if func_cases and func_cases.get(case, {}).get("verdict") not in (None, "IGUAL"):
                why = f" — consequência de {case} ({func_cases[case]['verdict']}: a falta não acontece no Renode)"
            rows.append(f"  - {r['name']}: placa {r.get('hw')} instruções, Renode {r.get('renode')}{why}")
        if preset == "c1-cycle":
            ok = [r for r in items if r.get("h_t1_exact") is True]
            bad = [r for r in items if r.get("h_t1_exact") is False]
            rows.append(f"  - H-T1 exata (Renode: Δ(K) − Δ(0) = instruções na janela, medidas por stepi): "
                        f"confirmada em {len(ok)}, refutada em {len(bad)}" +
                        (": " + ", ".join(r["name"] for r in bad[:12]) if bad else ""))
    return rows + [""]


def kalibera_section(kal, plan) -> list[str]:
    rows = ["## Repetições (Kalibera & Jones)", ""]
    var = [(n, e, st) for n, envs in kal["per_variant"].items() for e, st in envs.items()]
    k = plan.get("kalibera", {})
    if not var:
        rows.append(f"Esta campanha não tem séries com r1 ≥ 2 (iterações quentes: {plan['cycle_iters']}). "
                    f"As repetições vieram da regra {k.get('rule')} aplicada ao piloto "
                    f"`{k.get('from_pilot')}`: {k.get('why')} → {k.get('iters')} iteração(ões) quente(s), "
                    f"{k.get('executions')} execuções.")
        return rows + [""]
    d = kal["campaign_decision"]
    rows.append(f"Decisão para a campanha final: regra {d['rule']} — {d['why']} → {d['iters']} "
                f"iteração(ões) quente(s), {d['executions']} execuções.")
    nonzero = [(n, e, st) for n, e, st in var if st["rule"] != 1]
    rows.append(f"{len(var)} séries (variante × ambiente) com r1 ≥ 2 e r2 ≥ 2; "
                f"{len(var) - len(nonzero)} sem variação alguma.")
    if nonzero:
        rows += ["", "| Variante | Ambiente | r2 × r1 | T1² | T2² | Regra |", "|---|---|---|---|---|---|"]
        for n, e, st in nonzero:
            rows.append(f"| {n} | {e} | {st['r2']} × {st['r1']} | {st['T1^2']:.3g} | {st['T2^2']:.3g} | {st['rule']} |")
    return rows + [""]


def deviations() -> list[str]:
    return ["## Desvios declarados em relação ao material-base", "",
            "- Separadora `adds r4, r4, #1` em vez de `adds r7, r7, #1` (r7 guarda t0 no esqueleto).",
            "- LDM/STM com N ≥ 5 usam {r1–r4, r8…}: r5–r7 são registradores do instrumento.",
            "- T-DWT-06 com PRIMASK = 0: com PRIMASK = 1 o SVC escalaria para HardFault.",
            "- `IT AL` emitido como palavra crua (o montador recusa IT AL, legal sem \"senão\").",
            "- FEX-02 executa CLREX antes do STREX para garantir o monitor em Open Access.",
            "- Perfis do Renode: `renode` (plataforma do projeto) e `renode-doc` (alias de boot, VTOR = 0, "
            "bit-band, DIV_0_TRP gravável); IGUAL COM CONFIGURAÇÃO = só o segundo iguala.", ""]


# ───────────────────────────── resumo (README / monografia) ─────────────────────────────

# Uma variante representativa por classe de instrução (custo por unidade).
REPRESENTATIVE = (
    ("ALU 16/32 bits", "T-ALU-01"), ("MUL", "T-MUL-01"), ("MLA", "T-MUL-02.mla"),
    ("UMULL pequenos", "T-MUL-03.umull.pequenos"), ("UMULL grandes", "T-MUL-03.umull.grandes"),
    ("UDIV 32/1 bits", "T-DIV-01.a32.b1"), ("UDIV 8/8 bits", "T-DIV-01.a8.b8"),
    ("LDR em fluxo", "T-LS-01"), ("LDR dependente", "T-LS-02"), ("LDR + ALU", "T-LS-03"),
    ("STR imediato", "T-LS-06"), ("LDM 8 regs", "T-LSM-01.n8"), ("PUSH+POP 8 regs", "T-LSM-03.n8"),
    ("LDRD", "T-LSM-04.ldrd"), ("LDREX + STREX", "T-LSM-05.c"), ("LDR desalinhado (byte)", "T-AL-01.ldr.m1"),
    ("B tomado", "T-BR-01"), ("B<c> não tomado", "T-BR-03"), ("BX por registrador", "T-BR-06"),
    ("BL + BX LR", "T-BR-07"), ("LDR PC", "T-BR-09"), ("POP {PC}", "T-BR-10"), ("TBB", "T-BR-11"),
    ("IT + instrução", "T-IT-01"), ("ISB", "T-SYS-02"), ("SVC + retorno (vazio)", "T-DWT-06"),
    ("LDR periférico APB2 + ALU", "T-IO-01.apb2"), ("STR periférico (fluxo)", "T-IO-03.apb2"),
    ("STR periférico + DSB", "T-IO-04.apb2"),
    ("Cópia de palavras (por iteração)", "T-COMP-01"), ("CRC-32 bit a bit (por bit)", "T-COMP-02"),
)


def summary(results, figs) -> list[str]:
    from .renode_notes import NOTES
    rows = [f"# Resumo do C1 — campanha `{results['plan']['campaign']}`", ""]
    for title, part in (("Funcional (c1-func)", results["functional"]), ("Layout (c1-layout)", results["layout"])):
        cnt = Counter(c["verdict"] for c in part["cases"].values())
        rows += [f"## {title}", "", f"{len(part['cases'])} casos, {part['vectors']} vetores: "
                 + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())) + ".", ""]
        odd = [c for c in part["cases"].values() if c.get("board") and c["board"].startswith(("PLACA", "CONFLITO"))]
        for c in odd:
            rows.append(f"- placa: **{c['case']}** — {c['board']}")
        div = [c for c in part["cases"].values() if c["verdict"] not in ("IGUAL",)]
        if div:
            rows += ["", "| Caso | Veredito | O que difere no Renode | Causa provável (código do Renode) |",
                     "|---|---|---|---|"]
        for c in div:
            r = c.get("renode", {}).get("renode", {})
            what = r.get("why") or ", ".join(r.get("fields", [])[:4]) or "—"
            rows.append(f"| {c['case']} | {c['verdict']} | {what} | {NOTES.get(c['case'], '—')[:160]} |")
        rows.append("")
    vs = results["cycle"]["variants"]
    rows += ["## Temporal (c1-cycle): custo por unidade", "",
             "| Classe | Variante | TRM r1p1 | Placa | Renode | Placa × TRM |", "|---|---|---|---|---|---|"]
    for label, name in REPRESENTATIVE:
        v = vs.get(name)
        if v:
            rows.append(f"| {label} | {name} | {v['trm']} | {fmt_c(v.get('c_hw'))} | {fmt_c(v.get('c_renode'))} | "
                        f"{v.get('board_vs_trm', v.get('why', '—'))} |")
    real = {k: v for k, v in vs.items() if not k.startswith("_")}
    cnt = Counter(v["verdict"] for v in real.values())
    h_t1 = Counter(v.get("renode_vs_h_t1") for v in real.values() if v.get("renode_vs_h_t1"))
    trm = Counter(v.get("board_vs_trm") for v in real.values() if v.get("board_vs_trm"))
    rows += ["", f"{len(real)} variantes: " + ", ".join(f"{k} {n}" for k, n in sorted(cnt.items())) + ".",
             f"Renode × H-T1: " + ", ".join(f"{k} {n}" for k, n in h_t1.items()) + ".",
             f"Placa × TRM: " + ", ".join(f"{k} {n}" for k, n in trm.items()) + ".", ""]
    out_trm = [v for v in real.values() if v.get("board_vs_trm") == "FORA"]
    if out_trm:
        rows.append("Fora do intervalo do TRM na placa: " + "; ".join(
            f"{v['variant']} (TRM {v['trm']}, placa {v['c_hw']})" for v in out_trm) + ".")
    inval = [v for v in real.values() if v["verdict"] == "EVIDÊNCIA INVÁLIDA"]
    if inval:
        rows.append("Sem c publicado (linearidade): " + "; ".join(
            f"{v['variant']} Δ placa {v['env'].get('hw', {}).get('deltas_warm')}" for v in inval) + ".")
    trc = results.get("trace", {})
    for preset, items in trc.items():
        same = sum(1 for r in items if r.get("same_path"))
        cmp_ = sum(1 for r in items if "same_path" in r)
        rows.append(f"Traço {preset}: mesma sequência de PCs em {same} de {cmp_} chamadas.")
    return rows + [""]


# ───────────────────────────── figuras ─────────────────────────────

def figures(out: Path, results) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    vs = [v for k, v in results["cycle"]["variants"].items() if not k.startswith("_")]
    from .cycle import VARIANTS
    by = {v.name: v for v in VARIANTS}
    names = []
    for level, fname in (("N1", "fig_cpi_n1.png"), (None, "fig_cpi_todos.png")):
        sel = [v for v in vs if v.get("c_hw") is not None and not v["variant"].startswith(("T-DIV-01.a", "T-DIV-02"))
               and (level is None or v["level"] == level)]
        if not sel:
            continue
        fig, ax = plt.subplots(figsize=(8.2, 0.24 * len(sel) + 1.4), facecolor=SURFACE)
        ax.set_facecolor(SURFACE)
        for y, v in enumerate(reversed(sel)):
            pred = by[v["variant"]].trm
            if pred.lo is not None:
                hi = float(pred.hi) if pred.hi is not None else float(pred.lo) + 2
                ax.barh(y, hi - float(pred.lo) + 0.12, left=float(pred.lo) - 0.06, height=0.55,
                        color=C_TRM, edgecolor="none", zorder=1)
            ax.plot(float(Fraction(v["c_hw"])), y, "o", ms=9, color=C_HW, mec=SURFACE, mew=1.5, zorder=3)
            ax.plot(float(Fraction(v["c_renode"])), y, "s", ms=5, color=C_RN, mec=SURFACE, mew=1, zorder=4)
        ax.set_yticks(range(len(sel)), [v["variant"] for v in reversed(sel)], fontsize=7, color=INK)
        ax.set_xlabel("ciclos (placa) / ticks (Renode) por unidade", color=INK2, fontsize=8)
        ax.grid(axis="x", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=INK2, labelsize=7, length=0)
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(color=C_TRM, label="TRM r1p1 (intervalo previsto)"),
                           Line2D([], [], marker="o", ls="", color=C_HW, label="placa (STM32F103)"),
                           Line2D([], [], marker="s", ls="", color=C_RN, label="Renode 1.17.0")],
                  loc="lower right", fontsize=7, frameon=False)
        ax.set_title("Custo por unidade: TRM × placa × Renode" + (" (casos N1)" if level else ""),
                     color=INK, fontsize=9, loc="left")
        fig.tight_layout()
        fig.savefig(out / fname, dpi=180)
        plt.close(fig)
        names.append(fname)
    grid = {v["variant"]: v for v in vs if v["variant"].startswith("T-DIV-01.a") and v.get("c_hw")}
    if grid:
        from .cycle.alu import A_BITS, B_BITS
        fig, ax = plt.subplots(figsize=(6.4, 4.4), facecolor=SURFACE)
        data = [[float(Fraction(grid[f"T-DIV-01.a{a}.b{b}"]["c_hw"])) if f"T-DIV-01.a{a}.b{b}" in grid
                 else float("nan") for b in B_BITS] for a in A_BITS]
        from matplotlib.colors import LinearSegmentedColormap
        cmap = LinearSegmentedColormap.from_list("seq", SEQ)
        im = ax.imshow(data, cmap=cmap, vmin=2, vmax=12, aspect="auto", origin="lower")
        for i, row in enumerate(data):
            for j, val in enumerate(row):
                ax.text(j, i, f"{val:g}", ha="center", va="center", fontsize=7,
                        color=INK if val < 7 else SURFACE)
        ax.set_xticks(range(len(B_BITS)), [str(b) for b in B_BITS], fontsize=7, color=INK2)
        ax.set_yticks(range(len(A_BITS)), [str(a) for a in A_BITS], fontsize=7, color=INK2)
        ax.set_xlabel("divisor: b bits (2^b − 1)", fontsize=8, color=INK2)
        ax.set_ylabel("dividendo: a bits (2^a − 1)", fontsize=8, color=INK2)
        ax.set_title("UDIV na placa: ciclos por divisão (Renode: 1 em todos os pontos)", fontsize=9,
                     color=INK, loc="left")
        cb = fig.colorbar(im, ax=ax, shrink=0.8)
        cb.ax.tick_params(labelsize=7, colors=INK2)
        cb.outline.set_visible(False)
        for s in ax.spines.values():
            s.set_visible(False)
        fig.tight_layout()
        fig.savefig(out / "fig_udiv.png", dpi=180)
        plt.close(fig)
        names.append("fig_udiv.png")
    return names


def tables(out: Path, results) -> None:
    with (out / "casos_funcionais.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["preset", "caso", "classe", "nivel", "vetores", "placa_x_espec", "renode", "renode_doc",
                    "veredito", "fonte"])
        for preset, part in (("c1-func", results["functional"]), ("c1-layout", results["layout"])):
            for c in part["cases"].values():
                r = c.get("renode", {})
                w.writerow([preset, c["case"], c["klass"], c["level"], c["vectors"], c.get("board"),
                            r.get("renode", {}).get("result"), r.get("renode-doc", {}).get("result"),
                            c["verdict"], c["source"]])
    with (out / "variantes_temporais.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variante", "caso", "objeto", "trm", "c_placa", "c_renode", "delta", "placa_x_trm",
                    "renode_x_h_t1", "veredito", "deltas_placa", "deltas_renode"])
        for k, v in results["cycle"]["variants"].items():
            if k.startswith("_"):
                continue
            e = v.get("env", {})
            w.writerow([v["variant"], v["case"], v["obj"], v["trm"], v.get("c_hw"), v.get("c_renode"),
                        v.get("delta"), v.get("board_vs_trm"), v.get("renode_vs_h_t1"), v["verdict"],
                        e.get("hw", {}).get("deltas_warm"), e.get("renode", {}).get("deltas_warm")])
