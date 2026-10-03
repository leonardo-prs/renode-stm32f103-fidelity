# Migração: CubeMX regenerável → `vendor/` congelado + `main()` por cenário

> Status: **proposta** (não executada). Criado em 2026-10-03.

## 1. Objetivo

Parar de usar o `.ioc` como fonte de verdade da estrutura do projeto. Os
arquivos da ST (CMSIS, LL, startup, linker) ficam **congelados** em `vendor/`.
Cada cenário passa a ser um executável independente, com seu próprio `main()`,
e inicializa **somente** os periféricos de que precisa, via LL.

## 2. Estrutura alvo

```
vendor/                          # congelado, NUNCA editado (origem documentada em vendor/README.md)
  cmsis/                         # core_cm3.h, cmsis_*.h, stm32f1xx.h, stm32f103xb.h, system_stm32f1xx.h
  stm32f1xx_ll/
    inc/                         # stm32f1xx_ll_{bus,cortex,dma,exti,gpio,pwr,rcc,system,tim,usart,utils}.h
    src/                         # stm32f1xx_ll_{dma,exti,gpio,pwr,rcc,tim,usart,utils}.c
  startup_stm32f103xb.s
  STM32F103XX_FLASH.ld
  system_stm32f1xx.c
  stm32_assert.h
  README.md                      # versão STM32CubeF1, versão CubeMX, sha256 de cada arquivo
lib/
  board.c / board.h              # init comum mínimo: AFIO/PWR clock, SWD-only (NOJTAG), NVIC grouping
  clock_hsi8.c / .h              # SystemClock_Config() HSI 8 MHz, sem PLL (extraído do main.c atual)
  dwt.c / dwt.h                  # (sob demanda) CYCCNT enable/read
  syscalls.c, sysmem.c           # movidos de Core/Src (se ainda necessários)
src/
  sandbox.c                      # int main(void): board_init + clock + GPIO PC13
  c1_core.c                      # int main(void)
  c2_irq_baseline.c              # int main(void): + TIM2
  c3_irq_arbitration.c           # int main(void): + TIM2 + TIM3
  c4_usart.c                     # int main(void): + USART1
  echo_peer.c                    # int main(void): + USART1
CMakeLists.txt                   # 1 alvo executável por cenário, todos no mesmo build dir
```

## 3. Plano passo a passo

### Fase 0: Preparação (~15 min)
- [ ] Commit limpo do estado atual (o `CMakePresets.json` está modificado e não commitado).
- [ ] Tag `pre-migration` para poder voltar.
- [ ] Gravar os ELFs atuais de cada cenário com `sha256sum` e `arm-none-eabi-size`, como referência.

### Fase 1: Criar `vendor/` (~30 min)
- [ ] `git mv` de `Drivers/CMSIS` (só os headers do CM3 e do F1) → `vendor/cmsis/`.
- [ ] `git mv` dos `stm32f1xx_ll_*` → `vendor/stm32f1xx_ll/{inc,src}`.
- [ ] `git mv` de `startup_stm32f103xb.s`, `STM32F103XX_FLASH.ld`, `Core/Src/system_stm32f1xx.c` e `Core/Inc/stm32_assert.h` → `vendor/`.
- [ ] Escrever `vendor/README.md` com origem, versões e hashes.
- [ ] Remover o que sobrar de HAL e os templates CMSIS não usados (outros cores, DSP, etc.).

### Fase 2: Criar `lib/` (~45 min)
- [ ] Extrair de `Core/Src/main.c` → `lib/board.c`: clock AFIO/PWR, `NVIC_SetPriorityGrouping(4)`, prioridade do SysTick, `LL_GPIO_AF_Remap_SWJ_NOJTAG()`.
- [ ] Extrair `SystemClock_Config()` → `lib/clock_hsi8.c`.
- [ ] Mover `syscalls.c`/`sysmem.c` → `lib/` (ou remover se `--specs=nano.specs`/`nosys` bastar).
- [ ] Usar `MX_TIM2_Init`, `MX_TIM3_Init`, `MX_USART1_UART_Init` e `MX_GPIO_Init` (em `Core/Src/{tim,usart,gpio}.c`) **como referência** para as funções de init de cada cenário. Não manter os arquivos.

