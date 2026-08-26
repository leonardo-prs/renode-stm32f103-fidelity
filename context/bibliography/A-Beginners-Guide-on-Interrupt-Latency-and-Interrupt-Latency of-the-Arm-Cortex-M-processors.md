<!-- page 1 -->

# A Beginner’s Guide on Interrupt Latency - and Interrupt Latency of the Arm Cortex-M processors

*Joseph Yiu — Read time: 14 minutes*

## Introduction

All experienced embedded system designers know that interrupt latency is one of the key characteristics of a microcontrolller, and are aware that this is crucial for many applications with real time requirements. However, the descriptions of interrupt latency in various microcontroller literature often oversimplifies exactly what is included in the ‘interrupt latency’ detail.

This blog will cover the basics of interrupt latency, and what users need to be aware of when selecting a microcontroller with low interrupt latency requirements.

## The Definition of Interrupt Latency

The term interrupt latency refers to the number of clock cycles required for a processor to respond to an interrupt request, this is typically a measure based on the number of clock cycles between the assertion of the interrupt request up to the cycle where the first instruction of the interrupt handler expected (figure 1).

---

<!-- page 2 -->

**Figure 1: Definition of interrupt latency**

[DIAGRAM: A timing diagram illustrating interrupt latency over a timeline of 12 clock cycles (numbered 1-12 along the top horizontal axis).
- **Rows:** The diagram features rows labeled "IRQ", "Fetch", "Decode", and "Execute".
- **Pre-interrupt state (Left side, cycles 1-4):** Three blue blocks are shown aligned in the Fetch, Decode, and Execute rows, labeled "Thread". This represents the processor executing the main thread.
- **Interrupt signal:** The "IRQ" (Interrupt Request) line shows a rectangular signal pulse (hatched with vertical lines) starting around cycle 2.
- **Interrupt handling (Right side, cycles 10-12):** Three orange/yellow blocks appear in the Fetch, Decode, and Execute rows, aligned with the start of the Interrupt Service Routine execution. The final Execute block is labeled "ISR".
- **Latency path:** A blue diagonal line extends downwards from the peak of the IRQ signal, ending at the "ISR" execution block, representing the time delay (latency) between the interrupt request and the processor starting to execute service code.
- **Annotation:** A text label at the bottom reads "First instruction in ISR enter execution stage" with an arrow pointing up to the "ISR" block.]

In many cases, when the clock frequency of the system is known, the interrupt latency can also be expressed in terms of time delay, for example, in µsec.

In many processors, the exact interrupt latency depends on what the processor is executing at the time the interrupt occurs. For example, in many processor architectures, the processor starts to respond to a interrupt request only when the current executing instruction completes, which can add a number of extra clock cycles. As a result, the interrupt latency value can contain a best case and a worst case value. This variation can result in jitters of interrupt responses, which could be problematic in certain applications like audio processing (with the introduction of signal distortions) and motor control (which can result in harmonics or vibrations).

Ideally, a processor should have the following characteristics:

*   The interrupt latency should be low
*   The interrupt response is deterministic and low jitter
*   The interrupt handler take as short a time to execute as possible

---

<!-- page 3 -->

5/1/26, 12:51 PM  
A Beginner's Guide on Interrupt Latency - and Interrupt Latency of the Arm Cortex-M processors

*   Can be configured to enter sleep mode on the last instruction of the interrupt service routine if no other interrupt needs service (for interrupt driven applications)

The interrupt latency itself is not the full story. A microcontroller marketing leaflet highlighting an extremely low interrupt latency doesn't necessarily mean that the microcontroller can satisfy the real-time requirements of a product. A real embedded system might have many interrupt sources and normally each interrupt source has an associated priority level. Many processor architectures support the nesting of interrupts, which means during the execution of a low priority interrupt service routine (ISR), a high priority service can pre-empt and the low priority ISR is suspended, and resume when the high priority ISR completed (figure 2).

