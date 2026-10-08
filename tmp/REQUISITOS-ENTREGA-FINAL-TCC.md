# Diretiva de refatoração e entrega final — Renode × STM32F103

**Data:** 2026-10-09. **Destino:** agente responsável pela implementação final.
**Repositório:** `/home/leonardo/projects/renode-stm32f103-fidelity`.
**Idioma dos requisitos e da documentação de uso:** português.

## 1. Missão, autoridade e resultado exigido

Entregar o repositório de código do TCC finalizado: firmwares simples e verificáveis, plataforma Renode coerente, campanha automática de bancada e simulação, análise independente, traces compatíveis com Perfetto, testes da infraestrutura e ambiente sem legado operacional. A monografia não faz parte desta tarefa.

Este documento consolida as decisões do autor e a avaliação da sessão anterior. É a entrada autossuficiente para a nova sessão: não depender de `.slim/`, `tmp/reports/`, conversas anteriores ou relatórios exploratórios. O autor pretende apagar essas pastas. Resultados antigos e conclusões de agentes anteriores não são respostas esperadas a incorporar aos novos oráculos.

O autor autoriza o próximo agente a refatorar os arquivos próprios, ajustar nomes e configurações, implementar e validar a entrega e remover legado sem uso final. Isso não autoriza alterar `vendor/`, apagar dados experimentais irreproduzíveis, modificar arquivos fora do repositório ou produzir a monografia. A sessão que escreveu esta diretiva não implementou firmware nem executou uma nova campanha.

O requisito principal de engenharia é **complexidade que o aluno consiga revisar, compreender e defender em uma banca de graduação**. Priorizar C idiomático, funções pequenas, condições explícitas e instrumentos explicáveis. Evitar abstrações, compactações e mecanismos genéricos que tornem difícil compreender o experimento. Simplicidade não dispensa integridade dos dados, correção concorrente ou controles científicos.

### 1.1 Plano de trabalho de referência

Documento lido integralmente, cinco páginas:

- Windows: `D:\tcc\Plano de Trabalho - Leonardo Pereira Rodrigues dos Santos - RA177318.docx.pdf`.
- WSL: `/mnt/d/tcc/Plano de Trabalho - Leonardo Pereira Rodrigues dos Santos - RA177318.docx.pdf`.
- Data do plano: 31/08/2026; disciplina EA019; orientadora Wu Shin Ting.
- Tema: análise quantitativa da fidelidade funcional e temporal do Renode em relação ao hardware no STM32F103.

O plano estabelece quatro áreas: C1 execução e calibração do núcleo; C2 reatividade a timer e interrupção periódica; C3 prioridades, preempção, encadeamento e mascaramento; C4 comunicação serial, integridade e comportamento isolado e sob concorrência. Exige condições controladas, comparação simétrica, distribuições, critérios de decisão, dados reproduzíveis e classificação de fidelidade por recurso e condição. Não exige uma suíte exaustiva da ISA nem custos exatos de todas as instruções.

As clarificações atuais do autor especificam esse escopo: C1 primeiro mede núcleo e memória; calibração é complemento empírico. C4 trata concorrência como demanda de transmissão/recepção e competição pelo atendimento por software, sem repetir a matriz de prioridades do NVIC. Explicitar esse recorte conservador no README final e relacioná-lo ao plano.

### 1.2 Fonte de conhecimento e postura científica

- Consultar bibliografia pelo Zotero e fontes primárias Arm/ST/Antmicro. Não tratar código, comentários, notas de LLM ou este documento como prova de uma propriedade física.
- Para cada caso, identificar: especificação de referência, entrada, estado inicial, observáveis, expectativa funcional, previsão temporal e limitações.
- Separar comportamento especificado no manual, observado na placa e implementado pelo Renode. Registrar hipóteses como hipóteses.
- Não escrever testes destinados a confirmar obrigatoriamente a conclusão sugerida por dados antigos. Uma divergência legítima do Renode é resultado científico; um instrumento defeituoso não é.
- Conclusões limitadas ao exemplar, versão, configuração, operações e condições efetivamente examinados. Repetições em uma placa não representam uma amostra de placas.

## 2. Decisões de escopo e nomenclatura

Adotar a ordem do plano em toda a entrega:

| Nome final | Área | Origem atual para inspeção, não para cópia automática |
|---|---|---|
| C1 / `src/c1/` | Núcleo, operações e memória | `src/s1/` |
| C2 / `src/c2/` | Timers e IRQ de origem periférica | `src/s2/` |
| C3 / `src/c3/` | NVIC | `src/s4/` |
| C4 / `src/c4/` | USART | `src/s3/` |

Usar presets finais `c1`, `c2`, `c3`, `c4`, com artefatos em `build/<preset>/`. Se separar um cenário em dois firmwares tornar o código ou o orçamento de SRAM significativamente mais simples, aceitar sufixos descritivos, como `c1-functional` e `c1-timing`. Não conservar a inversão USART=C3/NVIC=C4 nem nomes exploratórios ambíguos. O número de executáveis não precisa permanecer em oito; a cobertura dos quatro cenários é o compromisso.

Cada executável deve ter um `main` curto, fluxo finito, casos identificáveis e término explícito. Não juntar todos os experimentos num firmware monolítico só para diminuir o número de presets. Não manter implementações velha e nova lado a lado na entrega.

### 2.1 Plataforma e configuração principal

- Referência final: STM32F103 genuíno disponível no laboratório, variante/capacidade documentadas e compatíveis com os binários. Base conservadora: STM32F103C8T6, 64 KiB flash e 20 KiB SRAM.
- Placa atual possivelmente compatível/clone: utilizável para desenvolver e diagnosticar, mas seus dados recebem identidade separada e não substituem a campanha final.
- Clock principal: HSI nominal 8 MHz, HCLK 8 MHz, sem HSE ou PLL. Registrar registradores reais e condições da bancada; não presumir frequência física exata nem transferir tolerâncias ST a um clone.
- Configuração Renode principal: `PerformanceInMips = 8`, única para C1–C4. É uma hipótese nominal de um milhão de instruções por segundo por MHz, não uma configuração ciclo-precisa nem um padrão universal do Renode.
- Um único quantum explícito, inicialmente 1 µs, congelado após verificar se é adequado à resolução exigida. Não fazer sweep de quantum/MIPS/atrasos na campanha principal. Se a resolução impedir uma pergunta, ajustar o protocolo antes da coleta final e registrar a decisão.
- Plataforma, versão, quantum e ligação de loopback idênticos entre cenários, salvo configuração do periférico necessária ao próprio caso. Não adaptar o simulador por caso para produzir o valor esperado.
- Escolher uma política explícita de ligação/atraso do loopback Renode, fundamentada no caminho da versão instalada. Não fixar `AutoUpdateDelay` por tradição nem impor outro atraso que duplique inadvertidamente a serialização já modelada. Registrar essa política; usar só uma na campanha principal.
- PA9→PA10 permanece conectado. Somente C4 habilita/configura USART1 ou dirige esses pinos. C1–C3 não usam USART para logs nem saídas de timer nesses pinos. SWD PA13/PA14 deve permanecer disponível.
- Toolchain Nix/CMake/Ninja existente, GNU C17, LL/CMSIS direto, sem HAL, sem OS, sem heap no firmware experimental e sem `printf` durante a medição. Preferir `-O2 -g3` fixo e documentado; nenhum cenário muda otimização para ajustar resultados.
- `vendor/` é congelado: não editar nem remover. `.clangd` é gerado: corrigir sua geração, não editar o resultado manualmente.

