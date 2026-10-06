status: active

## Alteração de governança solicitada pelo usuário
- Disponíveis somente explorer/librarian/fixer. Parent acumula estratégia/revisão/orquestração; não despachar oracle.
- ora-2 cancelado por objetivo substituído (read-only, sem partialwrites). Gates permanecem obrigatórios, agora revisão parent com evidência específica, não dependem de oracle.
- Docs acadêmicos fix-2 concluídos e lidos pelo parent: metodologia111linhas e bibliografia100linhas, labelsproposta/citações/limites/coerentes, semnovosexperimentos.
- Preflight parent: gcc15.3.1cmake4.4.3ninja1.13.2python3.14.7openocd0.12; STLinkUSB/dev/bus/usb/001/003plugdev, semttyUSB/ACM detectado. Daemon3333eRenode3335antigosvivos: reutilizar3333semkill, novoRenode>=3336.

## Alinhamento usuário (2026-10-07) — decisões ajustadas
1. Objetivo: 4 cenários FINAIS do TCC (S1núcleo/memória, S2timer→IRQ, S3USART, S4preempção vs arbitragem), cada um com firmware próprio (possivelmente >1arquivo src por cenário), testado HW+Renode, dados+manifesto+análise reproduzível, relatório por cenário em tmp/ com rigor bibliográfico. Limite ~4cenários, arquitetura livre.
2. TIMING — objetivo é ENTENDER o mecanismo. Ideal seria config única fiel (8MIPS + periféricos8MHz). Diagnóstico a provar: (a) config/periférico mal configurado ou (b) limitação do Renode. Se limitação: DOIS presets — P-nominal estritamente datasheet (8MIPS nominal, perif8MHz) e P-ajustado (MIPS derivado de calibração, como relatório intermediário). Medir impacto nos demais cenários. Solução elegante/única: MESMO mecanismo de configuração, parâmetro único (MIPS), rótulos de política nomeados; valor ajustado derivado formalmente (kernel de calibração designado em S1, congelado, validado em held-out: demais blocos S1 + S2/S3/S4). NUNCA per-cenário, nunca fitting pós-resultado. Presumido: ajustado = ÚNICO global (usuário pediu "elegante e única"); registrado, permitir correção.
3. BINÁRIO: sempre mesmo ELF por par ambientes, MAS verificar o binário contra o objetivo do cenário via disassembly (C1 foi "manchado": constant-folding removeu MUL/DIV pretendidos). Gate obrigatório: objdump confirma instruções/caminhos medidos, sem folded/eliminado, brackets medem o kernel certo, operands runtime (volatile/asm) impedem folding. Nome de função não prova presença.
4. RELATÓRIOS: NÃO usar tcc/ ainda. Intermediários em tmp/ (gitignored, auditável), estruturados e com rigor bibliográfico. .slim/ continua log central de descobertas/decisões/dúvidas (objetivo+porquê). tcc/ volta ao estado original (só references.bib + references-Inbox.bib).
5. RIGOR BIBLIOGRÁFICO p/ ARQUITETURA: propor cenários NASCENDO de bibliografia séria (Zotero principal; journals/conferences sérias permitidas), não justificar artificialmente escolhas arbitrárias depois do código. Cada escolha de cenário/métrica/protocolo → claim→source (página/seção), separando texto-lido vs metadados vs fontes técnicas.
6. Autonomia longa; usuário consultável para decisões que mudem direcionamento. Portas HW=3333, Renode>=3334 (coletor3336+).

