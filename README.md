# Renode × STM32F103 — functional and timing fidelity

Code, firmware, simulation and data of the undergraduate thesis *"Análise quantitativa da
fidelidade funcional e temporal do Renode em relação ao hardware no STM32F103"*
(Quantitative analysis of the functional and timing fidelity of Renode relative to the
hardware on the STM32F103; EA019, FEEC/UNICAMP).

The question is: **how far does [Renode](https://renode.io) 1.17.0 behave like the real
chip?** The target is an STM32F103C8T6 (*Blue Pill* board, Cortex-M3 r1p1 core, 8 MHz
HSI clock). The answer is given resource by resource, at three levels:

| Level | Question | Example |
|---|---|---|
| functional | is the result (value, flag, order of events) the same? | the `APSR` of an `ADDS` that overflows |
| instruction | is the sequence of executed instructions the same? | no main-flow instruction between two chained handlers |
| cycle | is the time, in `HCLK` cycles (8 MHz), the same? | `DWT_CYCCNT` ticks of an exception entry |

This repository holds everything needed to redo each result: the firmware of each case,
the description of each experiment in Renode, the scripts that compare what was observed
with what was expected, the exact binaries that ran and the raw data of each run.

## Contents

1. [The idea on one page](#the-idea-on-one-page)
2. [Results](#results)
3. [How to read the results](#how-to-read-the-results)
4. [How to reproduce](#how-to-reproduce)
5. [Repository layout](#repository-layout)
6. [Case firmware protocol](#case-firmware-protocol)
7. [The scenarios in detail](#the-scenarios-in-detail)
8. [License](#license)

## The idea on one page

**Case.** Each question is a *case* (for example, C2-03: "does a request inside a handler
preempt it only with a strictly higher group priority?"). A case is a piece of firmware
that sets up the situation and writes what it saw to an array in RAM (the *record*), a
script that runs that firmware in Renode and an analysis that compares the record with
what is expected.

**Oracle.** The expected value of a case comes from a single source, its *oracle*
(Howden, "Theoretical and Empirical Studies of Program Testing", IEEE TSE SE-4(4),
1978):

- **document (#oD)**: the reference manual (RM0008), the programming manual (PM0056) or
  the Cortex-M3 guide. The case runs only in Renode, with an exact stimulus, and the
  result is compared with what the document says. Used for rules.
- **board (#oP)**: the **same ELF binary** runs in Renode and on the board, and the
  Renode record is compared with the board record. Used for timing and for what the
  document does not determine.

**Scenarios.** The cases are grouped in four scenarios, each a ladder in which a case
relies on the ones before it, plus a preliminary verification of Renode's own
instruments:

| Scenario | Resource | Cases | Oracle |
|---|---|---|---|
| Instruments | the Renode hooks, pauses and traces the other scenarios use | 1 | independent reference (the firmware itself) |
| C1 | core: arithmetic, conversions, memory, the `DWT_CYCCNT` ruler, cost per instruction class, exception frame | 6 | board |
| C2 | interrupts (NVIC, masks, chaining) and timers | 13 | document (rules) and board (timing) |
| C3 | GPIO, EXTI and input capture | 7 | document (rules) and board (timing) |
| C4 | serial link USART2 → USART3 | 6 | document; board for the line (C4-06) |

**Verdict.** Each case (or each aspect of a case) is **EQUAL** when every observed item
matches the expected one and **DIVERGES** when at least one differs; `result.md` lists
every difference. A run that cannot be analyzed (unexpected exception, incomplete
record, repetitions that disagree) never becomes a verdict: the script stops and the
case is run again.

**Bench.** A single board (genuine ST STM32F103C8T6, CPUID `0x411FC231`, IDCODE
`0x20036410`) connected to an ST-Link V2 over SWD. Four wires link pins of the board
itself:

| Link | Pins | Used in |
|---|---|---|
| L1 | PA2 → PB11 | C4 (USART2 TX → USART3 RX) |
| L2 | PA6 → PA0 | C3 |
| L3 | PA7 → PA1 | C3 |
| L4 | PA5 → PB0 | C3 |

In Renode the same links are modelled: those of C3 in `renode/c3_links.repl`, that of
C4 by the *UART hub* of the Renode documentation.

## Results

The results are the `result.md` files of each scenario, written by the scripts from the
raw data next to them:

| Scenario | Result | Raw data |
|---|---|---|
| Instruments | [`data/instruments/result.md`](data/instruments/result.md) | `data/instruments/{reference,instrumented}/run-N/` |
| C1 — core | [`data/c1/result.md`](data/c1/result.md) | `data/c1/{renode,board}/<case>/` |
| C2 — interrupts and timer | [`data/c2/result.md`](data/c2/result.md) | `data/c2/{renode,board}/<case>/` |
| C3 — GPIO and EXTI | [`data/c3/result.md`](data/c3/result.md) | `data/c3/{renode,board}/<case>/` |
| C4 — serial link | [`data/c4/result.md`](data/c4/result.md) | `data/c4/{uh-a,uh-e,board}/<case>/` |

Overview of the verdicts (EQUAL / DIVERGES), per case and aspect:

| Case | Oracle | Verdict |
|---|---|---|
| Renode instruments | reference | EQUAL |
| C1-01 arithmetic and flags | board | EQUAL |
| C1-02 conversions and comparisons | board | EQUAL |
| C1-03 memory access and addressing | board | EQUAL |
| C1-04 `DWT_CYCCNT` ruler | board | EQUAL |
| C1-05 cost per instruction class and access target | board | DIVERGES |
| C1-06 exception frame and return | board | DIVERGES |
| C2-01 pending and enable | document | EQUAL |
| C2-02 priority and tie | document | EQUAL |
| C2-03 nested preemption | document | EQUAL |
| C2-04 masks — effect / value read | document | EQUAL / DIVERGES |
| C2-05 `WFI` and `PRIMASK` | document | EQUAL |
| C2-06 tail-chaining | document | EQUAL |
| C2-07 cost of an exception — entry / return / chaining | board | DIVERGES / DIVERGES / DIVERGES |
| C2-08 timer period | document | DIVERGES |
| C2-09 request during the service — by software / level of the flag | document | EQUAL / EQUAL |
| C2-10 tie between timers — pending together / synchronized start | board | EQUAL / DIVERGES |
| C2-11 coalescence during a mask | board | EQUAL |
| C2-12 timer count at the entry | board | DIVERGES |
| C2-13 flag clear before the return | board | DIVERGES |
| C3-01 output registers and input isolation | document | DIVERGES |
| C3-02 internal pull on a free pin | document | DIVERGES |
| C3-03 driven line between pins | document | EQUAL |
| C3-04 AFIO routing and EXTI0 edges | document | EQUAL |
| C3-05 EXTI pending and lost events | document | EQUAL |
| C3-06 input capture — capture / filter | board | EQUAL / DIVERGES |
| C3-07 response time — by the compare interrupt / by the pin / pin to pin | board | DIVERGES / DIVERGES / DIVERGES |
| C4-01 link enable | document | DIVERGES |
| C4-02 equal link — reception / transmitter | document | EQUAL / DIVERGES |
| C4-03 frame format — value and flags / frame time | document | DIVERGES / DIVERGES |
| C4-04 slow consumer | document | DIVERGES |
| C4-05 receive interrupt | document | EQUAL |
| C4-06 line mismatch — hub UH-A / hub UH-E | board | DIVERGES / DIVERGES |

This table is a summary; the source is always the `result.md`, with each item, what was
observed, what was expected and the environment of the run.

## How to read the results

### Structure of a `result.md`

Each `result.md` has three parts:

1. **Environment table**: one row per data set (case × condition), with the ELF used,
   the **SHA-256** of that ELF, the Renode version (or `—` on the board), the number of
   repetitions and, when there is one, the condition (for example, the *UART hub* mode).
   In a board-oracle case the Renode and board rows carry the **same SHA-256**: that is
   what guarantees both environments ran the same binary.
2. **Verdict table**: case, oracle, verdict.
3. **One section per case** (or per aspect), titled `case: verdict`, with:
   - how many runs there were in each environment and, in Renode, the virtual instant of
     the end;
   - `k/n items equal`: how many items matched;
   - `differences`: each differing item, with `observed` and `expected` side by side;
   - reading details (intervals, counts, cost tables, board ranges).

Example (C4-02, transmitter):

```
## C4-02 — equal link (`c4_02_equal_link`), transmitter, document, Renode UH-A: DIVERGES

- 3 runs in Renode; end at 19004000 ns
- 0/4 items equal
- differences:
-   BRR 832: span of writes 2–8 over 6 frames: observed 300, expected 49800–50040
```

It reads: with `BRR` = 832 (9600 bit/s at 8 MHz) the firmware waits for `TXE` before
each write; on the chip, seven consecutive writes take six frames (49 800 to 50 040
ticks); in Renode they take 300 ticks, that is, the Renode transmitter does not hold
`TXE` for the time of a frame.

### Verdicts

The comparison is always item by item. When a case has more than one aspect (for
example C2-04: the *effect* of the mask and the *value read* back from the register),
each aspect has its own verdict, so a divergence in one aspect does not hide the
equality of the other.

The thesis text is in Portuguese; its verdicts map as follows:

| Portuguese | English (code and `result.md`) |
|---|---|
| IGUAL | EQUAL |
| DIVERGE | DIVERGES |

Some comparison rules hold for several cases:

- **Repetitions.** Each case runs 3 times in each environment. The repetitions must give
  the same record; if they disagree the script stops (no verdict on unstable data).
- **Timing against the board.** A timing measure is EQUAL when the Renode value falls in
  the range the board showed for that measure; orders and counts are compared point by
  point.
- **Representative points.** Each point table (rates, priorities, offsets…) tests one
  point per equivalence class or boundary; the reason for each point is the comment next
  to it in `src/<scenario>/` and in the matching script.
- **Units.** A "cycle" is one `HCLK` period at 8 MHz (125 ns); a "tick" is the unit of a
  counter (`DWT_CYCCNT`, `TIMx_CNT`). In Renode, virtual time advances 125 ns per
  instruction (profile R1: 8 MIPS, 125 ns quantum).

### Raw data

Each data set is in `data/<scenario>/[<condition>/]<case>/`:

```
data/c2/board/c2_07_exception_cost/
├── environment.json     ELF, SHA-256, Renode version, repetitions, symbol addresses
├── run-1/board.log      (renode.log in Renode) — EVENT lines, read by scripts/sim.py
├── run-2/…
└── run-3/…
```

The format of the `EVENT` lines is in [Case firmware protocol](#case-firmware-protocol).
A `result.md` is always derived from these files: `--analyze` rewrites it without
running anything. A run also writes the Robot Framework output (`_robot/`) and the
OpenOCD transcripts next to the data; they are not versioned.

## How to reproduce

There are three levels of reproduction, from the cheapest to the most complete:

| Level | What it redoes | Needs |
|---|---|---|
| 1. Re-analysis | the `result.md` files from the versioned data | Nix |
| 2. Renode | build, Renode runs and analysis | Nix |
| 3. Full | the above plus the board runs | Nix, board, ST-Link, wires L1–L4 |

### Requirements

- Linux x86_64 (WSL2 on Windows included). The environment is declared for
  `x86_64-linux` only.
- [Nix](https://nixos.org) with flakes. [Determinate
  Nix](https://docs.determinate.systems/determinate-nix/) is recommended: flakes and the
  `nix` command are enabled out of the box, it installs and uninstalls with one command,
  and it works on WSL2.

No other tool needs to be installed: compiler, CMake, Ninja, OpenOCD, Renode and Python
all come from Nix, at the versions pinned by `flake.lock`.

### 1. Install Nix (Determinate)

```sh
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
```

Open a new terminal after installing. To remove it: `/nix/nix-installer uninstall`. On
WSL2, enable systemd in the distribution (`/etc/wsl.conf`: `[boot]` / `systemd=true`)
before installing.

### 2. Get the code and enter the environment

```sh
git clone https://github.com/leonardo-prs/renode-stm32f103-fidelity.git
cd renode-stm32f103-fidelity
git checkout v1.0.0                     # the published version
nix develop --no-update-lock-file
```

**Why `--no-update-lock-file`.** The versioned `flake.lock` pins the exact nixpkgs
revision (`github:NixOS/nixpkgs/c9fe7d12cd78d1adcd12dd15e24432dde5b155a0`) and, with it,
the version of every tool (Renode 1.17.0, `arm-none-eabi-gcc`, OpenOCD 0.12.0, Python 3).
`nix develop` already uses `flake.lock` when it exists and is complete; the option makes
sure that, if for any reason the lock does not match `flake.nix`, the command **fails**
instead of silently resolving a new revision. So any Linux machine gets the same
environment, byte for byte. To check the revision in use:

```sh
nix flake metadata --no-update-lock-file    # shows the locked nixpkgs revision
```

Never run `nix flake update` to reproduce the results: it changes the tool versions.

Optional: with [direnv](https://direnv.net) and
[nix-direnv](https://github.com/nix-community/nix-direnv), the versioned `.envrc` (`use
flake . --no-update-lock-file`) loads the same environment on entering the directory.

### 3. Build and check the binaries

```sh
cmake -B build -G Ninja
cmake --build build                     # every firmware → build/<fw>/firmware.elf (+ .bin, .map)
cmake --build build --target c3         # one firmware
sha256sum build/*/firmware.elf
```

The ELFs that produced the data are versioned at `build/<fw>/firmware.elf`, and the build
is reproducible across directories (`-ffile-prefix-map`): in the same Nix environment
the same source gives the same ELF. The printed SHA-256 values must equal those in the
environment table of each `result.md`. Each case script also does a clean build of its
firmware before running and records the SHA-256 in `environment.json`.

One firmware per scenario (`instruments`, `c1`, `c2`, `c3`, `c4`); `-O2 -g3`, no HAL,
only the CMSIS and inline LL headers in `vendor/` (frozen copies, origin and SHA-256 in
[`vendor/README.md`](vendor/README.md)); zero warnings (`-Werror`).

### Level 1 — re-analyze the published data

No simulation and no board: rewrites each `result.md` from `data/`.

```sh
python3 scripts/instruments.py --analyze
python3 scripts/c1.py --analyze
python3 scripts/c2.py --analyze
python3 scripts/c3.py --analyze
python3 scripts/c4.py --analyze
git status                              # no result.md may change
```

### Level 2 — run in Renode

Each command does a clean build of the firmware, runs the cases in Renode (through
`renode-test`, 3 repetitions), replaces the data of those cases in `data/` and rewrites
the scenario's `result.md`:

```sh
python3 scripts/instruments.py          # verification of the instruments (run it first)
python3 scripts/c1.py
python3 scripts/c2.py
python3 scripts/c3.py
python3 scripts/c4.py
python3 scripts/c2.py --cases C2-03     # one case only
```

Board-oracle cases need the board data to be analyzed: without `--board` the script
reuses the versioned board data; without it, the script stops and asks for `--board`.
With the same ELF and the same profile Renode is deterministic: the `EVENT` lines and the
`result.md` come out identical to the published ones; only Renode's own informational
lines in `renode.log` change (for example, the seed of the pseudorandom generator).

### Level 3 — run on the board as well

Material:

- a *Blue Pill* board with an STM32F103C8T6 (preferably genuine ST; clones with another
  core give other timings);
- an ST-Link V2 connected over SWD (SWDIO, SWCLK, GND, 3V3);
- wires: L1 PA2→PB11, L2 PA6→PA0, L3 PA7→PA1, L4 PA5→PB0.

Electrical care: mount and remove wires only with the board powered off. The link pins
stay inputs until the case configures them, and no firmware puts two push-pull outputs
on the same wire. C1 and C2 use no wire; C3 uses L2–L4; C4 uses L1.

Access to the ST-Link:

- Linux: the OpenOCD udev rule (`$(dirname $(which openocd))/../etc/udev/rules.d/60-openocd.rules`
  inside `nix develop`) must be in `/etc/udev/rules.d/`.
- WSL2: attach the ST-Link to the distribution with
  [usbipd-win](https://github.com/dorssel/usbipd-win) (`usbipd bind` once and
  `usbipd attach --wsl --busid <id>` on each connection). `lsusb` must list
  `0483:3748 STMicroelectronics ST-LINK/V2`.

Running (the same ELF in Renode and on the board):

```sh
python3 scripts/c1.py --board           # no wire
python3 scripts/c2.py --board           # no wire; C2-07, C2-10 to C2-13 on the board
python3 scripts/c3.py --board           # L2, L3, L4; C3-06 and C3-07 on the board
python3 scripts/c4.py --board           # L1; C4-06 on the board
```

`scripts/board.py` calls OpenOCD once per step (flash, `reset halt`, write
`selected_case`, breakpoints, run, read the record), with no GDB, and refuses to run if
port 3333 is already in use. Do not run two campaigns at the same time, nor rebuild a
firmware while its cases run: Renode and the board load the ELF from `build/`.

## Repository layout

```
flake.nix, flake.lock    Nix environment (tools and pinned versions)
CMakeLists.txt           one build for every firmware; add_firmware(<fw> <sources>)
cmake/                   cross toolchain (arm-none-eabi-gcc)
vendor/                  frozen CMSIS and STM32 LL headers (SHA-256 in vendor/README.md)

src/common/              protocol common to every case firmware: case.h/case.c (case
                         selection, record, end, boot, unexpected exception) and the linker script firmware.ld
src/instruments/         verification of the Renode instruments
src/c1/ … src/c4/        firmware of each scenario (one .c file each), with its point tables

renode/stm32f103_hsi8.repl   project platform: STM32F103C8, HSI 8 MHz, profile R1
renode/c3_links.repl         C3 links (L2, L3, L4) loaded over the platform
robot/renode.resource    project machine and shared log hooks
robot/<scenario>.robot   each experiment written out (stimuli, hooks, run time)

scripts/sim.py           common: build, ELF symbols, environment, renode-test call,
                         reader of the EVENT lines (read_run)
scripts/board.py         board adapter: flashes and runs a case through OpenOCD (ST-Link)
scripts/<scenario>.py    case constants, expected value, comparison and result.md

build/<fw>/firmware.elf  the exact binaries that produced the data
data/                    raw data and result.md of each scenario
```

Each case is therefore three pieces with the same name:

| Piece | File | Role |
|---|---|---|
| firmware | `src/<scenario>/<scenario>.c` | sets up the situation and writes the record |
| experiment | `robot/<scenario>.robot` | machine, stimuli, hooks and run time in Renode |
| analysis | `scripts/<scenario>.py` | expected value (with the citation of the document), comparison, verdict |

The scripts use only the Python standard library. Renode is treated as a black box: what
is expected of it comes from its public documentation and from the C1 results, not from
its source code.

## Case firmware protocol

Every case firmware follows `src/common/case.h`:

| Name | What it is |
|---|---|
| `selected_case` | case number, written before boot by the Renode monitor or by OpenOCD (`.noinit`: boot does not touch it) |
| `record`, `RECORD_CAPACITY` | what the firmware saw, in order (`.noinit`, 4608 words) |
| `record_length` | how many words of `record` are valid |
| `record_value(v)` | appends `v` to the record (ignored when full) |
| `finish_case()` | end of the case: disables interrupts, calls `record_complete`, sleeps (`WFI`) |
| `record_complete()` | empty hook point: the record is ready to be read there |
| `unexpected_exception()` | target of every exception the case does not use; loops on itself |

In Renode, `Start Case Run` (`robot/renode.resource`) writes `selected_case` and places
hooks at `record_complete` and `unexpected_exception`. On the board, `scripts/board.py`
does the same with hardware breakpoints. A run that reaches `unexpected_exception`
cannot be analyzed and is run again.

Each hook writes one line `EVENT <KIND> name=value …` (numbers in decimal or `0x`
hexadecimal; `words` is a comma-separated list). `scripts/sim.py` (`read_run`) is the
only reader, with one class per kind:

| Line | Written by | Fields |
|---|---|---|
| `EVENT ADDRESS` | `Log Address Hook`, before the instruction at an address | `pc time_ns instructions r0 r1 xpsr` |
| `EVENT WRITE` | `Log Write Hook`, on each word write to an address | `address value time_ns instructions pc` |
| `EVENT EXCEPTION_ENTRY` / `EXCEPTION_EXIT` | `Log Exception Hooks` | `time_ns instructions pc xpsr` |
| `EVENT MONITOR_PAUSE` | `Log Monitor Pause` | `time_ns instructions words` |
| `EVENT RECORD` | `Log Record Hook` at `record_complete` | `time_ns instructions words` |
| `EVENT UNEXPECTED_EXCEPTION` | `Log Unexpected Exception Hook` | — |

`instructions` counts the instructions executed before the event. The board writes
`board.log` with the same `RECORD` line (without `time_ns` and `instructions`: there is
no virtual time) or `UNEXPECTED_EXCEPTION`, so both environments are read the same way.
Time on the board is measured by the firmware itself (`DWT_CYCCNT`, `TIMx_CNT`) and goes
into the record.

## The scenarios in detail

### Renode instruments

```sh
python3 scripts/instruments.py [--analyze]
```

Before a hook, a monitor pause or the Renode instruction trace is used as an instrument,
each one is verified against a reference independent of it. Verdict EQUAL when every
criterion holds.

- `src/instruments/instruments.c` exercises PendSV, SysTick and one external IRQ,
  requested by `STIR` and by the monitor, in simple, chained and nested situations, with
  the same case protocol as every other firmware.
- `robot/instruments.robot` runs the firmware 3 times as a *reference* run (only the
  protocol, the stimuli and the reading of the record) and 3 times *instrumented* (every
  instrument, including 10,000 address-hook calls and the PC/opcode trace, kept as
  `trace.txt.xz`).
- `scripts/instruments.py` checks each instrument, that the firmware record is the same
  with and without instruments (non-intrusion) and that each variant repeats. At the end
  of an exception with instruction count N it checks the return at trace index N−1 and
  pairs it with the handler by `IPSR`, in a 12-cell matrix (PendSV, SysTick, external line
  by `STIR`, external line by the monitor × simple return, tail-chain, nested). The time
  the begin/end hooks report is an observation, not a timing instrument. The result holds
  for the tested profile, Renode version and instrument combinations.

### C1 — the core (board; no wire)

```sh
python3 scripts/c1.py [--board] [--cases C1-01 …] [--analyze]
```

One firmware (`c1`); each measured operation is in inline assembly, because the
instruction is the object itself. The same ELF runs 3 times in Renode and 3 times on the
board; each case compares both records item by item (the board is the reference).

| Case | Directory | Question |
|---|---|---|
| C1-01 | `c1_01_arithmetic` | arithmetic and flags: result and `APSR` of each operation, high word of long multiplies |
| C1-02 | `c1_02_conversions` | extensions, narrow loads and stores, `CMP` and 14 conditions |
| C1-03 | `c1_03_memory` | byte order, widths, unaligned access, multiple registers, stack, indexing |
| C1-04 | `c1_04_timebase` | consecutive `DWT_CYCCNT` reads, counter disabled, `ΔTIM2_CNT − ΔDWT` |
| C1-05 | `c1_05_instruction_cost` | ticks of each instruction class and access target |
| C1-06 | `c1_06_exception_frame` | the frame `SVC` stacks, `EXC_RETURN` and the return, on both stacks, with `SP` aligned or not and `STKALIGN` 0 and 1 |

- C1-05 runs each class at 16 and at 32 instructions, in a window with fixed registers,
  encoding and offset in the 64-bit flash line. `(t32 − t16) / 16`, the mean over
  instructions 17 to 32, removes what the neighbouring `DWT_CYCCNT` reads add at the
  ends. Its `result.md` has the table of the cost per class.

### C2 — interrupts and timer (Renode; board for the timing cases; no wire)

```sh
python3 scripts/c2.py [--board] [--cases C2-01 …] [--analyze]
```

One firmware (`c2`). The cases run in order and each one relies on the ones before it.
Rules are judged against the document and timing against the board. Each family of
cases has its own handler: the case selects a vector table through `VTOR`.

| Case | Directory | Oracle | Question |
|---|---|---|---|
| C2-01 | `c2_01_pending_and_enable` | document | a line requested while disabled stays pending, is served once enabled and is active during the service |
| C2-02 | `c2_02_priority_and_tie` | document | lower priority value first, group then subpriority; on a tie, lower exception number |
| C2-03 | `c2_03_nested_preemption` | document | a request in a handler preempts it only with a strictly higher group priority, and its `EXC_RETURN` says where it returns |
| C2-04 | `c2_04_masks` | document | `PRIMASK`, `BASEPRI`, `BASEPRI_MAX`: effect on the NVIC and value read back |
| C2-05 | `c2_05_wfi_and_primask` | document | a request wakes `WFI` with `PRIMASK` 0 and 1 and is served only with 0 |
| C2-06 | `c2_06_tail_chaining` | document | pending lines served in order with no main-flow instruction between them |
| C2-07 | `c2_07_exception_cost` | board | ticks of the entry, of the return and of the chaining |
| C2-08 | `c2_08_timer_period` | document | period of the update interrupt |
| C2-09 | `c2_09_repeated_request` | document | a request during the service, by software and by a flag left set |
| C2-10 | `c2_10_timer_tie` | board | TIM2 and TIM3 pending together; a start synchronized by hardware, in both master roles |
| C2-11 | `c2_11_coalescence` | board | update events during a mask become one service |
| C2-12 | `c2_12_timer_count_at_entry` | board | `TIM2_CNT` read first in the handler |
| C2-13 | `c2_13_flag_clear_before_return` | board | re-entries with the flag cleared k = 0, 1, 2 instructions before the return, with `DSB`, with a read back |

- Against the board: timing (C2-07, C2-12) is EQUAL inside the range the board showed
  over its points; orders and counts (C2-10, C2-11, C2-13) are compared point by point.
- C2-11 and C2-13 count events against the period of their own environment, so their
  counts do not inherit the difference judged in C2-08; `result.md` prints both periods.
- What the board measures (the first reads in the handlers, the mark and the
  instructions before the return, the reads around the request and the return) is in
  inline assembly, with fixed registers, encoding and offset in the 64-bit flash line.
  `SVC` gives C2-07 an exact return address.
- C2-06 uses the exception-end instruction counts (the return is instruction N−1); C2-05
  uses requests written by the monitor at an exact instant.

### C3 — GPIO and EXTI (Renode; board for C3-06 and C3-07; wires L2, L3, L4)

```sh
python3 scripts/c3.py [--board] [--cases C3-01 …] [--analyze]
```

How an external event reaches the firmware, and where on that path Renode stops behaving
like the chip. One firmware (`c3`). The cases run in order; rules against the document,
timing against the board. C3-06, whose capture is a measure of time, goes to the board
whole, its filter included (one oracle per case).

| Case | Directory | Oracle | Question |
|---|---|---|---|
| C3-01 | `c3_01_output_registers` | document | `ODR`, `BSRR` and `BRR` read back; `IDR` of an output with no wire follows each level change; a write to an input does not reach the line; both write paths |
| C3-02 | `c3_02_input_pull` | document | each change of the pull of a free pin changes `IDR`, by `ODR` or by `BSRR`/`BRR` |
| C3-03 | `c3_03_driven_line` | document | each link carries the rise and the fall |
| C3-04 | `c3_04_exti_routing` | document | `EXTICR1` and the trigger registers select which edge of which port enters |
| C3-05 | `c3_05_exti_pending` | document | when an event stays pending and when it is lost; an edge wakes the core from `WFI` |
| C3-06 | `c3_06_input_capture` | board | (a) both captures, and how far the capture difference is from the `DWT_CYCCNT` difference of the same edges; (b) the input filter |
| C3-07 | `c3_07_event_response` | board | ticks from the event to the handler, by the compare interrupt and by the pin, and from pin to pin |

| Link | Pins | Use |
|---|---|---|
| L2 | PA6 → PA0 | main stimulus; PA6 is also `TIM3_CH1` |
| L3 | PA7 → PA1 | the reaction of the handler, captured by `TIM2_CH2` |
| L4 | PA5 → PB0 | an edge on port B |

PA3 and PA4 have nothing attached.

- A level change is one item: the pair of reads before and after it, in each direction
  and by each path. A pin that keeps its level fails the item, and no read passes alone.
  The previous level always comes from `BSRR`/`BRR`.
- In C3-07, TIM3 makes the rise on PA6 by hardware, in phase with the core clock: the case
  measures the reaction to an edge no instruction produced. C3-05 uses the same edge with
  the core in `WFI`.
- Time with the core asleep is not judged: the board runs with a debugger connected, and
  the core does not allow `HCLK` to be turned off during a debug session (RM0008
  §31.16.1). C3-05 judges that the edge wakes the core and is served, and reports the
  ticks in Renode.
- The measures by the compare interrupt and by the pin use the same instructions up to
  the first read, so their difference is what the path through the pin adds. In the
  pin-to-pin measure the write to PA7 is the first thing in the handler.
- C3-06 compares each item with the board: the flags, the residual (capture difference
  minus `DWT_CYCCNT` difference, since the wait between the edges may differ per
  environment) and `CC1IF` of each filter point. C3-07 timing is EQUAL inside the range
  the board showed for that measure.

### C4 — serial link (Renode; board for C4-06; wire L1)

```sh
python3 scripts/c4.py [--board] [--cases C4-02 …] [--analyze]
```

One firmware (`c4`). USART2 transmits on PA2, the link L1 takes the line to PB11 and
USART3 receives, by polling; only C4-05 takes an interrupt. Each case is a list of
bursts: `c4_link` configures both ends and `c4_burst` writes the words and reads every
`RXNE`, recording each write and read with its `DWT_CYCCNT` instant and the status
register (layout at the top of `src/c4/c4.c`). The few direct register writes are the
object of study (the polling loop reads `SR` and writes `DR`, the bit time is an exact
`BRR` integer, each `CR1`/`CR2` change is a single write).

C4-01 to C4-05 keep the same configuration at both ends and are judged against the
document. C4-06, the last step, is the line: ends that disagree and a pin not connected.
The document gives no outcome outside the receiver's tolerance, so the board is the
oracle of the whole case.

| Case | Directory | Oracle | Question |
|---|---|---|---|
| C4-01 | `c4_01_link_enable` | document | words cross only with `TE` and `RE` |
| C4-02 | `c4_02_equal_link` | document | reception: words, flags, the first `RXNE` no earlier than 9.5 bits, `RXNE` every frame; transmitter: writes paced by `TXE`, `TC` = 0 while a word follows |
| C4-03 | `c4_03_frame_format` | document | 9N1, 8E1, 7E1, 8N2 at both ends: value read, error flags and frame time |
| C4-04 | `c4_04_slow_consumer` | document | read deferred past `RXNE`: words lost while `RXNE` = 1, overrun flag |
| C4-05 | `c4_05_receive_interrupt` | document | one handler entry per word with `RXNEIE`, none without it |
| C4-06 | `c4_06_line_mismatch` | board | the class of each point: transmitter rates from −7.45 % to +8.65 %, 8N2 → 8N1, 7E1 → 7O1, PA2 not alternate function; in both hub modes |

- Renode: the link is the *UART hub* of the documentation (`robot/c4.robot`), default
  mode (UH-A). C4-06 also runs in strict mode (UH-E). The hub joins the two USARTs, not
  their pins.
- Δ of C4-06 is the deviation of the bit time of the transmitter from the receiver's
  (`BRR` of USART2 / 832 − 1). RM0008 Tab. 193 is read as a tolerance in bit time: the
  samples of the last bit must fall inside the transmitter's frame, and 3.75 % is 3/8 of
  a bit in a 10-bit frame.
- The class of a point of C4-06 is `ok` (8 words right, no flag), `flags` (8 words right,
  with flags), `data` (a word wrong or another number of words) or `none` (nothing
  arrived); each point compares the class in Renode with the class on the board.
- Polled instants: a span between two of them is known within `Q_POLL`, so frame times
  are judged over a span of several frames, not per interval.

## License

[MIT](LICENSE), for everything in this repository except `vendor/`. The headers in
`vendor/` keep their upstream licenses, next to them: Apache-2.0 (Arm CMSIS and the ST
device headers) and BSD-3-Clause (ST LL).
