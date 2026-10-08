# Renode 1.17.0 — NVIC, tlib interrupt delivery, and virtual-time accounting

Pinned sources:
- renode-infrastructure @ 066a7f13c052215632d469c995c89aea37c573b1
- tlib @ 167decf9129758829762e582939128c0694e90d6

Method: the GitHub raw URLs suggested in the brief returned 404 for two paths.
The actual locations are below. Files were downloaded with curl (not WebFetch
summaries, which were lossy) and grepped for exact line numbers. Local copies
are in the session scratchpad, not in the repo.

Path corrections:
- NVIC is at `src/Emulator/Cores/Arm-M/NVIC.cs`. The brief's path
  `src/Emulator/Peripherals/Peripherals/IRQControllers/NVIC.cs` returns 404.
- tlib `cpu-exec.c` is at the repo root. `arch/arm/cpu-exec.c` returns 404.
- tlib `arch/arm/helper.c`, `arch/arm/translate.c`, `arch/arm/op_helper.c`,
  `arch/translate-all.c`, `exec.c`, `cpu.h` (`arch/arm/cpu.h`) exist at the paths shown.

URLs used (all at the pinned commits):
- https://raw.githubusercontent.com/renode/renode-infrastructure/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Cores/Arm-M/NVIC.cs
- https://raw.githubusercontent.com/renode/renode-infrastructure/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Cores/Arm-M/CortexM.cs
- https://raw.githubusercontent.com/renode/renode-infrastructure/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Cores/Arm/Arm.cs
- https://raw.githubusercontent.com/renode/renode-infrastructure/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/CPU/BaseCPU.cs
- https://raw.githubusercontent.com/renode/renode-infrastructure/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/CPU/TranslationCPU.cs
- https://raw.githubusercontent.com/antmicro/tlib/167decf9129758829762e582939128c0694e90d6/cpu-exec.c
- https://raw.githubusercontent.com/antmicro/tlib/167decf9129758829762e582939128c0694e90d6/translate-all.c (listed as `arch/translate-all.c`)
- https://raw.githubusercontent.com/antmicro/tlib/167decf9129758829762e582939128c0694e90d6/arch/arm/helper.c
- https://raw.githubusercontent.com/antmicro/tlib/167decf9129758829762e582939128c0694e90d6/arch/arm/translate.c
- https://raw.githubusercontent.com/antmicro/tlib/167decf9129758829762e582939128c0694e90d6/arch/arm/op_helper.c
- https://raw.githubusercontent.com/antmicro/tlib/167decf9129758829762e582939128c0694e90d6/exec.c
- https://raw.githubusercontent.com/antmicro/tlib/167decf9129758829762e582939128c0694e90d6/tcg/tcg.c (no `maximum_block_size` definition found)
- https://raw.githubusercontent.com/antmicro/tlib/167decf9129758829762e582939128c0694e90d6/arch/arm/cpu.h (cpu.h: `cpu_has_work` at line 1068)

Local repo context: `renode/stm32f103_hsi8.repl` line 37-40 instantiates
`nvic: IRQControllers.NVIC @ sysbus 0xE000E000` with `IRQ -> cpu@0`. `renode/c2.resc:20`
and `renode/c2busy.resc:18` set `emulation SetGlobalQuantum "0.000001"` (1 us).

---

## 1. NVIC (`src/Emulator/Cores/Arm-M/NVIC.cs`)

### 1.1 Priority computation and PRIGROUP (binary point)

Implemented. Two functions split group priority from full priority:

- `GetGroupPriority` (NVIC.cs:2559-2561): `return GetExceptionPriority(interruptNo, true);`
- `AdjustPriority` (NVIC.cs ~2564-2567): `return GetExceptionPriority(interruptNo, false);`
- `GetExceptionPriority` (NVIC.cs ~2569-2592, exact line range not re-read):
  fixed priorities for Reset (-4), HardFault_S (-3), NMI (-2), HardFault (-1);
  otherwise `priority = (int)priorities[interruptNo];` and, if `groupPriority`,
  `priority = ApplyPriorityGrouping(priority, secure);`, then `ApplyPriorityRestriction`.
