# Metodologia proposta — quatro cenários de fidelidade

**Estado em 7 de outubro de 2026: PROPOSTA; gate 1 pendente; não implementada nem validada experimentalmente por este documento.** Os nomes S1–S4 descrevem contratos experimentais, não comprovam a existência de firmware correspondente. A aprovação, a execução e a revisão final cabem à sessão principal.

## 1. Pergunta, escopo e fundamento

Avaliar em quais condições o Renode v1.17.0 reproduz o comportamento funcional e temporal de firmware bare metal no STM32F103C8T6, com HSI nominal de 8 MHz. Separar equivalência funcional, discrepância temporal e adequação a um uso declarado: concordância de saída não implica precisão ciclo a ciclo.

Sargent (2013, §1, §3.1 e §4) fundamenta a validade relativa ao propósito e às condições de uso, distinguindo verificação do modelo computacional e validade operacional; a precisão requerida deve ser definida antes ou no início da validação. Akram e Sawalha (2019, §II) sustentam o uso de microbenchmarks dirigidos a subsistemas e configurações comparáveis para diagnosticar discrepâncias. Seu estudo de gem5/x86 não fornece limiares para Cortex-M3/Renode. Hennessy e Patterson (2019, §1.8) fundamentam a explicitação de configurações e flags e alertam para a generalização limitada de kernels e programas sintéticos. As referências, páginas efetivamente verificadas e limites estão em [bibliografia-verificada.md](../context/bibliografia-verificada.md).

Manuais ST determinam o contrato do hardware; código-fonte fixado determina o comportamento do modelo. A síntese técnica e suas fontes estão em [renode-temporalidade.md](renode-temporalidade.md) e [renode-fontes.md](../context/renode-fontes.md). Discussões de mantenedores são contexto corroborativo, não substitutos de medição ou fundamentação acadêmica.

O plano histórico não estava disponível no diretório autorizado no levantamento inicial, que encontrou duas bibliografias. O escopo abaixo foi reconstruído das instruções atuais; essa limitação não permite inferir exclusão deliberada nem a causa da ausência do plano.

## 2. Contrato de comparação e unidades

- Comparar pares com **o mesmo ELF**, seed, parâmetros, payload e agenda nominal. Fixar compilador, flags, bibliotecas, versão do código e configuração do modelo. Qualquer diferença necessária deve ser declarada, não escondida em um ajuste por cenário.
- No hardware, DWT expressa ciclos do núcleo; converter por 8 MHz produz **segundos nominais**, não uma calibração do HSI efetivo. No Renode, DWT representa ticks derivados do tempo virtual do modelo, não ciclos microarquiteturais físicos. Tempo do host é uma terceira medida, separada.
- DWT e TIM derivados do mesmo HSI na bancada, ou da mesma fonte virtual no Renode, não fornecem calibração de clock independente. Na ausência de instrumento externo, declarar essa limitação. O ajuste de fábrica de HSI a 1% a 25 °C (RM0008, §7.2.2) não autoriza um erro universal de ±1%.
- Proposta temporal: Renode a **8 MIPS**, hipótese nominal de uma instrução por período de HCLK, sem fitting; **100 MIPS** como controle explícito. Comparar quantum de **1 µs** e **125 ns** por sensibilidade, não para escolher a configuração que melhor concorda. Registrar frequências explícitas de DWT, TIM e USART; não presumir árvore RCC F1 funcional.
- Registrar clock/readback físico, PSC, ARR, BRR, PRIGROUP, prioridades e máscaras. Definir reset e inicialização idênticos, incluindo o ponto de habilitação/zeragem dos contadores antes do primeiro evento observado.

## 3. S1 — núcleo e memória

**Objetivo:** verificar saídas e discriminar custos de execução em kernels delimitados, sem atribuir uma razão temporal global ao núcleo.

