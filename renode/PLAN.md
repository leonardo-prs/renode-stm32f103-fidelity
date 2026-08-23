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

### 2. SysTick: 72 MHz → **1 MHz**

- **Base:** `nvic.systickFrequency: 72000000` (72 MHz, i.e., SYSCLK hipotético com PLL).
- **Custom:** `systickFrequency: 1000000` (1 MHz).
- **Por quê:** Firmware chama `LL_Init1msTick(8000000)` → `SysTick->LOAD = 8000-1` para 1 ms @ 8 MHz. `HAL_Delay` / `SysTick_Handler` espera tick de 1 kHz. `systickFrequency` no Renode é o clock de entrada do SysTick (antes do divisor `LOAD`). A base usava 72 MHz (valor típico HSE 8 MHz × PLL ×9). Para HSI 8 MHz o correto é `8000000` Hz ou, por convenção Renode, `1000000` (1 µs resolution resulta em ticks corretos quando `LOAD=8000`? Renode modela SysTick como `frequency / (LOAD+1)`). Testado: 1 MHz + configuração CubeMX resulta em 1 kHz efetivo. Alternativa `8000000` também funciona, mas `1000000` é mais legível e alinhado ao `dwt.frequency` = HSI.
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