### 2.2 Fronteiras para reduzir sobreposição

| Cenário | Fenômeno investigado | Infraestrutura compartilhada não vira outra investigação |
|---|---|---|
| C1 | Resultados e duração de execução do núcleo/memória | DWT mede; timers e USART ficam fora |
| C2 | Timer, clock periférico, flags e evento que provoca IRQ | NVIC habilita a IRQ, sem matriz de prioridades |
| C3 | Seleção e atendimento de exceções no NVIC | IRQs pendidas por software; timers não geram estímulos principais |
| C4 | USART, quadro, capacidade de atendimento e sobrecarga | Polling preferencial; sem matriz de preempção de IRQs |

Compartilhar clock, timestamp e ABI é desejável. Repetir testes de todos os subsistemas dentro de cada cenário não é.

## 3. Requisitos C1 — núcleo e memória

### 3.1 Finalidade e perguntas

Investigar se o mesmo ELF ARM produz os resultados esperados na placa e no Renode para operações representativas, e em que medida a duração observada corresponde aos ciclos físicos. Formular as perguntas:

1. Operações e acessos à memória mantêm resultados e efeitos laterais nos casos normais e de fronteira escolhidos?
2. A referência nominal de 8 MIPS reproduz os tempos de cargas com características diferentes?
3. As diferenças de duração entre cargas mostram limitações de um modelo temporal baseado em contagem de instruções?
4. Como complemento, uma configuração empírica aproxima uma média definida, e como se comporta nas demais cargas?

Não declarar previamente que o Renode é funcionalmente perfeito ou instrução-preciso. Os testes sustentam equivalência das operações e sequências examinadas. Observar resultados finais iguais não prova estado intermediário correto após toda instrução. Se usar a expressão precisão por instrução, apresentar a evidência específica, eventualmente por tracing de execução complementar.

### 3.2 Cobertura funcional obrigatória

Selecionar uma matriz enxuta de aproximadamente 25–40 casos nomeados, agrupados em poucas funções. A quantidade é guia de cobertura, não quota a preencher com duplicatas.

- Aritmética `uint32_t`: soma com redução modular, subtração a partir de zero, multiplicação com bits altos descartados, divisão/resto com operandos representáveis e divisor não nulo.
- Aritmética com sinal: limites representáveis, valores positivos/negativos e divisão/resto válidos. Evitar overflow de sinal e `INT_MIN / -1`.
- Bits: AND/OR/XOR/NOT, máscaras nos bits extremos, deslocamentos válidos, composição/extração de campos. Explicar promoções de inteiros de 8/16 bits.
- Conversões: extensão de sinal e zeros e truncamento definido para tipos sem sinal; registrar convenções da implementação para casos dependentes da implementação, se incluídos.
- SRAM: leitura/escrita por 8/16/32 bits em posições devidamente alinhadas, byte order, preservação dos bytes vizinhos, padrões 0, todos 1, alternados e bits isolados.
- Flash: tabela conhecida realmente lida de `.rodata`, larguras/posições válidas, conteúdo completo verificado. A leitura não pode desaparecer por propagação de constantes.
- Cópia/preenchimento e uma operação de controle/algoritmo pequeno: verificar todo o resultado e limites da região; não só três posições ou uma assinatura fraca.

Empregar tipos de largura fixa. O firmware é compilado para ARM e o mesmo ELF é executado pelo Renode; o tamanho de `int` do hospedeiro não define a aritmética do alvo. Não gerar expectativas a partir de UB em C, ponteiros inválidos, aliasing inválido ou acessos fora dos objetos.

Padrões explícitos de fronteira têm prioridade sobre pseudoaleatoriedade. Uma sequência determinística de operandos adicionais pode ampliar a cobertura, com semente e entrada reproduzíveis. O oráculo host deve aplicar larguras/conversões explicitamente e ser independente da implementação do algoritmo do firmware.

### 3.3 Cobertura temporal obrigatória

Selecionar poucas cargas C, com entradas em tempo de execução e resultado verificável, que contrastem:

- operações de registradores e laços;
- multiplicação/divisão com operandos escolhidos;
- leituras/escritas SRAM e leituras flash;
- controle de fluxo/uma carga mista curta.

Medir blocos suficientemente longos para não dominar o resultado pelo observador. Usar ao menos três tamanhos em cargas onde se infere custo por iteração: verificar linearidade e reportar overhead; dois pontos não estabelecem linearidade. Separar primeira execução e posteriores apenas com entradas equivalentes e protocolo explícito.

C é a implementação principal. O compilador pode trocar operações, desenrolar laços, eliminar cargas e usar rotinas auxiliares. Conferir o ELF de cada carga decisiva e guardar uma descrição curta do caminho executado. `volatile` apenas onde necessário: não é uma barreira universal para o compilador.

Não rotular uma expressão C como medição de uma instrução exata sem verificar isso. Não calcular CPI físico dividindo tempo HW pelo tempo Renode como se a contagem dinâmica independente já estivesse demonstrada. Se CPI for reportado, obter contagem dinâmica válida para aquele intervalo; tracing de instruções Renode pode ser evidência complementar, com limites declarados. Tempo por carga e por iteração bastam para a entrega principal.

Permitir pequenos trechos de assembly quando a pergunta exigir instrução exata ou bracket confiável. Preferir uma rotina central de medição comentada e poucas exceções justificadas a uma biblioteca extensa de kernels. Respeitar ABI/AAPCS, alinhamento de SP, registradores preservados e limites do intervalo medido. Não exigir conhecer assembly avançado para entender o resultado de cada caso.

### 3.4 Complemento de calibração, restrito a C1

É parte complementar da entrega C1, executável separadamente e claramente identificado. Nunca substituir a referência nominal nem aplicar sua configuração a C2–C4.

- Definir antes da coleta uma carga ou conjunto de treinamento, pesos e função de erro. Se a média for o objetivo, explicitar qual média e quais pesos.
- Reservar outras cargas/entradas para avaliação. Congelar a regra antes de examinar seus resultados.
- Derivar o MIPS calibrado dos novos dados. Não conservar o antigo valor 7 como verdade ou resultado obrigatório.
- Verificar na versão instalada os valores aceitos e sua granularidade. Registrar valor solicitado e efetivo; não rotular fração truncada como valor executado.
- Exibir erro por carga e agregado, nominal versus calibrado. Melhorar uma média não demonstra custo correto por instrução nem validade geral.
- Se nenhuma configuração aproxima satisfatoriamente as cargas, registrar esse resultado. Não ajustar um MIPS por carga e chamar isso de calibração global.

### 3.5 Extensão HSE/PLL/72 MHz: opcional, fora da campanha principal

