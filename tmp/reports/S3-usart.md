# S3 — USART1 em loopback (firmwares s3a, s3b)

*Relatório intermediário. Metodologia comum: `00-metodologia.md`. Dados:
`data/fidelity/v1/{s3a,s3b}/`, análise `data/fidelity/v1/analysis/s3{a,b}.md`.*

## 1. Pergunta

Com a USART1 a 115200 8N1 (BRR = 0x45, USARTDIV 4,3125 a 8 MHz) e o fio
PA9 → PA10, o Renode reproduz (a) a **integridade** e a **semântica das
flags** (TXE, TC, RXNE, IDLE, ORE) e (b) o **tempo de quadro**?

## 2. Fundamentação

- RM0008 §27.3.4, p. 798: baud = f_CK / (16 × USARTDIV) → 1 quadro 8N1 =
  10 × 69 = **690 ciclos** de HCLK.
- RM0008 §27.3.2, pp. 792–793: escrever DR limpa TXE; "when no transmission
  is taking place, a write … places the data directly in the shift register
  … and the TXE bit is immediately set"; TE ligado envia um quadro ocioso.
- RM0008 §27.6.1, p. 818: TC "set by hardware if the transmission of a frame
  containing data is complete"; p. 819: ORE "set … when the word currently
  being received in the shift register is ready to be transferred into the
  RDR register while RXNE=1".
- RM0008 §27.3.3, pp. 795–796: "An overrun error occurs when a character is
  received when RXNE has not been reset … The shift register will be
  overwritten" (o RDR antigo é preservado).
- PM0056 §4.3.9, p. 126: IRQ sensível a nível que continua ativa no retorno
  da ISR "becomes pending again, and the processor must execute its ISR again".
- Renode 1.17, `STM32_UART.cs`/`UARTHub.cs` (fonte fixada): TXE sempre 1;
  TC imediato; ORE nunca; RX numa **fila ilimitada**; atraso por caractere
  só com `AutoUpdateDelay`; o hub entrega após `CharacterTransmissionDelay`
  (`tmp/research/renode-periph-models.md`).

## 3. Desenho

**s3a** (funcional, 2 trials, ver `src/s3/link.c`): ping-pong 32 B;
full-duplex 64 B (escreve sempre que TXE, lê sempre que RXNE; mede o
**adiantamento máximo do TX** = bytes escritos − lidos); overrun (4 bytes
sem ler DR; SR observado por 8 quadros sem leitura do DR — cada mudança vai
para o trace); recepção por IRQ (RXNEIE) com contagem de bytes **presos**
depois; transmissão por IRQ (TXEIE); IDLE; TC; TE desligado (o dado escrito
sai?).

**s3b** (temporal): byte isolado × 31 (instante de TXE, TC, RXNE, IDLE
relativos à escrita no DR, por *polling* do SR com DWT); 4 rajadas de 16
bytes (intervalo entre RXNE); 8 bytes até TC final.

Renode: UARTHub com loopback no usart1 (sem peer ativo); configurações com e
sem `AutoUpdateDelay`.

## 4. Resultados

### 4.1 Funcional (s3a, trial 2)

| teste | RM0008 (STM32F103) | placa (HW) | Renode | leitura |
|---|---|---|---|---|
| ping-pong 32 B | 32/32 | 32/32 | 32/32 | = |
| full-duplex 64 B | 64/64 | 64/64 | 64/64 | = |
| TX adiantado máx. | ≤ 2 (+1 em trânsito) | **3** | **63** | modelo: TXE sempre 1 |
| overrun: ORE | 1 | **0** | 0 | placa ≠ manual; Renode = placa |
| overrun: bytes após ler DR | 0 | **3 (em ordem)** | 3 | placa bufferiza ≥4 B |
| RXNE por IRQ: recebidos | 32 | 32 | **3** | **modelo: 29 bytes presos na fila** |
| TXE por IRQ | 32 | 32 | 32 | = |
| IDLE e limpeza SR→DR | sim | sim | sim | = |
| TC logo após escrever DR | 0 | 0 | **1** | modelo: TC imediato |
| TE = 0: dado transmitido? | não | não | **sim** | modelo ignora TE com UE=1 |