## Estado infra + barreira de modelo (2026-10-07)
- fix-2 (common ABI) concluído e verificado: inc/fidelity.h(111L)+fidelity_trace.h+lib/fidelity.c compilam isolados; snapshot10368B/offsets ok; obj 696B text+10368B bss; s1..s4.resc criados (8MIPS explícito, S3 hub passivo source-confirmed).
- fix-3 (coletor) morreu sem reportar MAS gravou scripts/fidelity_collect.py(21KB)+tests/test_fidelity_collect.py(14KB). Auditoria parent: 15/25 tests passam; 10 falham — FakeProcess sem __exit__ quando list(platform.uname()) dispara subprocess (platform.py 3.14 lazy processor). --mips ainda choices=(8,100) — precisa virar política nominal8/calibrated/global/default100-control conforme decisão do usuário.
- fix-4 (análise) morreu no meio: scripts/fidelity_format.py+scripts/fidelity_perfetto.py existem; scripts/fidelity_analyze.py e tests/test_fidelity_analysis.py AUSENTES.
- fix-5/fix-6/fix-7 (retry) error imediato "Model unavailable: lithosai/zai-org/GLM-5.3-Flash" — barreira de infra do provedor do fixer, não recusa. Policy ativada: parent implementa diretamente (workaround de barreira autorizado pelo usuário) mantendo escopos exclusivos: (a) fix tests/test_fidelity_collect.py mocks + generalizar --mips em policy nominal/calibrated/default100-control; (b) criar scripts/fidelity_analyze.py + tests/test_fidelity_analysis.py. lib-3 (bibliografia) segue rodando sem conflito de scope.

## Gate1 parent — aprovado para infraestrutura, condições explícitas
Não há solução cicloexata viaresc/repl; estudo fará concordânciafuncional e caracterização temporal, SEM equivalência universal/margens arbitrárias. 8MIPSnominalprédeclarado+100defaultcontrole; quantum1us+125nssensibilidade. Agenda não recalibrada. MesmoELF. S4softwarependprova comportamentoarquitetural de nesting, não latênciaeventoexterno. S3passiveloopbacksempeerativo avalidar; se fioausente registrar bloqueiosemfingircoleta. CPU/TXE/TC/ORE/RCCmodelgaps resultados legítimos.
Contratos pequenos e finitos, captura frozen, critériofuncional específico e negativos; modelosobserverticks domíniodeclarado. Fase2infra será revisada antes implementarfirmwares. Semdescartelegadoantespairedvalidation.

### ABI v1 CONGELADA para lanes independentes
- Símbolo global volatile FidelitySnapshot fidelity_snapshot, littleendian, sizeof10368bytes; uint32_ttodososfields, _Static_assertsizes/offsets, sempacked.
- Header32words/128bytes ordem: magic(0x46494431),version(1),scenario(1..4),state(0init/1running/2done/3error),error,core_hz(8000000),result_count,trace_capacity(128),result_capacity(128),trace_enabled(1),seed,rcc_cr,rcc_cfgr,flash_acr,dwt_ctrl,prigroup; trace_count[3];trace_drop[3];reserved[10].
- Resultrows[128][8] @offset128 (4096bytes). Cada row[trial,condition,a,b,c,d,e,f]. Trace[3][128] @offset4224 (6144bytes), entry[ ticks,event,trial,arg ]16bytes.
- Writers físicos MAIN0/IRQ_A1/IRQ_B2 (fixos ao ISR, não trocarporrole/prioridade). appendonly bounded128cada, sem IRQ mask nem índice compartilhado, DMBpublication, explícitodrop. Results exclusivamente MAIN apósISRquiesce.
- API fidelity_init(scenario,seed); fidelity_ticks(); fidelity_trace(writer,event,trial,arg); fidelity_result(trial,condition,a,b,c,d,e,f); fidelity_finish(error) noreturn; fidelity_complete(void) noreturn/noinline símboloGDB. DWT habilitado/resetantesBOOT; DONE apósIRQstop/disableglobal+DSB/snapshotreadback/freeze. No resetDWT apósinit. Helpers boundary inline se necessário.
- Events BOOT1 PHASE2 ERROR3; S1_BEGIN0x100 END0x101; S2_ENTER0x200 EXIT0x201 MASK0x202 RELEASE0x203; S3_TX0x300 RX0x301 SR0x302; S4_LENTER0x400 REQUEST0x401 HENTER0x402 HEXIT0x403 RESUME0x404 LEXIT0x405 ARB_ENTER0x406 ARB_EXIT0x407. Names L/H roles = requester/requested; writerphysicalIRQ_A/B fixed.
- Static totalSRAM limite16384inclruntime+bss (>=4096restantesinclstackreservado); vendorlinkerintocado. Memória snapshot10.4KB, firmwareextras<=4KB; verificar map/size poralvo. Runtime stackhighwater futuronegociável,nãoalegartesteainda.
- Máximofinalduration<60s nominal, CYCCNTtotal<halfwrap: decoder rejeita ambiguidadetemporal. Same-tickevents distintoswriters não têm causalorder automática; S4recordsactiveflags+trial disambiguam/protocol order reported.
- Infra owners: fix-common inc/fidelity.h/inc/fidelity_trace.h/lib/fidelity.c/CMakeLists/CMakePresets/renode/s1..s4.resc; fix-collect scripts/fidelity_collect.py/tests/test_fidelity_collect.py; fix-analysis scripts/fidelity_analyze.py/scripts/fidelity_perfetto.py/tests/test_fidelity_analysis.py. Nenhumruntime/buildatéparentgate2; phase3firmwares dependemcommon API.

