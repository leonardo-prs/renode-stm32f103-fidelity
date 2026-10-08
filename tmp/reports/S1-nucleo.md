# S1 — Núcleo e memória (firmwares s1a, s1b)

*Relatório intermediário. Metodologia comum: `00-metodologia.md`. Dados:
`data/fidelity/v1/{s1a,s1b}/`, análise `data/fidelity/v1/analysis/s1{a,b}.md`.*

## 1. Pergunta

O tempo de execução de código puro de CPU no Renode corresponde ao da
bancada? Se não, a diferença é explicada por um mecanismo identificável e
pode ser compensada por um parâmetro global (MIPS)?

## 2. Fundamentação

- Equação de desempenho: T = IC × CPI × T_clk; CPI = Σ IC_i·CPI_i / IC;
  "CPI_i should be measured and not just calculated from a table" (HENNESSY;
  PATTERSON, 2019, §1.9, pp. 52–54).
- Cortex-M3 r2p0, 0 wait states (DDI0337G Tab. 18-1, pp. 18-3..18-5;
  §18.3 pp. 18-7..18-8): ALU/MUL 1; LDR 2 com pipelining N+1 se o destino
  não forma o endereço seguinte; STR com imediato 1; desvio tomado 2 (1+P);
  LDM 1+N; UDIV 2–12 (terminação antecipada).
- Renode 1.17: tempo virtual = instruções ÷ PerformanceInMips (`BaseCPU.cs`
  L508–520); DWT é um `LimitTimer` sobre esse tempo (`DWT.cs`). Previsão:
  **toda instrução custa 8/MIPS ticks**, independentemente da classe.
- Microbenchmarks por classe como método de diagnóstico de simulador:
  AKRAM; SAWALHA, 2019 (§II, p. 54 — gem5/x86; usado como precedente
  metodológico, não como margem).

## 3. Desenho

**s1a** — 14 kernels em assembly (`src/s1/isa_kernels.S`), cada laço com
**16 instruções de uma única classe** + SUBS/BNE (o gate conta no ELF):
laço vazio, ADDS, MULS, UDIV rápido/lento, LDR independente/dependente, STR,
LDR de flash, desvio tomado, LDM×4, um **mix designado de calibração**
(congelado) e ADDS/LDR executando da SRAM. Medição por **inclinação**: cada
kernel roda com N = 8 e N = 264 iterações; (T₂₆₄ − T₈)/256 = custo por
iteração, sem chamada nem observador. 4 trials quentes + 1 linha COLD (1ª
execução após reset). Assinatura funcional de cada kernel × oráculo do host.

**s1b** — 6 cargas C reais em `-O2` (CRC32 bit a bit, insertion sort 64,
matmul 8×8 int32, FIR 16×128 q15, cópia 1 KiB, raiz inteira por Newton com
UDIV) + bracket vazio; entradas novas por trial (xorshift32), 8 trials
quentes + COLD; assinatura × oráculo do host (reimplementação Python).
Medição pelo bracket em asm `fidelity_measure`.

## 4. Resultados

### 4.1 Funcional

Assinaturas = oráculo do host em **100 %** das linhas, nos dois ambientes e
em todas as configurações (s1a 126/126 por run; s1b 63/63 por run). O Renode
executa a semântica de ALU/MUL/UDIV/LDR/STR/LDM/desvio corretamente.

### 4.2 Custo por classe (s1a) — o mecanismo

| classe (16 instr. + SUBS/BNE) | TRM (ciclos/iter) | HW medido | Renode 8 MIPS | CPI HW |
|---|---|---|---|---|
| laço vazio (2 instr.) | 3 | 3 | 2 | 1,50 |
| ADDS | 19 | 19 | 18 | 1,06 |
| MULS | 19 | 19 | 18 | 1,06 |
| STR | 19 | 19 | 18 | 1,06 |
| LDR independente | 20 (N+1) | 20 | 18 | 1,11 |
| LDR dependente | 35 | 35 | 18 | 1,94 |
| B tomado | 35 | 35 | 18 | 1,94 |
| LDM {4} | 83 | 83 | 18 | 4,61 |
| UDIV rápido | 2–12 | 51 (3/UDIV) | 18 | 2,83 |
| UDIV lento | 2–12 | 195 (12/UDIV) | 18 | 10,83 |
| LDR de flash | 2+contenção | 26 | 18 | 1,44 |
| mix (calibração) | 23 nominal | 22 | 18 | 1,22 |
| ADDS executando da SRAM | — | 20 | 18 | 1,11 |
| LDR executando da SRAM | — | 29 | 18 | 1,61 |

