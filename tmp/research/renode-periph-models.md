# Renode 1.17.0 — modelos de periféricos STM32F103 (fontes)

Commit fixado: `066a7f13c052215632d469c995c89aea37c573b1` (renode-infrastructure).
Base de URLs: `https://raw.githubusercontent.com/renode/renode-infrastructure/066a7f13c052215632d469c995c89aea37c573b1/<path>`
Árvore (API): `https://api.github.com/repos/renode/renode-infrastructure/git/trees/066a7f13c052215632d469c995c89aea37c573b1?recursive=1` (não truncada).

Arquivos (paths no repo):
- `src/Emulator/Peripherals/Peripherals/Timers/STM32_Timer.cs` (1018 linhas)
- `src/Emulator/Peripherals/Peripherals/UART/STM32_UART.cs` (457 linhas)
- `src/Emulator/Main/Peripherals/UART/UARTHub.cs` (325 linhas)
- `src/Emulator/Main/Peripherals/UART/IDelayableUART.cs` (extensões de delay)
- `src/Emulator/Cores/Arm-M/DWT.cs` (220 linhas)
- `src/Emulator/Main/Peripherals/Timers/LimitTimer.cs` (362 linhas)
- `src/Emulator/Main/Time/BaseClockSource.cs`, `src/Emulator/Main/Time/ClockEntry.cs`
- `src/Emulator/Cores/Arm-M/NVIC.cs` (DEMCR, OnGPIO)

Método: código-fonte lido integralmente nos trechos citados (download raw no commit fixado). Não foi executado nenhum teste. Itens marcados **UNVERIFIED** não foram confirmados no código lido.

Nota de escopo: o código é da lib de infraestrutura. Comportamento que depende do core Renode principal (`Machine`, `HandleTimeDomainEvent`, `ManagedThread`, framework de registradores `WriteZeroToClear`) não foi lido e está marcado como UNVERIFIED.

---

## A. STM32_Timer.cs

Classe: `public class STM32_Timer : LimitTimer, ...` (linha 24). Comentário na linha 22: "This class does not implement advanced-control timers interrupts".

Construção (linhas 26, 38): base `LimitTimer(machine.ClockSource, frequency, limit: initialLimit, direction: Ascending, enabled: false, eventEnabled: true, autoUpdate: false)`; largura do contador inferida de `initialLimit` (`timerCounterLengthInBits = floor(log2(initialLimit))+1`). Na plataforma `renode/stm32f103_hsi8.repl`, TIM1 usa `initialLimit: 0xFFFF` (linha ~96) e os demais timers usam o default do repl; `frequency: 8000000` em todos os timers (linhas 95, 101, ..., 175).

### A1. CNT, resolução, PSC

- **CNT calculado a partir do tempo virtual na leitura: SIM.** Linhas 324-334:
  ```csharp
  valueProviderCallback: _ =>
  {
      if(sysbus.TryGetCurrentCPU(out var cpu))
      {
          cpu.SyncTime();
      }
      return (uint)Value;
  }, name: "Counter value (CNT)")
  ```
  `Value` (LimitTimer.cs:231-235) lê `clockSource.GetClockEntry(OnLimitReached).Value`. O CPU é sincronizado antes da leitura (`SyncTime`).
