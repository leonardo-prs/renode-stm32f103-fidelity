# Fontes técnicas sobre temporalidade do Renode

Registro de fontes estabelecidas na investigação, transcrito em 7 de outubro de 2026. **Não são referências acadêmicas:** são documentação de software, código-fonte primário e discussões técnicas de mantenedores. A fundamentação metodológica acadêmica deve ser tratada separadamente em [metodologia-cenarios.md](../docs/metodologia-cenarios.md). A síntese interpretativa está em [renode-temporalidade.md](../docs/renode-temporalidade.md).

## 1. Identificação da versão

Versão estudada: [Renode v1.17.0](https://github.com/renode/renode/tree/v1.17.0).

| Componente | Revisão exata |
|---|---|
| `renode-infrastructure` | `066a7f13c052215632d469c995c89aea37c573b1` |
| `antmicro/tlib` | `167decf9129758829762e582939128c0694e90d6` |

Os links de código abaixo fixam revisão e linhas. Links de documentação `latest` são móveis: servem como manuais explicativos, não como prova de que toda funcionalidade descrita existe exatamente nessa versão. Linhas são localizadores dos trechos inspecionados; conclusões ficam limitadas a esses modelos.

## 2. Código-fonte primário — CPU, clocks e exceções

| Fonte fixada | Trechos e evidência estabelecida |
|---|---|
| [BaseCPU.cs — tempo reportado](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/CPU/BaseCPU.cs#L508-L520) | Conversão de `instructions + residuum` com `PerformanceInMips` |
| [BaseCPU.cs — padrão MIPS](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/CPU/BaseCPU.cs#L360) | Padrão 100 MIPS |
| [TranslationCPU.cs — contagem](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/CPU/TranslationCPU.cs#L143-L146) | `TlibGetTotalExecutedInstructions`, instruções ARM, não operações TCG |
| [TranslationCPU.cs — SyncTime](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/CPU/TranslationCPU.cs#L668-L679) | Sincronização temporal da CPU |
| [DWT.cs — construção](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Cores/Arm-M/DWT.cs#L17-L20) | `LimitTimer(machine.ClockSource, frequency, ...)` |
| [DWT.cs — leitura](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Cores/Arm-M/DWT.cs#L54-L63) | `SyncTime` antes da leitura do contador |
| [NVIC.cs — CLKSOURCE](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Cores/Arm-M/NVIC.cs#L1039-L1040) | Leitura fixa em 1; escritas ignoradas, sem seleção automática de HCLK/8 |
| [STM32_Timer.cs — construção](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/Timers/STM32_Timer.cs#L24-L30) | Fonte de clock e frequência do modelo |
| [STM32_Timer.cs — CNT](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/Timers/STM32_Timer.cs#L329-L333) | Leitura sincronizada com `SyncTime` |

O exame de `DWT.cs` identifica `CPICNT` como tag, não como modelagem dos stalls físicos. A ausência de um RCC F1 completo disponível é uma limitação do levantamento estabelecido, não uma afirmação sobre todos os modelos futuros ou sobre outra família STM32. Tags locais não constituem uma árvore de clocks.

No backend ARM, os localizadores de exceções são [helper.c, linha 1150](https://github.com/antmicro/tlib/blob/167decf9129758829762e582939128c0694e90d6/arch/arm/helper.c#L1150), [linhas 1304–1315](https://github.com/antmicro/tlib/blob/167decf9129758829762e582939128c0694e90d6/arch/arm/helper.c#L1304-L1315), [linha 1876](https://github.com/antmicro/tlib/blob/167decf9129758829762e582939128c0694e90d6/arch/arm/helper.c#L1876), [linhas 1950–1953](https://github.com/antmicro/tlib/blob/167decf9129758829762e582939128c0694e90d6/arch/arm/helper.c#L1950-L1953) e [linha 2023](https://github.com/antmicro/tlib/blob/167decf9129758829762e582939128c0694e90d6/arch/arm/helper.c#L2023). Os trechos implementam estados e quadros funcionais; não foi encontrada cobrança de 12/6 ciclos físicos. Não se deve inferir equivalência temporal de tail-chaining dessa implementação funcional.

## 3. Código-fonte primário — USART e loopback

| Fonte fixada | Trechos e evidência estabelecida |
|---|---|
| [STM32_UART.cs — frequência](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L23) | Frequência padrão 8 MHz |
| [Atraso inicial](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L71) | `CharacterTransmissionDelay` inicialmente vazio |
| [AutoUpdateDelay](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L103-L113) | Padrão falso |
| [DelayMultiplier](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L116-L125) | Padrão 1 |
| [ORE](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L179) | Sempre falso |
| [TXE](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L183) | Sempre verdadeiro |
| [TC](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L212-L214) | Conclusão imediata no caminho inspecionado |
| [UpdateDelay](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L304) | Atraso por baud e formato do caractere |
| [BaudRate](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs#L312-L313) | Relação frequência/BRR; BRR 69 e 8N1 dão 690 períodos nominais por quadro |
| [UARTHub.cs](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Main/Peripherals/UART/UARTHub.cs) e [linhas 73–75](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Main/Peripherals/UART/UARTHub.cs#L73-L75) | Loopback inclui emissor; agenda entrega com atraso do UART e mecanismo do destinatário |

A configuração passiva `CreateUARTHub "uartLoopback" true`, `connector Connect sysbus.usart1 uartLoopback`, `DelayMultiplier 1` e `AutoUpdateDelay true` foi estabelecida por inspeção do código, **sem teste runtime**. Não prova serialização de TX, correção de TXE/TC/ORE nem presença de PA9→PA10 na bancada.

## 4. Manuais de software — documentação móvel

| Manual | Contribuição e restrição |
|---|---|
| [Time framework](https://renode.readthedocs.io/en/latest/advanced/time_framework.html) | Tempo virtual, sincronização e avanço. Unidade virtual de 1 ns não torna quantum uma resolução universal; `AdvanceImmediately` não é clock físico; pacing não garante tempo real |
| [Execution tracing](https://renode.readthedocs.io/en/latest/execution-tracing/execution-tracing.html) | `cpu CreateExecutionTracing "tracer" @trace.bin PCAndOpcode true`; não presumir timestamp por instrução |
| [Metrics](https://renode.readthedocs.io/en/latest/basic/metrics.html) | `machine EnableProfiler @metrics.dump`; contagens de execução e acessos não são carga física/host |
| [RESD](https://renode.readthedocs.io/en/latest/basic/resd.html) | Timestamps virtuais em ns e replay em consumidores suportados; não é mecanismo universal para GPIO |

## 5. Ferramentas versionadas

Árvore de referência: [tools no tag v1.17.0](https://github.com/renode/renode/tree/v1.17.0/tools/).

- [execution_tracer](https://github.com/renode/renode/tree/v1.17.0/tools/execution_tracer): inspeção de fluxo/PC/opcode, sem assumir timestamps não documentados.
- [metrics_analyzer](https://github.com/renode/renode/tree/v1.17.0/tools/metrics_analyzer): análise dos dados do profiler.
- [gdb_compare](https://github.com/renode/renode/tree/v1.17.0/tools/gdb_compare): comparação funcional por stepping, não validação temporal.
- [csv2resd](https://github.com/renode/renode/tree/v1.17.0/tools/csv2resd): conversão para replay suportado pelo RESD.

Cuidados operacionais estabelecidos: `Sleep` genérico do Robot Framework é espera do host; preparar o UART tester antes de executar; separar runs diagnósticos com `sysbus LogPeripheralAccess sysbus.timer2 true` ou `sysbus.usart1 true`; não confundir timestamp do log do host com timestamp virtual.

## 6. Issues — declarações de mantenedores, não artigos científicos

- [Issue #518, comentário 3728721873](https://github.com/renode/renode/issues/518#issuecomment-3728721873): esclarece que o simulador não é cycle-accurate e não modela pipeline/stalls de memória para equivalência física. Evidência contextual corroborativa, não medição do firmware estudado.
- [Issue #445, comentário 1477713537](https://github.com/renode/renode/issues/445#issuecomment-1477713537): esclarece o foco funcional e a ausência de correspondência temporal 1:1. Não define margens experimentais de aceitação.

## 7. Limites de rastreabilidade

Esta transcrição usa resultados previamente estabelecidos; não refez consultas à rede, testes de comandos ou bancada. Links foram montados com caminhos e revisões fornecidos na investigação. A validação externa dos links, a aprovação metodológica e os ensaios são responsabilidade da sessão principal e da revisão final. Não há aqui alegação de equivalência experimental, tolerância universal do HSI, WCET ou validação física por ajuste de MIPS.