### Fase2 lançada / ownership ativo
- fix-2/ses_ee7dfd2bdffe3OHtbccz1VT4xk retomado: commonABI/CMakepresets+resc, scopeexato acima; semsrc/build/runtime.
- fix-3/ses_ee7d797e4ffeSJllOAP7CpNWrx novo: collector+testscorrespondentes, semruntime real; validaçãohostmocks.
- fix-4/ses_ee7d6dce6ffeX5nnTEtVb63mbU novo: adicionafidelity_format.py aoanalysis scope, decoder/analyzer/Perfetto+testscorrespondentes; hostsynthetic.
- Parent reconciliará todoswriters, inspecionará ABI/scripts e executará unittest integrado e sizeproportional antesgate2. Phase3firmware só apósAPIexistir/aprovada. Não tocar scopesescritaduranteativos.

# Retomada 2026-10-07 (tarde) — correções de log + Gate 2 + Fase 3
- Log estava desatualizado: --mips-policy nominal/calibrated/default100-control JÁ implementado em fidelity_collect.py (validação nominal=8, control=100, calibrated=derivado≠8/100). Mocks do coletor JÁ corrigidos: 26/26 verdes.
- scripts/fidelity_analyze.py EXISTIA (375L) mas truncado (SyntaxError L320-321) + semântica compare_rows; test_fidelity_analysis.py (13 testes) nunca rodou. Reparo parent (policy workaround): compare_rows itera colunas de valor presentes (a..f ou nomes contrato — spec do teste), check_s1 isenta cond 1 (empty_bracket) do iterations>0, fixtures corrigidos: s4 (publicação monotônica por writer, RESUME 30→36 → cadeia LENTER<REQUEST<HENTER<HEXIT<RESUME<LEXIT) e state3 (BOOT obrigatório MAIN[0]). SUÍTE: 39/39 OK (26 collect + 13 analysis).
- tcc/ confirmado de volta ao estado original (só 2 .bib) — decisão #4 cumprida; relatórios futuros em tmp/.