Recomendação: concluir primeiro a base HSI8. Esta extensão tem valor para investigar flash/prefetch/wait states, mas amplia o protocolo e não é requisito para finalizar a entrega principal. Não prometer um resultado nem criar presets incompletos.

Se implementada, delimitar a C1 e entregar integralmente um perfil separado. Separar duas perguntas: trocar HSI por HSE mantendo a frequência e elevar HCLK usando PLL. HSE por si só não equivale a 72 MHz nem causa wait states.

Comparar poucas cargas flash/SRAM sob configurações legais de frequência, latência da flash e prefetch, consultando datasheet/RM0008. Não experimentar latência de flash insuficiente em alta frequência. Garantir APB1 dentro do limite e inicialização com timeout e transição segura. Verificar a frequência do cristal real.

O perfil Renode deve registrar clocks e política temporal correspondentes; usar 8 MIPS em HCLK72 não é o análogo nominal de uma instrução por ciclo. Um perfil nominal de 72 MIPS pode servir à comparação separada. Não contaminar nem recalibrar os cenários principais. Não interpretar troca de origem de clock como medida de sua exatidão sem referência externa.

Para afirmar ausência/presença de wait states no modelo, combinar experimento com fonte da versão pinada. Diferença de custo também pode envolver prefetch, caminho de memória e sequência compilada. Não chamar prefetch ou uma primeira execução lenta de cache sem evidência.

### 3.6 Critério de entrega C1

Casos funcionais completos com oráculos definidos; cargas temporais verificadas no ELF; comparação nominal por carga; experimento complementar de calibração separado; conclusões possíveis sem alegar conformidade de toda a ISA. Timers/USART ficam inativos.

## 4. Requisitos C2 — timers e IRQ de origem periférica

### 4.1 Finalidade

Avaliar contagem, periodicidade, flags, configuração temporal e atendimento de IRQ provocada pelo timer. O evento de timer é assíncrono em relação ao fluxo de instruções de MAIN, ainda que determinístico e previsível a partir do clock/configuração; não significa aleatório ou gerado fora do chip. Sem fios adicionais.

### 4.2 Periféricos e árvore temporal

Cobrir **TIM2 e TIM3** como timers gerais APB1 e **TIM1** como contraste APB2, usando update interno. Se houver impedimento concreto de TIM1, demonstrá-lo e registrar cobertura não alcançada, sem substituir silenciosamente por mais um timer idêntico.

Usar somente recursos presentes na variante STM32F103 alvo. Não tomar a lista extensa da plataforma Renode como prova de que TIM5–TIM14, USART4/5 ou outros periféricos existem no C8.

Para cada timer, conferir clock enable, contagem habilitada/desabilitada, PSC, ARR, update e IRQ. Estímulos independentes, preferencialmente um timer por ensaio, evitam transformar C2 em teste de arbitração.

Explorar prescalers APB /1, /2 e /4 em perfis definidos, mantendo HCLK8 e MIPS8. A regra de clock do timer difere quando APB é dividido: derivar frequência e período do RM0008, não assumir `TIMCLK = PCLK` em todos os casos. Não testar todas as combinações possíveis: escolher contrastes que distingam regras e casos de preload.

Registrar RCC, frequências derivadas, PSC/ARR e modo efetivo. Verificar se o modelo acompanha mudanças de RCC dinamicamente. Se só puder receber frequência estática na plataforma, deixar essa limitação evidente: ajustar manualmente uma frequência prevista pode testar o timer sob essa frequência, mas não valida a árvore RCC dinâmica. Não introduzir callbacks corretivos para esconder a lacuna.

### 4.3 Matriz mínima de condições

- Contagem parada versus ativa; PSC e ARR com valores diferentes e períodos suficientemente observáveis.
- Update periódico: período entre observações, flags e contagem de atendimentos.
- PSC com transferência pelo update; ARR com e sem preload; UG e efeitos em contador/flags, com expectativa derivada do manual.
- UIF versus UIE: distinguir produção do evento, flag periférica, linha IRQ e pending do NVIC.
- Limpeza de UIF e controle de habilitação; avaliar quando um evento permanece observável ou é coalescido, sem presumir um IRQ por update sob sobrecarga.
- IRQ durante MAIN ocioso/polling e carga C simples, com mesma configuração do timer.
- Atraso controlado de atendimento para separar evento ocorrido de ISR atendida; manter o aprofundamento de PRIMASK/BASEPRI em C3.

Opcionais: WFI com estado de debug explicitamente controlado, one-pulse ou sincronismo interno entre timers. Não ampliar para PWM/capture externo, DMA ou todos os modos avançados.

### 4.4 Medidas e interpretação

- Período previsto: `(PSC + 1) × (ARR + 1) / TIMCLK`, quando as condições desse modo se aplicarem.
- Período observado entre registros; erro relativo/absoluto e distribuição.
- CNT no primeiro ponto instrumentado da ISR; converter com PSC e TIMCLK corretos e informar quantização.
- Tempo desde update até essa observação, incluindo entrada, prólogo, instruções e acesso ao barramento. Não chamá-lo de custo puro de entrada de exceção.
- Eventos gerados, atendimentos observados, flags e possíveis eventos perdidos/coalescidos; não inferir contagem não observada como fato.
- Comparar fontes de timestamp sem tratar relógios derivados da mesma origem como validação externa independente.

Sem timestamp real da borda, marcar borda reconstruída pela configuração como **prevista/inferida** no trace. Latências superiores a um período exigem desambiguação; CNT sozinho fornece posição no período, não número de períodos perdidos.

### 4.5 Critério de entrega C2

Tabela timer × condição × clock esperado/observado × resultado, incluindo contrastes APB e semântica de update. IRQ é causada pelo periférico. Nenhuma saída TIM1 deve dirigir PA9/PA10. Sem ajuste de MIPS por timer.

## 5. Requisitos C3 — NVIC

### 5.1 Finalidade e isolamento

Explorar seleção e atendimento de múltiplas interrupções: prioridade de grupo, subprioridade, empate por número de exceção, preempção, encadeamento e mascaramento. Gerar os estímulos principais por pending em software; periféricos dessas IRQs quiescentes. Assim, C3 não depende da periodicidade medida em C2.

Usar duas IRQs implementadas, handlers curtos e registro que preserve todas as ocorrências. AIRCR/PRIGROUP, bits implementados e convenção de prioridade documentados. Valor numérico menor representa maior prioridade; não confundir prioridade lógica com campo codificado.

### 5.2 Matriz obrigatória

- Ambas pendentes antes da liberação: grupo decide; subprioridade decide quando grupo igual; número de exceção decide empate. Variar ordem de solicitação no empate para distinguir ordem de pedido e regra arquitetural.
- Durante uma ISR: solicitar IRQ com grupo superior, igual e inferior; verificar onde a execução solicitante retoma. Subprioridade diferente com mesmo grupo não deve ser tratada como capacidade de preempção.
- Inverter os papéis das duas IRQs em condição representativa para não confundir número e prioridade.
- PRIMASK: solicitar, verificar pending sem execução e liberar.
- BASEPRI: IRQ acima e abaixo do limiar; conferir pending e execução após liberação. Distinguir prioridade zero e convenções de codificação quando aplicável.
- Encadeamento: IRQ pendente no fim de outra, verificando ordem e tempo do trecho observável. Comparar com controles adequados; sequência de handlers não basta para afirmar os ciclos arquiteturais de tail-chaining.
- Auto-repending: uma IRQ solicita nova ocorrência enquanto ativa; verificar número exato de entradas/saídas e ordem completa com a outra IRQ.

