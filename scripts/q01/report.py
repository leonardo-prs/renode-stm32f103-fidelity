"""Relatório Markdown do Q-01 (a partir de analysis/results.json)."""
from __future__ import annotations


def render(r: dict) -> str:
    plan = r["plan"]
    c = r["checks"]
    out = [f"# Q-01 — verificação do observador externo ({plan['campaign']})", "",
           f"**Veredito: {r['verdict']}**", "",
           "Caso #oD, só no Renode (03-quadro-comum.typ). Critério: em cada segmento entre "
           "pontos marcados consecutivos, Δ tempo virtual no gancho / 125 ns = Δ`DWT_CYCCNT` = "
           "instruções no traço de execução.", "",
           "## Condições", "",
           f"- Renode: {plan['renode']}; plataforma `{plan['platform']}`; "
           f"{plan['mips']} MIPS, quantum {plan['quantum_s']} s (perfil R1)",
           f"- ELF `{plan['elf']}` SHA-256 `{plan['elf_sha256']}`",
           f"- Revisão jj: `{plan['revision']}`; criado em {plan['created_utc']}",
           f"- {plan['passes']} passagens por execução (1ª fria: tradução nova; demais quentes); "
           f"{plan['repetitions']} repetições por variante",
           "- Variantes: " + "; ".join(
               f"`{v}` (ganchos nos pontos: {'sim' if x['point_hooks'] else 'não'}, "
               f"traço: {'sim' if x['trace'] else 'não'})" for v, x in plan["variants"].items()), ""]
    if r["why"]:
        out += ["## Motivos", ""] + [f"- {w}" for w in r["why"]] + [""]
    if c:
        out += ["## Conferências", "",
                f"- Determinismo entre repetições: {'sim' if c.get('deterministic') else 'NÃO'}",
                f"- Observador não intrusivo (CYCCNT igual com e sem ganchos/traço): "
                f"{'sim' if c.get('observer_non_intrusive') else 'NÃO'}",
                f"- Tempo virtual nos ganchos igual com e sem traço: "
                f"{'sim' if c.get('hooks_same_with_trace') else 'NÃO'}",
                f"- Segmentos em que as três medidas concordam: {c.get('segments_agree')}/{c.get('segments')}",
                f"- Δ tempo virtual sempre múltiplo de 125 ns: {'sim' if c.get('vt_multiple_of_tick') else 'NÃO'}",
                f"- Auxiliar (fora do critério): Δ`ExecutedInstructions` do núcleo = traço: "
                f"{'sim' if c.get('instr_counter_matches_trace') else 'NÃO'}", ""]
    if r["segments"]:
        out += ["## Segmentos", "",
                "| Pass. | Segmento | Conteúdo | Δvt (ns) | Δvt/125 ns | ΔCYCCNT | Traço | ΔExecutedInstr | Concordam |",
                "|---:|---|---|---:|---:|---:|---:|---:|:---:|"]
        for s in r["segments"]:
            out.append(f"| {s['pass']} | {s['from']}→{s['to']} | {s['what']} | {s['d_vt_ns']} | "
                       f"{s['d_vt_ticks']} | {s['d_cyccnt']} | {s['d_trace']} | "
                       f"{s['d_executed_instructions']} | {'sim' if s['agree'] else '**não**'} |")
        out.append("")
    out += ["## Leitura", "",
            "O caso só confere o observador: um IGUAL diz que o tempo virtual lido nos ganchos "
            "pode servir de régua aos casos #oD temporais (tick = instrução em R1), não que o "
            "Renode reproduz a temporização do Cortex-M3. As contagens por segmento (por exemplo, "
            "quantos ticks custa a entrada de exceção) são contexto para C2, não veredito deste caso.", ""]
    return "\n".join(out)
