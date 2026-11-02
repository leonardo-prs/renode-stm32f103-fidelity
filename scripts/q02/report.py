"""Relatório Markdown de uma campanha do Q-02 (a partir de analysis/results.json)."""
from __future__ import annotations

from . import spec


def render(r: dict) -> str:
    plan, c, h = r["plan"], r["checks"], r.get("hooks") or {}
    out = [f"# Q-02 — campanha {plan['campaign']}", "", f"**Veredito: {r['verdict']}**", "",
           "Verificação dos instrumentos genéricos do Renode (03-quadro-comum.typ, família Q): "
           "gancho de escrita no barramento, ganchos de início e fim de exceção e ações do monitor. "
           "O firmware só usa núcleo, SRAM e SCS e não é julgado; cada instrumento é conferido contra "
           "o traço de execução, a visão do próprio firmware e a especificação dos estímulos.", "",
           "## Condições", "",
           f"- Renode: {plan['renode']}; plataforma `{plan['platform']}`; {plan['mips']} MIPS, "
           f"quantum {plan['quantum_s']} s (perfil {plan['profile']})",
           f"- ELF `{plan['elf']}` SHA-256 `{plan['elf_sha256']}`; especificação `{plan['spec_hash']}`",
           f"- Revisão jj: `{plan['revision']}`; criado em {plan['created_utc']}",
           f"- Pausas do monitor em {plan['pauses_ns']} ns; execução de {plan['run_ns']} ns; "
           f"endereços vigiados {plan['watched']}",
           f"- {plan['repetitions']} repetições por variante: " + "; ".join(
               f"`{v}` (observação: {'sim' if x['observer'] else 'não'}, traço: {'sim' if x['trace'] else 'não'})"
               for v, x in plan["variants"].items()), "",
           "## Segmentos", ""]
    out += [f"- `{n}`: {d}" for n, d in spec.SEGMENTS] + [""]
    if r["why"]:
        out += ["## Motivos", ""] + [f"- {w}" for w in r["why"]] + [""]
    if r.get("criteria"):
        out += ["## Critérios", "", "| Instrumento | Critério | Resultado |", "|---|---|---|"]
        out += [f"| {x['instrument']} | {x['criterion']} | {'ok' if x['ok'] else '**FALHOU** ' + x['detail']} |"
                for x in r["criteria"]]
        out += ["", f"Por instrumento: {c.get('by_instrument')}", ""]
    if h:
        out += ["## Caracterização dos ganchos (fora do critério)", "",
                "Offset = tempo virtual/125 ns − instruções executadas, relativo aos pontos "
                f"(offset absoluto dos pontos: {h.get('offset_points')}).", ""]
        names = {"P": "ponto marcado", "H": "1ª instrução do tratador", "B": "início de exceção",
                 "E": "fim de exceção", "W": "escrita vigiada"}
        out += [f"- {names[k]}: {h[f'offset_{k}']}" for k in "PHBEW" if f"offset_{k}" in h]
        out += [f"- Índice entregue pelo gancho de início: {h.get('B_index')}; pelo de fim: {h.get('E_index')}",
                f"- PC no gancho de fim: {h.get('E_pc')}",
                f"- IPSR no gancho de início: {h.get('B_ipsr')}",
                f"- Bit de ativa (SHCSR) no início e na 1ª instrução: {h.get('active_bits')}",
                f"- Estado no gancho de fim: {h.get('E_state')}",
                f"- PC no gancho de início × instrução retomada: {h.get('B_pc_vs_resume')}",
                f"- Encadeamento: {h.get('tail_chain')}",
                f"- PC nas pausas: {h.get('pause_pc')}", "", "Sequência por segmento:", ""]
        out += [f"- `{n}`: {s}" for n, s in h.get("segments", {}).items()] + [""]
    return "\n".join(out)