Medir solicitação→primeiro registro, intervalo entre handlers e duração instrumentada, com limites do observador. IPSR/IABR/ICSR podem confirmar contexto quando necessários, sem ler muitos registradores em todo evento. A igualdade temporal não é requisito para o firmware terminar corretamente; é objeto da análise.

### 5.3 Limites de escopo

Late arrival, pop preemption e NMI/faults são complementos opcionais, não requisitos da entrega principal. Se mantiver late arrival, separar sua evidência da arbitragem e da preempção, controlar timer/fase e relatar intervalos entre pontos amostrados. Não depender do complexo experimento antigo para fechar C3.

Não perseguir prova de todo o subsistema de exceções. Não armazenar uma ocorrência por ID de evento: uma mesma entrada pode ocorrer várias vezes. Não usar flags RMW compartilhadas entre handlers preemptíveis sem solução concorrente explicada.

### 5.4 Critério de entrega C3

Matriz explícita de estímulos e sequências esperadas completas, incluindo repetição; contextos e tempos necessários; classificações independentes. Nenhum teste de capacidade da USART ou clock de timer entra na interpretação de C3.

## 6. Requisitos C4 — USART1

### 6.1 Finalidade e recorte de concorrência

Avaliar a USART: integridade, configuração de quadro, ritmo de transmissão/recepção, flags, armazenamento de dados pendentes e perda sob sobrecarga. Loopback PA9→PA10, sem modificar cabeamento.

Concorrência aqui significa transmissão e recepção em andamento enquanto o software tem capacidade limitada para atender a recepção. Caracterizar produtor→periférico→consumidor e demanda superior ao atendimento. Usar polling como base; atraso de leitura controlado e carga C no consumidor. Não repetir matriz NVIC/IRQ concorrente do C3. Um modo USART por IRQ é opcional apenas se trouxer uma pergunta específica do periférico e não aumentar substancialmente a complexidade.

Essa é a interpretação escolhida pelo autor para manter C4 conservadoramente alinhado ao plano e reduzir sobreposição. Torná-la explícita na documentação final.

### 6.2 Matriz obrigatória

1. **Transferência sem pressão:** byte isolado e sequência identificável; validar todos os bytes, ordem e término.
2. **Rajada e full duplex em loopback:** transmissão e recepção sobrepostas, sequência que detecte perda/duplicação, tamanho conhecido e timeout total.
3. **Baud/divisor:** ao menos três taxas representativas permitidas por PCLK; calcular baud realizado por BRR e erro frente ao solicitado. Não usar só 115200 nominal como verdade temporal.
4. **Quadro:** base 8N1 e pequeno conjunto de configurações suportadas, incluindo paridade par/ímpar e dois stop bits. No STM32F1, tamanho configurado inclui a posição de paridade; definir bits úteis efetivos e máscaras. Uma opção de 9 bits sem paridade pode ampliar cobertura se simples.
5. **TXE/TC/RXNE/IDLE:** distinguir quando são observados, sequência de limpeza/habilitação e dependência da leitura/escrita; timestamp por polling tem resolução do laço.
6. **Sobrecarga de RX:** atrasar leitura por quantidades conhecidas de quadros, observar ORE, bytes preservados/perdidos, recuperação e sequência de limpeza especificada.
7. **Pressão de TX/modelo:** verificar se respeitar TXE limita o produtor e se o tempo de entrega cresce com quantidade de dados. Distinguir ritmo de entrega e capacidade de buffering.

UE/TE/RE e sua influência em transmissão/recepção são casos pequenos adicionais úteis quando cabem no protocolo. Evitar um catálogo de modos sem uma pergunta ou observável claros.

### 6.3 Controles indispensáveis

- O transmissor recebe sequência de comprimento conhecido. O firmware deve esperar recepção completa ou timeout antes de declarar encerramento. Não esperar quatro quadros após enfileirar 32 bytes e concluir defeito de IRQ.
- Para overrun, controlar a oferta de dados de modo que a comparação não seja exclusivamente consequência de TXE constante no simulador. Usar um protocolo de produção com espaçamento conhecido e uma condição de pressão separada; registrar momentos de escrita e de leitura.
- Se a transmissão não oferece o estímulo previsto, esse desvio é resultado de TX; não atribuí-lo silenciosamente a RX/NVIC. Drenagem posterior pode receber bytes que ainda estavam em trânsito.
- A própria USART transmite a fonte de estímulo. Essa limitação do loopback deve ser documentada; não equivale a receptor excitado por instrumento independente.
- Mesmo quadro de TX/RX em loopback permite verificar dados e configuração/tempo, mas **não comprova detecção de erro de paridade ou framing error**. Esses erros exigem estímulo divergente controlado; não alegar cobertura se o cabeamento/protocolo não o permite.
- Padrões alternados simples não detectam todas as perdas/duplicações. Usar sequência indexada/blocos verificáveis e verificações completas.
- Estimar capacidade como limite inferior para os tamanhos ensaiados. Não concluir fila infinita a partir de nenhuma perda numa rajada finita. Corroborar mecanismo de buffering pela fonte da versão usada.
- Não reimplementar a USART no Renode para fazê-la corresponder ao manual. Limitações do modelo precisam permanecer mensuráveis.

### 6.4 Métricas e término

Baud efetivo calculado, bits por quadro, duração prevista/observada, duração de rajada, taxa útil, integridade, perdas/duplicações, ORE e recuperação, profundidade mínima de buffering inferida e tempos de flags. Não representar eventos virtuais de entrega de caracteres como medição de forma de onda física ou bits amostrados na linha.

### 6.5 Critério de entrega C4

Integridade completa sem carga e sob atendimento atrasado; quadro/divisor explícitos; flags e sobrecarga interpretadas sem depender de conclusões de IRQ; todas as condições encerradas ou diagnosticadas. Somente C4 toca USART1 e PA9/PA10.

## 7. Instrumentação e trace em SRAM

### 7.1 Arquitetura escolhida

Trace compacto em SRAM, inspirado no conceito de registro de eventos do RTT/SystemView; coleta via ST-Link/OpenOCD/GDB **após congelamento do ensaio**; conversão host para formato aceito pelo Perfetto. O caminho principal não depende de J-Link, SystemView instalado, RTT contínuo, UART de log ou instrumentação nativa do Renode.

O manual SystemView distingue gravação single-shot e circular post-mortem e descreve leitura por probe após parada. A inspiração é conceitual: implementar um formato próprio simples e documentado, sem alegar compatibilidade binária RTT/SystemView. Referência: UM08027 v4.10 rev.0, seções 1.1 e 3.15, inclusive coleta após parada e informação de tempo. Não copiar implementação proprietária.

