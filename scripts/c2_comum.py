"""Comum aos scripts do C2 (04-c2.typ): execuções, ganchos e resultado.

Cada script de etapa (c2_sw.py, c2_mon.py, c2_tim.py) descreve os seus
casos com `Caso` e chama `main`. Para cada caso:

  - o monitor grava o número do caso em `c2_caso` antes da partida;
  - variante `bare`: só o estímulo do caso e o gancho de fim (o firmware
    registra o que viu em c2_rec); variante `full`, quando o caso usa
    ganchos: também ganchos de endereço, de escrita e traço;
  - cada variante é repetida `reps` vezes (03-quadro-comum.typ §Repetições:
    três execuções com reinício da máquina);
  - validade: o firmware chegou ao fim sem exceção inesperada; o registro do
    firmware é igual com e sem ganchos (não intrusão); repetições idênticas
    (senão, NÃO DETERMINÍSTICO);
  - a análise do caso compara o observado com a resposta do documento.

Os instrumentos usados são os verificados no Q-01 (data/q/piloto-01): tempo
virtual nos ganchos de endereço e de escrita (125 ns por instrução), IPSR
lido no gancho do tratador, índice do traço = instruções executadas,
escrita e leitura pelo monitor com a simulação parada.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import sim

NS = sim.NS_PER_TICK
LIVRES = (0, 1, 2, 3, 4, 5, 18, 19, 20, 21, 22, 35, 36, 41, 42)   # = c2_livres em src/c2/c2.c
ISPR = 0xE000E200
STIR = 0xE000EF00
SIMBOLOS = ("c2_caso", "c2_irq", "c2_fim", "c2_falha", "c2_nrec", "c2_rec", "c2_status", "c2_nlog",
            "c2_vezes", "c2_pronto")
BRUTOS = ("eventos.txt", "pausas.txt", "mem.txt", "traco.txt")

VT = "machine.ElapsedVirtualTime.TimeElapsed.Ticks"        # ns de tempo virtual
GANCHO = {
    # endereço: PC, tempo virtual (ns), instruções executadas, IPSR
    "A": f"f = open(r'{{ev}}', 'a'); f.write('A %x %d %d %x\\n' % (pc, {VT}, self.ExecutedInstructions,"
         " self.GetRegister(25).RawValue)); f.close()",
    # escrita: endereço, valor, tempo virtual, instruções, PC da escrita
    "W": "f = open(r'{ev}', 'a'); f.write('W %x %x %d %d %x\\n' % (address, value,"
         " self.Machine.ElapsedVirtualTime.TimeElapsed.Ticks, cpu.ExecutedInstructions, cpu.PC.RawValue)); f.close()",
    "falha": "f = open(r'{dir}/falha.txt', 'w'); f.write('%x' % pc); f.close()",
    # fim: tempo virtual, instruções, c2_status, c2_nrec e c2_rec[0..c2_nrec)
    "fim": f"rd = machine.SystemBus.ReadDoubleWord; n = rd({{c2_nrec}}); f = open(r'{{dir}}/mem.txt', 'w');"
           f" f.write('%d %d %d %d\\n' % ({VT}, self.ExecutedInstructions, rd({{c2_status}}), n));"
           " f.write(' '.join('%d' % rd({c2_rec} + 4 * k) for k in range(n))); f.close()",
    # comando `python` do monitor, com a simulação parada: registra tempo,
    # instruções e as palavras lidas; depois faz as escritas do estímulo
    "pausa": "m = monitor.Machine; c = m['sysbus.cpu']; rd = m.SystemBus.ReadDoubleWord\n"
             "f = open(r'{dir}/pausas.txt', 'a'); f.write('P %d %d %s\\n' % (m.ElapsedVirtualTime.TimeElapsed.Ticks,"
             " c.ExecutedInstructions, ' '.join('%d' % rd(a) for a in {leituras}))); f.close()\n"
             "for a, v in {escritas}: m.SystemBus.WriteDoubleWord(a, v)\n",
}


@dataclass
class Pausa:
    """Pausa do monitor no instante `ns`: lê `leituras` e grava `escritas`."""
    ns: int
    escritas: list[tuple[int, int]] = field(default_factory=list)
    leituras: list[int] = field(default_factory=list)


@dataclass
class Caso:
    id: str                                     # "C2-01"
    numero: int                                 # gravado em c2_caso
    run_ns: int                                 # tempo virtual da execução
    analisa: Callable[[dict[str, "Execucao"], dict[str, int]], tuple[str, list[str]]]   # (execuções, símbolos)
    ganchos: tuple[str, ...] = ()               # símbolos com gancho de endereço (full)
    retornos: tuple[str, ...] = ()              # funções com gancho nas instruções de retorno (full)
    escritas: tuple[int, ...] = ()              # endereços com gancho de escrita (full)
    traco: bool = False                         # traço de PCs (full)
    pausas: Callable[[dict[str, int], dict], list[Pausa]] | None = None   # (símbolos, referência)
    referencia: Callable[[dict[str, int]], "Caso"] | None = None          # execução de referência

    @property
    def instrumentado(self) -> bool:
        return bool(self.ganchos or self.retornos or self.escritas or self.traco)


@dataclass
class Execucao:
    A: list[tuple[int, ...]]                    # (pc, ns, instruções, IPSR)
    W: list[tuple[int, ...]]                    # (endereço, valor, ns, instruções, pc)
    P: list[list[int]]                          # [ns, instruções, palavras lidas...]
    rec: list[int]
    fim: list[int]                              # [ns, instruções, c2_status, c2_nrec]
    traco: list[int] | None
    falha: bool

    def entradas(self, sym: dict[str, int]) -> list[tuple[int, ...]]:
        """Passagens pelo primeiro endereço de c2_irq."""
        return [a for a in self.A if a[0] == sym["c2_irq"]]


# ───────────────────────────── ELF ─────────────────────────────

def retornos(elf: Path, simbolo: str) -> list[int]:
    """Endereços das instruções de retorno (`bx lr`, `pop {…, pc}`) de uma função."""
    out = subprocess.run(["arm-none-eabi-objdump", "-d", f"--disassemble={simbolo}", str(elf)],
                         check=True, capture_output=True, text=True).stdout
    res = [int(m.group(1), 16) for m in re.finditer(r"^\s*([0-9a-f]+):\s+[0-9a-f ]+\s+(?:bx\s+lr|pop(?:\.w)?\s+\{[^}]*pc\})",
                                                    out, re.M)]
    if not res:
        raise SystemExit(f"nenhuma instrução de retorno em {simbolo}")
    return res


# ───────────────────────────── execução ─────────────────────────────

def escreve_resc(d: Path, elf: Path, sym: dict[str, int], caso: Caso, full: bool, pausas: list[Pausa]) -> Path:
    fmt = dict(ev=d / "eventos.txt", dir=d, **sym)
    for nome in ("A", "W", "falha", "fim"):
        (d / f"{nome}.py").write_text(GANCHO[nome].format(**fmt) + "\n")

    def py(nome: str) -> str:
        """Comando que executa o código do gancho; o arquivo é fechado a cada
        disparo (com milhares de disparos, `exec(open(…).read())` esgota os
        descritores e derruba o Renode)."""
        return f"\"with open(r'{d / nome}.py') as h: exec(h.read())\""

    linhas = [f"# {caso.id}, variante {'full' if full else 'bare'} (gerado por scripts/c2_comum.py)",
              *sim.machine(elf),
              f"sysbus WriteDoubleWord 0x{sym['c2_caso']:08x} {caso.numero}",
              f"sysbus.cpu AddHook 0x{sym['c2_falha']:08x} {py('falha')}",
              f"sysbus.cpu AddHook 0x{sym['c2_fim']:08x} {py('fim')}"]
    if full:
        enderecos = [sym[s] for s in caso.ganchos] + [r for s in caso.retornos for r in retornos(elf, s)]
        linhas += [f"sysbus.cpu AddHook 0x{a:08x} {py('A')}" for a in enderecos]
        linhas += [f"sysbus AddWatchpointHook 0x{a:08x} DoubleWord Write {py('W')}" for a in caso.escritas]
        if caso.traco:
            linhas.append(f'sysbus.cpu CreateExecutionTracing "t" @{d / "traco.txt"} PC')
    t = 0
    for k, p in enumerate(sorted(pausas, key=lambda p: p.ns)):
        (d / f"pausa{k}.py").write_text(GANCHO["pausa"].format(dir=d, leituras=p.leituras, escritas=p.escritas))
        if p.ns > t:
            linhas.append(f'emulation RunFor "{(p.ns - t) / 1e9:.9f}"')
        linhas.append(f"python {py(f'pausa{k}')}")
        t = p.ns
    linhas += [f'emulation RunFor "{(caso.run_ns - t) / 1e9:.9f}"', "quit", ""]
    resc = d / "run.resc"
    resc.write_text("\n".join(linhas))
    return resc


def le(d: Path) -> Execucao:
    ev: dict[str, list] = {"A": [], "W": []}
    if (d / "eventos.txt").exists():
        for line in (d / "eventos.txt").read_text().splitlines():
            k, *f = line.split()
            base = (16, 10, 10, 16) if k == "A" else (16, 16, 10, 10, 16)
            v = [int(x, b) for x, b in zip(f, base)]
            if k == "A":
                v[3] &= 0x1FF                   # xPSR → IPSR
            ev[k].append(tuple(v))
    fim, rec = [], []
    if (d / "mem.txt").exists():
        cab, _, corpo = (d / "mem.txt").read_text().partition("\n")
        fim, rec = [int(x) for x in cab.split()], [int(x) for x in corpo.split()]
    pausas = [[int(x) for x in line.split()[1:]] for line in (d / "pausas.txt").read_text().splitlines()] \
        if (d / "pausas.txt").exists() else []
    traco = [int(x, 16) for x in (d / "traco.txt").read_text().split()] if (d / "traco.txt").exists() else None
    return Execucao(ev["A"], ev["W"], pausas, rec, fim, traco, (d / "falha.txt").exists())


def executa(out: Path, elf: Path, sym: dict[str, int], caso: Caso, reps: int) -> None:
    ref: dict = {}
    if caso.referencia is not None:
        d = out / caso.id / "ref"
        d.mkdir(parents=True)
        print(f"{caso.id}/ref …", flush=True)
        rc = caso.referencia(sym)
        sim.run(escreve_resc(d, elf, sym, rc, True, rc.pausas(sym, {}) if rc.pausas else []), d / "renode.log")
        ref = {"execucao": le(d)}
    pausas = caso.pausas(sym, ref) if caso.pausas else []
    for variante in ("bare", "full") if caso.instrumentado else ("bare",):
        for rep in range(reps):
            d = out / caso.id / f"{variante}-{rep}"
            d.mkdir(parents=True)
            print(f"{caso.id}/{d.name} …", flush=True)
            sim.run(escreve_resc(d, elf, sym, caso, variante == "full", pausas), d / "renode.log")


# ───────────────────────────── análise ─────────────────────────────

def analisa_caso(d: Path, sym: dict[str, int], caso: Caso) -> tuple[str, list[str]]:
    runs = {p.name: le(p) for p in sorted(d.iterdir()) if p.is_dir() and p.name != "ref"}
    if (d / "ref").exists():
        runs["ref"] = le(d / "ref")
    notas: list[str] = []
    invalida = []
    for nome, r in runs.items():
        if r.falha or not r.fim or r.fim[2] != 1:
            invalida.append(f"{nome}: firmware não chegou ao fim" + (" (exceção inesperada)" if r.falha else ""))
    if invalida:
        return "EVIDÊNCIA INVÁLIDA", invalida
    recs = {tuple(r.rec) for nome, r in runs.items() if nome != "ref"}
    if len(recs) != 1:
        return "EVIDÊNCIA INVÁLIDA", ["registro do firmware difere entre variantes ou repetições "
                                      "(observador intrusivo ou execução não determinística)"]
    deterministico = True
    for v in ("bare", "full"):
        iguais = {tuple((d / n / f).read_bytes() if (d / n / f).exists() else b"" for f in BRUTOS)
                  for n in runs if n.startswith(v)}
        if len(iguais) > 1:
            deterministico = False
            notas.append(f"repetições da variante {v} diferem nos arquivos brutos")
    nomes = [n for n in runs if n != "ref"]
    notas.append(f"execuções: {', '.join(nomes)}; fim do caso em {runs['bare-0'].fim[0] / 1000:.1f} µs "
                 f"de tempo virtual ({runs['bare-0'].fim[1]} instruções); registro do firmware igual em todas")
    veredito, linhas = caso.analisa(runs, sym)
    if not deterministico:
        veredito = f"NÃO DETERMINÍSTICO ({veredito})"
    return veredito, notas + linhas


def main(firmware: str, casos: list[Caso], doc: str) -> None:
    ap = argparse.ArgumentParser(description=doc)
    ap.add_argument("--name", required=True, help="nome da campanha (data/c2/<firmware>/<nome>)")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--casos", nargs="*", help="só estes casos (ex.: C2-01 C2-04)")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--analyze", action="store_true", help="só refaz o resultado")
    a = ap.parse_args()
    elf = sim.ROOT / "build" / firmware / "firmware.elf"
    out = sim.ROOT / "data" / "c2" / firmware / a.name
    escolhidos = [c for c in casos if not a.casos or c.id in a.casos]
    if not a.analyze:
        if out.exists():
            raise SystemExit(f"{out} já existe")
        if not a.no_build:
            shutil.rmtree(sim.ROOT / "build" / firmware, ignore_errors=True)
            subprocess.run(["cmake", "--workflow", "--preset", firmware], cwd=sim.ROOT, check=True,
                           stdout=subprocess.DEVNULL)
        sym = sim.symbols(elf)
        usados = {s: sym[s] for s in sorted(set(SIMBOLOS) | {g for c in escolhidos for g in c.ganchos + c.retornos})
                  if s in sym}          # o que o firmware não usa sai no --gc-sections
        out.mkdir(parents=True)
        env = {**sim.environment(elf), "simbolos": usados, "repeticoes": a.reps,
               "casos": [c.id for c in escolhidos]}
        (out / "ambiente.json").write_text(json.dumps(env, indent=2, ensure_ascii=False) + "\n")
        for c in escolhidos:
            executa(out, elf, sym, c, a.reps)
    env = json.loads((out / "ambiente.json").read_text())
    sym = env["simbolos"]
    feitos = [c for c in escolhidos if (out / c.id).exists()]
    res = {c.id: analisa_caso(out / c.id, sym, c) for c in feitos}
    linhas = [f"# C2, firmware `{firmware}`: campanha `{out.name}`", "",
              "| | |", "|---|---|",
              *(f"| {k} | `{v}` |" for k, v in env.items() if k not in ("simbolos", "casos")),
              "| instrumentos | Q-01 IGUAL (`data/q/piloto-01`) |", "",
              "| Caso | Veredito |", "|---|---|",
              *(f"| {k} | **{v[0]}** |" for k, v in res.items())]
    for k, (v, detalhe) in res.items():
        linhas += ["", f"## {k}: {v}", "", *(f"- {x}" for x in detalhe)]
    (out / "resultado.md").write_text("\n".join(linhas) + "\n")
    print("\n".join(linhas))
    raise SystemExit(1 if any(v.startswith(("EVIDÊNCIA", "NÃO DET")) for v, _ in res.values()) else 0)


def veredito(erros: list[str], total: int, o_que: str) -> tuple[str, list[str]]:
    """IGUAL se não há erros; senão DIVERGE, com até 12 exemplos."""
    if not erros:
        return "IGUAL", [f"{total}/{total} {o_que} iguais ao documento"]
    return "DIVERGE", [f"{total - len(erros)}/{total} {o_que} iguais ao documento; divergentes "
                       f"(até 12): " + "; ".join(erros[:12])]
