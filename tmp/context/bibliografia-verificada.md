# Bibliografia verificada e limites de uso

Registro transcrito em **7 de outubro de 2026** a partir da pesquisa read-only concluída pela sessão principal. Esta redação não realizou novas consultas, não modificou Zotero nem arquivos `.bib`. “Texto verificado” abaixo descreve o acesso registrado pela pesquisa anterior, não uma nova leitura externa nesta transcrição. Metodologia: [metodologia-cenarios.md](../docs/metodologia-cenarios.md), **proposta, gate 1 pendente**. Fontes da implementação: [renode-fontes.md](renode-fontes.md); interpretação temporal: [renode-temporalidade.md](../docs/renode-temporalidade.md).

## 1. Hierarquia de evidência

Artigos/livros acadêmicos sustentam escolhas metodológicas; manuais primários sustentam contratos arquiteturais e periféricos; fonte Renode fixada sustenta afirmações sobre o modelo efetivo. Issues e blogs fornecem contexto explicativo, não substituem essas evidências. Metadados disponíveis não equivalem a texto integral lido. Não transferir limites numéricos de outra arquitetura para STM32F103.

## 2. Fontes acadêmicas com texto verificado

### Sargent — validação relativa ao propósito

**SARGENT, Robert G.** An Introduction to Verification and Validation of Simulation Models. In: *Proceedings of the 2013 Winter Simulation Conference*. IEEE, 2013. p. 321–327. DOI: [10.1109/WSC.2013.6721430](https://doi.org/10.1109/WSC.2013.6721430).

- Acesso: [PDF integral externo](https://informs-sim.org/wsc13papers/includes/files/027.pdf) lido e metadados confirmados em Crossref; item não encontrado no Zotero consultado.
- §1, p. 321: validade em relação ao propósito e condições; precisão requerida especificada antes ou no início da validação.
- §3.1: validade conceitual, verificação computacional, validade operacional e validade de dados.
- §4, p. 326, passos 2 e 6: propósito/precisão e avaliação em múltiplas condições.
- Limite: não prescreve aqui um teste estatístico, número de réplicas ou tolerância universal. Recomendações operacionais do protocolo não devem ser atribuídas literalmente ao autor.
- Não confundir com o artigo em *Journal of Simulation*, v. 7, p. 12–24, DOI `10.1057/jos.2012.20`: é outro artigo, não lido nesta pesquisa.

Entrada pronta apenas para futura importação autorizada (não aplicada ao `.bib`):

```bibtex
@inproceedings{sargent2013introduction,
  author    = {Sargent, Robert G.},
  title     = {An Introduction to Verification and Validation of Simulation Models},
  booktitle = {Proceedings of the 2013 Winter Simulation Conference},
  year      = {2013},
  publisher = {IEEE},
  pages     = {321--327},
  doi       = {10.1109/WSC.2013.6721430},
  url       = {https://informs-sim.org/wsc13papers/includes/files/027.pdf}
}
```

### Akram e Sawalha — microbenchmarks e diagnóstico

**AKRAM, Ayaz; SAWALHA, Lina.** Validation of the gem5 Simulator for x86 Architectures. In: *2019 IEEE/ACM Performance Modeling, Benchmarking and Simulation of High Performance Computer Systems (PMBS)*. IEEE, 2019. p. 53–58. DOI: [10.1109/PMBS49563.2019.00012](https://doi.org/10.1109/PMBS49563.2019.00012).

- Zotero: `EEAWTWJC`, citekey `akram2019`; metadados disponíveis, **sem anexo**.
- Texto lido externamente: [PDF dos proceedings SC19](https://sc19.supercomputing.org/proceedings/workshops/workshop_files/ws_pmbss111s2-file1.pdf).
- §II, p. 54: configuração comparável, contadores de hardware e microbenchmarks de controle, dependência, execução e memória; diagnóstico requer conhecimento da implementação.
- Limite: gem5/x86 Haswell, não Cortex-M3. Erros inferiores a 6% relatados nesse contexto não fornecem margem de aceitação para este TCC.

### Hennessy e Patterson — avaliação quantitativa reproduzível

**HENNESSY, John L.; PATTERSON, David A.** *Computer Architecture: A Quantitative Approach*. 6. ed. Morgan Kaufmann/Elsevier, 2019. ISBN 978-0-12-811905-1.

- Zotero: `7KNR6VY7`, PDF anexo consultado. Página PDF 7 confirma a sexta edição; PDF 8 confirma copyright 2019 e ISBN.
- §1.8, páginas PDF 71–79 / impressas 39–47: p. 39 distingue tempo de resposta e throughput; p. 40–41 trata kernels/toy/synthetic e limites de generalização; p. 45 trata reprodutibilidade de configurações/flags; p. 45–47 trata razões normalizadas.
- Limite: esse trecho não fornece método estatístico de equivalência nem prova de WCET. Paginação PDF e impressa não devem ser confundidas.

## 3. Manuais primários com trechos verificados

### ST PM0056 — exceções, prioridades e alinhamento

**STMicroelectronics.** *STM32F10xxx/20xxx/21xxx/L1xxxx Cortex-M3 programming manual*. PM0056, revisão 7, 2024.

- Zotero `IZMAAGNW`, citekey `zotero-item-1173`; anexo consultado, paginação conferida.
- [PDF oficial](https://www.st.com/resource/en/programming_manual/pm0056-stm32f10xxx20xxx21xxxl1xxxx-cortexm3-programming-manual-stmicroelectronics.pdf).
- §2.3.5–6, p. 35–36: prioridades. §2.3.6, p. 36: grupo determina preempção; mesmo grupo não produz nesting; subprioridade ordena exceções pendentes.
- §2.3.7, p. 37–38: nesting, tail-chaining e late arrival são mecanismos distintos.
- §3.3.5, p. 55: desalinhamento pode tornar acessos mais lentos e só é suportado por determinadas instruções. Sustenta cautela com trace packed; não mede o custo do logger proposto.

### ST RM0008 — clocks, TIM e USART

**STMicroelectronics.** *STM32F101xx, STM32F102xx, STM32F103xx, STM32F105xx and STM32F107xx advanced Arm-based 32-bit MCUs*. RM0008, revisão 21, 2021.

- Zotero `N7JVRKFW`, citekey `zotero-item-1175`; anexo consultado.
- [PDF oficial](https://www.st.com/resource/en/reference_manual/rm0008-stm32f101xx-stm32f102xx-stm32f103xx-stm32f105xx-and-stm32f107xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).
- §7.2.2, p. 95: HSI RC de 8 MHz, ajuste de fábrica a 1% **a 25 °C**, não garantia universal de ±1%.
- §15.3.1, p. 368: PSC buffered e ARR. §15.3.2, p. 369: contagem ascendente inclusiva de ARR, reinício e UG por software.
- §27.3.3, p. 795–796: RXNE/ORE, retenção do RDR antigo e limpeza por leitura SR→DR.
- §27.3.4–5, p. 798–800: baud/BRR e contribuições ao erro de clock. Formatação de tabelas não suficientemente segura para extrair um limiar numérico; nenhum foi adotado.
- §31.13, p. 1097: capacidades DWT; não determina latência de leitura de CYCCNT.

### ARM — consulta externa de instruções, revisão distinta

- Zotero `7WLXBF6T`: Cortex-M3 TRM **r2p0**, sem anexo. Zotero `62WD5QIU`: ARMv7-M Architecture Reference Manual, sem anexo. Não alegar leitura desses itens integrais.
- Consulta externa efetiva: [Cortex-M3 TRM r2p1, instruction-set summary / processor instructions](https://developer.arm.com/documentation/100165/0201/Programmers-Model/Instruction-set-summary/Processor-instructions).
- O trecho consultado indica LDR de dois ciclos sob hipóteses explicitadas, com efeitos de pareamento, dependências e stalls. Não autoriza atribuir um ou dois ciclos universalmente à leitura DWT.
- Limite: revisão externa r2p1 não é o item Zotero r2p0; variante/revisão efetiva do núcleo da bancada não foi verificada por essa leitura.

## 4. Metadados consultados, sem páginas verificadas

Coleção acadêmica Zotero `HNZMPXEC`: 22 itens tiveram metadados consultados read-only, sem mutações. Os itens abaixo não sustentam citações de páginas ou conteúdo não lido:

| Item | Identificação disponível | Limite |
|---|---|---|
| Yiu | `657R226N`, `yiu2013`; *The Definitive Guide to ARM Cortex-M3 and Cortex-M4 Processors*, 3. ed., Newnes, 2013; DOI [10.1016/C2012-0-01372-5](https://doi.org/10.1016/C2012-0-01372-5) | Metadados; sem páginas verificadas |
| Buttazzo | `7DX9F2DR`, `buttazzo2011`; *Hard Real-Time Computing Systems*, 3. ed., Springer, 2011; DOI [10.1007/978-1-4614-0676-1](https://doi.org/10.1007/978-1-4614-0676-1) | Metadados; não atribuir método de WCET sem leitura |
| Cebrián | `GFKGIAW3`, `cebrian2020`; “Semi-automatic validation of cycle-accurate simulation infrastructures: A case for gem5-x86”, *Future Generation Computer Systems*, v. 112, p. 832–847, 2020; DOI [10.1016/j.future.2019.07.032](https://doi.org/10.1016/j.future.2019.07.032) | Metadados; texto não verificado |
| Jane W. S. Liu | `EMNF4L8A`; *Real-Time Systems*, 2000 | Outline indisponível; nenhuma citação textual |

Fontes explicativas, não substitutos acadêmicos: Yiu `9AEDRTIS`/`yiu2016` (blog ARM sobre latência); Coleman `3WP5QUNW`/`coleman2019` (Memfault/NVIC); Baldassari `U9SPGK35`/`baldassari2020` (Memfault/profiling). Neste registro não se atribuem páginas verificadas a esses itens.

## 5. Rastreabilidade e pendências

Nenhum resultado de bancada, margem de equivalência ou aprovação de gate decorre deste ledger. Permanecem para a sessão principal a validação documental final, eventual importação bibliográfica autorizada, confirmação de links e implementação/ensaios. Ausência do plano histórico no diretório autorizado limita o contexto; não prova exclusão nem causa. A revisão deve manter a distinção entre texto efetivamente consultado, metadados, proposta metodológica e evidência experimental ainda inexistente para os contratos novos.