- **Mecanismo de contagem** (`BaseClockSource.cs`): a entrada de relógio avança por `emulatorTicks * entry.Ratio + entry.ValueResiduum`, com resíduo fracionário preservado entre passos (linhas 280-285 descendente; 307-313 ascendente: `entryTicks = emulatorTicks * entry.Ratio + entry.ValueResiduum; entry.ValueResiduum = entryTicks.Fractional;`). `ClockEntry.cs:28`: `Ratio = FrequencyToRatio(Step * Frequency)`. Ou seja, a taxa de contagem é `frequency / divider` exata em racional; a granularidade observável é limitada pela resolução de `TimeStamp`/`Step` do domínio de tempo (**UNVERIFIED**: `TimeStamp.cs`/`TimeDomain` não lidos).
- **Resolução nominal:** com `frequency: 8000000` (repl) e PSC=0, 1 tick = 125 ns; com PSC=p, 1 tick = (p+1)·125 ns (derivado de `LimitTimer.Divider`, abaixo).
- **PSC aplicado: SIM, mas NÃO bufferizado.** Linhas 348-358:
  ```csharp
  {(long)Registers.Prescaler, new DoubleWordRegister(this)
      .WithValueField(0, 16, writeCallback: (_, val) => Divider = val + 1, valueProviderCallback: _ => (uint)Divider - 1, name: "Prescaler value (PSC)")
      ...
      .WithWriteCallback((_, __) =>
      {
          for(var i = 0; i < NumberOfCCChannels; ++i)
          {
              channels[i].Timer.Divider = Divider;
          }
          UpdateInterrupts();
      })
  ```
  `LimitTimer.Divider` setter (LimitTimer.cs:200-215) troca imediatamente a frequência da entrada de relógio: `effectiveFrequency = Frequency / divider; clockSource.ExchangeClockEntryWith(OnLimitReached, oldEntry => oldEntry.With(frequency: effectiveFrequency));`. **Diferença em relação ao HW:** no STM32 real o PSC é bufferizado e só entra em vigor no próximo evento de update. Aqui não há buffer: a escrita muda a taxa imediatamente. (Também não há reset do contador de prescaler no UG; não modelado.)

### A2. Update interrupt (UIF / UIE), IRQ level vs pulso

- **Quando CNT atinge ARR (LimitReached):** linhas 50-64:
  ```csharp
  LimitReached += delegate
  {
      if(updateDisable.Value) { return; }
      if(Mode == WorkMode.OneShot) { enableRequested = false; }
      Limit = autoReloadValue;
      this.Log(LogLevel.Noisy, "IRQ pending");
      updateInterruptFlag = true;
  ```
  **UIF é setado incondicionalmente** (linha 64), independente de UIE. UIE só é consultado em `UpdateInterrupts` (linha 756).
- Linhas 86-92: se UIE e `repetitionsLeft == 0`, recalcula `repetitionsLeft` e chama `UpdateInterrupts()`. Linhas 94-97 decrementam `repetitionsLeft`.
- **UIF é "sticky"** até software limpar: a flag é `FieldMode.Read | FieldMode.WriteZeroToClear` (linha 235), leitura retorna `updateInterruptFlag` (246), escrita de 0 limpa (238-242: `if(!val) updateInterruptFlag = false;`). Escrita de 0 no SR dispara `UpdateInterrupts()` via `WithWriteCallback` (263). (Semântica exata do `WriteZeroToClear` no framework de registradores: **UNVERIFIED**.)
- **Linha IRQ: NÍVEL, não pulso.** Linhas 748-765:
  ```csharp
  var ccIrq = false;
  for(...) ccIrq |= channels[i].InterruptFlag & channels[i].InterruptEnable;
  var updateIrq = updateInterruptFlag & updateInterruptEnable.Value;
  var triggerIrq = triggerInterruptFlag.Value & triggerInterruptEnable.Value;
  IRQ.Set(ccIrq || updateIrq || triggerIrq);
  BreakInterrupt.Set(false);
  UpdateInterrupt.Set(updateIrq);
  TriggerInterrupt.Set(triggerIrq);
  CommutationInterrupt.Set(false);
  CaptureCompareInterrupt.Set(ccIrq);
  ```
  Ou seja, a linha permanece alta enquanto (UIF & UIE). Se UIE é desabilitado com UIF setado, a linha cai (`updateIrq` = 0) mas UIF permanece; ao reabilitar UIE, a linha sobe novamente (escrita em DIER dispara `UpdateInterrupts`, linha 232). Isto é compatível com o comportamento de nível do HW.
