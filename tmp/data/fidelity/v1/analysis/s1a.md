# S1A — custo por classe de instrução

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 10 | sim | `a3e0c657b0ab` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q1us | 3 | sim | `a3e0c657b0ab` | upkzpxpvszmy 5c51a3cc973a |
| hw-free | 3 | sim | `a3e0c657b0ab` | upkzpxpvszmy 5c51a3cc973a |
| rn-m100-q1us | 2 | sim | `a3e0c657b0ab` | upkzpxpvszmy 5c51a3cc973a |
| rn-m7-q1us | 2 | sim | `a3e0c657b0ab` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q125ns | 2 | sim | `a3e0c657b0ab` | upkzpxpvszmy 5c51a3cc973a |

## Verificações funcionais

| verificação | ambiente | resultado |
|---|---|---|
| assinatura dos kernels = oráculo do host | hw | 1260/1260 |
| assinatura dos kernels = oráculo do host | rn-m8-q1us | 378/378 |
| assinatura dos kernels = oráculo do host | hw-free | 378/378 |
| assinatura dos kernels = oráculo do host | rn-m100-q1us | 252/252 |
| assinatura dos kernels = oráculo do host | rn-m7-q1us | 252/252 |
| assinatura dos kernels = oráculo do host | rn-m8-q125ns | 252/252 |

## Custo por iteração (inclinação, trials quentes 1..4 × runs)

*Unidade: HW: ciclos HCLK; Renode: ticks do DWT virtual (8 MHz)*

