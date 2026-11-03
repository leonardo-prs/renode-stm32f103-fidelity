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
src/c2/           C2: c2.c/c2.h/c2.ld comuns; sw.c (etapas 1–2), mon.c (etapa 3), tim.c (etapa 4)
scripts/sim.py    comum: máquina do projeto, execução do Renode, símbolos, ambiente
scripts/q.py      caso Q-01
scripts/c2_comum.py   C2: execuções bare/full × repetições, ganchos, pausas, validade, resultado
scripts/c2_sw.py, c2_mon.py, c2_tim.py   C2: casos de cada firmware e a resposta do documento
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
| `C2-01`–`C2-03` | Pendência, prioridade e empate, preempção | IGUAL | `data/c2/c2-sw/piloto-01` |
| `C2-04` | Máscaras | DIVERGE (leitura de `BASEPRI` com 8 bits; efeito igual) | idem |
| `C2-05` | Latência de entrada (STIR) | DIVERGE (1 ciclo × 12) | idem |
| `C2-06` | Encadeamento | IGUAL (#qF), DIVERGE (#qT: 1 ciclo × 6) | idem |
| `C2-07` | Chegada tardia | DIVERGE; fronteira deslocada (K = 1) | `data/c2/c2-mon/piloto-01` |
| `C2-08` | Chegada durante o retorno | IGUAL (janela de 1 tick) | idem |
| `C2-09` | `WFI` e `PRIMASK` | IGUAL | idem |
| `C2-10` | Período do TIM2 | DIVERGE ((PSC + 1)·ARR) | `data/c2/c2-tim/piloto-01` |
| `C2-11` | Empate entre timers | IGUAL | idem |
| `C2-12` | Coalescência | IGUAL; fronteira reproduzida | idem |
| `C2-13`–`C2-16` | C2 etapa 5: placa (#oP) | a implementar | — |

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

## C2 — interrupções, etapas 1 a 4 (#oD, só Renode)

```
python3 scripts/c2_sw.py  --name piloto-01      # C2-01–C2-06, preset c2-sw
python3 scripts/c2_mon.py --name piloto-01      # C2-07–C2-09, preset c2-mon
python3 scripts/c2_tim.py --name piloto-01      # C2-10–C2-12, preset c2-tim
  [--casos C2-04 …] [--reps 3] [--no-build] [--analyze]
```

Um firmware por etapa (as etapas 1–2 compartilham), todos com os vetores
e a partida de `src/c2/c2.c`: todas as linhas de interrupção vão para um
tratador `c2_irq`, que anota o número da exceção num registro circular e
numa contagem por exceção. O monitor grava o número do caso em `c2_caso`
antes da partida; o firmware percorre todos os pontos do caso e grava em
`c2_rec` o que viu; o gancho em `c2_fim` despeja o registro.

- Variante `bare` (só estímulo e fim) em todos os casos; variante `full`
  (ganchos de endereço, de escrita, de retorno e traço) nos casos que
  medem tempo ou janela. Três repetições de cada (reinício da máquina).
- Validade: fim sem exceção inesperada, registro do firmware igual em
  todas as execuções (não intrusão), repetições idênticas nos brutos.
- Estímulos: escrita do firmware (etapas 1–2, 4), escrita no `ISPR` ou
  em `TIMx_CR1` pelo monitor com a simulação parada (etapa 3, `C2-11`).
- `data/c2/<firmware>/<campanha>/`: `ambiente.json`, uma pasta por caso
  com as execuções (`bare-N`, `full-N`, `ref`), `resultado.md`.

## Depuração no VS Code

Tarefas e configurações em `.vscode/`: "Build: q" e "Renode: q" (sobe o
Renode com GDB em :3334 por `scripts/renode_start.sh` e encerra no fim).

## Material retirado

O C1 herdado, a primeira implementação do C2, as versões anteriores do
caso Q e o código do plano anterior foram movidos para `tmp/legado/` (não
versionado; índice em `tmp/legado/README.md`) e continuam no histórico do
jj.