- Grouping mask (NVIC.cs:2594-2599):
  ```csharp
  private int ApplyPriorityGrouping(int priority, bool secure)
  {
      var binaryPointMask = ~((1 << binaryPointPosition.Get(secure) + 1) - 1);
      return priority & binaryPointMask;
  }
  ```
  The subpriority bits below the binary point are cleared for group priority.
- PRIGROUP write (NVIC.cs:1234-1239, AIRCR bits 8-10):
  ```csharp
  .WithValueField(8, 3, writeCallback: (_, value) =>
  {
      if(binaryPointPosition.Get(isNextAccessSecure) != (int)value)
      {
          binaryPointPosition.Get(isNextAccessSecure) = (int)value;
          FindPendingInterrupt();
      }
  }, name: "PRIGROUP")
  ```
- `binaryPointPosition` is a `SecurityBanked<int>` (NVIC.cs:41, field at 2761).

So subpriority does NOT prevent preemption between different groups. It does
prevent preemption within the same group, because preemption compares group priority only (see 1.2).

### 1.2 Preemption decision

`FindPendingInterrupt()` is at NVIC.cs:81-133. The relevant code:

```csharp
// NVIC.cs:85
var preemptNeeded = activeIRQs.Count != 0;
// NVIC.cs:88-100
foreach(int i in pendingIRQs)
{
    if(isLockedUp && i != (int)SystemException.NMI) { continue; }
    var currentIRQ = irqs[i];
    // ComparePriorities() uses full priority, exception number,
    // and Security state when selecting between pending exceptions.
    if(IsCandidate(currentIRQ) && (result == null || DoesAPreemptB(i, result.Value)))
    {
        result = i;
    }
}
// NVIC.cs:102-113
if(preemptNeeded && result != null)
{
    var activeTop = activeIRQs.Peek();
    if(GetGroupPriority(result.Value) >= GetRawExecutionPriority())
    {
        result = null;
    }
    else
    {
        this.NoisyLog("IRQ {0} preempts {1}.", ExceptionToString(result.Value), ExceptionToString(activeTop));
    }
}
// NVIC.cs:117-127
if(result == null) { IRQ.Set(false); maskedInterruptPresent = false; return null; }
var groupPriority = GetGroupPriority(result.Value);
var canBecomeActive = groupPriority < GetExecutionPriority();
// WFI ignores PRIMASK, but it must still account for active
// exceptions, BASEPRI, and FAULTMASK (rule RHRMJ).
var canWakeFromWfi = groupPriority < GetExecutionPriority(ignorePrimask: true);
IRQ.Set(canBecomeActive);
maskedInterruptPresent = canWakeFromWfi;
return result;
```

Key facts:
- A pending IRQ preempts iff `GetGroupPriority(pending) < GetRawExecutionPriority()`
  (NVIC.cs:105; the `>=` case cancels the preemption). Lower numeric value = higher urgency.
- `GetRawExecutionPriority` (NVIC.cs:2543-2557) is the minimum group priority over the
  active-exception stack `activeIRQs`, starting at 0x100 (no active exception).
- `IsCandidate` (NVIC.cs:2650-2655): `Pending | Enabled` set and no `Active` bit.
- The IRQ output line to the CPU is asserted only if the pending IRQ can become active
  under the current execution priority (BASEPRI/PRIMASK/FAULTMASK): `IRQ.Set(canBecomeActive)`
  at NVIC.cs:127. Masking is therefore applied inside the NVIC, not in tlib.

### 1.3 Ordering of equal-priority pending IRQs

`DoesAPreemptB` (NVIC.cs:2336-2353):

```csharp
var priorityA = AdjustPriority(exceptionA);   // full priority, not group
var priorityB = AdjustPriority(exceptionB);
if(priorityA != priorityB) return priorityA < priorityB;
var numberA = exceptionA & ~BankedExcpSecureBit;
var numberB = exceptionB & ~BankedExcpSecureBit;
if(numberA != numberB) return numberA < numberB;   // lower exception number wins
var secureA = !IsInterruptTargetNonSecure(exceptionA);
var secureB = !IsInterruptTargetNonSecure(exceptionB);
return secureA && !secureB;
```