- **Lado NVIC** (`armm/NVIC.cs:145-160`, `OnGPIO`): `value == true` → `irqs[number] |= IRQState.Running; SetPending(number);`; `false` → limpa `Running`. Ou seja, a entrada é tratada como nível com pendência no flanco de subida. Se a linha permanece alta após o retorno do handler, se há re-pendência: **UNVERIFIED** (exigiria ler `NVIC.CompleteIRQ`, linha 434).
- **Quando UIE=0 e UIF setado (sem IRQ):** a flag é mantida, a linha não sobe. Caso especial: a chamada em `LimitReached` só chama `UpdateInterrupts()` se UIE=1 (linha 86); com UIE=0 a linha não é reavaliada naquele ponto, mas o estado de saída permanece baixo, correto.
- **Separação de linhas:** no repl (`stm32f103_hsi8.repl`, TIM2) `IRQ -> nvic@28` e `UpdateInterrupt -> dma1@2`. Para TIM1 (repl ~linha 89-97): `UpdateInterrupt -> nvic@25`, `CaptureCompareInterrupt -> nvic@27`, `TriggerInterrupt -> nvic@26`, `BreakInterrupt -> nvic@24` (linhas separadas). A linha `IRQ` (default) é o OR de todas (linha 759).
- **Caveat RCR:** com TIM1_RCR>0, UIF é setado a cada período (linha 64) mas a IRQ só é reavaliada quando `repetitionsLeft==0` (linhas 86-91). **Não é UIF gated por RCR.**

### A3. Capture/compare

- **Match CCRx**: cada canal tem um `LimitTimer` `cctimer{n}` com `Limit = CCRx` (linhas 104, 396-403: `channels[j].Timer.Limit = val`). O evento de match é o `LimitReached` desse timer (linhas 105-138) — em tempo virtual, não por polling.
- **Flag CCxIF só é setada se CCxIE=1:** linhas 132-136:
  ```csharp
  if(channel.InterruptEnable)
  {
      channel.InterruptFlag = true;
      this.Log(LogLevel.Noisy, "cctimer{0}: Compare IRQ pending", j + 1);
      UpdateInterrupts();
  }
  ```
  **Diferença vs HW:** no STM32 real CCxIF é setado no match independentemente de CCxIE. Aqui, o canal só recebe eventos quando `CCxIE || CCxE` (`UpdateTimer`, linhas 845-853: `Timer.Enabled = parent.Enabled && IsInterruptOrOutputEnabled && parent.Value < Timer.Limit`). Logo, em modo de comparação sem IRQ (CCxIE=0) o CCxIF não é setado.
- **Linhas de IRQ separadas:** `CaptureCompareInterrupt` (linha 582/764) = OR de CCxIF&CCxIE; `UpdateInterrupt` (576/761) = UIF&UIE; `TriggerInterrupt` (578/762); `BreakInterrupt` e `CommutationInterrupt` sempre 0 (760, 763). Para TIM1, o repl separa UpdateInterrupt e CaptureCompareInterrupt em NVICs distintos.
- Input capture (`HandleCapture`, linhas 888-909): `CapturedValue = parent.Value` após `cpu.SyncTime()` (898-902); overcapture (904-907). Leitura do CCR limpa CCxIF (415-418).
- Sinais de entrada TI: `SetInput` (827-843) detecta bordas; `InputPrescalerDivider` (`ICxPSC`) implementado (890-895).

### A4. Slave mode, trigger, OPM, RCR, EGR