1. Exercitar aritmética, dependências, desvios e acessos à memória com operandos derivados de entradas runtime/seed. Tornar resultados duráveis por checksum e estado final verificável; impedir que operações relevantes sejam eliminadas ou constant-folded.
2. Inspecionar o disassembly do ELF para confirmar instruções e caminhos pretendidos, em particular multiplicação/divisão quando requeridas. Um nome de função não prova sua presença no executável.
3. Medir brackets ao redor do kernel, não spans emitidos depois dele. Incluir bracket vazio com a mesma instrumentação, publicando seu custo e variabilidade. Não presumir que subtrair uma constante elimina todos os efeitos do observador.
4. Fazer sweep predeclarado de tamanhos e iterações, respeitando SRAM/stack. Verificar checksums, limites de acesso e ausência de overflow antes de comparar duração.

**Observáveis:** saída/checksum, tamanho, caminho confirmado, duração bruta, bracket vazio e diferença temporal por configuração. Limite: microbenchmarks não demonstram desempenho geral nem WCET.

## 4. S2 — TIM2 periódico e resposta a IRQ

**Objetivo:** avaliar período, fase de atendimento e efeitos de carga/mascaramento; não medir uma “latência pura do NVIC”.

Configurar e registrar PSC/ARR e a sequência de atualização/inicialização. No upcount, o período inclui ARR+1 contagens; PSC é buffered e UG pode alterar a inicialização (RM0008, §15.3.1–2). Definir origem temporal após limpar flags e estabilizar o contador.

- Controle descarregado, seguido de carga foreground determinística predeclarada.
- Amostrar CNT no ponto instrumentado do handler e registrar DWT, trial e flags. A fase após update é proporcional a **CNT × (PSC+1)** em ticks do timer, não a `(ARR+1−CNT)`, que representa tempo até o próximo update. Converter para HCLK somente com a razão de clocks declarada. Para PSC=7 e timer a 8 MHz, a resolução é de oito ciclos nominais.
- O ponto em C inclui prólogo, instruções anteriores, leitura e observador. Não rotular essa fase como custo isolado de entrada de exceção; múltiplos períodos bloqueados tornam a fase insuficiente para reconstruir toda a espera.
- Ensaiar masked-release com janela conhecida e fonte periódica ainda ativa, distinguindo isso do controle em que a fonte/IRQ está desabilitada. Registrar estado pendente e UIF antes/depois, com a política de limpeza explicitada.
- Explorar bloqueios inferiores e superiores ao período para evidenciar coalescência. **UIF é flag, não fila de eventos**: não igualar número de updates físicos ao número de handlers nem reconstruir eventos perdidos apenas pelo bit.

**Observáveis:** períodos, fase de atendimento, contagem de handlers, flags e eventos coalescidos sob cada condição. Sem afirmar entrada de exceção de 12±2 ciclos ou validar tail-chaining temporal por ordem funcional.

## 5. S3 — USART, payload, serviço e blackout

