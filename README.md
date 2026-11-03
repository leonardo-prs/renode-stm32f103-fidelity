# Renode × STM32F103 — código e simulação do TCC (EA019, UNICAMP)

Código do TCC *"Análise quantitativa da fidelidade funcional e temporal do
Renode em relação ao hardware no STM32F103"*. A especificação dos casos é
a fundamentação (`tcc/documentacao/fundamentacao/`); as decisões de
implementação e os resultados ficam em `tcc/documentacao/desenvolvimento/`.
Este README documenta o código e como reproduzi-lo.

## Ambiente

```
nix develop            # ou direnv: arm-none-eabi-gcc, cmake, ninja, renode 1.17.0, python3
```

Um preset CMake por firmware (`cmake --workflow --preset <preset>` →
`build/<preset>/firmware.elf`), `-O2 -g3`, sem HAL/LL, só os headers CMSIS
de `vendor/`. Zero warnings. Python só com a biblioteca padrão.

## Estrutura

```
src/q/            firmware do caso Q-01 (q.c, q.ld)
scripts/sim.py    comum: máquina do projeto, execução do Renode, símbolos, ambiente
scripts/q.py      caso Q-01
renode/stm32f103_hsi8.repl   plataforma do projeto (perfil R1: 8 MIPS, quantum 125 ns)
renode/debug.resc            depuração no VS Code (GDB em :3334)
vendor/           CMSIS e SVD congelados
data/<caso>/<campanha>/      dados das campanhas (não versionado)
```

Cada caso é um firmware em C e um script Python. O script gera o `.resc`
de cada execução, roda o Renode num processo novo (`--port -1`), compara
o que foi observado com a referência do caso e escreve `resultado.md` com
o ambiente (SHA-256 do ELF, versão do Renode, revisão, data).

## Estado

| Caso | O quê | Resultado | Campanha |
|---|---|---|---|
| `Q-01` | Verificação dos instrumentos do Renode | IGUAL, 17/17 critérios | `data/q/piloto-01` |
| `C2-01`–`C2-16` | Interrupções, em 5 etapas (`04-c2.typ`) | a implementar | — |

## Q-01 — instrumentos do Renode

```
python3 scripts/q.py --name piloto-01            # build do zero, execuções, resultado
python3 scripts/q.py --name piloto-01 --analyze  # refaz só o resultado
```

Verifica, sem oráculo, cada instrumento do Renode que os casos usam contra
uma referência independente dele (`03-quadro-comum.typ`, §Verificação dos
instrumentos do Renode). Saída: 0 = IGUAL, 1 = REPROVADO.

- `src/q/q.c` — firmware em C, só núcleo, SRAM e SCS/DWT, em duas
  passagens: pontos marcados (`q_mark` grava o `DWT_CYCCNT`), escritas por
  `q_store` (`str` + `bx lr`) numa palavra da SRAM e no ICSR, PendSV e
  SysTick pedidos pelo ICSR (simples, encadeados, aninhados), um gancho que
  grava na SRAM (`q_trigger`) e duas esperas por valores que o monitor
  grava em pausas. O que o firmware viu fica em `q_rec`.
- `scripts/q.py` — duas variantes (`bare`: só estímulos; `full`: ganchos
  de endereço, de escrita, de início e fim de exceção e traço) × 2
  repetições; 17 critérios (tempo virtual × instruções × `DWT_CYCCNT` ×
  traço; escrita na instrução do store, com R0/R1; uma passagem por entrada
  em tratador; monitor e gancho que gravam; não intrusão; repetições
  idênticas).

## Depuração no VS Code

Tarefas e configurações em `.vscode/`: "Build: q" e "Renode: q" (sobe o
Renode com GDB em :3334 por `scripts/renode_start.sh` e encerra no fim).

## Material retirado

O C1 herdado, a primeira implementação do C2, as versões anteriores do
caso Q e o código do plano anterior foram movidos para `tmp/legado/` (não
versionado; índice em `tmp/legado/README.md`) e continuam no histórico do
jj.