### Fase 3: Converter cenários (~1,5–2 h)
- [ ] Cada `src/*.c`: `xxx_main(void)` vira `int main(void)` e chama `board_init()`, `clock_hsi8_init()` e o init dos **seus** periféricos.
- [ ] Remover a lógica de "quarentena" de periféricos no início de cada `cX_main()` (deixa de ser necessária, ver D2).
- [ ] Handlers de IRQ continuam no `.c` de cada cenário. Fault handlers default vêm do startup (weak) ou de `lib/faults.c`.

### Fase 4: Novo `CMakeLists.txt` (~1 h)
- [ ] Biblioteca `OBJECT`/`STATIC` `vendor_ll` (LL + system + startup) com `-w` ou warnings relaxados.
- [ ] Biblioteca `board` (`lib/`) com os warnings estritos do projeto.
- [ ] Função `add_scenario(name src)` → `firmware_<name>.elf`, mais `.bin`/`.hex`/`.map` e `size`.
- [ ] Remover a variável `SCENARIO` e o `CMakePresets.json` por cenário. Ficam só os presets `Debug` e `Release`.
- [ ] Manter `cmake/gcc-arm-none-eabi.cmake` (renomear para `cmake/toolchain-arm.cmake`, que agora é nosso). Remover `arm-toolchain.cmake` da raiz se for duplicado.
- [ ] Manter a geração do `.clangd`.

### Fase 5: Limpeza (~15 min)
- [ ] Remover `Core/`, `Drivers/`, `cmake/stm32cubemx/`, `.mxproject`.
- [ ] `.ioc`: mover para `vendor/reference/` como **documentação histórica** (pinout), ou remover.
- [ ] Remover `stm32cubemx` do `flake.nix` (ou movê-lo para um shell opcional `.#cubemx`).
- [ ] Atualizar `AGENTS.md`, `README.md` e os `.resc` (caminhos dos ELFs).

### Fase 6: Validação (~1 h, com hardware)
- [ ] `cmake --preset Debug && cmake --build build/Debug` gera todos os ELFs sem warnings no nosso código.
- [ ] Comparar `size` com a referência da Fase 0: tamanho igual ou menor (sem inits ociosos).
- [ ] Sandbox: LED pisca no HW e no Renode.
- [ ] C2/C3: o período do TIM medido via DWT bate com o da referência.
- [ ] C4/echo: a USART transmite o padrão esperado.
- [ ] Build duplo limpo gera ELFs com `sha256` idêntico (build determinístico).

**Estimativa total: ~5–6 h.** A estimativa inicial (3–4 h) supunha que os
cenários A/B ainda fossem placeholders. Já existem 6 cenários implementados
(ver D1).

## 4. Justificativas

### J1. Um `.ioc` = uma configuração de hardware, mas o projeto tem várias
Os cenários têm necessidades disjuntas (GPIO, TIM2, TIM2+TIM3, USART1). Com um
único `.ioc`, **todos** os periféricos são inicializados em **todos** os
cenários antes do dispatch (ver D2). Para um trabalho que mede fidelidade
temporal, periféricos e IRQs ativos que não pertencem ao experimento são uma
variável de confusão. Mantê-los sob controle com "quarentena" depende de
disciplina, não de estrutura.

### J2. O valor do CubeMX é baixo com a política "HAL proibido"
O ponto forte do CubeMX é gerar `MX_*_Init()` e integração HAL. Com LL puro, o
init de periféricos são poucas linhas de registradores/LL, que ficam mais
legíveis e citáveis dentro do próprio cenário.

### J3. Rastreabilidade para publicação
"TIM2 configurado em `src/c2_irq_baseline.c` L40–55, PSC=799, ARR=999" é
auditável por um revisor. Código gerado espalhado entre `Core/`, blocos
`USER CODE` e o dispatch por `#ifdef` não é.