## Gate 2 — REVISÃO PARENT (gov. do usuário: gates sem oracle) — APROVADO com condições
Evidência: (1) unittest 39/39; (2) compile isolado lib/fidelity.c (-Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes) limpo; size: 532B text + 10368B bss (fidelity_snapshot 0x2880 = ABI exata) — extras ≤4KB ✓, SRAM estático 10368+stack ≥2KB dentro de 16384 ✓; (3) parity: s1..s4.resc idênticos (logLevel 1, quantum 1us, PerformanceInMips 8 policy nominal, ELF build/<s>/firmware.elf); CMake presets s1..s4 + add_scenario já ligam fidelity; collector pair_runs exige identidade elf/source/platform/seed/scenario; (4) race tracer: canais físicos single-writer append-only bounded 128, publicação por count++ pós-DMB, sem ring overwrite/IRQ mask, drop explícito; results MAIN após quiesce; finish disable_irq+DSB+readbacks+freeze — consistente com decoder (BOOT único MAIN[0], monotonicidade por writer, half-wrap/60s).
Condições p/ Fase 3 (firmwares): contratos RESULT_CONTRACT exatos; trial IDs globais únicos 1..N (check_s4 indexa por trial só); trace ≤128/writer por run (subconjunto instrumentado + agregados nas rows); operands volatile/seed anti-fold (gate objdump depois); mesmo ELF nos 2 ambientes; sem margens arbitrárias; interrupções/firmware param antes de cada fidelity_result.

## Fase 3 — protocolos congelados por cenário (decisão parent, derive do contrato)
- Comum: board_init → fidelity_init(scenario, 123U) → trials → fidelity_finish(0) noreturn; kernels em funções nomeadas noinline; handlers com protótipo; SRAM extra ≤4KB; timeouts DWT limitados (sem hang); LL apenas.
- S1 src/s1_core.c: conds 1..7 (empty_bracket, alu_dep, mul, div, branch, sram_rw, calibration); rows a=expected_checksum b=actual_checksum c=iterations d..f=0; S1_BEGIN/END por trial no MAIN; 4 trials/cond = 28 rows, trial 1..28; 56 entradas trace + BOOT ✓. empty_bracket: 0 iterações, checksums 0. calibration = kernel designado p/ política calibrated (mix fixo load/store/alu/mul/branch, 1000 it), congelado.
- S2 src/s2_timer_irq.c: conds 1..5 (busy_leisurely, wfi_leisurely, busy_masked_release, wfi_masked_release, disabled_source); rows a=serviced b=expected c=coalesced d=min_gap_ticks e=max_gap_ticks f=flags_end; TIM2 1kHz (PSC7/ARR999), 64 períodos/trial; expected via janela DWT/8000; coalesced=expected−serviced; cond3/4: mask ≥5 períodos (S2_MASK/RELEASE no MAIN) depois re-enable → 1 service com UIF; cond5: IRQ desabilitada o trial todo (serviced=0, coalesced=expected); ENTER/EXIT só nos 1os 3 services/trial (IRQ_A) = 90+4+1=95 ≤128; 3 trials/cond = 15 rows, trial 1..15.
- S3 src/s3_usart.c: conds 1..4 (leisurely_10ms, burst, blackout_ore, ore_recovery); rows a=tx_bytes b=rx_bytes c=ore_events d=recovery_ok e=checksum_ok f=first_byte_retained; USART1 115200 BRR 0x45, loopback PA9→PA10 (HW) / UARTHub passivo (RN), payload 16B seed; cond1 espaçada 10ms (DWT 80000 ticks); cond2 back-to-back TXE; cond3 não lê DR → ORE no HW (RN ore_events=0 = model gap legítimo, nunca fingir); cond4 recuperação RM0008 §27.3.5 (SR→DR) com first_byte_retained=byte antigo em DR; eventos S3_TX/RX por byte só 1os 8 bytes do trial 1/cond (4×8×2=64) + S3_SR por ORE + BOOT ✓; cond 1,2,4: rx==tx && checksum_ok; 2 trials/cond = 8 rows, trial 1..8.
- S4 src/s4_preemption.c: conds 1..5 (positive_preempt, neg_same_group_sub, neg_equal_priority, swap_preempt, arbitration); rows a=order_ok b=low_active_at_henter c=ipsr_at_henter d=msp_delta e=h_pending_after f=0; IRQs TIM2_IRQn+TIM3_IRQn software-pended (NVIC_SetPendingIRQ, sem periférico); PRIGROUP field=4 (3 group [7:5] + 1 sub [4]) — OBRIGATÓRIO p/ neg_same_group_sub ser expressível no F1 (board.h NVIC_PRIORITYGROUP_4 é 4:0 — NÃO usar); roles L=requester/H=requested, canais FISICOS fixos (swap_preempt troca roles, não canais); cadeia por trial LENTER→REQUEST→[HENTER→HEXIT]→RESUME→LEXIT (S4_ORDER do analyzer); negativos: HENTER/HEXIT após LEXIT (h_pending_after=1); arbitration: pend ambos simultâneos, 1 par ARB_ENTER/ARB_EXIT bracketando, order_ok = grupo maior roda 1º; low_active flag volatile setada por L antes do REQUEST; msp_delta = MSP_L − MSP_H; 2 trials/cond = 10 rows, trial 1..10; trace 5×2×6+4+1=65 ✓.
- Ownership Fase 3 (fixer RESTAURADO — barreira de modelo resolvida pelo usuário, 2026-10-07): 4 lanes paralelas disjuntas rodando: fix-5/ses_ee774bb02ffezHLmQBnDIQsRbt = src/s1_core.c; fix-6/ses_ee774bb01ffe7RIiOxKXawX7AE = src/s2_timer_irq.c; fix-7/ses_ee774bafcffepvy81dI2zb5cKs = src/s3_usart.c; fix-8/ses_ee774bafbffefGeKOqDeryxB3E = src/s4_preemption.c. Briefs conter protocolo congelado acima + regras anti-fold + budget de trace + syntax-check only (sem build/run/portas). Parent serializa builds (cmake --preset sN) + gate objdump + map/size após reconciliar. Depois: execução HW(3333)+Renode(≥3334) via fidelity_collect.py, análise, relatórios em tmp/.
- Adendo briefs: S3 cond4 usa byte duplicado como ESTÍMULO de provocação (excluído da contagem tx/rx do payload de 8B — documentar); S2 expected = janela DWT/8000 (±1 quantização), coalesced=expected−serviced por construção.
- Padrão de falha fixer (2026-10-07 tarde): lanes terminam "sem resposta de texto" sem gravar deliverable (fix-5/7/8 1ª gen; fix-6 2 gens truncadas na leitura). Mitigação: task_revive com prompt de continuação explícita (fix-5 gen9, fix-7 gen7, fix-8 gen8) + fix-9 lane nova para S2 (ses_ee7740721ffeyyTN3rVgXuKIHT). Se revives falharem outra vez: parent implementa direto (policy workaround já autorizada) começando por S1. Verificação de deliverable = existence + arm-none-eabi-gcc -fsyntax-only.

