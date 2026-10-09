# Avaliação e refinamento adicional — 09/10/2026

## 1. Parecer

O recorte atual está alinhado às quatro áreas do plano de trabalho e às suas
clarificações. Os firmwares mantêm experimentos compreensíveis em C, sem OS:
C1 núcleo/memória, C2 timers e IRQ periférica, C3 NVIC e C4 USART. A calibração
permanece exclusiva do complemento do C1; C2–C4 usam a configuração nominal
única de 8 MIPS/125 ns.

**A revisão encontrou defeitos relevantes para a validade do TCC.** Foram
corrigidos no código, no coletor, nos oráculos, na análise e na documentação.
A integração curta terminou e os dados foram reanalisados com os oráculos
corrigidos. Isso prepara a bancada para a coleta final; os resultados físicos
continuam pertencendo ao exemplar atual, provavelmente compatível/clone.

Não há fundamento para apresentar os dados dessa placa como validação final
do STM32F103 genuíno, nem para declarar fidelidade universal de ISA/ciclo.
O README distingue agora resultados históricos, observações novas,
especificação e mecanismo implementado pelo Renode.

## 2. Problemas encontrados e desenvolvimento realizado

| Área | Problema e consequência | Correção |
|---|---|---|
| C1: linguagem C | Acessos de 16 bits a objetos de 32 bits e leitura de bloco por cast podiam violar aliasing/tipo efetivo. `volatile` não corrige isso. | Tipos GNU `may_alias` nos acessos apropriados e `memcpy` na interpretação dos blocos. Convenções GNU explicitadas. |
| C1: desalinhamento | Cópia por bytes não demonstra funcionamento de acessos desalinhados LDR/STR. | Caso 30, offsets 1/2/3, leitura/escrita de 16/32 bits e preservação dos vizinhos. Helpers C `packed`/`may_alias`; gate confere as quatro instruções realmente emitidas. |
| C1: cópia SRAM | Conferir o retorno/última palavra poderia aceitar uma cópia parcialmente errada. | Todo o destino é coletado e conferido em cada repetição, fora do bracket. SRAM do firmware temporal dimensionada para os dados completos. |
| C1: descrição do ELF | O `switch` era descrito como tabela de salto sem que isso correspondesse ao binário. | Documentação corrigida para seleção aritmética/condicional. Expressão C não é rotulada como instrução sem examinar o ELF. |
| C2: medição | Limites presumidos para polling e UG podiam produzir falsa divergência. | Brackets reais para CNT/UG; leitura posterior comprova reinício sem depender da visibilidade imediata e sem confundir UG com overflow natural. A leitura imediata permanece nos dados. |
| C2: IRQ atrasada | Uma fonte ainda ativa podia produzir outro evento; CNT podia ser tratado indevidamente como latência. | Fonte congelada antes da liberação; MAIN e ISR leem CNT e conferem sua preservação; janela adicional detecta duplicação. Fase e intervalo do marcador de liberação recebem nomes próprios. |
| C2: configuração | Valores solicitados podiam ser confundidos com configuração aplicada. | Registro de PSC/ARR e estado CR1/DIER/CCER/clock enable realmente lidos. Previsão não é redefinida por registrador incorreto. |
| C3: contrato do estímulo | Sequência de tokens poderia coincidir com argumentos/configuração incorretos. | Prioridades lidas de volta, EXTI isolada, argumentos completos conferidos, todas as ocorrências preservadas, incluindo auto-repending. |
| C4: oráculo | Configuração observada podia alterar a própria expectativa; layouts parciais eram frágeis. | Tabela independente por ID e payload local versionado `0x43340002`; contagens, tamanhos e formatos conferidos. |
| C4: erros e capacidade RX | Ler DR podia limpar erros antes do registro; entrega tardia podia parecer retenção em FIFO. | Erros acumulados antes de DR, confirmação de TC, guardas e timestamps de produção/drenagem. Suspeita de entrega tardia invalida a inferência de capacidade. |
| Análise: falhas | Valor modal podia esconder falha ocasional ou concordância entre dois comportamentos errados. | Todas as observações e falhas entram na análise; comparação HW×Renode e conformidade de cada ambiente são eixos separados. |
| Análise: tempo | Margens de polling não demonstradas eram usadas como aprovação de ciclo. | Comparação descritiva de medianas e diferenças; resolução nominal não aprova precisão de ciclo nem prazo de aplicação. |
| Análise: agregação | Eventos internos podiam parecer repetições independentes; ajustes temporais podiam esconder resultados funcionais válidos. | Estatística por reset, tamanho efetivo de amostra explícito e separação de linhas funcionais e derivadas. |
| Análise: identificação | Rótulos com limites/valores diferentes impediam comparar o mesmo item entre ambientes. | Rótulos estáveis e verificações de invariantes booleanas; valores temporais ficam nos dados/métricas. |
| Trace | Rollover, nesting e pareamento de bytes podiam gerar visualização incorreta. | Reconstrução pelos tickets, intervalos locais ao caso, união dos períodos preemptados e recusa de pareamento TX/RX quando conteúdo/ordem divergem. |
| Coleta | Retomada e snapshots precisavam de vínculos mais fortes; processos podiam deixar descendentes ativos. | Plano/ELF/ABI/nonce/hash revalidados, publicação protegida, tentativas preservadas, timeouts, locks e encerramento apenas dos grupos próprios. |
| Startup Renode | Entre bind e listen, a propriedade da porta podia parecer ausente. | Confirmação da condição antes de classificá-la como servidor alheio; teste reproduz a janela bind→listen. Não há conexão a servidor sem propriedade confirmada. |
| GDB/stepi | Operação de bits sobre `$pc` tipado como ponteiro fazia o script falhar. | Conversão explícita para inteiro no guard e no laço; diagnóstico real na placa e no Renode. |
| Debug por Bash | O wrapper Renode muda de diretório; usar cwd para autenticar o PID impedia encerrar a própria instância. | Identidade por PID, instante de criação e argumento do processo; start/stop real conferidos. |