### J4. Reprodutibilidade
A saída do CubeMX depende da versão do CubeMX e do pacote STM32CubeF1, ambos
proprietários e fora do controle do `flake.lock`. Arquivos congelados no git,
com hashes em `vendor/README.md`, não dependem de nenhuma ferramenta externa
para serem reconstruídos. Também tira o `stm32cubemx` (unfree, GUI, pesado) do
caminho crítico do Nix.

### J5. Não reescrever o que a ST já fornece
Startup, linker script e headers de registradores ficam como estão. São a
referência do fabricante, reescrevê-los não acrescenta nada científico e só
introduz risco.

### J6. Um build, todos os ELFs
Hoje cada cenário exige um diretório de configure (preset por cenário). Com um
alvo por cenário, um único `cmake --build` gera tudo. Isso simplifica scripts,
CI e a coleta automatizada de dados.

### J7. Momento
Migrar antes da coleta de dados definitiva evita refazer medições por mudança
de estrutura.

## 5. Descobertas (estado real do repo em 2026-10-03)

- **D1. Há mais cenários do que o `AGENTS.md` descreve.** O `src/` contém
  `sandbox`, `c1_core`, `c2_irq_baseline`, `c3_irq_arbitration`, `c4_usart`
  e `echo_peer`. Não existem `scenario_a.c`/`scenario_b.c`. O `main.c` ainda
  declara `scenario_a_main`/`scenario_b_main` (resíduo). O `AGENTS.md` está
  desatualizado.
- **D2. Contaminação de periféricos confirmada.** `Core/Src/main.c` chama
  `MX_GPIO_Init()`, `MX_TIM2_Init()`, `MX_USART1_UART_Init()` e
  `MX_TIM3_Init()` **antes** do dispatch, para todos os cenários. O comentário
  no `main.c` menciona que cada `cX_main()` "quarentena" os periféricos, ou
  seja, a contaminação já é conhecida e está sendo contornada manualmente.
- **D3. O CubeMX já gera LL (não HAL).** `Drivers/STM32F1xx_HAL_Driver/Src` só
  contém `stm32f1xx_ll_*.c` (dma, exti, gpio, pwr, rcc, tim, usart, utils). A
  remoção de HAL é, na prática, só renomear/mover.
- **D4. `tim.c`, `usart.c` e `gpio.c` já existem em `Core/Src`.** Servem de
  referência direta para os inits por cenário.
- **D5. Arquivos soltos na raiz:** `arm-toolchain.cmake` (possível duplicata de
  `cmake/gcc-arm-none-eabi.cmake`), `data/`, `tcc/` e `Core/{Inc,Src}/Backup`.
  Verificar se devem ser versionados ou removidos.
- **D6.** `CMakePresets.json` com modificações não commitadas e presets por
  cenário (`Debug-C1`, `Debug-C2`, …), que ficam obsoletos após a Fase 4.

## 6. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Diferença sutil no init (ordem de clocks, prioridades NVIC) muda o timing | Comparar as medições DWT antes e depois (Fase 6). Extrair o init literalmente do código gerado |
| Perder a capacidade de visualizar o pinout | Guardar o `.ioc` em `vendor/reference/` como documento |
| Quebrar os `.resc` e os perfis de debug | Atualizar os caminhos na Fase 5. Smoke test no Renode na Fase 6 |
| Dados já coletados com a estrutura antiga | Registrar a tag `pre-migration` nos metadados dos dados antigos. Recoletar se necessário |

## 7. Texto sugerido para a monografia

> Os arquivos de suporte do fabricante (CMSIS, drivers Low-Layer, startup e
> linker script) foram obtidos do pacote STM32CubeF1 vX.Y.Z por meio do
> STM32CubeMX 6.17 e mantidos sem modificação no diretório `vendor/` do
> repositório, com seus hashes SHA-256 registrados. Cada cenário experimental
> é um executável independente que inicializa exclusivamente os periféricos
> necessários ao experimento, eliminando interferência de periféricos ociosos.