[DIAGRAM: A sequential execution timeline titled "Figure 2: Nested Interrupt support". The horizontal axis represents "Time" directed from left to right. The diagram illustrates the pre-emption of a lower priority interrupt by a higher priority interrupt (nested interrupt).

Visual elements include rectangular blocks representing code execution phases:
1.  **main()** (start): A light blue box on the left.
2.  **ISR1**: A light blue box to the right of main(), representing a lower priority Interrupt Service Routine.
    *   Label: "IRQ #1 Lower priority" with a downward arrow pointing to the transition from main() to ISR1.
    *   A red arrow indicates the trigger into ISR1.
3.  **ISR2**: A light blue box positioned above the timeline, occurring after ISR1 starts.
    *   Label: "IRQ #2 Higher priority" with a downward arrow. Below it is yellow text "(Nested IRQ)".
    *   A red arrow points from ISR1 to ISR2 indicating the pre-emption.
    *   A gray arrow connects ISR2 back to the resumed ISR1.
4.  **ISR1** (resumed): A second light blue box to the right of ISR2, representing the resumption of the first routine.
    *   A dotted line connects the end of the first ISR1 block to this resumed block, indicating the suspension period during ISR2 execution.
5.  **main()** (end): A light blue box on the far right.
    *   A dotted line connects the end of the resumed ISR1 block to this final main() block.
    *   A gray arrow points from the resumed ISR1 to main()."

**Figure 2:** *Nested Interrupt support*

Many embedded systems require nested interrupt handling, and when a high priority level is running, services to low priority interrupt requests would be

https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/beginner-guide-on-interrupt-latency-and-interr... 3/20

---

<!-- page 4 -->

delayed. Thus the interrupt latency is normally a lot worse for low priority interrupts, as would be expected.

The nested interrupt handling requirement means that the interrupt controller in the system needs to be flexible in interrupt management, and ideally provide all the essential interrupt prioritization and masking capability. In some cases this could be handled in software, but this can increase the software overhead of the interrupt processing (and code size) and increase the effective latency of serving interrupts. This is discussed in more detail later.

## Cortex-M processor family and NVIC

The Nested Vector Interrupt Controller (NVIC) in the [Cortex-M processor family](#) is an example of an interrupt controller with extremely flexible interrupt priority management. It enables programmable priority levels, automatic nested interrupt support, along with support for multiple interrupt masking, whilst still being very easy to use by the programmer

For the [Cortex-M0](#) and [Cortex-M0+](#) processors, the NVIC design supports up to 32 interrupt inputs plus a number of built-in system exceptions (figure 3). For each interrupt input, there are four programmable priority levels (figure 4). For the [Cortex-M3](#) and [Cortex-M4](#) processors the NVIC supports up to 240 interrupt inputs, with 8 up to 256 programmable priority levels (also shown in figure 4). Bear in mind that in practice the number of interrupt inputs and the number of priority levels are likely to be driven by the application requirements, and defined by silicon designers based on the needs of the chip design.

---

<!-- page 5 -->

5/1/26, 12:51 PM

A Beginner’s Guide on Interrupt Latency - and Interrupt Latency of the Arm Cortex-M processors

[DIAGRAM: A block diagram titled "Cortex-M" enclosed in a large light-blue rounded rectangle. The diagram illustrates the processor's internal architecture.
- Central Block: A large beige rectangle labeled "Core" on the right side.
- Left Block: A tall beige rectangle labeled "NVIC" on the left side.
- Bottom Block: A smaller beige rectangle labeled "Sys Tick" at the bottom.
- Inputs (Left): Outside the blue box, arrows point into the NVIC block.
  - Single arrow labeled "NMI".
  - Four arrows labeled "IRQs".
- Interconnects:
  - A thick double-headed horizontal arrow connects the NVIC and Core blocks.
  - Three arrows point from the "Core" block back towards the "NVIC" block. This group of arrows is labeled "System exceptions".
  - The "Sys Tick" block is connected to the bottom of the "NVIC" block.]

**Figure 3:** The NVIC in the Cortex-M processor family supports multiple interrupt and exception sources

[DIAGRAM: A diagram labeled "Figure 4: Priority levels in Cortex-M processors" divided into two sections.
- **Left Section (Priority Levels Bar Chart):**
  - A vertical axis representing priority levels. An arrow on the left points upwards labeled "Higher priority".
  - Top blocks:
    - Address label "-2": A yellow bar labeled "NMI".
    - Address label "-1": A yellow bar labeled "HardFault".
  - A horizontal line separates the top section from the bottom at address "0x00".
  - Bottom section: A large beige rectangle labeled "IRQs".
  - Axis Labels (vertical): 0x00, 0x40, 0x80, 0xC0.
- **Right Section (Register Bit Fields):**
  - Top Sub-diagram:
    - Title: "Priority level registers in Cortex-M0/M0+".
    - Visual: A horizontal rectangular bar representing a register.
    - Labels: Top numbers "7", "6" mark specific bits. A number "0" marks the lower end.
    - Contents: Bits 7 and 6 are shown as two distinct squares at the left end. The rest of the bar is a continuous yellow block.
  - Bottom Sub-diagram:
    - Title: "Priority level registers in Cortex-M3/M4".
    - Visual: A horizontal rectangular bar representing a register.
    - Labels: Top numbers "7", "6", "5" mark specific bits. A number "0" marks the lower end.
    - Contents: Bits 7, 6, 5 are distinct squares. Bits 4 and 3 are shown as squares. Bit 2 is a dashed box labeled "optional" with a green tint. Bits 1 and 0 are at the end.]

**Figure 4:** Priority levels in Cortex-M processors

In addition to the interrupt requests from peripherals, the NVIC design supports internal exceptions, for example, an exception input from a 24-bit timer call SysTick, which is often used by the OS. There are also additional system exceptions to support OS operations, and a Non-Maskable Interrupt (NMI) input. The NMI and HardFault (one of the system exceptions) have fixed priority levels.

https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/beginner-guide-on-interrupt-latency-and-interr... 5/20

---

<!-- page 6 -->

# Interrupt Latency on the Cortex-M processor family

The interrupt latency of all of the Cortex-M processors is extremely low. The latency count is listed in table 1, and is the exact number of cycles from the assertion of the interrupt request up to the cycle where the first instruction of the interrupt handler is ready to be expected, in a system with zero wait state memory systems:

| Processors | Cycles with zero wait state memory |
| :--- | :--- |
| Cortex-M0 | 16 |
| Cortex-M0+ | 15 |
| Cortex-M3 | 12 |
| Cortex-M4 | 12 |

*Table 1: Interrupt latency of Cortex-M processors with zero wait state memory systems*

The interrupt latency listed in table 1 makes a number of simple assumptions:

* The memory system has zero wait state (and with resources not being used by other bus masters)
* The system level design of the chip does not add delay in the interrupt signal connections between the interrupt sources and the processor
* The Interupt service is not blocked by another current running exception/interrupt service
* For Cortex-M4, with FPU enabled, the lazy stacking feature is enabled (this is the default)

---

<!-- page 7 -->

5/1/26, 12:51 PM A Beginner's Guide on Interrupt Latency - and Interrupt Latency of the Arm Cortex-M processors

* The current executing instruction is not doing an unaligned transfer/bitband transfer (which can take 1 extra transfer cycle)

To make the Cortex-M devices easy to use and program, and to support the automatic handling of nested exceptions or interrupts, the interrupt response sequence includes a number of stack push operations. This enables all of the interrupt handlers to be written as normal C subroutines, and enables the ISR to start real work immediately without the need to spend time on saving current context.

The stacking operation of the Cortex-M3/M4 processor is shown in figure 5. The diagram shows that register R0 to R3, and R12 are pushed onto the stack within the 12 cycle interrupt latency. If the processing inside the ISR only needs five registers or less, there is no need for additional stacking.

[DIAGRAM: A timing diagram illustrating the 12-cycle interrupt latency of a Cortex-M processor. The horizontal axis represents clock cycles 1 through 15. Vertical grid lines mark each cycle. Several signal traces are depicted:]
- **CLK:** A square wave oscillating every cycle.
- **INTISR[2]:** A signal line that goes low at the beginning of cycle 1.
- **HADDRS[31:0]:** Shows addresses being written to the stack. Values include "SP+18", "SP+0", "SP+8", "SP+10".
- **HWDATAS[31:0]:** Shows data being written. Values include "PC", "r0", "r1", "r2", "r3", "r12", "LR". Intermediate address labels "SP+1C", "SP+4", "SP+C", "SP+14" are also visible.
- **HADDRI[31:0]:** Shows instruction addresses. "0x48" is visible near cycle 4. "xPSR" is visible above cycle 6. Values "100", "104", "108" are visible in cycles 6, 7, 8.
- **HRDATAI[31:0]:** Shows instruction data. Value "100" is visible in cycle 6.
- **CURRPRI[7:0]:** Shows current priority. A "2" is visible near cycle 14.
- **ETMIMSTAT[2:0]:** Shows event status. Values "000", "100", "001", "000" appear in sequence.
- **ETMINTNUM[8:0]:** Shows interrupt number. Value "18" appears in cycles 8 and 14.
- **Annotations:**
    - "ISR fetch" arrow spans from cycle 6 to 10.
    - "Handler fetch" arrow spans from cycle 13 to 15.
    - "Twelve-cycle ISR entry latency" arrow spans from cycle 1 to 13.
    - "First ISR instruction in Execute stage" indicates the transition around cycle 12-13.

https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/beginner-guide-on-interrupt-latency-and-interr... 7/20

---

<!-- page 8 -->

*Figure 5: Interrupt entry sequence (stacking) on the Cortex-M3 processor*

# The Myth of Interrupt Latency

'So if I choose a processor with the lowest interrupt latency then that must be good, right?' Unfortunately it is not as simple as that. The interrupt latency figures often only provide one aspect of the interrupt handling performance, but does not give the complete picture:

Interrupt latency figures do not include any software overhead.

In a number of processor architectures, additional software wrapper code is needed for interrupt handlers to:

*   handle the stacking of registers, and/or
*   switch the register bank to a different one, and/or
*   check which interrupt required servicing (shared interrupt pin), and/or
*   locate or branch to the starting of interrupt handlers (not vectored),
*   unstack saved registers at the end of the ISR, etc.

All of these can result in additional, often significant, delays in the processing of interrupts. For example, typically in the 8051 which is still widely used today, there are multiple register banks so it is possible to avoid the need to write software to push registers to stack by switching register banks. You also need a branch/jump instruction to branch to the beginning of the ISR:

| **8-bit (e.g. 8051)** | **Cortex-M** |
| :--- | :--- |
| 1) Interrupt latency | 1) Interrupt latency |

---

<!-- page 9 -->

### 8-bit (e.g. 8051) | Cortex-M
--- | ---
2) `SJMP`/`LJMP` to handler | 2) Starting real handler code
3) `PUSH PSW` | 
4) `ORL PSW, #<span style="color: blue">00001000b</span>` | 
5) Starting real handler code | 