**Pré-condição pendente:** confirmar fisicamente PA9/TX → PA10/RX, sem remapeamento. Se indisponível, registrar bloqueio de bancada; não substituir silenciosamente por peer ativo. O loopback passivo do Renode é confirmado por inspeção de fonte, **não por execução**, conforme [renode-temporalidade.md, §5](renode-temporalidade.md#5-usart-atraso-de-entrega-não-é-ocupação-física-do-transmissor).

Comparar no mesmo modelo a configuração padrão (`AutoUpdateDelay=false`) e a variante declarada `AutoUpdateDelay=true`, `DelayMultiplier=1`, com hub incluindo o emissor. O atraso não corrige TXE sempre verdadeiro, TC imediato, ORE falso ou falta de serialização física de TX.

Com clock nominal de 8 MHz, BRR `0x45`=69 e 8N1, baud=8 000 000/69 e duração nominal de quadro=**690 ciclos**, ou **86,25 µs**. Usar esse divisor, não arredondar para 694 ciclos a partir de “115200”.

1. Controle descarregado: payload determinístico, um byte a cada **10 ms nominais**, agenda fixa e sem reescalonamento entre ambientes. Registrar sequência recebida, checksum, perdas/duplicações, flags e instantes de escrita/serviço. O instante de escrita em DR não equivale automaticamente ao início ou fim do quadro no fio.
2. Rajada: agenda e número de bytes predeclarados; comparar serviço e preservação do payload, explicitando a limitação de throughput do modelo.
3. Blackout de recepção: suspender o serviço RX por janela conhecida enquanto **TX continua capaz de alimentar a linha**. Não usar como contraprova de ORE uma suspensão que também interrompa todo TX. A implementação dessa alimentação e a comprovação de bytes transmitidos durante a janela são requisitos pendentes antes da execução.
4. Controle negativo de overrun: produzir nova recepção com RDR ainda não lido. No hardware, esperar ORE com retenção do dado antigo em RDR; registrar o estado e executar leitura **SR seguida de DR** para recuperação (RM0008, §27.3.3). Verificar retorno ao serviço e integridade subsequente.

**Interpretação:** ORE sempre falso no modelo é lacuna conhecida, não um “pass” por ausência de erro. Concordância no controle de 10 ms não demonstra fidelidade de rajadas, ocupação TX, blackout ou recuperação de overrun. TIM que agenda escrita foreground também não deve ser rotulado como ISR USART.

## 6. S4 — preempção real e arbitragem separada

**Objetivo:** demonstrar funcionalmente nesting de exceções e distinguir preempção de ordenação de pendências. O estímulo principal é software-pended para controlar a solicitação durante o handler baixo; uma extensão por timer exige contrato posterior.

No ensaio positivo, o handler de menor prioridade entra e, **ainda ativo**, solicita a IRQ de maior prioridade. Exigir a ordem por trial:

```text
LENTER → REQUESTH → HENTER → HEXIT → LRESUME → LEXIT
```

Registrar IPSR e evidência de que a IRQ baixa permanece ativa durante HENTER; combinar essa evidência com ordem e trial. Timestamp sozinho, duas IRQs sucessivas ou sticky flags sobrescritas não demonstram nesting. Eventos HEXIT/LEXIT emitidos em C antecedem epílogo e exception return; seus spans não medem todo o custo arquitetural da exceção.

Controles necessários (PM0056, §2.3.5–7):

- Mesmo grupo de prioridade de preempção, subprioridades diferentes: não deve haver preempção; subprioridade ordena pendências. Incluir também prioridades iguais como controle sem preempção.
- Ambas pendentes sob máscara, seguidas de liberação: testar **arbitragem**, em ensaio separado, sem apresentá-lo como nesting provocado durante atividade da baixa.
- Trocar as prioridades para verificar a inversão esperada dos papéis; registrar PRIGROUP, prioridades codificadas, máscaras e estados por trial.

**Observáveis:** sequência, identidade da exceção, estado ativo/pendente, continuidade da baixa, resultados funcionais e spans instrumentados. Não inferir custos físicos de tail-chaining/late arrival nem custo de retorno a partir de eventos C.

## 7. Instrumentação proposta e validade dos dados

Propor registros de **16 bytes alinhados**, com timestamp, evento, trial e argumento, e buffers separados por writer (foreground, IRQ baixa, IRQ alta). Cada writer publica append-only com contagem limitada e contador de drops; sem ring overwrite, sem `head++` compartilhado entre handlers aninhados e sem mascarar IRQs no logger. Ownership por writer é requisito, não apenas uso de `volatile`.

O schema, offsets e capacidade devem ser fixados e verificados no ELF/parser antes da coleta. Planejar trace em torno de 6 KB, snapshot/resultados até 8 KB e reserva de stack de pelo menos 2 KB, sujeito à validação real da SRAM de 20 KB. Formato packed de cinco bytes tem risco de acessos desalinhados: PM0056, §3.3.5, sustenta essa cautela, mas não quantifica o custo deste logger.

Leitura de DWT não deve ser presumida como operação de um ciclo. Medir observador/bracket vazio, inspecionar instruções e reportar custo no contexto; a tabela LDR do TRM ARM consultado tem hipóteses e não autoriza um custo universal de leitura de CYCCNT.

Depois do último ensaio: parar fontes, impedir novos writers, finalizar contagens e publicação, executar a barreira definida e **congelar antes de DONE/experiment_complete**. Só então admitir breakpoint e dump. Resetar contadores antes de BOOT. Validar wrap, drops, limites, spans e ordem; rejeitar dados ambíguos ou truncados em vez de aceitá-los pelo tamanho do arquivo. Exportação Perfetto deve preservar o domínio de ticks e converter unidades explicitamente, sem apresentar ticks virtuais como ciclos físicos.

## 8. Coleta reproduzível proposta

Cada run começa de reset independente. A proposta inicial prevê três runs exploratórios e pelo menos cinco finais se o custo permitir; quantidade definitiva, justificativa e eventual insuficiência devem ser declaradas antes da validação final. Essa escolha operacional não é uma prescrição literal de Sargent. Amostras dentro de um run podem ser correlacionadas; não tratá-las automaticamente como réplicas independentes nem considerar reset garantia absoluta de independência ambiental.

O manifesto deve conter: identificador do run/par, seed, parâmetros e agenda; hash do ELF e fontes; compilador/flags; clock nominal/readback; versão/revisões Renode, plataforma, MIPS, quantum e opções USART; versão/schema do tracer; conexão física; critérios de término, timeout e erro; hashes dos dumps brutos. Preservar dados brutos imutáveis e registrar resets, falhas e exclusões com motivo.

O coletor proposto usa execução até término finito e dump pós-freeze, sem attach-polling que interfira na medição. Exigir ownership de processo/porta, timeout limitado e limpeza somente de processos próprios; não matar instâncias herdadas indiscriminadamente. Hardware é exclusivo e builds que alteram a configuração do workspace devem ser serializados. Arquivo stale não pode satisfazer uma nova coleta. Instrumentação diagnóstica adicional deve ficar em runs identificados separadamente.

## 9. Análise e critérios de conclusão

Primeiro verificar invariantes funcionais por cenário e qualidade do trace. Só depois comparar duração, ordem e erro sob configurações pareadas. Reportar erro assinado e absoluto e, quando a referência for não nula, erro relativo; publicar dados, ECDF, mediana, dispersão e quantis cuja estimabilidade seja justificada pelo número de runs/amostras. Distinguir resumo dentro de run e variabilidade entre runs; não ocultar falhas na agregação.

Máximo observado é **máximo da amostra**, não WCET. Não adotar ±1,5%, 12±2 ciclos, correlação de Spearman ou qualquer p-valor como certificado automático de equivalência. Ausência de diferença estatisticamente detectada não prova equivalência; correlação não garante igualdade de tempos. Não selecionar condições ou margens após observar concordância.

Para uma futura conclusão de adequação temporal, declarar previamente o uso pretendido, observáveis críticos e margens justificadas por esse uso, antes da validação e sem fitting aos resultados. Enquanto esse requisito estiver pendente, concluir somente sobre concordância funcional observada e distribuição completa das discrepâncias sob as condições registradas. Limitações conhecidas (clock sem calibração independente, CPU instruções/MIPS, USART incompleto, custo do observador) acompanham cada interpretação.

## 10. Pendências de aprovação

Gate 1 deve aprovar contratos, configuração temporal, ABI/ownership, tamanhos e estímulos finitos; implementação e validação runtime vêm depois. Permanecem pendentes: ligação física USART, alimentação TX durante blackout, verificação do coletor/parser, orçamento real de memória, justificativa amostral definitiva e margens de adequação por uso. Este documento não relata novos ensaios, não altera firmware e não transforma dados exploratórios anteriores em validação final.