- **SMCR:** SMS (bits 0-2) implementado: Reset (`HandleResetMode`, linha 619-620), Gated (622-623), Trigger (625-627), Encoder 1/2/3 (`HandleEncoderMode`, 631-640; ativado em 607-611). **External clock mode 1 (SMS=7) não suportado:** linhas 187-189 apenas logam Warning.
- **TS (Trigger Selection, bits 4-6):** linha 207 `WithEnumField(4, 3, out triggerSelection)`, mas o roteamento só aceita TI1/TI2: `CheckTriggerSelect` (682-684) retorna true só para `TimerInput1`/`TimerInput2`. Os `InternalTrigger0..3` (enum linhas 994-1003) **não são roteados** (sem ITRx entre timers).
- **MMS (TRGO, bits 4-6 de CR2):** linha 174 `.WithTag("Master mode selection (MMS)", 4, 2)` — **não implementado** (TRGO não é emitido).
- **ETR (ETF/ETPS/ECE/ETP, linhas 209-212):** tagged, **não implementado**. ETR (ExternalTrigger=7) não é roteado.
- **OPM (One-pulse, CR1 bit 3):** linha 155 `writeCallback: (_, val) => Mode = val ? WorkMode.OneShot : WorkMode.Periodic`. No overflow: linha 57-60 `enableRequested = false`; a entrada de relógio também desabilita (`BaseClockSource.cs:290` e `:320`: `entry.With(enabled: entry.Enabled & (entry.WorkMode != WorkMode.OneShot))`). CEN lê `enableRequested` (152), que volta a 0 — coerente com HW.
- **RCR (TIM1_RCR, linha 373-376):** `WithValueField(0, 8, out repetitionCounter)`. Usado **somente** para gate de IRQ (linhas 86-90, 94-97). **Não altera o período do contador** (`Limit = autoReloadValue`, linha 62). **Não implementado como repetition counter real.**
- **EGR.UG (linhas 265-295):** suportado (bit 0). Efeitos: CNT=0 (ascendente, linha 274) ou CNT=ARR (descendente, 278); `repetitionsLeft = RCR` (281); **UIF setado só se `!URS && UIE`** (283-287) — **diferença vs HW**: no STM32 o UG seta UIF independentemente de UIE. Também: UG respeita UDIS (268-270). CC1G..CC4G e TG são tagged (296-301) — sem efeito.
- **ARR preload (ARPE = CR1 bit 7, linha 164 "APRE"):** escrita em ARR (360-372): `autoReloadValue = val; Enabled = enableRequested && autoReloadValue > 0; if(!autoReloadPreloadEnable.Value) Limit = autoReloadValue;`. Com APRE=1, o novo ARR só entra em `Limit` no próximo `LimitReached` (linha 62). **Comportamento compatível com o preload do HW.** (Note: `Enabled` é atualizado imediatamente, linha 364.)
- **Sem CCPC/CCUS/CCDS** (tagged, linhas 170-173).

### A5. Reset
Linhas 555-569: `registers.Reset()`, `autoReloadValue = initialLimit`, `Limit = initialLimit`, `repetitionsLeft = 0`, `updateInterruptFlag = false`, `UpdateInterrupts()`.

---

## B. STM32_UART.cs

Classe (linha 21): `public class STM32_UART : BasicDoubleWordPeripheral, IUART, IDelayableUART`. Construtor (23): `frequency` default 8000000; `repl` define `frequency: 8000000` (linha 18).

### B1. Flags de SR (linhas 175-188)

