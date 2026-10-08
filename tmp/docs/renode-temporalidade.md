# Temporalidade do Renode na avaliação do STM32F103

Registro técnico de investigação — 7 de outubro de 2026. Escopo: Renode **v1.17.0**, STM32F103C8T6 com HSI nominal de 8 MHz e firmware bare metal. As constatações abaixo provêm de documentação técnica, código-fonte e respostas de mantenedores; **não são resultados experimentais de equivalência com a bancada**. As fontes e seus localizadores estão em [renode-fontes.md](../context/renode-fontes.md). A fundamentação acadêmica e o protocolo experimental pertencem a [metodologia-cenarios.md](metodologia-cenarios.md), documento complementar em elaboração.

## 1. Versão e domínios de tempo

O código inspecionado corresponde aos componentes do Renode v1.17.0:

- `renode-infrastructure`: `066a7f13c052215632d469c995c89aea37c573b1`;
- `antmicro/tlib`: `167decf9129758829762e582939128c0694e90d6`.

A documentação pública em `latest` é uma referência explicativa móvel: não substitui esses identificadores para descrever a implementação avaliada.

Devem ser separados quatro observáveis:

1. **Tempo físico:** passagem de tempo na bancada, sujeita aos clocks efetivos e aos instrumentos disponíveis.
2. **Tempo virtual Renode:** agenda da simulação, avançada pelos participantes do framework temporal.
3. **Contadores emulados:** DWT, TIM e SysTick, derivados dos modelos e da fonte virtual; não constituem medições físicas independentes.
4. **Tempo do host:** duração real do processo, esperas, logs e custo de instrumentação do simulador.

O framework representa tempo virtual em unidades de 1 ns. O **quantum** é um intervalo de sincronização, não uma resolução universal de todos os eventos ou periféricos. A opção `AdvanceImmediately` permite avançar sem esperar o relógio do host; não representa um clock físico. O comportamento padrão procura não executar adiantado em relação ao host, mas não garante execução em tempo real: carga computacional e instrumentação podem atrasá-la.

## 2. CPU: instruções convertidas em tempo, não ciclos microarquiteturais

Em `BaseCPU.cs`, linhas 508–520, o tempo reportado é obtido por `TimeInterval.FromCPUCycles(instructions + residuum, PerformanceInMips)`. Apesar do nome do método, a quantidade de entrada é uma contagem de **instruções executadas**. `TranslationCPU.cs`, linhas 143–146, obtém essa contagem via `TlibGetTotalExecutedInstructions`: trata-se de instruções ARM, não de operações intermediárias TCG. O valor padrão de `PerformanceInMips` é **100** (`BaseCPU.cs`, linha 360).

Para um trecho com aproximadamente N instruções executadas e desempenho configurado M MIPS, a relação de referência é:

\[
\Delta t_{RN} \approx \frac{N}{M\,10^6}\;\mathrm{s}.
\]

A aproximação explicita o modelo, não promete precisão de cada leitura: sincronização, resíduos e granularidade de execução precisam ser considerados. Essa conversão não fornece um modelo microarquitetural dos custos de cargas, desvios, divisões, pipeline, stalls de memória ou entrada/saída de exceções do Cortex-M3. O campo `CPICNT` aparece apenas como tag no modelo inspecionado, não como contador validado desses custos.

Assim, **MIPS configurado não é HCLK**. Configurar 8 MIPS apenas estabelece a hipótese nominal de uma instrução por período de um HCLK de 8 MHz; não estima o CPI físico, não foi ajustado aos dados e não constitui validação temporal. A proposta é usar 8 MIPS como condição nominal e 100 MIPS como controle explícito, com análise de sensibilidade do quantum (1 µs e 125 ns). **Essa proposta permanece pendente de aprovação do gate metodológico.** Não se admite ajuste por cenário, fitting dos tempos físicos ou reescalonamento da agenda de estímulos para obter concordância.

## 3. DWT, TIM, RCC e SysTick

O `DWT.cs` cria um `LimitTimer` sobre `machine.ClockSource` (linhas 17–20) e sincroniza a CPU antes de ler o contador (linhas 54–63). Com frequência do modelo em 8 MHz:

\[
\Delta\mathrm{DWT}_{RN} \approx 8\,\frac{N}{M}.
\]

Consequentemente, DWT simulado não é evidência de ciclos físicos gastos pelo núcleo. Comparar DWT e TIM no Renode pode verificar coerência interna, mas **não validar independentemente a fidelidade temporal**: ambos derivam da mesma fonte virtual. O `STM32_Timer` recebe fonte de clock e frequência no construtor (linhas 24–30); a leitura de CNT chama `SyncTime` (linhas 329–333).

Não foi identificado um modelo completo de RCC F1 disponível para reproduzir a árvore de clocks exigida aqui. Tags locais de CR não implementam a árvore de clocks; um modelo de outra família não deve ser usado como substituto presumidamente equivalente. Frequências dos periféricos precisam ser registradas como parâmetros explícitos, sem atribuir-lhes uma derivação automática de HSI/AHB/APB.

No NVIC inspecionado, `CLKSOURCE` do SysTick é lido como 1 e escritas são ignoradas (linhas 1039–1040). Portanto, selecionar HCLK/8 no firmware não implica que o modelo o reproduza automaticamente.

## 4. Exceções: estado funcional não demonstra custo temporal

O código ARM de `tlib` implementa transições de exceção e quadros de estado. Nos trechos localizados de `arch/arm/helper.c` não foi encontrada cobrança dos custos físicos de 12 ou 6 ciclos usualmente associados a certas transições Cortex-M. Isso não nega a implementação funcional de mecanismos de exceção; impede inferir seu custo temporal a partir de mudanças de estado.