# Objetivo e estado herdado — 2026-10-07
Redesenhar aproximadamente quatro cenários finais do TCC, sustentados por bibliografia, com coleta reproduzível HW/Renode, DWT e Perfetto, e relatórios em /mnt/c/Users/Leonardo/projects/tcc. Usuário ausente: contornar bloqueios sem inventar resultados.

## Restrições
- HW/OpenOCD 3333; Renode >=3334. Hardware é recurso exclusivo, builds configuram .clangd: serializar builds.
- vendor congelado; preservar alterações herdadas e não executar mutações jj sem autorização específica. Inspeção inicial: change uysnponw, commit 50a8a223; op 28456f3d5d67.
- Estado da sessão anterior está em .slim/deepwork/tcc-20261007.md (somente leitura). Não aceitar suas conclusões sem auditoria: chamar DWT de ciclo físico no Renode e limites arbitrários de aceitação são riscos centrais.
- Já existem OpenOCD 3333 (PID 136493), Renode 3335 (PID 136471); não matar processos sem identificar ownership.
- Zotero CLI configurado localmente. Diretório tcc contém inicialmente apenas duas bibliografias .bib.

## Grafo de trabalho e gates
1. Auditoria/temporalidade: explorer audita código+dados existentes; librarian pesquisa fontes Renode/tempo; librarian audita Zotero+plano e fundamentação (lanes read-only independentes). Gate oracle 1: contrato temporal e desenho de quatro cenários, risco de validação circular.
2. Infraestrutura/metodologia: fixer(s) com scopes disjuntos para tracer/coleta/análise e plataforma; firmware só após contrato aprovado. Gate oracle 2: evidência observável, race de tracer, paridade inputs/outputs.
3. Firmware e execução: fixer(s) por cenários; validação de build serial e bancada exclusiva, Renode independente com portas reservadas. Gate oracle 3: resultados reproduzíveis e distinção preempção/arbitragem.
4. Análise e relatórios: relatórios por cenário com rastreabilidade de fontes, limites, dados brutos, scripts e diagnóstico de lacunas. Gate oracle 4: rigor científico e integridade da entrega.
Cada gate: um review inicial, até dois re-reviews só se materialmente necessário. Sem commits automáticos (política jj exige consentimento); fronteiras serão registradas aqui.