### 7.2 Requisitos do formato e buffers

- ABI versionada, little-endian, campos de largura explícita e verificações de tamanho/layout. Cabeçalho com magic, versão, tamanho, estado, cenário/caso, capacidades, contagens, clock, erros e identificação necessária.
- Eventos com timestamp bruto, ID semântico, contexto escritor, sequência monotônica, caso/ensaio e dados mínimos. Repetições de um mesmo ID são ocorrências distintas, nunca sobrescritas por indexação pelo ID.
- Buffer circular por escritor físico: MAIN e cada handler produtor. Um handler tem seu buffer mesmo que seu papel lógico/priority mude. Evitar uma posição global compartilhada que exija mascarar IRQs para cada registro.
- Documentar capacidade, cursor e política de wrap/drop. Detectar todas as perdas e sobrescritas; reservar/publicar registros de maneira coerente. Não bloquear esperando o host consumir.
- Nos ensaios científicos obrigatórios, dimensionar a janela ou dividir execução para preservar todos os eventos necessários. Wrap é mecanismo diagnosticável, não permissão para apagar o começo do experimento e produzir métricas completas.
- Uma perda que não afete um resultado independente pode invalidar só as métricas dependentes do trace; nunca omiti-la. Nenhuma classificação completa de ordem usa trace truncado sem advertência.
- Dados de resultados tabulares podem ser separados do ring, publicados por MAIN após quiescência dos handlers. Não escrever resultados largos concorrentemente sem necessidade.
- Orçamento total abaixo de 20 KiB incluindo stack, resultados, buffers e variáveis. Provar pelo mapa e margem de stack. Não impor a recomendação genérica de tamanho de SystemView à SRAM desta placa.
- Finalização: parar estímulos, garantir writers quiescentes, registrar contexto final e publicar DONE ou FAILED antes do ponto de coleta. Host verifica todos os invariantes antes de interpretar.

### 7.3 Clock, ordem e interferência

- DWT CYCCNT no hardware é contador de ciclos nas condições declaradas; no Renode é contador derivado de tempo virtual, não prova de ciclos microarquiteturais.
- Guardar ticks brutos e frequência/configuração. Usar conversão derivada dos metadados; nunca constante universal `ticks / 8` escondida no conversor.
- Protocolo deve resolver rollover de 32 bits. Preferir janelas curtas com âncora explícita e garantia de duração; testar reconstrução. Não obter origem por mínimo dos valores brutos quando ocorre wrap. Se múltiplos wraps forem possíveis, exigir informação suficiente para reconstruí-los ou rejeitar o trace.
- Merge respeita ordem por escritor, causalidade e timestamps. Empates/precisão insuficiente devem aparecer como ambiguidade; não fabricar ordem física usando ID ou ordenação arbitrária.
- Registrar pontos exatos de observação: primeiro registro de ISR não é primeira instrução; escrita em DR não é começo medido do bit; update previsto não é borda capturada.
- Medir custo do timestamp/logger/bracket e controlar sua localização. Gerar eventos fora do bracket C1 quando possível, usando timestamps já capturados. Não subtrair indiscriminadamente o custo de um logger diferente.
- Não mascarar interrupções no logger de C3 para facilitar uma estrutura compartilhada: isso muda o fenômeno. Preferir propriedade de buffer por contexto, com publicação documentada.
- Sem watches/polling de SRAM durante a janela medida. Se houver controle conectado versus execução sem debugger, mantê-lo explícito e limitado; desligar polling não estabelece estado igual a power-on.

## 8. Exportação e análise Perfetto

### 8.1 Formato de entrega

O formato obrigatório pode ser **Chrome Trace Event JSON**, oficialmente aceito pelo Perfetto e simples de manter em Python. Trace protobuf nativo é alternativa se houver necessidade concreta; não tornar SDK/daemon Perfetto parte do firmware bare metal.

Entregar um trace por execução e visão comparativa selecionada por critério explícito. Todos os runs permanecem disponíveis; não exportar apenas o primeiro como representante sem critério. Diferenças de repetibilidade também precisam ser acessíveis.

No JSON Chrome, timestamps e durações são em microssegundos, inclusive frações. `displayTimeUnit` não muda a unidade de `ts`. Se usar protobuf, declarar clock e unidade corretamente. Metadata de run/clock deve sobreviver à importação ou ter sidecar referenciado, não depender de um campo extra que a UI ignore.

### 8.2 Semântica visual obrigatória

- Trilhas separadas por ambiente, execução, caso e contexto: MAIN e IRQs/USART conforme o cenário.
- Slices para duração de operação/handler, instantes para solicitação e observação, counters para atraso/período/estado/capacidade quando úteis.
- Identificar ticks físicos versus virtuais. HW e Renode não compartilham uma origem absoluta; alinhamento ao início do caso é convenção comparativa declarada, sem reescalar duração para fazê-la coincidir.
- Relacionar solicitação e atendimento por IDs quando a relação é observada; não desenhar relação causal com evento perdido ou ambíguo.
- Distinguir duração inclusiva de um handler (inclui preempção) e tempo efetivo/exclusivo. Trilhas de contextos não são prova de execução simultânea em um núcleo. Não somar slices preemptadas como se toda duração fosse CPU ativa.
- Eventos previstos/inferidos visivelmente distintos dos registrados. Dados sem precisão suficiente não recebem timestamps de borda inventados.
- Traces incompletos: avisos de perda, intervalos truncados e diagnóstico. Não parear BEGIN/END por heurística que esconda perdas ou troque ocorrências.

### 8.3 Validação

Validar importação real com Perfetto Trace Processor e/ou UI e registrar versão. Para um conjunto pequeno conhecido, conferir quantidade de slices, duração, eventos, aninhamento e contadores; não aceitar só JSON sintaticamente válido. Comparar os valores exportados aos ticks/resultados brutos.

Estatística é calculada dos dados brutos decodificados. Perfetto é ferramenta de inspeção/validação e visualização, não substitui oráculos nem evidência de equivalência.

Consultar os scripts do Renode fornecidos pelo autor e as ferramentas de tracing da versão instalada. Adotar somente recursos pertinentes; não presumir exportador Perfetto presente no diretório `scripts/`. Tracing nativo do Renode pode ajudar a confirmar instruções ou mecanismos, mas fica diagnóstico separado da instrumentação simétrica de bancada.

## 9. Campanha automática: um comando no laboratório

### 9.1 Interface e preparação

Entregar um ponto de entrada Bash curto, com ajuda e parâmetros claros, que use o ambiente Nix existente e delegue parsing/análise a Python. Evitar duplicar o coletor em Bash. O README deve apresentar um comando completo para campanha final; esta diretiva não fixa sua sintaxe.

Pré-condições: probe conectado, alimentação adequada, SWD disponível, PA9→PA10 conectado e ambiente instalado. Preparação pode exigir configuração inicial de USB/WSL, permissões e Nix; isso precisa estar documentado. Depois do comissionamento, não exigir edição manual de `.resc`, offsets, frequências ou caminhos para cada cenário.

