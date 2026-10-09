# C1 como fundamento de C2–C4: dependências, validade e escopo

## O que precisa funcionar para permitir cada cenário?

### Takeaway

Não há gate científico global «C1 passou inteiro» e, sobretudo, não se exige igualdade temporal entre núcleo real e simulado para estudar periféricos. Exige-se que o instrumento e o subconjunto de mecanismos usados por cada observável sejam confiáveis; uma divergência fora desse subconjunto não bloqueia o cenário. Esta é uma conclusão metodológica inferida do desenho concreto dos ensaios, não uma regra de arquitetura escrita literalmente nos manuais. A distinção já está prevista na diretiva técnica: perdas podem invalidar somente métricas dependentes do trace, e ordem pode ser válida onde latência não é. [Diretiva §§7.2, 10.3](/home/leonardo/projects/renode-stm32f103-fidelity/tmp/REQUISITOS-ENTREGA-FINAL-TCC.md:281).

### Cited Findings

- A abertura atual afirma que, se o núcleo calcular valor diferente **ou gastar ciclos diferentes**, todo cenário posterior «herda o erro». É amplo demais: a divergência temporal pode ser justamente um resultado do estudo, e a dependência deve ser delimitada por observável. [Material-base, Pergunta, linhas 9–12](/mnt/d/tcc/material-base/c1/01-pergunta.typ:9).
- O instrumento concreto compartilha memória de resultados, DWT e um logger com sequência global. O logger realiza `LDREX → leitura CYCCNT → STREX`, repetindo se necessário; publica registros por escritor e usa DMB antes de avançar o cursor. [lib/fidelity.c:40–80](/home/leonardo/projects/renode-stm32f103-fidelity/lib/fidelity.c:40). O documento corretamente identifica FEX-04 como dependência do coletor. [Material-base, Funcional:466–489](/mnt/d/tcc/material-base/c1/05-funcional.typ:466).
- A arquitetura abre o monitor local em entrada e saída de exceção, e a ST documenta que uma exceção remove a marca exclusiva. Essa propriedade é funcional: não exige custo de LDREX/STREX igual. [ARM ARM §A3.4.4, linha 3454](/mnt/d/tcc/zotero/artefacts/armlimited2021.md:3454); [PM0056 §2.2.7, linhas 940–985](/mnt/d/tcc/zotero/artefacts/stmicroelectronics2024.md:940).
- O DWT_CYCCNT real conta ciclos do núcleo exceto durante halt, é de 32 bits e dá wrap; diferenças são válidas dentro da janela de uma volta. [TRM r1p1 §11.5.1, linhas 6426–6432](/mnt/d/tcc/zotero/artefacts/armlimited2007.md:6426). O projeto explicita que o CYCCNT no Renode é derivado de tempo virtual, não de pipeline físico. [inc/fidelity.h:29–33](/home/leonardo/projects/renode-stm32f103-fidelity/inc/fidelity.h:29).
- Os valores de CPUID, VTOR, MPU e assinatura são casos separados; o próprio texto reconhece que várias divergências de identidade não alteram o resultado de uma instrução. [Material-base, Layout:79–96](/mnt/d/tcc/material-base/c1/06-layout.typ:79).

### Inferences

Matriz proposta, com requisitos **mínimos**, não promessa de que uma amostra C1 prove toda a ISA:

| Observável | Base funcional comum necessária | Base temporal necessária | O que uma falha não bloqueia automaticamente |
|---|---|---|---|
| Todos: resultados congelados | Imagem/entradas corretas; execução e retorno básico; SRAM e stack íntegros; inicialização .data/.bss; ABI/decodificador/nonce/contagens; restauração do estado entre casos | Nenhuma para ler valores; timeout do host deve existir fora do DWT | CPUID diferente, bit-band ausente, saturação ou fault não utilizados |
| C2: configuração, CNT parado, PSC/ARR/UG/UIF | Acessos MMIO nas larguras corretas, máscaras e comparações; valores brutos recuperáveis | Só necessária para afirmações de taxa/instante | Falha da parte NVIC pode deixar verificações de timer sem IRQ válidas |
| C2: taxa/período de timer | Acima e clock/contexto registrados | CYCCNT utilizável; relação HCLK/TIMCLK declarada; janela/polling quantificados | CPI físico diferente não bloqueia razão CNT/tempo virtual; limita comparação de reação do software |
| C2: IRQ e atendimento atrasado | Entrada/retorno básico, vetor/stack/contexto; fonte e pending observáveis; logger com integridade | Para períodos/latências: acima, custo/ponto do observador e limite de polling | Falhar máscara/arbitragem não é motivo para ocultar achado; restringe atribuição ao timer se NVIC também divergir |
| C3: arbitragem, preempção, máscaras, repetição | Base comum + entrada/retorno/contexto básico + registro de ordem que não depende de uma suposição sobre a arbitragem investigada | Nenhuma igualdade CPU para ordem puramente causal | PRIMASK/BASEPRI/preempção são objeto de C3, não condições para «permiti-lo» |
| C3: tempos instrumentados | Mesma base e trace completo | CYCCNT válido, overhead e intervalos corretos | Não se pode chamar intervalo entre logs de latência bruta nem inferir custo puro de tail-chain |
| C4: bytes e flags em caso isolado | Acessos SR/DR com número/largura/ordem corretos; buffers e conversões íntegros; configuração registrada | Só para deadlines e conclusão de ausência; host watchdog independente | Falha de NVIC em cenário sem IRQ, bit-band ausente e CPUID diferente |
| C4: baud, rajada, ORE/leitura atrasada | Acima; confirmar estímulo efetivamente oferecido e recebido | Base de tempo + relação HCLK/PCLK2 + janelas e instantes de observação; verificar oferta não condicionada inadvertidamente ao modelo | CPI diferente não proíbe experimento; muda pressão de polling/TX/RX, e resultado passa a ser da plataforma completa se não isolado |

As dependências funcionais gerais remetem a FA/FL/FS/FC/FMEM e LAY-03/04; logger concorrente acrescenta FEX; exceções acrescentam FSY/FEN. Não demandar que **todos** os vetores dessas famílias passem para **todo** uso. Selecionar codificações/mecanismos que o ELF e instrumento efetivamente usam. [Catálogo e política de disassembly](/mnt/d/tcc/material-base/c1/04-metodo.typ:119).

Exemplos concretos de separação:

1. Renode retorna CPUID diferente, mas nenhuma carga seleciona caminho por CPUID: registrar identidade divergente e continuar; igualdade de UID não é pré-condição de execução. [Material-base, Layout:73–96](/mnt/d/tcc/material-base/c1/06-layout.typ:73).
2. Divisão demora diferente, mas devolve resultado correto: C3 pode continuar com arbitragem funcional; taxa de atendimento e carga concorrente C2 devem reconhecer custo CPU diferente. A TRM prevê divisão 2–12 ciclos e dependência de operandos. [TRM §18.2, Tab.18-1, linhas 8890–8921](/mnt/d/tcc/zotero/artefacts/armlimited2007.md:8890).
3. Saturação ou bit-band falha: não bloquear C2–C4 se não usados. A falha é relevante ao domínio C1 e ao uso desse recurso, sem generalização indevida. [Catálogo FQ/FBB](/mnt/d/tcc/material-base/c1/05-funcional.typ:249).
4. CYCCNT congela, não é monotônico dentro da janela, ou wrap é decodificado incorretamente: tempos e loops de deadline ficam inválidos; valores digitais independentes já capturados podem ser preservados, com classificação parcial. O firmware usa DWT inclusive em `fid_delay` e timeouts de C2/C4. [inc/fidelity.h:181–186](/home/leonardo/projects/renode-stm32f103-fidelity/inc/fidelity.h:181); [C2:144–175](/home/leonardo/projects/renode-stm32f103-fidelity/src/c2/timers.c:144); [C4:73–99](/home/leonardo/projects/renode-stm32f103-fidelity/src/c4/usart.c:73).
5. FEX-04 ou logger falha: não confiar na ordenação global por tickets sob preempção; ainda pode estudar valores finais e ordem por escritor preservada, ou redesenhar instrumento e repetir os casos afetados. Não transformar trace suspeito em «NVIC fora de ordem». [lib/fidelity.c:63–80](/home/leonardo/projects/renode-stm32f103-fidelity/lib/fidelity.c:63).