## Evidência planejada
- Timing: separar virtual time, host elapsed, DWT simulado, HCLK/TIM/SysTick; não calibrar MIPS por teste. Contraprovas com instruções de CPI diferente e periférico independente.
- Funcional: mesmo ELF/manifesto por par, estado final e invariantes, repetição de reset.
- Preempção (cenário final 4 conforme usuário): nesting/order e estado ativo, controle negativo mesma preemption priority; timestamp sozinho não basta.
- Tracer: limite SRAM, ISR nested writer, overflow, wrap, overhead, export parse validado; DWT load não equivale automaticamente a um ciclo.
- Bancada: registrar clocks/readback, payloads/loopback UART real disponível, ausência de equipamento externo como limite explícito.

## Tarefas
- Recon/research iniciais concluídas e reconciliadas: exp-1, lib-1, lib-2.
- Em andamento (validation owner: parent):
  - ora-1 / ses_eea56cadeffeHFo7Zs02mEtmi3: gate1 attempt1/3, read-only; aprovar contrato/ABI/evidência antes firmware.
  - lib-1 / ses_eea5d5450ffetwoUzX8VYdVOI5: complemento concluído; librarian read-only não gravou docs. Fonte confirma CreateUARTHub(name,boolloopback=false): trueincluiremetente, aplica atrasoCharacterTransmissionDelay/ReceptionDelay. SintaxeSOURCEvalidada: emulation CreateUARTHub "uartLoopback" true + connector Connect sysbus.usart1 uartLoopback + usart1 AutoUpdateDelay true/DelayMultiplier1; bancada PA9→PA10ainda verificar. Não corrige TXE/TC/ORE/serialização.
  - lib-2 / ses_eea5d0c51ffejQ18wTXSSHKJ2F reutilizada: research H&Pedition/Sargent/Akram; mensagem enfileirada corrigindo scope read-only, conteúdo final será entregue para fixer (sem afirmar mensagem lida).
  - fix-1 / ses_eea54e80bffe06PkqvRBrjmbYm: writer exclusivo tcc/docs/renode-temporalidade.md e tcc/context/renode-fontes.md, transcrição factual lib-1semresearch/runtime.
- Pendentes: reconciliar → contrato/implementação → coleta → análise/relatórios → gates finais.