Parâmetros: nome/identidade da campanha, board/exemplar, número de repetições, cenários selecionados, modo piloto/final, retomada e complemento C1 calibrado separado. Nenhum valor calibrado é propagado implicitamente aos outros cenários.

### 9.2 Sequência obrigatória

1. Pré-verificar dependências, versões, portas, probe, memória/dispositivo, espaço e configuração; obter lock para impedir duas campanhas sobre o mesmo HW.
2. Compilar todos os firmwares finais e executar verificações do ELF/layout e integridade vendor. Capturar hashes e flags.
3. Gerar e congelar manifesto/plano da campanha: casos, entradas/sementes, repetições, configurações e critérios. Não alterar pesos/oráculos no meio da aquisição.
4. Subir OpenOCD próprio e identificar exemplar. UID/IDCODE/CPUID/flash size são metadados e diagnóstico, não autenticação conclusiva. Identidade física informada pelo autor integra o registro.
5. Gravar cada ELF e verificar imagem. Gravação única por lote é aceitável; fazer reset definido antes de cada execução. Se regravar, registrar isso.
6. Executar todos os casos no HW; esperar término/timeout; coletar snapshot congelado, validar e salvar logs.
7. Executar o mesmo ELF e entradas no Renode nominal; estado inicial novo por run, preferencialmente processo novo ou reset cuja limpeza seja demonstrada.
8. Decodificar/verificar completude, avaliar oráculos, gerar estatística, tabelas/figuras e traces Perfetto.
9. Produzir resumo com previsto/realizado/válido/inválido/divergente por condição, duração da campanha e limitações. Código de saída diferencia infraestrutura incompleta de campanha completa com divergência científica prevista.

Uma divergência Renode×HW pode ser o resultado esperado da pesquisa e deve permitir coleta completa. FAILED do instrumento, timeout, dados corruptos e condição ausente não podem passar como sucesso. Separar esses estados no formato e no resumo.

### 9.3 Repetições

- Piloto: 10 execuções completas por firmware e ambiente principal.
- Padrão da campanha final: **50 execuções**, parâmetro para 100 ou mais. Estes números são decisão operacional inicial, não obrigação bibliográfica nem garantia estatística universal.
- Uma execução pode percorrer todos os casos; 50 resets fornecem 50 observações por caso quando cada caso ocorre uma vez. Repetições internas/IRQs permanecem agrupadas pelo run, não viram amostras independentes automaticamente.
- Usar piloto para avaliar dispersão e precisão necessária. Documentar por que 50/100 é suficiente para a pergunta ou por que não é. Não ampliar silenciosamente até obter a conclusão desejada.
- No Renode, repetir as mesmas entradas/configuração para avaliar repetibilidade. Variar entradas é outra dimensão de cobertura, registrada separadamente.
- Identidade de resultados funcionais e tempos virtuais em N runs significa determinismo observado sob essas condições; não prova determinismo universal. Hash bruto contendo UTC ou dados do host não é teste de determinismo do alvo.
- Preservar ordem de aquisição e identificação da sessão. Se houver drift, analisar por bloco/run; não pooling indiscriminado. Hardware e Renode não precisam executar simultaneamente.
- Reset não é power-cycle. Desligamento físico automático não é requisito sem hardware adicional.

### 9.4 Recuperação, arquivos e propriedade de processos

- Timeouts host para cada etapa, além dos limites firmware. Recuperação não apaga a tentativa falha. Se houver retry, gerar tentativa distinta e limitar quantidade.
- Retomada exige mesmos hashes, versão ABI, plano, configurações e exemplar. Não concatenar campanhas incompatíveis por coincidência de nome.
- Não usar `killall`, `pkill` genérico, tomar a porta de outro processo ou encerrar OpenOCD de terceiros. Portas ocupadas resultam em erro claro ou seleção controlada de porta própria.
- Cleanup/trap encerra somente filhos da campanha e preserva arquivos de diagnóstico. Não precisa de acesso destrutivo ao ambiente do usuário.
- Manifestos e dados imutáveis após finalização, com hashes, timestamps host separados dos ticks do alvo, timeout/tentativas, versões de ferramentas, identidade do ELF/plataforma/fontes, registradores de clock/debug e seed.
- Estrutura de dados aberta, autodescritiva e documentada; snapshot binário e logs preservados, tabelas CSV/JSON, relatório técnico de resultados e traces. Relatório é produto da análise do software, não monografia nem documentação acadêmica copiada para este repo.
- Estimar tempo e tamanho da campanha a partir do piloto. Não prometer duração sem medi-la.

## 10. Oráculos, análise e classificação científica

### 10.1 Validação de entrada

Decodificador rejeita magic/ABI/layout/tamanho incorretos, capacidades inválidas, registros truncados, estados inconsistentes e contagens impossíveis. Verificar identidade firmware/cenário/caso, hashes, seed, clock/configuração e conjunto de casos esperado. Estado DONE sem todos os casos não é campanha completa.

Não inferir sucesso só porque GDB alcançou um símbolo ou conseguiu ler SRAM. DONE, FAILED, erro de protocolo, erro científico e timeout são conceitos distintos.

### 10.2 Resultados e estatística

- Oráculos funcionais independentes por caso. Não usar HW automaticamente como expectativa quando ele diverge da especificação, nem modelo Renode como referência para validar a si mesmo.
- Resultados completos: entradas, expectativas, valores observados, estados, divergências e razão da classificação. Hash pode suplementar, não ocultar toda a evidência funcional.
- Por condição: número planejado/coletado/válido, média, desvio padrão, mediana, mínimo/máximo e distribuição/ECDF/histograma apropriado. Intervalos de confiança somente com método e hipóteses adequados; não aplicar automaticamente normalidade a dados constantes ou correlacionados.
- Jitter definido operacionalmente: desvio em relação ao período, dispersão de latência ou outra grandeza indicada; não chamar qualquer diferença de jitter.
- Erro absoluto/relativo de tempo comparável, com unidade, resolução, overhead e frequência nominal/medida identificados. Incerteza HSI não é sempre ±1% nem pode ser confundida com erro microarquitetural.
- Primeira execução e posteriores com protocolo explícito. Não excluir primeiro dado após olhar resultados nem comparar entradas diferentes como efeito isolado de aquecimento.
- Resultados perdidos/erros não desaparecem das estatísticas do sucesso. Reportar exclusões e justificativas; análises válidas podem usar subconjunto explicitamente identificado.
- Variação e falhas ocasionais precisam ficar visíveis; médias podem esconder ordem incorreta, perda ou limiares.

### 10.3 Critérios e perfil em degraus

Definir antes da campanha final os critérios por observável. Resultados funcionais exatos usam igualdade quando o contrato exige. Temporais usam resolução/quantização, incerteza instrumental e adequação a um uso declarado. Não inventar tolerância universal nem chamar divergência explicável de equivalência aceitável.

Classificar por recurso/condição, por exemplo:

1. concordância funcional e temporal segundo o critério declarado;
2. concordância funcional com divergência temporal;
3. divergência funcional;
4. evidência insuficiente/instrumento inválido.