Em particular, uma sequência de IRQs compatível com tail-chaining funcional **não comprova tail-chaining temporal**. Preempção e arbitragem devem ser demonstradas por nesting, estados ativo/pendente, prioridades e ordem de eventos, com controles negativos; timestamps isolados não bastam. Os comentários de mantenedores nas issues #518 e #445 corroboram o escopo funcional e a ausência de precisão ciclo a ciclo, mas não substituem a inspeção da versão fixada.

## 5. USART: atraso de entrega não é ocupação física do transmissor

No modelo `STM32_UART`, a frequência padrão é 8 MHz. `CharacterTransmissionDelay` começa vazio; `AutoUpdateDelay` é falso por padrão e `DelayMultiplier` é 1. Com atualização automática habilitada, o atraso é calculado segundo baud rate e formato do caractere. Para 8N1 e BRR `0x45` = 69:

\[
\mathrm{baud}=\frac{8\,10^6}{69},\qquad
t_{quadro}=\frac{10\times69}{8\,10^6}=86{,}25\;\mu\mathrm{s}.
\]

São **690 períodos nominais de HCLK por quadro**, não 694. O valor deriva do divisor programado, não da aproximação de 115200 baud.

O `UARTHub` aceita loopback incluindo o emissor. Agenda a entrega a partir de `now + CharacterTransmissionDelay` do UART emissor e do mecanismo de atraso do destinatário. A sintaxe abaixo foi validada **no código-fonte, não em execução** para a versão fixada:

```text
emulation CreateUARTHub "uartLoopback" true
connector Connect sysbus.usart1 uartLoopback
sysbus.usart1 DelayMultiplier 1
sysbus.usart1 AutoUpdateDelay true
```

Essa configuração é um loopback passivo proposto, sem firmware de peer ativo. Sua contraparte física seria PA9/TX → PA10/RX, sem remapeamento; **a presença dessa ligação em bancada ainda não foi confirmada**.

O atraso do hub não corrige limitações do UART: TXE é sempre verdadeiro, TC é imediato e ORE é sempre falso nos campos inspecionados. Tampouco serializa automaticamente a ocupação física de TX. Uma rajada pode, portanto, produzir um contraexemplo à equivalência, mesmo com atraso de entrega. Um byte a cada 10 ms é um controle descarregado útil para restringir esse problema, não prova geral de fidelidade de throughput, overrun ou serviço sob blackout.

Uma agenda determinística de estímulos a cada 10 ms permite comparar entradas nominais; a quantidade de trabalho CPU executada entre estímulos continuará dependente do modelo instruções/MIPS. **A agenda não deve ser reescalada para acomodar os resultados.**

## 6. Instrumentação: usos e limites

As ferramentas versionadas ficam em `renode/tools` no tag v1.17.0. Seu uso deve ser separado da execução principal quando houver custo diagnóstico significativo.

| Recurso | Uso admissível | Limite relevante |
|---|---|---|
| Execution tracer | Inspecionar PCs e opcodes executados; confirmar kernels e caminhos | `PCAndOpcode` não implica timestamp por instrução |
| `gdb_compare` | Comparar execução passo a passo e estados funcionais | Não é comparação de ciclos físicos |
| Profiler / `metrics_analyzer` | Contagens de instruções, memória, acessos a periféricos e exceções | Não confundir métricas com `CurrentLoad` ou carga do host |
| RESD / `csv2resd` | Replay com timestamps virtuais em ns em consumidores suportados | Não é injeção universal em GPIO; `UARTRESDFeeder` é consumidor específico |
| Log de acessos | Diagnóstico de registros e sequência de acessos | Timestamp de log do host não é automaticamente tempo virtual |

Exemplos documentados de instrumentação, **não executados nesta investigação**:

```text
cpu CreateExecutionTracing "tracer" @trace.bin PCAndOpcode true
machine EnableProfiler @metrics.dump
sysbus LogPeripheralAccess sysbus.timer2 true
sysbus LogPeripheralAccess sysbus.usart1 true
```

Um `Sleep` genérico de Robot Framework espera no host, não avança necessariamente um intervalo virtual determinado. Um UART tester com correspondência esperada deve ser instalado **antes** de iniciar a execução, para evitar perder o evento observado. Diagnósticos devem preservar hashes, parâmetros temporais e domínio de timestamp, sem tratar a lentidão causada por logs como comportamento físico do MCU.

## 7. Consequências para a avaliação

- Fixar versão, ELF e configuração; registrar MIPS, quantum, frequências e opções do UART em cada execução.
- Verificar primeiro invariantes funcionais e instruções efetivamente presentes no ELF; diferenças temporais não substituem essa verificação.
- Apresentar separadamente tempo virtual, contadores simulados e tempo do host. Não rotular DWT Renode como medição de ciclos físicos.
- Comparar configurações predeclaradas sem calibrar por ensaio. Coerência entre contadores da mesma fonte não deve ser usada como validação independente.
- Interpretar discrepâncias no domínio e sob as condições observadas. Não estabelecer margens de equivalência sem fundamentação e protocolo; não extrapolar drift universal de ±1% do HSI nem inferir WCET.
- Registrar como pendentes a aprovação da proposta temporal, a validação runtime do loopback e a confirmação da ligação física. Nenhuma delas foi realizada por esta transcrição documental.

**Conclusão:** Renode oferece execução funcional e uma agenda virtual reproduzível sob configuração controlada, mas o modelo inspecionado não sustenta a equivalência ciclo a ciclo do Cortex-M3. Ajustar MIPS ou atrasar a entrega de UART não elimina essa limitação. A investigação deve medir onde há concordância funcional e quais discrepâncias temporais persistem, sem converter configuração nominal em validação física.