## Retomada após limite de uso / reload
- User pediu continuar. Não houve implementação de firmware ou runtime. Estado jj continua50a8a223com24arquivosherdados; OpenOCD3333PID136493eRenode3335PID136471aindativos.
- ora-1/fix-1reportaramusage_limit; trackingantigonãoestá disponível(task_status/task_reviveunknown). Gate1nãofoirealizado: falha não conta como aprovação/review.
- Inspeção REAL dos dois docs técnicos detectou writesparciais úteis: tcc/docs/renode-temporalidade.md115linhas e tcc/context/renode-fontes.md78linhas completos e coerentes; preservados semnovaescritura. Task_resultantigofix-1retornoustatusincerto, não foi retomado nem duplicado scope.
- lib-2concluiumetadados/fulltext: H&P6ed2019ISBN978-0-12-811905-1PDF7/8confirmado. SargentWSC2013pp321–327DOI10.1109/WSC.2013.6721430, Akram2019pp53–58DOIconfirmado. Conteúdo prontos devolvido(read-only), semdocsacadêmicosainda.
- Running ora-2/ses_ee7e09e1fffeHToUoAytzZAHFn: Gate1attempt1/3sobreestadoagoradocumentado, scopearquiteturaABIprotocolo/paridade read-only; validação parent.
- Running fix-2/ses_ee7dfd2bdffe3OHtbccz1VT4xk: writerexclusivo tcc/docs/metodologia-cenarios.md e tcc/context/bibliografia-verificada.md (semconflitocomdocstécnicos), transcrevefontesverificadas semresearch; validação parent.

## Auditoria exp-1 reconciliada
- Final S4 = preempção/arbitragem; estado anterior propunha S3 e será substituído.
- trace_emit e C3 record têm índice compartilhado inseguro em nesting; DONE não congela snapshot, BOOT antecede reset CYCCNT, overflow/wrap e conversor insuficientes.
- C1 MUL/DIV constant-folded (ELF sem mul/udiv/sdiv); spans emitidos depois do kernel medem logger, sem outputs funcionais duráveis.
- C2 latência CNT*8 (não (1000-CNT)*8), inclui prologue/logger, resolução 8 ciclos; 1024 amostras, >4097 emits vs buffer2048. C2 SRAM margem estática 456B.
- C3 sweep não provoca high durante low de modo controlado; sticky flags/SP sobrescritos, MSP de C inclui prólogo. Necessário trials correlacionados e controles same-group/both-pending.
- C4 BRR69 corresponde690 HCLK/frame; race check-WFI, timeout não confiável, cooperative TIM2 rotulado como ISR, hub ativo vs loopback passivo não são entradas equivalentes.
- Runners têm pkill global/leaks/attach polling/stale dumps sem bounds; substituir antes de execução. Processos herdados observados sem ownership autorizado: não matar globalmente.
- data/val1 C1 pares preliminares confirmam razão17–19x variável; não comprovam causalidade microarquitetural. C2 HW completo, Renode timeout; C3/C4 sem validação final. Sem manifestos imutáveis: dados exploratórios somente.
- Priorização de remediação: buffers por writer/ensaio com publicação congelada; collector start/reset/run-to-completion/dump-at-end com PID exclusivo; funcional/disassembly invariants antes de temporal; sem limiares arbitrários ±1.5%,12±2/Spearman.