### Gaps

- C1 não prova por si só que o logger funciona sob todas as preempções. Um SVC entre LDREX/STREX exercita limpeza do monitor, mas não esgota o protocolo real. Requer diagnóstico dirigido do instrumento (tickets únicos, progresso, contagens redundantes, nenhuma publicação parcial/perda) nas condições de C3. Isso é teste de instrumento, sem duplicar a matriz científica de prioridades.
- C1 não estabelece frequência física absoluta do HSI somente com contagem de ciclos. Para segundos físicos/exatidão do oscilador é necessária referência externa; para razões em ciclos sob HCLK declarado, não é preciso prometer esse ensaio extra. [Diretiva §3.5 e §10.2](/home/leonardo/projects/renode-stm32f103-fidelity/tmp/REQUISITOS-ENTREGA-FINAL-TCC.md:142).

## Como separar falha científica de falha de instrumento?

### Takeaway

Acrescentar ao método estados separados de «observação válida e divergente» e «evidência inválida/insuficiente», por observável. O catálogo de veredictos atual não contém explicitamente o segundo, embora o projeto o exija e o experimento com faltas tenha caminhos que podem perder continuidade. [Método, veredictos:239–259](/mnt/d/tcc/material-base/c1/04-metodo.typ:239); [Diretiva §10.3:395–400](/home/leonardo/projects/renode-stm32f103-fidelity/tmp/REQUISITOS-ENTREGA-FINAL-TCC.md:395).

### Cited Findings

- O firmware do C2 mede CNT na primeira operação útil de `timer_isr`, antes do logger, limpa fonte e lê de volta; logo seu observável não é automaticamente latência física desde update. [C2:84–92](/home/leonardo/projects/renode-stm32f103-fidelity/src/c2/timers.c:84).
- O C3 já registra que os timestamps de tail-chain incluem logger, epílogo e prólogo e não medem isoladamente tail-chaining. [C3:234–236](/home/leonardo/projects/renode-stm32f103-fidelity/src/c3/nvic.c:234). A TRM descreve tail-chaining como omissão de push/pop e início da ISR seis ciclos após saída da anterior, portanto contar logs não observa diretamente essa mecânica. [TRM §5, linhas 2849–2851](/mnt/d/tcc/zotero/artefacts/armlimited2007.md:2849).
- C4 registra instantes de escrita DR e leitura DR, e seu comentário ressalta que loopback não é fonte externa independente; não oferecer estímulo esperado impede atribuir ausência de ORE ao receptor. [C4:398–400](/home/leonardo/projects/renode-stm32f103-fidelity/src/c4/usart.c:398). A ST define ORE quando chega novo caractere com RXNE não resetado e geração de baud em função fCK/USARTDIV. [RM0008 §27.3.3, linhas 28658–28664](/mnt/d/tcc/zotero/artefacts/stmicroelectronics2021.md:28658); [§27.3.4, linha 28732](/mnt/d/tcc/zotero/artefacts/stmicroelectronics2021.md:28732).
- Para timers, TIMCLK=PCLK com prescaler APB1; senão TIMCLK=2×PCLK. Essa relação pertence ao mecanismo RCC/timer de C2; não deve ser presumida como passada por C1 só porque HCLK=8 MHz. [RM0008 §7.2, linhas 3319–3326](/mnt/d/tcc/zotero/artefacts/stmicroelectronics2021.md:3319).
- A arquitetura descreve efeitos e regras de acessos Device: sem repetir acessos, sem coalescer os de mesmo endereço, pois podem ter efeito colateral. Assim, conferir só SRAM não valida toda a semântica MMIO. [ARM ARM §A3.5.5, linhas 3717–3744](/mnt/d/tcc/zotero/artefacts/armlimited2021.md:3717). As barreiras têm finalidade funcional de ordenação além de custo. [PM0056 §2.2.4, linhas 828–854](/mnt/d/tcc/zotero/artefacts/stmicroelectronics2024.md:828).

### Inferences

Critério proposto antes da campanha:

