# S1A — custo por classe de instrução

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 1 | sim | `8efd2454cf97` | uznsmkwqmvyk 3e3e7866c1e6 |
| rn-m8-q1us | 1 | sim | `8efd2454cf97` | uznsmkwqmvyk 3e3e7866c1e6 |

## Verificações funcionais

| verificação | ambiente | resultado |
|---|---|---|
| assinatura dos kernels = oráculo do host | hw | 126/126 |
| assinatura dos kernels = oráculo do host | rn-m8-q1us | 126/126 |

## Custo por iteração (inclinação, trials quentes 1..4 × runs)

*Unidade: HW: ciclos HCLK; Renode: ticks do DWT virtual (8 MHz)*

| kernel | instr/iter | TRM ciclos/iter | hw /iter | hw faixa | rn-m8-q1us /iter | rn-m8-q1us faixa | CPI HW | nota TRM |
|---|---|---|---|---|---|---|---|---|
| loop | 2 | 3 | 3 | 3..3 | 1.99 | 1.98..1.99 | 1.5 | SUBS 1 + B<cond> tomado 1+P (P=1) |
| alu | 18 | 19 | 19 | 19..19 | 18 | 18..18 | 1.06 | ADDS 1 ciclo |
| mul | 18 | 19 | 19 | 19..19 | 17.98 | 17.97..17.99 | 1.06 | MUL 1 ciclo |
| udiv_fast | 18 | — | 51 | 51..51 | 18 | 17.99..18 | 2.83 | UDIV 2–12 ciclos (mínimo quando divisor > dividendo) |
| udiv_slow | 18 | — | 195 | 195..195 | 18 | 17.99..18 | 10.83 | UDIV 2–12 ciclos (quociente grande → perto do máximo) |
| ldr | 18 | 20 | 20 | 20..20 | 17.98 | 17.98..18 | 1.11 | LDR 2; LDRs seguidas pipelinam (N+1) |
| ldr_dep | 18 | 35 | 35 | 35..35 | 18.01 | 17.99..18.02 | 1.94 | LDR 2; destino usado no endereço seguinte → sem pipelining |
| str | 18 | 19 | 19 | 19..19 | 17.99 | 17.98..18 | 1.06 | STR Rx,[Ry,#imm] sempre 1 ciclo |
| ldr_flash | 18 | — | 26 | 26..26 | 17.99 | 17.98..17.99 | 1.44 | LDR de flash: 2 + possível contenção com o fetch |
| branch | 18 | 35 | 35 | 35..35 | 18 | 17.98..18 | 1.94 | B tomado com imediato = 2 ciclos |
| ldm | 18 | 83 | 83 | 83..83 | 18.01 | 17.99..18.02 | 4.61 | LDM 1+N (N=4) |
| mix | 18 | — | 22 | 22..22 | 18 | 17.99..18 | 1.22 | mix (calibração): soma nominal 23, pipelining LDR→STR pode tirar 1 |
| alu_ram | 18 | — | 20 | 20..20 | 17.99 | 17.99..18 | 1.11 | ALU executando da SRAM (barramento System) |
| ldr_ram | 18 | — | 29 | 29..29 | 18 | 17.98..18 | 1.61 | LDR com código na SRAM (contenção no barramento System) |

## Primeira execução após reset (COLD − WARM, mesma N)

*Unidade: ciclos/ticks*

| kernel | hw excesso 1ª exec. | rn-m8-q1us excesso 1ª exec. |
|---|---|---|
| loop | 224..224 | 2..2 |
| alu | 221..221 | 1..1 |
| mul | 337..337 | -2..-2 |
| udiv_fast | 325..325 | -5..-5 |
| udiv_slow | 387..387 | 0..0 |
| ldr | 221..221 | -3..-3 |
| ldr_dep | 216..216 | 0..0 |
| str | 222..222 | -5..-5 |
| ldr_flash | 223..223 | -1..-1 |
| branch | 224..224 | 1..1 |
| ldm | 313..313 | -3..-3 |
| mix | 111..111 | 0..0 |
| alu_ram | 1..1 | -2..-2 |
| ldr_ram | 1..1 | 1..1 |

## Derivados

```json
{
  "calibration": {
    "kernel": "mix (s1k_mix, congelado)",
    "hw_cycles_per_iter": 22.0,
    "instr_per_iter": 18,
    "cpi": 1.2222222222222223,
    "mips_exact": 6.545454545454545,
    "mips_integer": 7,
    "rule": "MIPS_cal = 8 MHz / CPI_mix; Renode só aceita inteiro"
  }
}
```

## Notas

- Renode 1.17: tempo = instruções ÷ PerformanceInMips (BaseCPU); com 8 MIPS e DWT a 8 MHz, 1 instrução = 1 tick em qualquer classe.