***

*Table 2: Interrupt latency compare between 8051 and Cortex-M processors*

As a result, whilst an 8051 microcontroller might have a lower interrupt latency on paper, the overall interrupt latency, when including the software overhead, is much worse than a Cortex-M based microcontrollers.

### **Interrupt Latency figure does not tell you how long it takes to carry out interrupt handling task**

As in any program code, ISRs take time to execute. The faster the performance of the processor, the quicker the interrupt request is serviced, and the longer the system can stay in sleep mode thus reducing power consumption. When considering from the time an interrupt request is asserted to the time the interrupt processing is actually completed, the Cortex-M processors can be much better than other microcontrollers due to these higher performance characteristics (figure 6).

---

<!-- page 10 -->

5/1/26, 12:51 PM
A Beginner's Guide on Interrupt Latency - and Interrupt Latency of the Arm Cortex-M processors

[DIAGRAM: Figure 6: Interrupt latency when considering processing performance.
This is a comparison chart showing interrupt processing flow for two types of microcontrollers.
Top section labeled "8-bit microcontroller":
- A timeline sequence of colored blocks: Yellow labeled "Latency", Grey labeled "Software overhead", Orange labeled "ISR", Grey labeled "Software overhead", Yellow labeled "Return Latency".
- An arrow labeled "Interrupt" points to the start of "Latency".
- An arrow labeled "IRQ service completed" points to the end of the first "ISR" block.
- A bracket labeled "What really matters" spans from the start of "Latency" to the middle of the first "Software overhead" block following "ISR".

Bottom section labeled "Cortex-M microcontroller":
- A timeline sequence of colored blocks: Yellow labeled "Latency", Orange labeled "ISR", Yellow labeled "Return Latency".
- An arrow labeled "IRQ service completed" points to the end of the "ISR" block.
- A bracket labeled "What really matters" spans from the start of "Latency" to the end of the "ISR" block.]