```csharp
Register.Status.Define(this, 0xC0, name: "USART_SR")   // reset 0xC0 = TC | TXE
    .WithTaggedFlag("PE", 0)
    .WithTaggedFlag("FE", 1)
    .WithTaggedFlag("NF", 2)
    .WithFlag(3, FieldMode.Read, valueProviderCallback: _ => false, name: "ORE") // we assume no receive overruns
    .WithFlag(4, out idleLineDetected, FieldMode.Read, name: "IDLE")
    .WithFlag(5, out readFifoNotEmpty, FieldMode.Read | FieldMode.WriteZeroToClear, name: "RXNE")
    .WithFlag(6, out transmissionComplete, FieldMode.Read | FieldMode.WriteZeroToClear, name: "TC")
    .WithFlag(7, FieldMode.Read, valueProviderCallback: _ => true, name: "TXE") // we always assume "transmit data register empty"
```
- **TXE:** sempre 1 (linha 183).
- **TC:** setado **imediatamente** na escrita de DR (linha 213: `transmissionComplete.Value = true;`), sem esperar o tempo de frame. Limpo por escrita de 0 no SR (WZTC, 182).
- **ORE:** nunca setado (linha 179: `valueProviderCallback: _ => false`).
- **PE/FE/NF/LBD/CTS:** tagged, nunca setados.
- **IDLE:** setado por `ReportIdleLineDetected` (linhas 287-294) após 1 frame sem novos caracteres (linhas 157-160: `machine.ScheduleAction(idleFrameDuration, ...)` com `idleFrameDuration = GetActualTransmissionDuration(CharacterLength)`).
- **RXNE:** `readFifoNotEmpty` = `receiveFifo.Count > 0` (linhas 144, 202).
- **FIFO de recepção: SIM, fila.** `private readonly Queue<byte> receiveFifo = new Queue<byte>();` (linha 423), `receiveFifo.Enqueue(value)` em `ReceiveChar` (143). **Não há single-DR nem ORE.** Se um byte chega com RXNE já setado, ele é **enfileirado** (sem overrun); RXNE continua 1 até a fila esvaziar. Fila **ilimitada**.

### B2. Leitura/escrita de DR e limpeza de flags (linhas 189-217)

Leitura de DR (190-204):
```csharp
valueProviderCallback: _ => {
    uint value = 0;
    // "Cleared by a USART_SR register followed by a read to the USART_DR register."
    // We can assume that USART_SR has already been read on the ISR.
    idleLineDetected.Value = false;
    if(receiveFifo.Count > 0) { value = receiveFifo.Dequeue(); }
    readFifoNotEmpty.Value = receiveFifo.Count > 0;
    Update();
    return value;
}
```
- **IDLE é limpo por qualquer leitura de DR**, sem exigir leitura prévia de SR (o comentário assume SR lido; o código não verifica).
- **RXNE é limpo por leitura de DR** quando a fila esvazia (202). Também pode ser limpo por escrita de 0 no SR (WZTC, 181), **mas isso não remove o byte da fila** — possível divergência (RXNE=0 com dado na fila).
- **Leitura de SR não limpa nada por si** (SR não tem read-side-effect no código).

Escrita de DR (205-214):
```csharp
writeCallback: (_, value) => {
    if(!usartEnabled.Value && !transmitterEnabled.Value) { ...drop...; return; }
    CharReceived?.Invoke((byte)value);
    transmissionComplete.Value = true;
    Update();
}
```
- **Condição de drop usa `&&`:** o caractere é descartado só se UE=0 **e** TE=0; se apenas um deles estiver setado, transmite. (Compare com o HW, que exige ambos.) Divergência a registrar.
- O caractere sai **sincronamente** via `CharReceived` (linha 212) — **nenhum atraso de transmissão no próprio UART**; o atraso é aplicado pelo hub (ver C).

### B3. Delays: AutoUpdateDelay / CharacterTransmissionDelay / DelayMultiplier

- Propriedades: `CharacterTransmissionDelay` (71) e `CharacterReceptionDelay` (73), default `TimeInterval.Empty`.
- `AutoUpdateDelay` (103-114) default **false** (campo, 416). `DelayMultiplier` (116-127) default **1** (417).
- `UpdateDelay()` (296-305):
  ```csharp
  if(baudrate == 0) { CharacterTransmissionDelay = TimeInterval.Empty; return; }
  CharacterTransmissionDelay = this.GetActualTransmissionDuration(CharacterLength) * DelayMultiplier;
  ```
  Chamado apenas se `AutoUpdateDelay` (linhas 109-111, 122-124, 322-325 em `UpdateBaudrate`).