A expansão do firmware é principalmente conferência e instrumentação. Não
foi adicionada uma implementação extensa em assembly da ISA. O bracket
assembly continua isolado e o restante se organiza em casos C nomeados.
Os scripts Python têm mais validações: são necessários para defender que
um número pertence ao ELF, ao reset e à condição que o relatório declara.

## 3. Validação executada

**Não foram executadas campanhas de 50/100 repetições nesta revisão.**

| Verificação | Resultado |
|---|---|
| Cinco presets, build e gate | Sem warnings; limites conservadores de flash/SRAM atendidos; 39 arquivos do vendor conferidos por SHA-256. |
| Regressões de ABI/análise/Perfetto | 40 testes passaram, incluindo importação real. |
| Regressões do coletor/processos/campanha | 16 testes passaram, incluindo portas de terceiros, bind antes de listen, timeout de descendentes, retomada e integração simulada. |
| Regressões C1 | 5 testes passaram; corrupção de palavra interna da cópia e de bytes vizinhos é detectada. |
| Regressões C2/C3 | 14 testes passaram, com casos sintéticos e capturas; layouts antigos/incompletos, estímulos errados, prioridade, repetições e CNT congelado são conferidos. |
| Regressões C4 | Fixture com 324 verificações; 62 casos negativos passaram. |
| Integração real inicial `refinement-20261009-01` | 22 capturas válidas, nenhuma tentativa falha, 16/16 importações Perfetto conferidas; retomada sem recoleta. |
| Integração real após ajustes C2 `refinement-20261009-02` | 22 capturas válidas em 23 tentativas; uma falha de startup preservada e recuperada; 22 traces por run, 5 comparativos e 16/16 importações conferidas. Retomada sem recoleta. |
| Diagnóstico novo por stepi | `empty/0`: 3 instruções; `alu/16`: 101. Sequências de PCs iguais na placa e no Renode. |
| Debug Bash | Start/stop real do Renode em :3334 passou. |
| Conferência final de arquivos | `git diff --check` e sintaxe Bash passaram; vendor preservado; sem pasta operacional `tests/`. |

Total: **75 testes unittest**, além dos 62 casos negativos do C4. Testes
sintéticos e integração simulada não são apresentados como evidência física.

As retomadas ocorreram antes das últimas correções do host/README. O plano
congela também esses arquivos; uma nova retomada com fontes diferentes deve
ser recusada. A reanálise posterior conserva os snapshots e grava em
`analysis/provenance.json` a identidade dos fontes da aquisição e da análise.
As últimas correções de startup/stepi foram exercitadas pelo diagnóstico real
curto e pelas regressões; os cinco ELFs mantiveram os hashes da segunda
integração.

### Evidências para leitura

- [Relatório integrado atualizado](../data/fidelity/refinement-20261009-02/analysis/report.md).
- [Contabilidade de todas as tentativas](../data/fidelity/refinement-20261009-02/analysis/accounting.csv).
- [Verificações funcionais](../data/fidelity/refinement-20261009-02/analysis/checks.csv).
- [Estatísticas por reset](../data/fidelity/refinement-20261009-02/analysis/stats.csv).
- [Identidade da reanálise](../data/fidelity/refinement-20261009-02/analysis/provenance.json).
- [Validação Perfetto](../data/fidelity/refinement-20261009-02/analysis/perfetto/validation.json).
- [Comparação Perfetto C1](../data/fidelity/refinement-20261009-02/analysis/perfetto/compare-c1-timing.json).
- [Diagnóstico curto de instruções](../data/fidelity/diagnostic/refinement-short-instructions-20261009-02/review.json).
- [Documentação técnica completa](../README.md).

## 4. O que os resultados novos permitem dizer

- **C1 funcional:** 30 casos e 629 verificações por run, conformes nos dois
  ambientes nas capturas examinadas. A cópia temporal também confere o bloco
  completo. Isso sustenta as operações examinadas, sem cobrir toda a ISA.
