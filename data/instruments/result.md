# Verification of the Renode instruments

**Verdict: EQUAL**

| | |
|---|---|
| elf | `build/instruments/firmware.elf` |
| elf_sha256 | `e9c8fda01af65627f8d15593078a954d91c9295d6b1609895029668d1d65e36f` |
| renode | `Renode v1.17.0` |
| reps | `3` |

| Criterion | Result | Detail |
|---|---|---|
| monitor writes selected_case before boot: the firmware reads the value | ok |  |
| address hook writes to memory: the firmware reads the value | ok |  |
| monitor pause ends at the requested instant (and on a whole instruction) | ok | reference/run-1: [20000000, 25000000, 30000000] ns |
| monitor writes in the pause: the firmware reads the value | ok |  |
| monitor reads memory in the pause: record_length and record so far equal to the final record | ok |  |
| address and write hooks: virtual time = 125 ns × instructions | ok | instrumented/run-1: 10108 events |
| Δ DWT_CYCCNT = Δ instructions between marked points | ok | instrumented/run-1: 14 points |
| trace: the instruction at the index of each address hook is the hook PC | ok | instrumented/run-1: 10082 hooks, trace of 240157 |
| write hook: one per call of store, at the store instruction, with address and value from R0/R1 | ok | instrumented/run-1: 26 writes |
| hook at the 1st address of PendSV_Handler: one pass per entry, IPSR = 14 | ok | instrumented/run-1: 15 entries |
| hook at the 1st address of SysTick_Handler: one pass per entry, IPSR = 15 | ok | instrumented/run-1: 9 entries |
| hook at the 1st address of External_Handler: one pass per entry, IPSR = 16 | ok | instrumented/run-1: 6 entries |
| exception begin at the instruction of each handler entry; one end per begin | ok | instrumented/run-1: 30 begins, 30 ends |
| exception ends: paired by IPSR, return at N-1 and correct successor | ok | instrumented/run-1: 30 ends; all 12 matrix cells |
| address hook under load: at least 10000 calls | ok |  |
| external line: 6 entries (firmware STIR and monitor ISPR requests) | ok | instrumented/run-1: 6 entries |
| non-intrusion: firmware record equal with and without instruments | ok |  |
| repetitions of the reference run identical (parsed events) | ok |  |
| repetitions of the instrumented run identical (parsed events) | ok |  |

Begin/end hook time offsets in ticks (observation, not judged): {'begin': [-1, 0], 'end': [-1]}.

Return matrix (instrumented/run-1, ends per cell):

| Source | simple | tail-chain | nested |
|---|---:|---:|---:|
| PendSV | 1 | 1 | 1 |
| SysTick | 1 | 1 | 1 |
| external STIR | 1 | 1 | 1 |
| external monitor ISPR | 1 | 1 | 1 |

Values (instrumented/run-1): 15 PendSV entries, 9 SysTick, 6 external; monitor wait 29681 and 9992 rounds; instructions at the pauses [160000, 200000, 240000].