`pendingIRQs` is `SortedSet<int>` (NVIC.cs:37), iterated in ascending order, so
equal full priority resolves to the lowest exception number (verified).

Note: selection uses full priority (ARM `ComparePriorities`, groupPri=FALSE),
while preemption uses group priority. This matches the Armv8-M rule quoted in the code comment.

### 1.4 Writes: ISER, ICER, ISPR, ICPR, IPR, BASEPRI, PRIMASK

- Dispatch in `WriteDoubleWord` (NVIC.cs:503-530):
  - ICER/ISER → `EnableOrDisableInterrupt(...)` (NVIC.cs:507, 517)
  - ICPR (NVIC.cs:522) and ISPR (NVIC.cs:527) → `SetOrClearPendingInterrupt(..., set, isSecure)`
- `SetOrClearPendingInterrupt` (NVIC.cs:2423-2456): calls `SetPending(i)` / `ClearPending(i)`,
  then `FindPendingInterrupt()` (NVIC.cs:2452 inside the loop region and 2470 at the end).
- `SetPending` (NVIC.cs:2231-2236) escalates to HardFault if needed, then calls
  `SetPendingWithoutEscalation`.
- **ISPR immediate effect:** the write updates `irqs[]`, then `FindPendingInterrupt()` sets the
  `IRQ` GPIO line (NVIC.cs:127). The `.repl` wires `IRQ -> cpu@0`
  (`renode/stm32f103_hsi8.repl:40`). `Arm.cs:337-346` maps GPIO 0 to `Interrupt.Hard`.
  `TranslationCPU.cs:389-410` (`OnGPIO`) then calls `TlibSetIrqWrapped`
  (`TranslationCPU.cs:1634-1657`), which calls `TlibSetIrq(Hard, 1)`.
  In tlib, `handle_interrupt` sets the pending bit and `env->exit_request = 1` (`exec.c`, function
  `handle_interrupt`). So the ISPR effect reaches the CPU at the next TB boundary of the current
  `tlib_execute` call, not synchronously within the store instruction.
  Caveat: `TranslationCPU.cs:397-404` only forwards the IRQ if `started` and either the CPU is in
  WFI/Lockup or `!(DisableInterruptsWhileStepping && IsSingleStepMode)`.
- BASEPRI: `BASEPRI_S` / `BASEPRI_NS` setters (NVIC.cs ~913-950) call `FindPendingInterrupt()`
  (lines 927, 947). Called from tlib through `OnBASEPRIWrite` (`CortexM.cs`, [Export]).
  `GetPriorityBoost` (NVIC.cs:2479-2541) applies BASEPRI (`basepri.NonSecureVal`), PRIMASK
  (`cpu.GetPrimask(false)`, NVIC.cs:2495 and 2520) and FAULTMASK (`cpu.GetFaultmask`).
  PRIMASK and FAULTMASK are stored in tlib and read through `Arm.cs:140, 172` (`tlibGetFaultmask`, `tlibGetPrimask`).
- PRIMASK writes (MSR) happen in tlib. The NVIC re-evaluates only when something calls
  `FindPendingInterrupt()`. tlib `helper.c:766` calls `refresh_pending_irq();` (in the CPSR write
  path; the function body was NOT read, so it is UNVERIFIED how it reaches Renode).

### 1.5 Readback

Implemented (NVIC.cs:713-737 in `ReadDoubleWord`):
- ISER/ICER readback: `HandleEnableRead` (NVIC.cs:2202-~2220): bit-packs `Enabled` state.
- ISPR/ICPR readback: `GetPending` (NVIC.cs:2658-2661): bit-packs `Pending`.
- IABR (active bit range): `GetActive` (NVIC.cs:2664-2667): bit-packs `Active`.

### 1.6 SCB ICSR VECTACTIVE / VECTPENDING

Implemented as read-only fields (NVIC.cs:1077-1080):
```csharp
.WithValueField(0, 9, FieldMode.Read, valueProviderCallback: _ => (uint)(activeIRQs.Count == 0 ? 0 : activeIRQs.Peek()), name: "VECTACTIVE")
...
.WithValueField(12, 9, FieldMode.Read, valueProviderCallback: _ => (ulong)(FindPendingInterrupt() ?? 0), name: "VECTPENDING")
```
Side effect: reading VECTPENDING calls `FindPendingInterrupt()`, which re-drives the `IRQ` line.
RETTOBASE is implemented (NVIC.cs:1078-1079). ISRPENDING is a tagged flag (NVIC.cs:1081, the value is not derived from state).