# Interrupt Latency figure does not tell you the throughput / capacity of interrupt processing

In relation to the total number of clock cycles of the ISR execution, the maximum throughput / capacity of the system can also be very important in many heavily loaded systems. The maximum request per second depends on the system clock speed as well as the number of clock cycles required for the interrupts to be processed.

[DIAGRAM: Figure 7: Cortex-M based microcontrollers have a much higher interrupt handling capacity
This is a timing diagram comparing processing capacity over time.
- A horizontal arrow at the top is labeled "Time".
- Top row labeled "8-bit microcontroller": A sequence of alternating yellow/orange blocks and grey blocks. A double-headed arrow below the first group is labeled "ISR execution time".
- Bottom row labeled "Cortex-M microcontroller": A continuous sequence of yellow/orange blocks. A double-headed arrow below the first block is labeled "ISR execution time".]

In traditional 8-bit/16-bit systems, the run time for ISRs can be many more cycles than with Cortex-M based microcontrollers because of lower

https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/beginner-guide-on-interrupt-latency-and-inte... 10/20

---

<!-- page 11 -->

performance. When combined with the higher maximum clock speed of many Cortex-M based microcontrollers, the maximum interrupt processing capacity can be much higher than other microcontroller products.

## Interrupt Latency figure does not tell you about the jitter of interrupt response time

