# renode/PLAN.md — STM32F103 HSI 8 MHz: diffs vs base Renode 1.16.1

> Base: `platforms/cpus/stm32f103.repl` do pacote `renode-1.16.1` (`/nix/store/.../lib/renode/platforms/cpus/stm32f103.repl`).
> Customização: `renode/stm32f103_hsi8.repl` — plataforma dedicada ao Blue Pill STM32F103C8T6 em HSI 8 MHz puro (sem HSE/PLL).
> Data: 2026-08-19. Autor: fix do TCC EA019.

## Objetivo

Reproduzir fielmente o **reset state** do STM32F103C8T6 (RM0008 §7): HSI RC em 8 MHz, sem cristal externo, sem PLL. Isso elimina variáveis de hardware (cristal HSE, wait-states de flash em >24 MHz) que Renode não modela e caracteriza o drift de ±1% do HSI como métrica, não bug (ver AGENTS.md).

## Diffs (base → `stm32f103_hsi8.repl`)

### 1. Clock dos 14 timers: 10 MHz → **8 MHz**

- **Base:** `frequency: 10000000` em todos os `timer1..timer14`.
- **Custom:** `frequency: 8000000`.
- **Por quê:** No hardware real, `SystemClock_Config()` mantém `SYSCLK = HSI = 8 MHz`, `APB1/APB2 prescaler = /1`, logo `TIMxCLK = 8 MHz` (RM0008 §8, CubeMX `RCC_TIMCLK = 8 MHz`). A base usava 10 MHz arbitrário (exemplo Renode para APB).
- **Impacto:** Cenário A (TIM2 PSC=799 ARR=999 → 100 ms) depende disso. Erro de 20% se mantiver 10 MHz.

### 2. SysTick: 72 MHz → **8 MHz** (corrigido 2026-09-22; era 1 MHz)

- **Base:** `nvic.systickFrequency: 72000000` (72 MHz, i.e., SYSCLK hipotético com PLL).
- **Custom:** `systickFrequency: 8000000` (clock de entrada do SysTick = HSI).
- **Por quê:** Firmware chama `LL_Init1msTick(8000000)` → `SysTick->LOAD = 8000-1` para 1 ms @ 8 MHz: `(LOAD+1)/freq = 8000/8MHz = 1ms` por construção. O valor anterior (1 MHz) deixava o tick 8× lento — inócuo na prática (cenários C1–C4 desligam o SysTick; sandbox não o usa), mas a plataforma mentia. Corrigido na auditoria de knobs (ver `tcc/tmp/log.md`).
- **Referência:** `Core/Src/main.c: LL_Init1msTick(8000000);`.

### 3. DWT CYCCNT: inexistente → **8 MHz**

- **Base:** sem `dwt: Miscellaneous.DWT`.
- **Custom:** adicionado:
  ```repl
  dwt: Miscellaneous.DWT @ sysbus 0xE0001000
      frequency: 8000000
  ```
- **Por quê:** Cenário A mede jitter via `DWT->CYCCNT` (ciclo-a-ciclo). Sem DWT, leitura retorna 0 e o timestamping é impossível. `CYCCNT` em Cortex-M3 incrementa a cada ciclo de core; core = HSI = 8 MHz (sem PLL). Frequência explícita permite correlação tempo ↔ ciclos.
- **Validação:** `strncmp` do buffer DWT será feito via `scripts/dump_sram.sh` (GDB `dump binary memory`).

### 4. RCC_CR: `0x0A020083` → **`0x00000083`**

- **Base:** `Tag <0x40021000, 0x40021003> "RCC_CR" 0x0A020083` (bits fictícios PLLS3 etc de outra família).
- **Custom:** `0x00000083`.
- **Por quê:** Reset value real no STM32F103 (RM0008 §7.3.1): `RCC_CR = 0x00000083` → `HSION=1 (bit0)`, `HSIRDY=1 (bit1)`, `HSITRIM=0x10 (bits 3-7 = 10000b)` mas a exibição de 8 bits dá `0x83` (TRIM+READY+ON). A base misturava bits de famílias F4/H7 (PLLON etc). Para fidelidade HSI puro, apenas HSI ON/RDY.
- **Nota:** Em simulação, RCC é apenas `Tag` (debug region) — não é modelado dinamicamente. O valor é para inspeção GDB (`x/1wx 0x40021000`).

### 5. Memórias: tamanho genérico → **64 KB Flash / 20 KB SRAM**

- **Base:**
  ```
  sram: @0x20000000 size 0x10000000 (256 MB)
  flash: @0x00000000 size 0x20000000 (512 MB)
  fsmcBank1: @0x60000000 256 MB
  ```
- **Custom:**
  ```
  flash_alias: @0x00000000 64 KB
  flash: @0x08000000 64 KB
  sram: @0x20000000 20 KB (0x5000)
  fsmcBank1: mantido 256 MB
  ```