AIRCR key check: `NVIC.cs:560` `if(key != VectKey)`; `VectKey = 0x5FA` at NVIC.cs:2773.
SYSRESETREQ and VECTRESET are handled in the AIRCR path (around NVIC.cs:1250-1280).

### 1.7 Interface between tlib and NVIC (CortexM.cs `[Export]` callbacks)

- `FindPendingIRQ` (CortexM.cs:971-974): `return nvic?.FindPendingInterrupt() ?? 0;`
- `PendingMaskedIRQ` (CortexM.cs:1001-1004): `return nvic.MaskedInterruptPresent ? 1 : 0;`
- `CompleteIRQ` (CortexM.cs:1020-1023): `return nvic.CompleteIRQ(number) ? 1 : 0;`
- `AcknowledgeIRQ` (CortexM.cs ~1025-1028): `return nvic?.AcknowledgeIRQ() ?? 0;`
- `NVIC.AcknowledgeIRQ` (NVIC.cs:476-493): pops the best pending IRQ, sets `Active`, clears
  `Pending`, pushes onto `activeIRQs`, and calls `IRQ.Set(false)`.
- `NVIC.CompleteIRQ` (NVIC.cs:434-466): checks the top of the active stack, deactivates, calls
  `FindPendingInterrupt()`.
- The NVIC tlib interface function names referenced in tlib (`tlib_nvic_*`) are mapped to these
  exports. The tlib side is `arch/arm/arch_callbacks.c` (`DEFAULT_*` declarations, lines 28-34).

### 1.8 Not found / not implemented

- ABSENT: lockup and WFI stop unless the CPU is locked up (see §2.4).
- Lockup: `NVIC.cs:90` skips non-NMI IRQs while `isLockedUp`; `SetLockupState` at NVIC.cs:420-430.
- WFI/sleep hooks: `NVIC.cs:901` `cpu.AddHookAtWfiStateChange(HandleWfiStateChange)` and
  `NVIC.cs:2136-2160` set `InSleep` / `InDeepSleep` GPIO outputs.

---

## 2. tlib (`cpu-exec.c`, `translate.c`, `helper.c`, `translate-all.c`)

### 2.1 When is a pending interrupt recognized? (between TBs, not per instruction)

`cpu_exec` in `cpu-exec.c` (main loop starts ~line 290):

```c
/* cpu-exec.c:298-302 */
if(env->v7m.locked_up && (!(env->interrupt_request & CPU_INTERRUPT_HARD) ||
                          tlib_nvic_find_pending_irq() != ARMV7M_EXCP_NMI)) {
    return EXCP_LOCKUP;
}
/* cpu-exec.c:305-311 */
if(!cpu_has_work(env)) { ...; return EXCP_WFI; }
/* cpu-exec.c:324-341 */
if(env->exception_index >= 0) {
    if(env->return_on_exception || env->exception_index >= EXCP_INTERRUPT) { ...break; }
    else {
        do_interrupt(env);
        ...
    }
}
/* cpu-exec.c:348-359 : inner loop, executed before every TB */
next_tb = 0;
for(;;) {
    cpu_sync_instructions_count(env);
    interrupt_request = env->interrupt_request;     /* cpu-exec.c:352 */
    if(unlikely(interrupt_request)) {                /* cpu-exec.c:353 */
        ...
        if(process_interrupt(interrupt_request, env)) { next_tb = 0; ... }
    }
```

The check runs at the head of the inner `for(;;)`, i.e., before each translation block
(lines 348-359). The exit_request check is also per TB (`cpu-exec.c:402-404`,
`if(cpu->instructions_count_value == cpu->instructions_count_limit) env->exit_request = 1;`).
Within a TB, no interrupt check happens. Delivery granularity is therefore TB boundaries.