The jitter of interrupt response time refers to the variation (or value range) of interrupt latency cycles. In many systems, the interrupt latency cycle depends on what the CPU is doing when the interrupt takes place. For example, in an architecture like the 8051, if the processor is executing a multicycle instruction, the interrupt entry sequence cannot start until the instruction is finished, which can be a few cycles later. This results in a variation of the number of interrupt latency cycles, and is commonly referred as jitter.

[DIAGRAM: A timing comparison diagram labeled Figure 8 showing interrupt response differences.
**Top Row (8-bit microcontroller):**
- Label: "8-bit microcontroller"
- Red annotation box: "Multi-cycle instructions cannot be interrupted"
- Visual: Three horizontal bars representing time with yellow and grey segments.
- Three arrows point downward labeled "Periodic Interrupt".
- The top bar shows a grey segment (multi-cycle instruction) that delays the interrupt service.
- The middle bar highlights a red circle with "Jitter" inside it. An arrow points from this circle to a red box labeled "Jitter caused by executing a multi-cycle instruction".
**Bottom Row (Cortex-M microcontroller):**
- Label: "Cortex-M microcontroller"
- Blue annotation box: "Cortex-M : Multi-cycle instructions can be interrupted"
- Visual: Three short, uniform yellow/orange bars representing consistent, short interrupt responses.
- Three arrows point downward labeled "Periodic Interrupt".
**Axis:** A horizontal line at the bottom with an arrow pointing right, labeled "Time".
**Caption:** *Figure 8: Cortex-M processors are designed to have limited jitter in interrupt response*"

*Figure 8:* Cortex-M processors are designed to have limited jitter in interrupt response

In many applications the jitter doesn't matter. However, in some applications, like audio or motor control, the jitter can results in distortion of audio signals, or vibration/noise of motors due to this unwanted jitter.

---

<!-- page 12 -->

In Cortex-M processors, if a multiple cycle instruction is being executed when an interrupt arrives, in most cases, the instruction is abandoned and restarted when the ISR is completed. If the Cortex-M3/Cortex-M4 processor receives an interrupt request during a multiple load/store (memory access) instruction, the current state of the multiple transfer is automatically stored as part of the PSR (Program Status Register) and when the ISR completes, the multiple transfer can resume from where it was stalled by using the saved information in the PSR. This mechanism provides high performance processing while at the same time maintains low jitter in the interrupt response time.

# So what should I look for?

Over the years the marketing literature from various microcontroller vendors has incomplete or misleading information on the interrupt latency. For example, sometimes machine cycles are used (instead of clock cycles) for quoting interrupt latencies and in some cases, quotes the interrupt latency but does not including software overhead. It’s important to fully investigate the details to understand the total interrupt latency work and time.

# What else could make a difference?

The Cortex-M processors incorporate some additional optimizations during interrupt handling to reduce overheads even further:

## Tail chaining

When an ISR is completed, and if there is another ISR waiting to be served, the processor will switch to the other ISR as soon as possible by skipping some of the unstacking and stacking operations which are normally needed (figure 9). This is called Tail Chaining, and can be just six cycles in the Cortex-

---

<!-- page 13 -->

M3 and Cortex-M4 processors. This also makes the processor much more energy-efficient by avoiding unnecessary memory accesses.

[DIAGRAM: A timing and process flow diagram illustrating "Tail Chaining". It consists of three rows of signals/steps aligned against a timeline:
1. **IRQ 1**: A signal line that goes high, stays high, and then goes low.
2. **IRQ 2**: A signal line below IRQ 1 that goes high while IRQ 1 is high, stays high longer, and then goes low. It represents a nested interrupt.
3. **Interrupt Processing**: A sequence of blocks representing the processor states at the bottom:
- **Block 1**: "Stacking (PUSH to stack)". This aligns with the rising edge of IRQ 1.
- **Block 2**: "ISR 1". This follows stacking.
- **Transition**: Between ISR 1 and ISR 2, there is a small gap. An arrow points up to this gap labeled "Tail-chain". An arrow points down to the space between ISR 1 and ISR 2 labeled "Interrupt exit".
- **Block 3**: "ISR 2". This follows the tail-chain transition.
- **Block 4**: "Unstacking (POP from stack)". This follows ISR 2. An arrow points down to the transition between ISR 2 and Unstacking labeled "Interrupt exit".
**Caption**: Figure 9: Tail chaining]

# Late Arrival

If a high priority interrupt request arrives during the stacking stage of a lower priority interrupt, the high priority interrupt will always be serviced first. This ensures high priority interrupts are serviced quickly, and avoids another level of stacking operation during the nested interrupt handling process. In addition this will save energy on power consumption (due to less access to memory) and less stack space too.

---

<!-- page 14 -->

**Figure 10: Late arrival**

[DIAGRAM: A timing diagram and process flow illustrating interrupt handling.
- **Trace 1 (Top):** Labeled "IRQ 1 (Higher priority)". Signal waveform goes Low → High → Low.
- **Trace 2 (Middle):** Labeled "IRQ 2 (Lower priority)". Signal waveform goes Low → High → Low. The High phase starts before IRQ 1 and ends after IRQ 1 ends (overlapping).
- **Trace 3 (Bottom / Process Flow):** A horizontal sequence of rounded rectangles connected by arrows, labeled "Interrupt Processing" on the left.
    - Sequence of blocks: "Stacking (PUSH to stack)" → "ISR 1" → "ISR 2" → "Unstacking (POP from stack)".
    - **Annotations:**
        - An arrow labeled "Late arrival" points upward into the "Stacking (PUSH to stack)" block.
        - An arrow labeled "Interrupt exit" points downward from the IRQ 1 waveform into the gap between "ISR 1" and "ISR 2".
        - An arrow labeled "Tail-chain" points upward into the gap between "ISR 1" and "ISR 2".
        - An arrow labeled "Interrupt exit" points downward from the IRQ 2 waveform into the gap between "ISR 2" and "Unstacking".
]

**Pop pre-emption**

If an interrupt request arrives just as another ISR exiting and the unstacking process is underway, the unstacking sequence is stopped and the ISR for the new interrupt is entered as soon as possible (figure 11). Again, this avoids unnecessary unstacking and stacking, and reduces power consumption and latency.

[DIAGRAM: A timing diagram and process flow illustrating "Pop pre-emption".
- **Trace 1 (Top):** Labeled "IRQ 1". Signal waveform is High, then Low. It covers a duration longer than the ISR 1 block.
- **Trace 2 (Middle):** Labeled "IRQ 2". Signal waveform is Low, then High, then Low. It starts after IRQ 1 is active but ends after IRQ 1 is finished.
- **Trace 3 (Bottom / Process Flow):** Labeled "Interrupt Processing".
    - Sequence of blocks: "Stacking (PUSH to stack)" → "ISR 1" → [Gap/Box] → "ISR 2" → "Unstacking (POP from stack)".
    - **Annotations:**
        - An arrow labeled "Interrupt exit" points downward from the IRQ 1 waveform into the gap after ISR 1.
        - An arrow labeled "Unstacking" points upward from inside the gap after ISR 1.
        - An arrow labeled "Stack Pop Pre-emption" points from the gap into the transition towards ISR 2.
        - An arrow labeled "Interrupt exit" points downward from the IRQ 2 waveform into the gap between ISR 2 and Unstacking.
]

**Figure 11: Pop pre-emption**

---

<!-- page 15 -->

# Do banked registers make a difference?

In some architecture there are multiple register banks, and ISR can use a different, sometimes dedicated, register bank to avoid the overhead of stacking and un-stacking. For example, the 8051 provides four register banks. In the original 8051 the banked registers implementation was memory based, but newer accelerated 8051 designs now use register hardware.

[DIAGRAM: Figure 12: Banked registers. Two diagrams are presented side-by-side.

**Left Diagram:**
A vertical stack of rectangular blocks in a light yellow/beige color.
- Top 4 blocks are labeled: R0, R1, R2, R3.
- Below R3 are 2 unfilled/blank rectangular sections.
- Below those is one final rectangular section.
- **Label below:** "Register bank for normal program"

**Right Diagram:**
A vertical stack of rectangular blocks in a red/salmon color positioned slightly in front of a similar stack in light pink.
- Top 4 red blocks are labeled: R0, R1, R2, R3.
- Behind the red stack, corresponding light pink blocks are visible.
- Below the red R3 block, there are unfilled rectangular sections leading to two final blocks at the bottom (red in front, pink in back).
- A large curly brace spans the vertical difference between the front red stack and the back pink stack on the right side.
- **Label next to brace:** "Additional register bank for lower priority IRQ"
- **Label below:** "Register bank for highest priority IRQ"

The diagrams illustrate the concept of having separate physical or dedicated memory blocks for registers to handle interrupts without saving state.]

*Figure 12: Banked registers*

Banked registers can reduce the overhead of context saving and restore in limited circumstances. However, this will often result in larger silicon area, higher power consumption and is not scalable to support the many levels of flexible nested interrupt system requirements. In some cases, like the 8051, there is the need for additional software overhead to switch the register bank(s). The Arm Cortex-M processors do not use banked registers, and this will provide much better energy efficiency and competitive performance when comparing interrupt driven systems with other microcontroller processor architectures.

## Extra functionality with Cortex-M processors

https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/beginner-guide-on-interrupt-latency-and-inte… 15/20

---

<!-- page 16 -->

# Debug Support

The Cortex-M processors support comprehensive debug support features. The Cortex-M3 and Cortex-M4 processors also offer exception trace support which allows the capture and examination of the exception/interrupt history and timing information in a debugger.

**Exception Trace**

| Num | Name | Count | Total Time | Min Time In | Max Time In | Min Time Out | Max Time Out | First Time [s] | Last Time [s] |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2 | NMI | 0 | 0 s | | | | | | |
| 3 | HardFault | 0 | 0 s | | | | | | |
| 4 | MemManage | 0 | 0 s | | | | | | |
| 5 | BusFault | 0 | 0 s | | | | | | |
| 6 | UsageFault | 0 | 0 s | | | | | | |
| 11 | SVCall | 475 | 158.236 us | 77.500 us | 80.736 us | 135.861 us | 14.549 s | 0.00021660 | 25.44279225 |
| 12 | DbgMon | 0 | 0 s | | | | | | |
| 14 | PendSV | 0 | 0 s | | | | | | |
| 15 | SysTick | 2576 | 4.309 ms | 1.417 us | 93.694 us | 765.222 us | 10.066 ms | 0.00087276 | 25.47015878 |
| 16 | ExtIRQ 0 | 0 | 0 s | | | | | | |
| 17 | ExtIRQ 1 | 0 | 0 s | | | | | | |
| 18 | ExtIRQ 2 | 0 | 0 s | | | | | | |
| 19 | ExtIRQ 3 | 0 | 0 s | | | | | | |
| 20 | ExtIRQ 4 | 0 | 0 s | | | | | | |
| 21 | ExtIRQ 5 | 0 | 0 s | | | | | | |
| 22 | ExtIRQ 6 | 0 | 0 s | | | | | | |
| 23 | ExtIRQ 7 | 0 | 0 s | | | | | | |

*Figure 13: Exception trace in Cortex-M3 and Cortex-M4 processors*

The trace information can be captured using a single pin trace interface called Serial Wire Viewer (SWV), or a multi-bit trace port interface, which has higher trace bandwidth for supporting full instruction trace with an ETM (Embedded Trace Macrocell). The trace information can be very useful for debugging.

**Zero jitter support on Cortex-M0/Cortex-M0+ processors**

The interrupt latency of Cortex-M processors can be affected by wait states of the on chip bus system, which can result in a small jitter. The Cortex-M0 and Cortex-M0+ processors have an optional feature to force interrupt response time to have zero jitter. This is done by forcing the interrupt latency to be the

---

<!-- page 17 -->

worst case (i.e. interrupt latency + wait state effect). This feature is typically not used in microcontrollers (just process the interrupt request as quick as possible), but is used in some special SoC designs that demand zero jitter in interrupt responses.

## Sleep-on-Exit feature

Sleep-on-Exit is a programmable feature which, when enabled, puts the processor into sleep mode when exiting an ISR if no other interrupt request needs to be serviced. This is very useful for any interrupt driven application, and can save power because it avoids the extra clock cycles in the thread (e.g. “main()” code) state, and reduces the amount of stacking and un-stacking normally needed for interrupt entry and exit. It also has a side effect (and benefit) of a shorter interrupt response time because stacking is not needed. For example, on the Cortex-M0, the wake up from Sleep-on-Exit is only 11 cycles.

[DIAGRAM: A timing diagram with 5 signal rows.
- Column 1 (Labels): TIMERINT, SCLK, HCLK, TXEV, SLEEPING. All show an initial value of "0".
- Column 2 (Waveforms): Green digital waveforms on a black background.
- Signals:
    1. TIMERINT: Goes high (IRQ asserted).
    2. SCLK: Oscillating clock signal.
    3. HCLK: Oscillating signal (bus clock), active when TIMERINT is high.
    4. TXEV: Goes high to indicate an event.
    5. SLEEPING: Goes low.
- Annotations:
    - "IRQ sampled" text with an arrow pointing down to the rising edge of the TIMERINT signal.
    - "SEV executed" text with an arrow pointing down to the rising edge of the TXEV signal.
    - A horizontal double-headed arrow connects the "IRQ sampled" point and the "SEV executed" point, indicating a duration (latency).
]

**Figure 14:** Sleep-on-Exit can reduce interrupt latency (first instruction in ISR is SEV)

Note that this technique is particularly useful for interrupt driven applications.

## Wait-for-Event (WFE) sleep

---

<!-- page 18 -->

## A Beginner's Guide on Interrupt Latency - and Interrupt Latency of the Arm Cortex-M processors

There are two instructions for entering sleep modes: **WFI** (Wait for Interrupt) and **WFE** (Wait for Event). WFE enters sleep mode conditionally, and can wake up by events including:

*   Interrupts
*   Hardware event (via an input pin called RXEV)
*   Debug events

The WFE sleep can be woken up quickly without invoking the interrupt/exception sequence. This can shorten the wake up time to just a few cycles. For example, in the Cortex-M0 processor, it can take just four cycles to wake up from sleep mode:

[DIAGRAM: Figure 15. Title: "Wake up from WFE using event input (RXEV)". The figure shows a timing diagram split into two distinct sections. On the left, a grey panel lists signal labels and their states: **RXEV** (0), **SCLK** (1), **HCLK** (1), **TXEV** (0), **SLEEPING** (0). On the right, corresponding green waveforms are displayed on a grid. Above the waveforms, text annotations mark "IRQ sampled" and "SEV executed". A double-headed black arrow spans the distance between these two points, highlighting the latency duration. The waveforms depict clock signals and logic transitions corresponding to the wake-up event described in the text.]

**Figure 15:** Wake up from WFE using event input (RXEV)

In this operation the processor resumes from where it was stalled, just after the WFE instruction. Instead of using an RXEV input, a peripheral interrupt with a different feature called **SEV-ON-PEND** (also a programmable feature) can be used to generate the event and wake up the processor, without the need to execute an ISR.

Once again, note that this technique is most useful for interrupt/event driven applications, and can only be useful when it is known that there is only one interrupt/event source that is being waiting for. If there are other interrupt

---
https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/beginner-guide-on-interrupt-latency-and-inte…

---

<!-- page 19 -->

sources, the program code in thread must still check for the reason for waking up from sleep mode.

## Conclusions

The NVIC in the Cortex-M processors provides very flexible interrupt management and many useful features. One key aspect of the NVIC technical advantages is the low interrupt latency. When this is combined with the high performance of the Cortex-M processors, all interrupt requests can be processed quickly and thus provide high interrupt processing throughput. The interrupt latency on the Cortex-M processors is deterministic, and doesn’t have any hidden software overhead, which can be observed in many other architectures.

The Cortex-M processors are designed to be easy to use. For example, the NVIC programmer’s model is very simple, and the interrupt handlers can be programmed as normal C functions. At the same time, it is very powerful. All interrupts have programmable interrupt priority levels and support nested interrupts automatically. Furthermore, the NVIC supports vectored interrupt operations so that there is no need to use software to determine which interrupt to serve, and additional optimizations like tail chaining help reducing interrupt processing overhead and make the processor more energy efficient at the same time.

[Read more about Cortex-M processors](https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/beginner-guide-on-interrupt-latency-and-inte...)

Re-use is only permitted for informational and non-commercial or personal use only.

---

<!-- page 20 -->

<!-- blank page -->