- **Instrumento válido:** mesmo ELF e entradas; imagem/ABI verificadas; caso e vetor identificados; dados completos ou validade parcial delimitada; contador utilizável para aquele intervalo; nenhuma escrita fora dos buffers/stack; estado final confiável. Para retomada após faults, PC/xPSR/pilhas/máscaras/status/configuração devem ser restaurados conforme contrato, ou reiniciar vetor/caso em reset independente.
- **Conformidade funcional do objeto:** comparar somente bits definidos e campos válidos com o oráculo. Capturar um valor diferente, falta inesperada ou ausência de falta é resultado científico quando a captura é íntegra. Não exigir C1 inteiro verde para apresentar resultado negativo.
- **Divergência temporal:** quantificar diferença no observável definido e sua resolução/incerteza; não invalidar simplesmente por diferir do TRM/placa. Não corrigir MIPS dos demais cenários para fazê-los passar.
- **Inconclusivo:** registro ausente, sequência truncada, instrumento sem progresso, sem prova de oferta dos quadros, reset/fault que perdeu observações, endpoint temporal diferente entre ambientes. Não classificar como igualdade nem atribuir automaticamente a um modelo específico.

«Resultado de periférico» deve ser condicionado à forma de provocá-lo. Uma CPU mais rápida no Renode muda quantas vezes o software faz polling entre eventos e a fase dos acessos. C2/C4 podem comparar comportamento da **plataforma executando o mesmo programa** sem estar inválidos; apenas não podem atribuir toda diferença ao timer/UART isoladamente. Para isolar um periférico, usar razões documentadas, dados brutos e estímulos suficientemente espaçados/registrados, e distinguir data de evento de data de observação. [C2, count-rate com brackets de leitura CNT:224–245](/home/leonardo/projects/renode-stm32f103-fidelity/src/c2/timers.c:224); [C4, burst:222–253](/home/leonardo/projects/renode-stm32f103-fidelity/src/c4/usart.c:222).

### Gaps

- Não há no material-base atual matriz que vincule cada métrica posterior aos recursos C1 e ação em caso de falha. É recomendação adicionar essa matriz conceitual, sem implementar novos mecanismos nesta revisão.
- Testes de C1 não eliminam ameaça de barramento MMIO nem custos de logger concorrente. Medir DMB em bloco vazio não demonstra por si só ordenação sob toda condição. Validar invariantes do protocolo é mais direto que prometer conformidade universal das barreiras.
- Colega ARM identificou defeitos na proposta de recuperação (PC empilhado ímpar e T não reparado para INVSTATE). Evidência detalhada é responsabilidade da revisão arquitetural; aqui a implicação é impedir propagação silenciosa de estado corrompido para casos seguintes.

## Qual abordagem C1 dá valor sem explodir a complexidade?

### Takeaway

C1 tem valor em caracterizar o domínio de confiança do núcleo/memória e em explicar onde tempo virtual orientado por instruções preserva ou altera relações relevantes aos cenários posteriores. Demonstrar novamente que Renode não é ciclo preciso não basta; também não é necessário tentar certificar o Cortex-M3 inteiro. Seleção rastreável por dependência e por mecanismo é mais defensável para o objetivo de simplicidade.

### Cited Findings