- **HW = TRM ciclo a ciclo** em todas as classes com valor fixo; os trials
  quentes são idênticos bit a bit entre runs (determinismo total).
- **Renode = 18 ticks em todas as classes** (laço vazio 2): o modelo
  instruções/MIPS confirmado experimentalmente. O "CPI" do Renode é imposto
  (≡ 1 a 8 MIPS); o HW varia de 1,06 a 10,8 — fator **10×** entre classes.

### 4.3 Primeira execução (COLD − WARM, mesmo N)

HW: **+110 a +440 ciclos** na 1ª execução de cada kernel **em flash** (v1:
loop 217, alu 223, udiv_fast 440, ldr 328, ldm 306, mix 110…; os valores
mudam com o layout do binário); **zero** para os kernels em SRAM; reprodutível bit a bit a cada reset, com e sem
depurador conectado (free-run com *polling* desligado) e independente do
tempo desde o boot (atraso de 200 ms testado). O RM0008 descreve só um
*prefetch buffer* de 2×64 bits (§3.3.3, p. 54), sem cache — o efeito é
atribuído à placa (provável clone, metodologia §5). Renode: 0 (±5 de
resolução).

### 4.4 Cargas reais (s1b) e validação da calibração (campanha v1)

Medianas dos 8 trials quentes (HW: 10 runs; Renode: 2–3 runs, idênticos
entre si). Erro = (Renode − HW)/HW, pareado por trial (mesmos dados de
entrada).

| carga | HW (ciclos) | CPI efetivo (HW/RN8) | erro 8 MIPS (nominal) | erro **7 MIPS (calibrado)** | erro 100 MIPS (padrão) | erro 8 MIPS q125 ns |
|---|---|---|---|---|---|---|
| crc32 | 15 639 | 1,36 | −26,3 % | −15,7 % | −94,1 % | −26,3 % |
| isort | 11 697 | 1,28 | −21,7 % | −10,6 % | −93,7 % | −21,8 % |
| matmul | 5 873 | 1,55 | −35,4 % | −26,2 % | −94,8 % | −35,5 % |
| fir | 19 872 | 1,72 | −42,0 % | −33,7 % | −95,4 % | −42,0 % |
| memcpy | 1 823 | 1,74 | −42,5 % | −34,6 % | −95,4 % | −42,7 % |
| isqrt | 16 173 | 2,06 | −51,5 % | −44,5 % | −96,1 % | −51,5 % |

- A política calibrada (pré-declarada: MIPS = 7 = round(8/1,222), mix do
  S1A) **reduz** o erro em todas as cargas, mas deixa −11 % a −45 %: o mix
  designado (CPI 1,22) não representa código compilado real (CPI 1,28–2,06,
  mais desvios tomados, LDR dependentes de pilha, UDIV).
- **Limite analítico de qualquer MIPS único** (não é política, é análise a
  posteriori): com erro = 8/(M·CPI) − 1 e CPI ∈ [1,28; 2,06], o melhor M
  contínuo (≈ 5,07) dá ±23,4 %; o melhor inteiro (M = 5) dá +25 % / −22 %.
  Nenhuma escolha de MIPS deixa todas estas seis cargas abaixo de ~±22 %.
- O padrão do Renode (100 MIPS) subestima o tempo em ~94–96 %: é "rodar o
  mais rápido possível", não uma hipótese de fidelidade.
- O quantum (1 µs × 125 ns) **não altera** o tempo de CPU; só melhora a
  resolução de leitura do DWT (bracket vazio: 9 → 4 ticks).

## 5. Interpretação

1. **Funcional: fiel.** A execução de instruções (resultados) é exata.
2. **Temporal: não fiel por construção, mas previsível.** O Renode mede
   *contagem de instruções*, não ciclos; a razão HW/Renode é o CPI da carga,
   que no Cortex-M3 varia 10× entre classes. A TRM prevê o CPI do HW ciclo a
   ciclo — o simulador poderia ser corrigido por um modelo de custo por
   classe; o parâmetro global MIPS não basta.
3. **MIPS como calibração:** um único valor só acerta cargas com o mesmo
   perfil do kernel de calibração; a granularidade inteira do parâmetro
   (12–14 % a 8 MHz) limita ainda mais.

## 6. Limitações

- Placa provavelmente clone: o núcleo é Cortex-M3 r2p0 legítimo (tempos =
  TRM), mas o efeito de 1ª execução e a contenção da LDR de flash podem ser
  específicos da memória do clone.
- Sem caches nem wait states a 8 MHz: frequências maiores (com WS) teriam
  CPI_HW maiores e mais variáveis.
- Cargas s1b pequenas (1–20 k ciclos); representativas de laços de firmware,
  não de aplicações inteiras.
