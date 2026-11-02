"""Relatório Markdown de uma campanha do C2 #oD (a partir de analysis/results.json)."""
from __future__ import annotations

PHASES = ("ARMED", "PENDING", "SERVED")


def _yn(v) -> str:
    return "sim" if v else "**NÃO**"


def render(r: dict) -> str:
    plan = r["plan"]
    c = r["checks"]
    out = [f"# {r['case']} — campanha {plan['campaign']}", "",
           f"**Veredito: {r['verdict']}**", "",
           "Caso #oD, só no Renode (04-c2.typ): interrupção desabilitada no NVIC recebe pedido por "
           "software; depois é habilitada. Oráculo (ARM ARM §B3.4.1): fica pendente sem ser atendida; "
           "é atendida uma vez ao habilitar; pendência zerada no fim.", "",
           "## Condições", "",
           f"- Renode: {plan['renode']}; plataforma `{plan['platform']}`; {plan['mips']} MIPS, "
           f"quantum {plan['quantum_s']} s (perfil {plan['profile']})",
           f"- ELF `{plan['elf']}` SHA-256 `{plan['elf_sha256']}`; catálogo `{plan['catalog_hash']}`",
           f"- Revisão jj: `{plan['revision']}`; criado em {plan['created_utc']}",
           f"- {len(plan['points'])} pontos (linhas livres × STIR/ISPR) numa execução; "
           f"{plan['repetitions']} repetições por variante; prioridade {plan['params']['c2_09_prio']} "
           f"(byte 0x{plan['params']['c2_09_prio'] << 4:02x}), janela de {plan['params']['c2_09_window']} voltas",
           "- Variantes: " + "; ".join(
               f"`{v}` (observador externo: {'sim' if x['observer'] else 'não'}, traço: "
               f"{'sim' if x['trace'] else 'não'})" for v, x in plan["variants"].items()), ""]
    if r["why"]:
        out += ["## Motivos", ""] + [f"- {w}" for w in r["why"]] + [""]
    if c:
        out += ["## Conferências", "",
                f"- Determinismo entre repetições: {_yn(c.get('deterministic'))}",
                f"- Observador não intrusivo (o que o firmware vê é igual sem e com ganchos/traço): "
                f"{_yn(c.get('observer_non_intrusive'))}",
                f"- Registro do observador igual sem e com traço: {_yn(c.get('events_same_with_trace'))}",
                f"- Pontos por veredito: {c.get('points_by_verdict')}", ""]
    if r.get("hooks"):
        h = r["hooks"]
        out += ["## Caracterização dos ganchos (fora do critério)", "",
                "Offset = tempo virtual/125 ns − instruções executadas, relativo aos pontos marcados "
                "(contagem de eventos por offset).", ""]
        names = {"P": "ponto marcado (endereço)", "H": "1ª instrução do tratador (endereço)",
                 "B": "início de interrupção", "E": "fim de interrupção", "W": "escrita no NVIC/SCB"}
        out += [f"- {names[k]}: {h[k]}" for k in "PHBEW" if k in h]
        out += [f"- Índice entregue pelo gancho de início: {h.get('B_index_values')} "
                f"(IPSR no gancho: {h.get('B_ipsr_values')})",
                f"- PC no gancho de fim: {h.get('E_pc_values')}", ""]
    if r["points"]:
        out += ["## Pontos", "",
                "Estado da linha em cada fase, visto de fora: habilitada/pendente/ativa/atendimentos "
                "(e = 1, p = 1, a = 1, n). Esperado: ARMED 0/0/0/0, PENDING 0/1/0/0, SERVED 1/0/0/1.", "",
                "| # | Ponto | ARMED | PENDING | SERVED | Depois | Veredito |",
                "|---:|---|:---:|:---:|:---:|:---:|---|"]
        for p in r["points"]:
            o = p["observed"]
            cells = [f"{o[ph]['enabled']}/{o[ph]['pending']}/{o[ph]['active']}/{o[ph]['served']}" for ph in PHASES]
            out.append(f"| {p['index']} | {p['point']} | " + " | ".join(cells) +
                       f" | {o['entries_after_served']} | {p['verdict']} |")
        out.append("")
    out += ["## Leitura", "",
            "O firmware também registra o que ele próprio vê (pendência lida no ISPR e atendimentos "
            "contados pelo tratador); a discordância com o observador externo invalida o ponto, não "
            "o faz divergir. O estado ICSR e as máscaras lidos em cada ponto estão nos dados brutos "
            "(events.txt) e não entram no critério.", ""]
    return "\n".join(out)