- `CharacterLength` (131): `(M ? 9 : 8) - (paridade ? 1 : 0)`. (Paridade é somada novamente na extensão.)
- `baudrate` (linhas 312-313 em `UpdateBaudrate`, 307-326):
  ```csharp
  var fraction = oversamplingMode.Value == OversamplingMode.By16 ? dividerFraction.Value : dividerFraction.Value & 0b111;
  var divisor = 8 * (2 - (int)oversamplingMode.Value) * (dividerMantissa.Value + fraction / 16.0);
  var newBaudrate = divisor == 0 ? 0 : (uint)(frequency / divisor);
  ```
  Ou seja `baud = fck / (16·USARTDIV)` (com OVER8 → 8·USARTDIV), **truncado a inteiro** (`(uint)`). O baud efetivo é derivado do BRR.
- Extensão (`IDelayableUART.cs`, linhas 15-25):
  ```csharp
  return TimeInterval.FromNanoseconds((ulong)Math.Ceiling(
      ( 1 /*start*/ + dataBits + (ParityBit == None ? 0 : 1) + GetNumberOfStopBits() ) / BaudRate * 1e9));
  ```
  Duração do caractere = (start + dados + paridade + stop) / baud, arredondada para cima em ns. Stop bits: 1→1, 0.5→0.5, 1.5→1.5, 2→2 (linhas 27-44).
- **Onde o delay é aplicado:** no **lado de transmissão via hub** (`UARTHub.cs:71-75`: `when = now + duart.CharacterTransmissionDelay`) e, no lado de recepção, `CharacterReceptionDelay` somado pelo hub (`UARTHub.cs:198-200`). **No próprio STM32_UART, o delay de TX não é aplicado** (DR → CharReceived imediato).
- **Lado RX do próprio UART:** `WriteChar` (30-55) enfileira em `intermediateReceiveQueue` e um `ManagedThread` (355-385) com `period = GetActualTransmissionDuration(CharacterLength)` (375) entrega **um caractere por frame** em `ReceiveChar`. Se `baudrate == 0`, entrega imediatamente (38-43, 342-351). **Ou seja, o RX é paceado por frame no próprio UART**, além do delay do hub. (Comportamento exato do primeiro `Restart()` do thread: **UNVERIFIED**, `ManagedThread` não lido.)
- **Configuração no projeto:** `renode/s3.resc` linhas 11-12 define `sysbus.usart1 DelayMultiplier 1` e `AutoUpdateDelay true`. **`renode/c4.resc` NÃO define AutoUpdateDelay** (busca por `AutoUpdateDelay|DelayMultiplier|CharacterTransmission` em `renode/*` retornou só s3.resc) → em c4 o `CharacterTransmissionDelay` fica `TimeInterval.Empty` e o hub entrega **sem atraso de transmissão** (ver C).

### B4. Interrupções (linhas 328-336)

```csharp
IRQ.Set(
    (idleLineDetectedInterruptEnabled.Value && idleLineDetected.Value) ||
    (receiverNotEmptyInterruptEnabled.Value && readFifoNotEmpty.Value) ||
    (transmitDataRegisterEmptyInterruptEnabled.Value) || // TXE is assumed to be true
    (transmissionCompleteInterruptEnabled.Value && transmissionComplete.Value)
);
```
- **RXNEIE, TXEIE, TCIE, IDLEIE: suportados** (CR1 bits 5, 7, 6, 4: linhas 228-231).
- **TXEIE: a linha fica alta enquanto TXEIE=1** (TXE é sempre 1) — nível constante, sem "re-arm" por escrita. Divergência natural: no HW a IRQ TXE só fica ativa quando TDR vazio, que aqui é sempre.
- **PEIE (bit 8), EIE, CTSIE, LBDIE:** tagged, não geram IRQ.
- Linha IRQ: **nível** (saída `IRQ` GPIO, 134). Reset (57-69) faz `IRQ.Set(false)`.

---