`process_interrupt` (`translate.c:16646-16700`):
```c
if((interrupt_request & CPU_INTERRUPT_HARD) &&
   (env->regs[15] < ARM_M_FNC_RETURN_MIN))   /* ~translate.c:16685-16687 */
{
    env->exception_index = EXCP_IRQ;
    do_interrupt(env);
    return 1;
}
```
The guard `regs[15] < ARM_M_FNC_RETURN_MIN` prevents taking an interrupt on an EXC_RETURN magic PC.

### 2.2 What bounds TB size?

`translate-all.c:153-157`:
```c
static inline uint32_t get_max_tb_instruction_count(CPUState *env)
{
    uint32_t current_instructions_count_limit = env->instructions_count_limit - env->instructions_count_value;
    return maximum_block_size > current_instructions_count_limit ? current_instructions_count_limit : maximum_block_size;
}
```
- So a TB is also capped by the remaining instruction budget (`instructions_count_limit`).
- `maximum_block_size` default: UNVERIFIED (not defined in the files read; the Renode setter is
  `TranslationCPU.cs:882-893`, `MaximumBlockSize`).
- Other TB terminators (`translate.c`): page boundary (`translate.c:16583-16585`:
  `if((base->pc - (base->tb->pc & TARGET_PAGE_MASK)) >= TARGET_PAGE_SIZE) return 0;`),
  branches, exceptions/SWI, and WFI (`DISAS_WFI`, `translate.c:104, 4508, 16617-16618`).

### 2.3 Instruction counter / quantum interaction

- `cpu-exec.c:156` and `cpu-exec.c:236`: `max_icount = instructions_count_limit - instructions_count_value`.
  This value is used for TB lookup (`tb->icount <= max_icount` / `was_cut` checks).
- `cpu-exec.c:350`: `cpu_sync_instructions_count(env)` at each TB boundary, then the interrupt check (352-359).
- `cpu-exec.c:402-404`: when the counter reaches the limit, `exit_request = 1`, forcing a return to Renode.
- When an external IRQ is raised, `exec.c` `handle_interrupt` sets `env->exit_request = 1`
  (`exec.c:~1258-1260`). The CPU leaves the current chain at the next TB boundary.

Net effect: an IRQ raised at virtual time t is taken at the first TB boundary after the event is
delivered to tlib. If the event arrives during `tlib_execute(n)`, the CPU stops at the next TB
boundary (and never past the instruction limit, since TBs are cut at `instructions_count_limit`).
If it arrives between calls, it is taken at the start of the next call.

### 2.4 WFI

- Translation: `translate.c:4503-4508` (A32 `WFI` → `DISAS_WFI`); `translate.c:7467-7474`
  (CP15 `ARM_CP_WFI`); `translate.c:16617-16618` (`gen_helper_wfi()`).
- Helper: `op_helper.c:202-206`:
  ```c
  void HELPER(wfi)(void)
  {
      env->exception_index = EXCP_WFI;
      env->wfi = 1;
  }
  ```
- `cpu.h:1068-1080` `cpu_has_work`: if `env->wfi`, `has_work = tlib_nvic_get_pending_masked_irq() != 0;` (M-profile).
- `cpu-exec.c:305-311`: no work → `return EXCP_WFI`.
- `cpu-exec.c:340-343`: EXCP_WFI from `do_interrupt` returns control to Renode with `ret = 0`.
- Renode side: `TranslationCPU.cs:749-755` maps `TlibExecutionResult.WaitingForInterrupt` and
  `Lockup` to `ExecutionResult.WaitingForInterrupt`.
- Virtual-time skip: `BaseCPU.cs:804-823`:
  ```csharp
  if(result == ExecutionResult.WaitingForInterrupt)
  {
      if(!InDebugMode && !neverWaitForInterrupt)
      {
          var instructionsToSkip = Math.Min(InstructionsToNearestLimit(), instructionsLeftThisRound);
          virtualTimeAhead = machine.LocalTimeSource.ElapsedVirtualHostTimeDifference;
          if(!machine.LocalTimeSource.AdvanceImmediately && virtualTimeAhead.Ticks > 0 && instructionsToSkip > 0)
          {
              // sleeps host time only when the virtual clock is ahead of real time
              ...
          }
          ReportProgress(instructionsToSkip);
      }
  }
  ```
  So WFI advances virtual time by `min(InstructionsToNearestLimit(), leftover)` instructions.
  This means WFI skips virtual time to the next clock-source limit (timer deadline), not per
  instruction. Host sleep happens only in real-time mode.