- **Por quê:** O C8T6 tem exatamente 64 KB flash (`0x08000000-0x0800FFFF`) e 20 KB SRAM (`0x20000000-0x20004FFF`). O mapeamento gigante da base impede detecção de overflows e estouro de `.ld`. O alias em `0x00000000` persiste (BOOT0=0 → flash aliased) para compatibilidade com vetores em 0.
- **Linker:** `STM32F103XX_FLASH.ld` já usa esses limites — agora coerente.

### 6. `usart1..5` mantidos, sem `frequency` override

- Base não define `frequency` em USART (usa default do modelo). Mantido — USART clock deriva do PCLK2 (8 MHz), divisores são calculados pelo LL. Não afeta sandbox.

### 7. GPIO / AFIO / EXTI / nvic: idêntico à base

- Nenhuma mudança nos IPs — pinagem do Blue Pill (PC13 LED) já compatível.

## Referências

- RM0008 Rev 21 §7 (RCC), §8 (GPIOs), §13 (DBGMCU)
- PM0056 (Cortex-M3 Programming Manual) — DWT CYCCNT
- `Core/Src/main.c` — `SystemClock_Config()` atual
- Renode docs: `platforms/cpus/stm32f103.repl` (tag `DWT`, `systickFrequency`)

## Próximos passos

- [ ] `renode/scenario_a.resc` e `scenario_b.resc` (mesma plataforma, ELFs diferentes)
- [ ] `scripts/flash_stlink.sh` / `dump_sram.sh`
- [ ] smoke test HW vs sim com métricas quantitativas (jitter, drift)

## Cenários C1–C4 (2026-09-22, atualizado após runs)

Infra de simulação para a suíte de fidelidade C1–C4. Mesma plataforma
(`renode/stm32f103_hsi8.repl`, HSI 8 MHz) do sandbox; só o ELF muda.
Estrutura dos `.resc` espelha `renode/sandbox.resc`.

| resc | máquina(s) | ELF | fonte |
|------|---------|-----|-------|
| `renode/c1.resc` | `c1_hsi8` | `@build/c1/firmware.elf` | `src/c1_core.c` |
| `renode/c2.resc` | `c2_hsi8` | `@build/c2/firmware.elf` | `src/c2_irq_baseline.c` (V1 WFI) |
| `renode/c2busy.resc` | `c2busy_hsi8` | `@build/c2busy/firmware.elf` | mesmo, `-DC2_BUSY_LOOP=ON` (V2) |
| `renode/c3.resc` | `c3_hsi8` | `@build/c3/firmware.elf` | `src/c3_irq_arbitration.c` (Q default 1us; sweep E(Q) via resc em /tmp, ver Quantum) |
| `renode/c4.resc` | `c4dut` + `c4peer` + hub `c4hub` | `@build/c4/firmware.elf` + `@build/echo/firmware.elf` | `src/c4_usart.c` + `src/echo_peer.c` |

(Uso: `renode --disable-xwt -e "s @renode/cN.resc"`; builds `build/c1|c2|c2busy|c3|c4|echo`. SCENARIO=ECHO no CMakeLists só p/ o peer.)

### Quantum

Default `emulation SetGlobalQuantum "0.000001"` (1us) em C1/C2/C4 (fixo).
Em **C3 o quantum é variável experimental E(Q)**: perfis via `-e` na chamada
NÃO são confiáveis (produziram buffers bit-idênticos — overrides ignorados);
gerar resc temporário em `/tmp` com a linha in-file (mecanismo comprovado).
Sweep documentado: 1us/10us/100us/1ms (ver relatório + `tcc/tmp/log.md`).

### logLevel

`logLevel 3` em todos (mesmo nível do `sandbox.resc`: 0=silent, 3=debug).
Nota operacional: com stdout redirecionado p/ arquivo, as linhas INFO após
`System bus created` não têm flush — log parado + CPU 100% = emulação
correndo, NÃO travamento. Verificar progresso via GDB (`:3333`) ou monitor
(`:1234`), nunca pelo arquivo de log (lição em `tcc/tmp/log.md`).

### C4 loopback: DECIDIDO — UART hub dual-machine (2026-09-22)

Firmware C4 é loopback-agnóstico (mesmo ELF nos dois mundos). Modelo
STM32_UART sem wire TX→RX; socket/PTY destruiria o timing (RTT wall-clock).
Solução canônica Renode: `emulation CreateUARTHub "c4hub"` + machine-1
`echo_peer` (polling RX→TX, `src/echo_peer.c`, sem GDB) — entrega em
virtual-time com atraso ≤ quantum (8c), caracterizado na análise.
Diferença metodológica vs jumper passivo do HW declarada aqui e no log.