## C. UARTHub.cs

Criação (23-25, 42): `emulation.CreateUARTHub(name, loopback = false)` → `new UARTHub<byte>(loopback)`. Campo `shouldLoopback = loopback` (54).

- **Loopback:** linha 193: `foreach(var recipient in uarts.Where(x => shouldLoopback || x.Key != sender))` — com `loopback=true`, o emissor também recebe o próprio byte; com false, só os outros.
- **Encaminhamento: AGENDADO em tempo virtual, não imediato.** `AttachTo` (59-85):
  ```csharp
  if(uart is IDelayableUART duart) {
      d = x => {
          var now = TimeDomainsManager.Instance.VirtualTimeStamp;
          var when = now + duart.CharacterTransmissionDelay;
          HandleCharReceived(x, when, uart);
      };
  } else {
      d = x => HandleCharReceived(x, TimeDomainsManager.Instance.VirtualTimeStamp, uart);
  }
  uarts.Add(uart, d);
  uart.CharReceived += d;
  ```
- Entrega (234-237): `recipient.GetMachine().HandleTimeDomainEvent(recipient.WriteChar, obj, localWhen, ...)` com `localWhen = when + CharacterReceptionDelay` (198-200). **Delay efetivo = CharacterTransmissionDelay(sender) + CharacterReceptionDelay(recipient)**, ambos default `Empty` (zero) no STM32_UART.
- **Entrega sempre no mesmo instante virtual de `now` quando delays são zero**, mas via `HandleTimeDomainEvent` (**o instante exato de execução vs quantum: UNVERIFIED** — código do Machine não lido). O `renode/c4.resc` (linhas 5-9) documenta "entrega do hub é em virtual-time com atraso ≤ quantum (1 µs = 8 c @ 8 MHz)"; **isto não foi verificado no código**.
- `started` (165) **não é inicializado** → `false` até `Start()/Resume()` (87-100). `HandleCharReceived` retorna cedo se `!started` (174-177). **UNVERIFIED**: quem chama `Start()` (presumivelmente `IHasOwnLife` no start da emulação; c4.resc diz "auto-start no `start`").
- Compatibilidade (249-273): baud, paridade e stop bits são comparados; mismatch apenas **loga** e só descarta se `StrictMode` (232). `StrictMode` default **false** (55). Em modo não-strict, mismatch é entregue.
- Fault injection (defaults 0 / int.MaxValue): `DroppedCharacterRate` (184), `FlipBits` (191, 297-318; retorna direto se `BitFlipRate==0`), `FrameErrorRate` (219-222) — inativos por padrão.
- Eventos: `DataTransmitted` (179), `DataRouted` (227, 236).

---

## D. DWT.cs

Classe: `DWT : BasicDoubleWordPeripheral, IKnownSize` (linha 15), `Size = 0x1000` (29).