- Wakeup: `cpu.AddHookAtWfiStateChange` (NVIC.cs:901) and `tlib_on_wfi_state_change` (`cpu-exec.c:266-276`).
- Deep-sleep and systick handling: `NVIC.cs:2136-2160`.

### 2.5 Exception entry / exit cycle cost

- ABSENT: no cycle cost for exception entry or exit in tlib (`helper.c`, `op_helper.c`, `cpu-exec.c`).
  The searches for "cycle" in `helper.c` returned only `cpu_before/after_cycles_per_instruction_change`
  (helper.c:5193-5201). The 12-cycle entry and 6-cycle tail-chain figures from the M3 TRM are not modeled.
- The only per-TB cycle accounting is the PMU hook (`translate.c:16700-16716`,
  `gen_helper_pmu_count_instructions_cycles(icount)`), which uses the instruction count
  (`TranslationCPU.cs:897-919` `CyclesPerInstruction`).
- Stacking is performed atomically inside `do_interrupt_v7m` (`helper.c:1876` onward), with
  `v7m_push` calls (e.g. `helper.c:1831-1845`) and no time advance.

### 2.6 Tail-chaining and late-arrival

- Tail-chaining IS implemented as a flag, but without cycle savings:
  - `helper.c:1144` and `helper.c:1426`: `env->v7m.exception_return_tailchain = true;`
  - `helper.c:1886-1888`: the flag is consumed on the next entry (`exception_return_tailchain = false`).
  - `helper.c:1950-1956`: `if(exception_return_tailchain) { lr = exception_return_type; }`
    with the comment "TailChain() reuses the EXC_RETURN".
  - No cycle accounting in either direction.
- Late-arrival: `helper.c:1794-1806` `v7m_resolve_stacking_fault` calls
  `tlib_nvic_set_pending_stacking_fault` and, when the result is `REPLACED`, re-acknowledges
  the replacement exception without a new frame ("DerivedLateArrival()").
  Because stacking is one atomic C call, there is no window in which a new IRQ can arrive during stacking.
  The only late-arrival path is the stacking-fault case. This is an inference from the code structure.

---

## 3. Renode instruction counting and virtual time

### 3.1 Conversion of instructions to virtual time

- `BaseCPU.cs:299-302`: `public uint PerformanceInMips { get => performanceInMips.Value; set => ... }`.
- `BaseCPU.cs:360`: default in the constructor: `PerformanceInMips = 100;`. The platform description
  must set the value to match the modeled clock. UNVERIFIED whether `renode/stm32f103_hsi8.repl`
  sets it (it was not read here).
- `BaseCPU.cs:313`: `ElapsedCycles` accumulates in `DoPause`/`ReportProgress` (`BaseCPU.cs:513-518`:
  `var cycles = instructions + executedResiduum; ... ElapsedCycles += cycles;`).
- Conversion: `interval.ToCPUCycles(PerformanceInMips, ...)` (`BaseCPU.cs:749`), and
  `TimeInterval.FromCPUCycles(...)` for the reverse (`BaseCPU.cs:61, 68`). Virtual time = instructions / PerformanceInMips.
- `TranslationCPU.cs:668-680` `SyncTime()`: reads `TlibGetExecutedInstructions()` and reports progress.
  It is the path the GPIO/bus code uses to sync time mid-execution.

### 3.2 Quantum and per-call instruction budget

- `BaseCPU.cs:741-749`: each granted time interval is converted to a number of instructions
  (`instructionsToExecuteThisRound`), bounded by `TimeHandle` (the quantum).
- `BaseCPU.cs:765-794`: the loop calls `ExecuteInstructions` on `toExecute = min(InstructionsToNearestLimit(), instructionsLeftThisRound)`.
  The comment (`BaseCPU.cs:~771-773`) says: "this puts a limit on instructions to execute in one round
  and makes timers update independent of the current quantum."