## Pesquisas lib-1/lib-2 aceitas — Gate1 contexto
- Renode1.17 Infrastructure066a7f13c052215632d469c995c89aea37c573b1, tlib167decf9129758829762e582939128c0694e90d6. BaseCPU usa instruções/MIPS para reportar tempo; DWT é LimitTimer virtual de8MHz sincronizado por SyncTime. Sem ciclos pipeline/memória/exceção12/6. Respostas mantenedores issues445/518 corroboram.
- Proposta temporal primária8MIPS (hipótese1instr/HCLK nominal, NÃO estimativa física), controle100MIPS explícito; quantum1us+125ns sensibilidade. Sem fitting, per-scenario tuning ou equivalência forçada. Tempo host separado, TIM/DWT mesma fonte não observação independente.
- USART STM32_UART permite AutoUpdateDelay=true/DelayMultiplier1 para UARTHub; TXE sempretrue, TC imediato, ORE false. Delay não corrige shiftregister. BRR69=690ticks/frame. Clock tree F1 RCC ausente, tags não hardware. SysTick CLKSOURCE forçado1 no NVIC; evitar falso HCLK/8. Não prometer execução_tracer timestamps nem metrics host load.
- Bibliografia confirmada: PM0056 IZMAAGNW rev7§2.3.5–7 pp35–38 grupo/subprioridade/nesting; §3.3.5p55 desalinhamento. RM0008 N7JVRKFW rev21 §7.2.2p95 HSI1% a25°C apenas; §15.3.1–2pp368–369 timers; §27.3.3–5pp795–800 UART/ORE/baud. H&P7KNR6VY7 §1.8 PDF71–79 reprodutibilidade/microbench caveat (edição verificar). Akram2019 EEAWTWJC DOI10.1109/PMBS49563.2019.00012 fulltextsc19§II control/dependency/execution/memory validation. Sargent WSC2013 fulltextinforms-sim.org/wsc13papers/includes/files/027.pdf §3.1/§4 validação por uso/condições/precisão predeclarada.
- Zotero22items HNZMPXEC; Yiu/Buttazzo/ARM TRM sem anexos, não alegar páginas lidas. Plano ausente no tcc (apenas2bib); não bloquear autonomia nem inventar conteúdo. Relatórios explicitarão escopo reconstruído a partir instrução usuário.

## Gate1 — proposta a revisar (attempt1/3)
- Quatro finais: S1núcleo/memória com outputs/disassembly/controlevazio; S2TIM2período/resposta sob carga+masked-release; S3UARTpayload/intervalos/serviço+blackout/limitaçãoORE; S4software-pendednestedIRQ+same-group(subprio)/bothpendingarbitration/swapprio, timer extension posterior.
- Paridade: mesmo ELF fixo/reset independent replicates (inicial3, final>=5se custo permitir), stimuli gerados firmware exceto UART externo opção. UART detectar conexão primeiro sem pressupor outra placa, self-loop hardware provável históricoPA9→PA10; sim deve reproduzir passivo sem peerativo se possível.
- ABIproposta: inc/fidelity.h + inc/fidelity_trace.h, lib/fidelity.c (ownersinfra), src/s1_core.c..s4_preemption.c (ownersfirmware). Captura alinhada por writer (main/low/high) com append-only bounded_count/drop_count, timestamp+event+trial+arg, buffers compactos (~6KBtrace total), snapshotresults <=8KB, stack>=2KB (limiteSRAM20KB). Não IRQ mask no logger, não ringoverwrite, DONE só após IRQstop/freeze/DSB; terminal function experiment_complete com breakpoint permitido só apósfreeze.
- Collector novo Python stdlib chama GDBbatch como subprocess bounded timeout, usa3333HWdaemonexistente identificado/semkill, configuraresetloadrun até terminal HWbreakpoint pósmedição; RenodeownedPIDporta>=3336, readinessnão listenerestranho, geraresc/RunForouGDBcontinuecomplete, dumpcombinedbounds/protocol/schema/config/ELFhash/sourcehash/rawimmutable/runmanifest. Sem attachpoll nem pkillglobal. Falha nunca validada pelo tamanho arquivoantigo.
- Scripts análise testsparse/nooverflow/orderinvariants/counterwrap/rejectambiguous spans; exportPerfetto+B/E/Xcomtickdomainmetadata, JSON/CSVsummaryECDFquantiserro; nenhuma margem arbitrária/WCETclaim.
- Escolha naming/migração a confirmar oracle: novos presets s1..s4 evitando confusão c3/c4 histórico; remover antigos da experiência final apósvalidação (preservar rawdata). IDEtaskslaunch devem seguir novos presets em laneintegration.
- Riscoagora: fixarABI/ownership/experimentosfinitos/payloadUARTparity e planoevidência semseguir legado inválido. Oracle não repetir pesquisa; usarachados estabelecidos.