Os nomes finais podem variar; a distinção não. Um modelo pode servir para integridade de bytes e não para ORE, ou para ordem de IRQs e não para latência. Não criar um escore único que esconda esses limites.

Se não existir prazo de aplicação que fundamente uma margem, reportar diferença e erro como caracterização e declarar que adequação temporal a esse uso não foi estabelecida. A entrega deve permitir essa resposta honesta à pergunta do plano.

## 11. Riscos históricos a reinspecionar, não conclusões prontas

A auditoria anterior identificou os itens abaixo. O código pode já ter mudado; verificar o estado atual e os ELFs, sem copiar automaticamente diagnósticos. Não depender dos relatórios que serão apagados.

| Item observado anteriormente | Requisito de prevenção na nova entrega |
|---|---|
| Matmul C acumulava `int32_t` fora da faixa, enquanto Python forçava wrap | Eliminar UB; ranges/oráculo compatíveis; usar carga mais simples se adequado |
| Bracket empilhava 20 bytes antes de chamar C | Garantir SP alinhado segundo AAPCS; verificar ELF e chamada |
| RXNE: 32 escritas e espera de só quatro quadros | Observar término real ou timeout; separar TXE, entrega e atendimento |
| Explicação antiga atribuía bytes drenados a falha de re-pending do NVIC | Reexaminar versão fonte/estímulo; não usar interpretação como oráculo |
| Log de sequência possuía uma posição por ID e apagava repetições | Registro de ocorrências com sequência e contagem integral |
| Oráculo aceitava sequência reduzida do self-repend | Verificar duas entradas/saídas e sua ordem completa |
| `volatile` RMW em flags e DIER entre handlers | Propriedade de dados por contexto ou sincronização apropriada, sem alterar medição |
| Timeout de ensaio não era distinguido da conclusão | Registrar status por caso e rejeitar completude falsa |
| Assinaturas de STR/cópia não verificavam efeitos completos | Ler e verificar destino/estado efetivamente alterado |
| Collector aceitava snapshot decodificável como sucesso | Verificar estado, flags, casos e invariantes independentes |
| Análise omitiria dados inválidos/condições ausentes | Contabilidade integral e exclusões explícitas |
| CPUID/benchmarks usados para inferir autenticidade/generalização | Registrar exemplar; campanha legítima separada; limites de domínio |
| Muitas configs e MIPS7 tratado como dado fixo | Nominal8 único; calibração nova restrita a C1 |

Não conservar erros antigos por compatibilidade. Se a ABI mudar, versionar e rejeitar dados incompatíveis; não interpretar automaticamente dados antigos sob o novo significado de C3/C4.

## 12. Limpeza do ambiente e documentação final

Antes de remover arquivos, inspecionar referências reais, mudanças do usuário e dados. O autor quer uma árvore final enxuta; a autorização cobre limpeza do legado técnico da implementação, não destruição indiscriminada.

Remover/substituir quando sem função final: presets antigos `sandbox/c1/c2/c2busy/c3/c4/echo` com significado exploratório, fontes ausentes, `.resc` antigos, scripts de coleta/análise duplicados, geração de traces antiga incompatível, `.theia/`, configurações IDE órfãs, headers de trace sem uso, planos técnicos obsoletos e build trees que criem ambiguidade. Como `c1`–`c4` passam a ser nomes finais, substituir sua definição, não apenas apagá-la.

Preservar e adaptar: Nix/lock, vendor, linker/startup, CMake/toolchain, EditorConfig, suporte VS Code mínimo coerente, scripts realmente necessários e testes da entrega. Não reconstruir o ambiente de ferramentas do zero sem motivo.

Dados existentes são evidência: separar por identidade/ABI como exploratórios e retirar da análise final. Não apagá-los sem pedido específico. Se o autor exigir remoção da árvore ativa, propor arquivo/backup verificável dentro dos limites autorizados. Não copiar para Windows ou outros diretórios sem autorização de escrita. Não usar operações destrutivas globais em Git.

Atualizar README com: propósito e limites, mapa C1–C4, requisitos de bancada, único comando de campanha, presets, parâmetros, formato de dados/trace, abertura no Perfetto, critérios, limpeza segura e tabela de validações realizadas. Manter documentação técnica essencial junto do código/README; não criar `docs/` ou `context/` acadêmicos neste repositório.

Textos acadêmicos permanecem fora do repo, atualmente com plano em `D:\tcc`; contexto histórico cita também `C:\Users\Leonardo\projects\tcc`. Não migrar ou escrever nesses locais nesta tarefa. Atualizar orientações locais conflitantes quando permitido, sem modificar esta diretiva silenciosamente ou depender de AGENTS gitignored para explicar a entrega a terceiros.

**Este arquivo diretivo deve permanecer acessível durante a refatoração e a revisão do autor.** Não removê-lo como parte da limpeza sem instrução posterior. `tmp/` pode ser ignorado pelo Git; a especificação final dos casos, ABI e uso deve sobreviver nos arquivos técnicos versionados da entrega, não somente aqui.

## 13. Implementação, verificação e critérios de conclusão

O próximo agente deve executar e registrar as verificações necessárias para a entrega. Evitar grande suíte artificial; concentrar nos modos reais de falha e nos instrumentos que sustentam a análise.

### 13.1 Ordem sugerida

1. Inspecionar estado atual e confrontar plano/requisitos; mapear o que reaproveitar e o que retirar.
2. Definir matriz final de casos, observáveis e referência de cada caso, sem resultados preestabelecidos.
3. Simplificar ABI/trace e publicar contrato; corrigir collector e oráculos antes da campanha longa.
4. Implementar C1–C4 com nomes corretos e verificar footprint/ELFs.
5. Integrar campanha nominal, análise e Perfetto; executar piloto.
6. Validar instrumentos e completar campanha final quando a placa legítima estiver disponível.
7. Entregar complemento de calibração C1 e limpeza/documentação coerentes.

Não incorporar a extensão 72 MHz em detrimento das etapas obrigatórias. Não executar firmware antigo incompatível com loopback permanente.

### 13.2 Verificações mínimas

- Build de todos os presets finais no Nix; warnings próprios resolvidos; integridade vendor; uso de RAM/flash e stack.
- Propriedades decisivas da medição no ELF e validade da ABI. Static gate só deve afirmar propriedades que realmente verifica.
- Decodificador: fixtures válidas e corrompidas, contagens, truncamento, versão, estado, circular wrap/perdas, rollover e eventos repetidos.
- Oráculos: casos de fronteira aritméticos, conversões, buffers completos, prioridades e repetição; testes negativos que demonstrem rejeição de resultados incorretos.
- Concorrência do trace e dados: sequência preservada sob preempção, writers fixos, nenhum registro parcial aceito. Dimensionamento com margem.
- Campanha: indisponibilidade de HW/porta, timeout, coleta incompleta, retry/retomada, incompatibilidade de identidade, cleanup de filhos.
- Perfetto: importação e conferência de tempos/slices/eventos; empates, aninhamento, perda, rollover e unidade.
- Renode: smoke de cada firmware e campanha piloto nominal completa.
- HW: smoke e piloto nos recursos disponíveis, registrando exemplar; campanha final no STM32 legítimo. Resultados de clone são preliminares.