O defeito mais sério é **funcional**: com recepção por interrupção o Renode
entrega 3 de 32 bytes e deixa 29 na fila. A linha de IRQ do `STM32_UART`
fica alta enquanto há dados; depois da 1ª ISR o NVIC do Renode não volta a
pender (pende na borda), ao contrário do NVIC real, para o qual uma IRQ de
nível ainda ativa no retorno "becomes pending again" (PM0056 p. 126). Um
firmware correto de recepção por IRQ **perde dados** na simulação.

O overrun mostra que a placa não segue o RM0008: nenhum ORE e 4 bytes
recuperados — comportamento de FIFO de recepção, atribuído a um clone (ver
metodologia §5). Nesse teste o Renode *coincide com a placa* e *diverge do
manual*; o relatório não chama isso de fidelidade.

### 4.2 Temporal (s3b)

| métrica (ciclos/ticks após escrever DR) | teórico | HW | Renode (AutoUpdateDelay on) | Renode (off) |
|---|---|---|---|---|
| TXE de volta | ≤ 1 bit (69) | 66 | 0 | 0 |
| TC | 690 | 743 | 0 | 0 |
| RXNE | ≈ 690 | 768 | **1390 (2 quadros)** | **704** |
| IDLE | ≈ 1380 | 1405 | 2080 | 1398 |
| intervalo RXNE em rajada | 690 | 685 (673..714) | 690 | 694 |
| TC final de 8 bytes | 5520 | 5585 | **78** | **78** |

(HW inclui a granularidade do laço de polling, ~10–30 ciclos.)

- A **entrega** de bytes ao receptor é bem modelada **sem** `AutoUpdateDelay`:
  704 × 768 por byte e ≈ 690 por quadro em rajada. Com `AutoUpdateDelay` o
  atraso é aplicado duas vezes (hub + ritmo do receptor): 2 quadros.
  A configuração da sessão anterior (`AutoUpdateDelay true`) era a errada.
- O **lado do transmissor** não tem tempo: TXE e TC instantâneos → um laço
  "espera TC" termina 70× mais cedo (78 × 5585); o adiantamento do TX é 63 ×
  3.

## 5. Interpretação

1. Integridade de dados em fluxos simples (polling, ritmo do TX): **fiel**.
2. Semântica de flags do transmissor (TXE/TC/TE): **não fiel** — afeta
   qualquer firmware que use TC (ex.: desligar RS-485 DE) ou TXE para
   controle de fluxo.
3. Recepção por IRQ: **defeito funcional** do par UART/NVIC do Renode.
4. Tempo de recepção: **fiel em média** sem `AutoUpdateDelay` (erro ~8 %
   num byte isolado, < 1 % por quadro em rajada); com ele, 2×.
5. Overrun: impossível no Renode (fila ilimitada); na placa também não
   ocorre — a referência física aqui é atípica.

## 6. Limitações

- A placa diverge do RM0008 na recepção (clone provável); os itens de
  overrun não podem ser atribuídos ao "STM32F103".
- TE = 0 no HW produz às vezes um quadro espúrio (0x00) — o teste verifica se
  o *dado escrito* saiu, não se "algo chegou".
- Medição por polling: resolução de uma volta de laço (≈ 10–30 ciclos no HW).
- s3a no HW não é bit a bit idêntico entre runs: o bit LBD (8) do SR e o
  quadro espúrio do teste TE = 0 variam — o desligamento do transmissor deixa
  a linha baixa o bastante para ser lida como *break*. Os contadores de dados
  (recebidos, divergências, adiantamento) são estáveis em todos os runs.