| kernel | instr/iter | TRM ciclos/iter | hw /iter | hw faixa | rn-m8-q1us /iter | rn-m8-q1us faixa | hw-free /iter | hw-free faixa | rn-m100-q1us /iter | rn-m100-q1us faixa | rn-m7-q1us /iter | rn-m7-q1us faixa | rn-m8-q125ns /iter | rn-m8-q125ns faixa | CPI HW | nota TRM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| loop | 2 | 3 | 3 | 3..3 | 1.99 | 1.99..2.02 | 3 | 3..3 | 0.16 | 0.16..0.16 | 2.28 | 2.25..2.28 | 2 | 2..2 | 1.5 | SUBS 1 + B<cond> tomado 1+P (P=1) |
| alu | 18 | 19 | 19 | 19..19 | 18 | 18..18 | 19 | 19..19 | 1.44 | 1.44..1.45 | 20.56 | 20.56..20.56 | 18 | 18..18 | 1.06 | ADDS 1 ciclo |
| mul | 18 | 19 | 19 | 19..19 | 18 | 18..18 | 19 | 19..19 | 1.44 | 1.44..1.44 | 20.56 | 20.56..20.59 | 18 | 18..18 | 1.06 | MUL 1 ciclo |
| udiv_fast | 18 | — | 51 | 51..51 | 18 | 18..18 | 51 | 51..51 | 1.44 | 1.44..1.44 | 20.56 | 20.56..20.59 | 18 | 18..18 | 2.83 | UDIV 2–12 ciclos (mínimo quando divisor > dividendo) |
| udiv_slow | 18 | — | 195 | 195..195 | 18 | 18..18 | 195 | 195..195 | 1.44 | 1.44..1.44 | 20.58 | 20.56..20.59 | 18 | 18..18 | 10.83 | UDIV 2–12 ciclos (quociente grande → perto do máximo) |
| ldr | 18 | 20 | 20 | 20..20 | 17.99 | 17.99..17.99 | 20 | 20..20 | 1.44 | 1.44..1.44 | 20.56 | 20.56..20.59 | 18 | 18..18 | 1.11 | LDR 2; LDRs seguidas pipelinam (N+1) |
| ldr_dep | 18 | 35 | 35 | 35..35 | 17.99 | 17.99..18.01 | 35 | 35..35 | 1.44 | 1.44..1.44 | 20.56 | 20.56..20.56 | 18 | 18..18 | 1.94 | LDR 2; destino usado no endereço seguinte → sem pipelining |
| str | 18 | 19 | 19 | 19..19 | 17.99 | 17.99..18.02 | 19 | 19..19 | 1.44 | 1.44..1.44 | 20.56 | 20.56..20.56 | 18 | 18..18 | 1.06 | STR Rx,[Ry,#imm] sempre 1 ciclo |
| ldr_flash | 18 | — | 26 | 26..26 | 17.99 | 17.99..18.02 | 26 | 26..26 | 1.44 | 1.43..1.44 | 20.56 | 20.56..20.56 | 18 | 18..18 | 1.44 | LDR de flash: 2 + possível contenção com o fetch |
| branch | 18 | 35 | 35 | 35..35 | 17.99 | 17.99..18 | 35 | 35..35 | 1.44 | 1.43..1.44 | 20.56 | 20.56..20.56 | 18 | 18..18 | 1.94 | B tomado com imediato = 2 ciclos |
| ldm | 18 | 83 | 83 | 83..83 | 17.99 | 17.99..17.99 | 83 | 83..83 | 1.44 | 1.44..1.45 | 20.56 | 20.56..20.56 | 18 | 18..18 | 4.61 | LDM 1+N (N=4) |
| mix | 18 | — | 22 | 22..22 | 18 | 18..18 | 22 | 22..22 | 1.44 | 1.44..1.44 | 20.58 | 20.56..20.59 | 18 | 18..18 | 1.22 | mix (calibração): soma nominal 23, pipelining LDR→STR pode tirar 1 |
| alu_ram | 18 | — | 20 | 20..20 | 18 | 18..18 | 20 | 20..20 | 1.44 | 1.44..1.44 | 20.58 | 20.56..20.59 | 18 | 18..18 | 1.11 | ALU executando da SRAM (barramento System) |
| ldr_ram | 18 | — | 29 | 29..29 | 18.01 | 18..18.02 | 29 | 29..29 | 1.44 | 1.43..1.44 | 20.56 | 20.56..20.59 | 18 | 18..18 | 1.61 | LDR com código na SRAM (contenção no barramento System) |

## Primeira execução após reset (COLD − WARM, mesma N)

*Unidade: ciclos/ticks*

| kernel | hw excesso 1ª exec. | rn-m8-q1us excesso 1ª exec. | hw-free excesso 1ª exec. | rn-m100-q1us excesso 1ª exec. | rn-m7-q1us excesso 1ª exec. | rn-m8-q125ns excesso 1ª exec. |
|---|---|---|---|---|---|---|
| loop | 217..217 | 6..6 | 217..217 | 0..0 | 0..0 | 0..0 |
| alu | 223..223 | 0..0 | 223..223 | 0..0 | 0..0 | 0..0 |
| mul | 220..220 | 1..1 | 220..220 | 0..0 | 0..0 | 0..0 |
| udiv_fast | 440..440 | 5..5 | 440..440 | -1..-1 | 0..0 | 0..0 |
| udiv_slow | 270..270 | -2..-2 | 270..270 | 0..0 | 0..0 | 0..0 |
| ldr | 328..328 | -3..-3 | 328..328 | 0..0 | 0..0 | 0..0 |
| ldr_dep | 210..210 | 4..4 | 210..210 | 0..0 | 0..0 | 0..0 |
| str | 215..215 | 3..3 | 215..215 | 0..0 | 0..0 | 0..0 |
| ldr_flash | 219..219 | 2..2 | 219..219 | -1..-1 | 0..0 | 0..0 |
| branch | 217..217 | -4..-4 | 217..217 | -1..-1 | 0..0 | 0..0 |
| ldm | 306..306 | 0..0 | 306..306 | 2..2 | -8..-8 | 0..0 |
| mix | 110..110 | -1..-1 | 110..110 | 0..0 | 0..0 | 0..0 |
| alu_ram | 0..0 | 3..3 | 0..0 | -1..-1 | 0..0 | 0..0 |
| ldr_ram | 0..0 | 2..2 | 0..0 | -1..-1 | 8..8 | 0..0 |

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