### 13.3 Definition of done

- [ ] Quatro cenários cobrem seus requisitos, com mínima sobreposição e C3=NVIC/C4=USART.
- [ ] C1 usa C predominante, compara funcional/temporal nominal e inclui calibração separada sem conclusões predeterminadas.
- [ ] C2 cobre TIM2/TIM3/TIM1, eventos/flags e contrastes da árvore temporal, ou limitações demonstradas e visíveis.
- [ ] C3 preserva sequências completas, inclusive repetição, prioridades, preempção, encadeamento e mascaramento.
- [ ] C4 cobre integridade, quadro/divisor, flags e sobrecarga com leitura atrasada e janela completa.
- [ ] Mesmo ELF e entradas por comparação; MIPS8 único na campanha principal; todos os parâmetros registrados.
- [ ] Trace ring robusto e coleta pós-execução; perdas e interferência diagnosticadas; importação Perfetto verificada.
- [ ] Um comando realiza build, aquisição, validação, análise e exportação sem ajustes manuais por cenário.
- [ ] Repetições configuráveis, contabilidade integral e retomada consistente.
- [ ] Critérios, distribuições e classificação por recurso/condição, sem confundir divergência científica e falha de instrumento.
- [ ] Legado sem função removido; dados preservados/separados; README e IDE/presets coerentes.
- [ ] Builds/testes/pilotos realizados e suas versões/resultados documentados.
- [ ] Campanha final na placa legítima realizada, ou pendência explicitamente identificada sem fingir que foi validada.

Sem placa legítima disponível, é possível finalizar a implementação e deixá-la pronta para o laboratório. Não é possível afirmar que a validação final em STM32 genuíno foi concluída. Informar exatamente essa dependência e o comando que a resolve, sem substituir por dados exploratórios. Não marcar o resultado como 100% validado quando faltar evidência material.

## 14. Referências para o agente

Links `latest`, `master` e `main` são pontos de descoberta, não versões congeladas. Registrar versão/commit realmente aplicável antes de fundamentar comportamento. Bibliografia Zotero pode conter itens sem PDF e anexos diferentes do livro indicado; verificar documento e edição antes de citar páginas.

### 14.1 Referências solicitadas pelo autor

- [SEGGER SystemView — UM08027](https://www.segger.com/downloads/jlink/UM08027_SystemView.pdf): inspiração conceitual de eventos, timestamps e modos de captura; conferir seções citadas, sem dependência de J-Link.
- [Perfetto — documentação](https://perfetto.dev/docs/).
- [Renode — scripts do repositório](https://github.com/renode/renode/tree/master/scripts): inspecionar recursos realmente existentes na versão usada; não presumir conversor específico.

### 14.2 Trace e tempo

- [Perfetto — formatos externos, incluindo Chrome JSON](https://perfetto.dev/docs/getting-started/other-formats).
- [Perfetto — Trace Processor](https://perfetto.dev/docs/analysis/trace-processor).
- [Perfetto — Track events](https://perfetto.dev/docs/instrumentation/track-events).
- [Perfetto — TracePacket e ClockSnapshot](https://perfetto.dev/docs/reference/trace-packet-proto).
- [Perfetto UI](https://ui.perfetto.dev/).
- [Renode — time framework](https://renode.readthedocs.io/en/latest/advanced/time_framework.html).
- [Renode — execution tracing](https://renode.readthedocs.io/en/latest/execution-tracing/execution-tracing.html).
- [Renode — modelagem de periféricos](https://renode.readthedocs.io/en/latest/advanced/writing-peripherals.html).

### 14.3 Especificação e fundamentação

- RM0008 Rev.21, especialmente árvore RCC pp.93–96, flash, TIM1/TIM2–4 e USART. Zotero item conhecido `N7JVRKFW`. [PDF ST](https://www.st.com/resource/en/reference_manual/rm0008-stm32f101xx-stm32f102xx-stm32f103xx-stm32f105xx-and-stm32f107xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).
- PM0056 Rev.7: exceções, prioridades, máscaras e registradores do Cortex-M3. Zotero item conhecido `IZMAAGNW`. [PDF ST](https://www.st.com/resource/en/programming_manual/pm0056-stm32f10xxx20xxx21xxxl1xxxx-cortexm3-programming-manual-stmicroelectronics.pdf).
- Datasheet da variante física STM32F103 utilizada: periféricos existentes, limites de clock, flash e tolerância HSI. Localizar versão oficial correspondente, não extrapolar de outra densidade.
- Cortex-M3 TRM correspondente à revisão física e ARMv7-M Architecture Reference Manual. [TRM r2p0 DDI0337G, cópia do documento Arm](https://www.keil.com/dd/docs/datashts/arm/cortex_m3/r2p0/ddi0337g_cortex_m3_r2p0_trm.pdf). Não pressupor r2p0 na placa legítima futura.
- [AAPCS32](https://github.com/ARM-software/abi-aa/blob/main/aapcs32/aapcs32.rst): chamadas, registradores e alinhamento.
- [WG14 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf): texto público C11 útil para regras preservadas em C17, incluindo aritmética e UB; não apresentá-lo como publicação final C17.
- Hennessy/Patterson, Computer Architecture: A Quantitative Approach, 6ª ed., equação de desempenho e CPI, pp.52–54. Zotero item conhecido `7KNR6VY7`.
- Yiu, The Definitive Guide to ARM Cortex-M3 and Cortex-M4 Processors, 3ª ed., e textos Arm sobre latência de exceções: consultar conteúdo efetivamente acessível.
- [Sargent, Verification and Validation of Simulation Models, WSC 2013](https://informs-sim.org/wsc13papers/includes/files/027.pdf): domínio, propósito e precisão requerida.
- [NIST — intervalos de confiança da média](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm): selecionar método conforme hipóteses e dados, sem regra mágica de número de repetições.

### 14.4 Fonte do Renode para investigar mecanismos

A auditoria anterior examinou `renode-infrastructure@066a7f13c052215632d469c995c89aea37c573b1`. Usar essa referência apenas se corresponder à instalação final; registrar a revisão real e do tlib.

- [STM32_UART.cs nessa revisão](https://raw.githubusercontent.com/renode/renode-infrastructure/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs).
- [NVIC.cs nessa revisão](https://raw.githubusercontent.com/renode/renode-infrastructure/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Cores/Arm-M/NVIC.cs).
- Timer/RCC/BaseCPU/tlib: localizar implementações da revisão real, conferir clocks, flags, entrega de IRQ e avanço temporal. Nome de classe ou comentário não é demonstração de comportamento completo.

## 15. Instrução final ao agente implementador

Entregar experimentos que permitam descobrir os resultados novamente, com instrumentação confiável e complexidade defensável pelo aluno. Manter a referência nominal, explicar limitações por recurso e preservar a evidência. Este documento define a entrega desejada; ele não fornece resultados a reproduzir artificialmente.