- O texto promete transformar **cada linha e cada regra** da tabela temporal em microbenchmark. [Abertura:74–82](/mnt/d/tcc/material-base/c1/00-abertura.typ:74). A tabela inventariada estima 106 casos funcionais/layout e aproximadamente 60 temporais; soma de vetores funcionais/layout aproximada 9.107. Essa é soma das estimativas, não prova de quantidade final ou cobertura ISA; «caso» agrupa múltiplas instruções/codificações. [Implementação:32–60](/mnt/d/tcc/material-base/c1/09-implementacao.typ:32).
- O desenho usa três novos presets e vários arquivos assembly por família, com recuperação genérica de faults e captura própria de reset. [Implementação:19–29,65–88](/mnt/d/tcc/material-base/c1/09-implementacao.typ:19). Isso oferece controle necessário para flags/codificações e evita UB de C, mas amplia a base instrumental que precisa ser validada.
- Há divergência documental entre esse novo desenho e a diretiva antiga: esta sugeria 25–40 casos, C predominante com poucas exceções assembly e complemento separado de calibração. [Diretiva §§3.2–3.4](/home/leonardo/projects/renode-stm32f103-fidelity/tmp/REQUISITOS-ENTREGA-FINAL-TCC.md:92). O material atual exclui calibração. [Limites:37–38](/mnt/d/tcc/material-base/c1/10-limites.typ:37). **Não é erro científico por si:** o usuário explicitamente refina o método e o código está defasado. É decisão de escopo a reconciliar nos documentos, não obrigação de voltar ao método antigo.
- Kang define o modelo 1-CPI e o separa de modelos que usam custos por instrução; não valida Renode ou Cortex-M3 específico. Seu alvo principal é processador moderno superscalar fora de ordem, de modo que o diagnóstico de complexidade/caches não pode ser importado literalmente para M3. [Kang §2.1, linhas 80–94](/mnt/d/tcc/zotero/artefacts/kang2016.md:80).
- A TRM mostra que desempenho depende de pares: LDRs independentes podem se sobrepor, LDR PC e table branches bloqueiam, store buffer cheio atrasa; isto já fundamenta comparar famílias e interações, sem precisar toda a ISA. [TRM §18.3, linhas 8934–8967](/mnt/d/tcc/zotero/artefacts/armlimited2007.md:8934).
- Contadores de perfil são aproximadamente acurados; uma identidade derivada deles não é gate de contagem exata independente. [ARM ARM §C1.8.4, linha 35375](/mnt/d/tcc/zotero/artefacts/armlimited2021.md:35375). O texto reconhece aproximação, mas simultaneamente diz que contagem «deve coincidir» com estática/stepi. [Ciclo:323–341](/mnt/d/tcc/material-base/c1/07-ciclo.typ:323).

### Inferences

Organização recomendada:

1. **Base instrumental e subconjunto comum:** valores/flags usados; ramos de controle; SRAM/larguras/vizinhos; flash/literais; .data/.bss/stack; DWT/wrap/janela; logger/exclusivos básicos; SVC entry/return/IPSR. Poucos casos, cada um vinculado às métricas que sustenta. Não prometer certificação total.
2. **Contrastes temporais por mecanismo:** ALU; divisão e longa multiplicação com operandos de terminação distinta; LDR isolado/dependente vs sequência pipelinável; store; múltiplos N; desvio tomado/não/alinhado; IT e folding; barreiras; flash vs SRAM. Mantém assembly onde necessário para medir exatamente o mecanismo. Evitar duplicar famílias que não adicionam mecanismo ou risco distinto, sem excluir edge cases funcionais úteis.
3. **Cobertura de bordas funcional seletiva:** selecionar pelos ramos do pseudocódigo e entradas extremas, como o documento já faz; conservar motivação por caso. Ampliar ISA, modos de privilégio/reset, bit-band, áreas reservadas e fault variants como cobertura diagnóstica delimitada, sem torná-los requisitos universais de C2–C4.
4. **Uma ou duas composições com propósito:** uma sequência que representa polling/acesso de memória e uma carga com contraste de operações. Validar saída/caminho e comparar previsão/medida; não supor soma de custos isolados por causa do pipeline. O resultado útil é mostrar acertos/erros por composição e condições de uso, sem validar cargas não executadas.

Formulação final sugerida: «C1 estabelece, para um conjunto declarado de operações e condições, a concordância funcional e os limites da correspondência entre instruções executadas, ciclos físicos e tempo virtual. Esses resultados definem quais observáveis de C2–C4 podem ser interpretados diretamente, quais exigem cautela e quais não têm suporte instrumental.»

Em vez de «C1 dá certo», exigir **C1 produz evidência válida**. É perfeitamente possível que C1 encontre divergências funcionais/temporais e ainda sustente partes de C2–C4, desde que as dependências afetadas sejam rastreadas. A contribuição acadêmica é um mapa justificado de validade por recurso/condição, com contraprovas reproduzíveis e limites de atribuição, não a obrigação de obter equivalência global.

### Gaps

- A melhor cardinalidade final só pode ser fixada após matriz mecanismo × caso × uso no ELF. As contagens atuais são estimativas e não justificam, por si, mais cobertura.
- Tempo livre do revisor não reduz custo de implementação/defesa do aluno. A escolha entre catálogo amplo e núcleo seletivo é metodológica; apresentar esforço e valor marginal, sem tratar o catálogo atual como errado só por estar maior que o anterior.