- **C1 temporal:** a distinção permanece clara. Em n=256, as medianas warm
  de divisão pequena/grande foram 2828/4587 ticks na placa e 1288/1288 no
  Renode nominal. Estes são tempos das cargas, não CPI por instrução inferido
  a partir do tempo do simulador.
- **Calibração:** configuração escolhida de 6 MIPS/500 ns; erro médio no
  treino passou de 27,9% para 11,0%, e na avaliação de 48,9% para 31,8%.
  Melhorar a média não corrige o custo por instrução. MIPS e quantum mudam
  juntos: o complemento compara configurações e não isola causalmente MIPS.
- **C2:** a placa atende às verificações aplicadas; Renode diverge em
  registradores de clock, aplicação dos perfis APB, PSC e UIF/UG. O relatório
  identifica o item responsável; uma configuração não modelada não deve ser
  escondida por um período que coincida em outro caso.
- **C3:** configuração, sequências completas, argumentos, máscaras e
  ocorrências conferiram nos dois ambientes; os intervalos diferem. Ordem
  correta de atendimento não prova os ciclos físicos de tail-chaining.
- **C4:** continuam visíveis diferenças de TC, paridade e palavra de 9 bits.
  Na leitura atrasada, placa atual e Renode preservam até oito bytes sem ORE:
  coincidem entre si e divergem do contrato usado. Isso não valida o STM32F103
  especificado nem demonstra capacidade infinita.

Identidade física registrada: CPUID `0x412fc230`, IDCODE `0x20030410`, flash
informada de 128 KiB e UID de 96 bits zerado. Esses campos são metadados,
sem constituir autenticação do fabricante. Repetibilidade foi observada nos
dois resets de cada condição; não é prova geral de determinismo.

## 5. Fundamentação e cobertura restante

O plano de trabalho de 31/08/2026 foi relido, e os contratos foram conferidos
com RM0008 Rev. 21 e PM0056 Rev. 7 disponíveis no Zotero (`N7JVRKFW` e
`IZMAAGNW`). As referências primárias de GCC, Renode, SystemView e Perfetto
estão vinculadas na seção 13 do README. Comentários, resultados antigos e
comportamento do clone não são usados para redefinir o manual.

A biblioteca/manual não é verdade física absoluta sobre qualquer placa;
é a referência normativa do contrato do componente especificado. Uma
observação contrária exige distinguir instrumento, exemplar e simulador.

### Limites que precisam acompanhar a defesa

1. **Placa genuína:** a campanha final ainda deve ser realizada nesse
   exemplar, com sua identidade e nome próprios. Os dados atuais permanecem
   preliminares.
2. **Instruções:** o diagnóstico novo cobre duas combinações. As 25
   combinações completas do ELF atual não foram percorridas nesta revisão;
   a campanha final mantém essa etapa. PCs iguais evidenciam o caminho,
   sem validar todo estado intermediário arquitetural.
3. **Tempo:** HSI nominal não é medição de frequência física. Logger,
   prólogos/epílogos, barreiras e debugger fazem parte das condições. Mínimo
   observado do logger não limita todo custo sob preempção/retry.
4. **C1:** sem testes dedicados de bit-banding, faults, exclusividade ou
   flash sob wait states/72 MHz. São extensões possíveis, fora da matriz
   obrigatória representativa.
5. **C2:** timers determinísticos geram IRQ assíncrona à thread; não são
   fonte imprevisível externa. A cobertura não inclui todos os modos de
   timer ou toda a árvore RCC.
6. **C3:** não isola stacking/tail-chaining em ciclos, late arrival,
   FAULTMASK, NMI e faults. Isso delimita o que “NVIC validado” significa.
7. **C4:** loopback não injeta paridade/enquadramento errados, não mede
   forma de onda e não usa clocks externos independentes. Capacidade
   observada é limite inferior nas condições aplicadas.
8. **Amostragem:** dois resets validam o fluxo curto. O orçamento de 50 da
   campanha final não é demonstração universal de suficiência; eventual
   dispersão ou investigação de falhas raras exige definir a precisão ou
   taxa que se pretende estudar. Uma placa não é amostra de placas.

**HSE/PLL/72 MHz:** considero uma extensão útil para contrastar clock/flash,
mas acrescenta variáveis e depende de suporte do modelo ou de registrar sua
ausência. Mantive a base HSI8 e os quatro cenários delimitados. É preferível
concluir a comparação controlada e defensável antes de ampliar a bancada.

## 6. Encaminhamento

O repositório foi refinado, a documentação técnica foi atualizada e a bancada
curta foi validada. O próximo passo experimental é o piloto e a campanha na
placa genuína, usando os comandos do README e um nome novo de campanha.

Os diagnósticos e regressões desta sessão ficam separados em `tmp/refinement/`
e `data/`. Relatórios históricos foram preservados. A diretiva original foi
mantida, a monografia não foi produzida e nenhum commit foi criado.