- **Contador:** `cycleCounter = new LimitTimer(machine.ClockSource, frequency, this, "CycleCounter", direction: Direction.Ascending);` (20). Como o `limit` default é `ulong.MaxValue` (LimitTimer.cs:20), o contador interno é 64 bits; a leitura faz truncamento para 32 bits (62: `return (uint)cycleCounter.Value;`) — equivalente ao wrap de 32 bits do HW.
- **Frequência:** `dwt0: Miscellaneous.DWT @ sysbus 0xE0001000`, `frequency: 8000000` (`renode/stm32f103_hsi8.repl` linhas 303-304). Ou seja, CYCCNT conta a 8 MHz (HSI), **não** no clock do core simulado — coerente com HSI 8 MHz do projeto.
- **Sincronização:** leitura de CYCCNT chama `machine.SystemBus.TryGetCurrentCPU(...)` → `cpu.SyncTime()` (58-61) antes de retornar `cycleCounter.Value`.
- **Escrita (CYCCNT=0 etc.):** SIM, `writeCallback: (_, val) => { cycleCounter.Value = val; }` (55-56). `LimitTimer.Value` setter (LimitTimer.cs:238-248) lança exceção se `value > initialLimit` (ulong.MaxValue, então não ocorre).
- **CTRL.CYCCNTENA (bit 0):** honrado — `writeCallback: cycleCounter.Enabled = val` (34-38), readback via `cycleCounter.Enabled` (38). Contagem para com CYCCNTENA=0 (entrada de relógio desabilitada). Default desabilitado (`enabled` default false, LimitTimer ctor linha 20).
- **Gate por DEMCR.TRCENA: NÃO aplicado.** No HW ARMv7-M o DWT só conta com `DEMCR.TRCENA=1`. Em `armm/NVIC.cs` (linhas 1720-1738, registrador DEMCR 0xDFC, linha 3118): `.WithFlag(24, name: "TRCENA (Trace Enable)")` com comentário "The trace flag only store written data. Changing it doesn't change the behavior of the model." **Logo, CYCCNT conta apenas com CYCCNTENA, sem TRCENA — divergência vs HW.**
- Demais registradores (comparators, masks, functions, CPICNT/EXCCNT/SLEEPCNT/LSUCNT/FOLDCNT, PCSR): tagged/sem efeito (linhas 64-156).

---

## E. Relevantes ao LimitTimer (base de STM32_Timer e DWT)

- `Divider` setter (LimitTimer.cs:200-215): troca `frequency` da entrada imediatamente (sem buffer).
- `Limit` setter (167-191): troca `period` imediatamente.
- `Enabled` setter (272-287): troca `enabled` imediatamente via `ExchangeClockEntryWith`.
- `OnLimitReached` (303-320): `rawInterrupt = true`; se `eventEnabled`, dispara `LimitReached`.
- Reset (322-334).

---

## Resumo de divergências (para a metodologia)

| Tópico | Renode 1.17.0 (fonte) | STM32F103 HW |
|---|---|---|
| PSC | aplicado imediatamente (STM32_Timer.cs:349, 355; LimitTimer.cs:200-215) | bufferizado, efetivo no próximo update |
| UIF | setado em todo overflow, independe de UIE (STM32_Timer.cs:64) | igual |
| UIF por UG | só se UIE (STM32_Timer.cs:283) | independe de UIE |
| CCxIF | só se CCxIE (STM32_Timer.cs:132) | independe de CCxIE |
| RCR | só gate de IRQ (86-97); período não muda | repetition counter real (TIM1) |
| TRGO (MMS) / ITRx / ETR | não implementado (174, 682-684, 209-212) | implementado |
| ECM1 (SMS=7) | não suportado (187-189) | suportado |
| ORE | nunca setado (STM32_UART.cs:179) | setado com overrun |
| TC | setado imediatamente no write de DR (213) | após frame |
| Condição de drop em TX | `!UE && !TE` (207) | exige UE e TE |
| DWT | conta com CYCCNTENA apenas (DWT.cs:34-38) | exige DEMCR.TRCENA |
| Delay de hub | zero se AutoUpdateDelay=false (default); c4.resc não seta | depende do fio físico |

## Itens UNVERIFIED (resumo)
- `WriteZeroToClear` do framework de registradores (semântica exata da escrita 0/1).
- `ManagedThread` (primeiro Restart; alinhamento ao período do frame).
- `HandleTimeDomainEvent` / `TimeStamp` / quantum: instante exato de entrega do hub.
- Quem chama `UARTHub.Start()` e se a plataforma usa `AutoUpdateDelay` fora de s3.resc (core Renode principal não lido; c4.resc não o define).
- Re-pendência do NVIC com linha de nível alta após handler (`NVIC.CompleteIRQ`, linha 434 — não lido em detalhe).
- Resolução mínima de tempo (`TimeStamp`) e granularidade de CNT.
- Renode não modela wait states/pipeline; ver AGENTS.md (não verificado por este estudo).