- `BaseCPU.cs:930-948` `InstructionsToNearestLimit()`: the number of instructions until the next
  clock-source limit (`machine.ClockSource.NearestLimitIn`). Timers that register limits therefore
  stop the CPU at their deadline, not at the quantum boundary.
- `TranslationCPU.cs:703-740` `ExecuteInstructions` → `TlibExecute(numberOfInstructionsToExecute)` (the native
  `tlib_execute`), then `TlibGetExecutedInstructions()` for the actual count.

### 3.3 Are IRQs delivered at quantum boundaries?

Not necessarily. Delivery is determined by two mechanisms:
1. A timer with a clock-source limit: `InstructionsToNearestLimit()` (BaseCPU.cs:930) bounds each
   `ExecuteInstructions` call to the timer deadline. The timer fires at the right instruction count
   (within the TB size limit from §2.2). The IRQ then reaches tlib via `OnGPIO` → `TlibSetIrqWrapped`
   → `handle_interrupt` (`exit_request = 1`), and is taken at the next TB boundary. Net latency is at
   most one TB, and TBs are cut at the instruction budget.
2. A peripheral without a limit (raises an IRQ from an arbitrary point in host time): the IRQ becomes
   visible at the next `tlib_execute` call or the next TB boundary. In that case the latency is bounded
   by the scheduling quantum (the scenarios in this repo use `SetGlobalQuantum 0.000001`, i.e. 1 us,
   see `renode/c2.resc:20` and `renode/c4.resc:9`, which notes 1 us = 8 cycles at 8 MHz).

Whether the STM32 timers used in this project register clock-source limits was NOT verified (UNVERIFIED).

---

## Unverified items (summary)

- `maximum_block_size` default value (tlib). Not found in `tcg/tcg.c`, `exec.c`, `translate-all.c`, `cpu-exec.c`.
- Whether `refresh_pending_irq()` (tlib helper.c:766) re-runs `FindPendingInterrupt` after a PRIMASK MSR. Definition not read.
- The exact line range of `GetExceptionPriority` (NVIC.cs ~2569-2592) and `HandleEnableRead` / `EnableOrDisableInterrupt` bodies. Start lines are verified, end lines are approximate.
- Whether the project `.repl` sets `PerformanceInMips` (BaseCPU default is 100).
- Whether the STM32F1 timers (TIM2 etc.) use clock-source limits, which determines whether timer IRQs are delivered exactly at the deadline or at the quantum.
- Whether the Renode NVIC `IRQ` GPIO and the tlib `tlib_nvic_*` externals are the only paths for ISPR delivery (the ISPR effect was traced through `OnGPIO`, verified as code path, not executed).
- Exception-entry/exit cycle costs: ABSENT in the code read (no cycle counting). The statement that Renode is 0-cycle for entry is an inference from absence, not a measured result.

## Key findings (short)

1. Priorities: `GetGroupPriority` masks subpriority bits via PRIGROUP (`NVIC.cs:2594-2599`). Preemption compares group priority (`NVIC.cs:105`). Equal-group pending IRQs are not preempting actives. Selection among pending uses full priority, then lowest exception number (`NVIC.cs:2336-2353`).
2. ISPR: the write calls `SetOrClearPendingInterrupt` → `FindPendingInterrupt` → `IRQ.Set` → CPU `OnGPIO` → `TlibSetIrq` → tlib `exit_request=1`. Taken at the next TB boundary.
3. tlib recognizes pending interrupts only at TB boundaries (`cpu-exec.c:352-359`), never per instruction.
4. TB size is capped by the remaining instruction budget (`translate-all.c:153-157`) and by the page boundary (`translate.c:16583-16585`).
5. WFI skips virtual time to the next clock-source limit (`BaseCPU.cs:804-823`).
6. No cycle cost is modeled for exception entry, exit, tail-chaining, or late-arrival. Tail-chaining and late-arrival exist as state-machine logic only (`helper.c:1794-1806`, `1950-1956`).
7. Quantum (`SetGlobalQuantum`) bounds scheduling granularity. Timer IRQs with clock-source limits are delivered at the deadline; other IRQs are delivered at the next TB boundary after the quantum slice begins.
