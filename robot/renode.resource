*** Settings ***
Documentation     Project machine, run control and inline log hooks shared by every suite.
...               Each hook writes one `EVENT` line (kind, then name=value fields) to the run's
...               renode.log, read by scripts/sim.py.
Library           String

*** Variables ***
${REPL}           ${CURDIR}/../renode/stm32f103_hsi8.repl
${MIPS}           8                   # R1 profile: 8 MIPS, 125 ns quantum (one 8 MHz HCLK cycle)
${QUANTUM}        0.000000125

*** Keywords ***
Create Project Machine
    [Documentation]    The project machine, with the firmware ELF (the same binary as the board).
    Execute Command    mach create "stm32f103"
    Execute Command    machine LoadPlatformDescription @${REPL}
    Execute Command    emulation SetGlobalQuantum "${QUANTUM}"
    Execute Command    sysbus.cpu PerformanceInMips ${MIPS}
    Execute Command    sysbus LoadELF @${ELF}

Start Run
    [Documentation]    Fresh machine whose log (flushed on every line) is <directory>/renode.log.
    [Arguments]    ${directory}
    Reset Emulation
    Execute Command    logFile @${directory}/renode.log true
    Create Project Machine
    Create Log Tester    1
    Set Suite Variable    ${NOW}    0

Start Case Run
    [Documentation]    Fresh machine for one run of a case firmware (src/common/case.h): the
    ...                monitor writes ${case} to selected_case; hooks at unexpected_exception and
    ...                at record_complete.
    [Arguments]    ${directory}    ${case}
    Start Run    ${directory}
    Execute Command    sysbus WriteDoubleWord ${SELECTED_CASE} ${case}
    Log Unexpected Exception Hook    ${UNEXPECTED_EXCEPTION}
    Log Record Hook    ${RECORD_COMPLETE}    ${RECORD}    ${RECORD_LENGTH}

Run Until
    [Documentation]    Run until the virtual instant ${ns} (ns from the start of the run).
    [Arguments]    ${ns}
    ${seconds}=    Evaluate    '%.9f' % ((${ns} - ${NOW}) / 1000000000)
    Execute Command    emulation RunFor "${seconds}"
    Set Suite Variable    ${NOW}    ${ns}

Finish Run
    [Documentation]    Run until ${ns} and fail if any hook raised a Python error.
    [Arguments]    ${ns}
    Run Until    ${ns}
    Should Not Be In Log    Python runtime error    timeout=0.001

Log Address Hook
    [Documentation]    EVENT ADDRESS pc time_ns instructions r0 r1 xpsr, before the instruction at ${address}.
    [Arguments]    ${address}
    Execute Command    sysbus.cpu AddHook ${address} "self.Log(LogLevel.Info, 'EVENT ADDRESS pc=%#x time_ns=%d instructions=%d r0=%#x r1=%#x xpsr=%#x' % (pc, machine.ElapsedVirtualTime.TimeElapsed.Ticks, self.ExecutedInstructions, self.GetRegister(0).RawValue, self.GetRegister(1).RawValue, self.GetRegister(25).RawValue))"

Log Write Hook
    [Documentation]    EVENT WRITE address value time_ns instructions pc, on each word write to ${address}.
    [Arguments]    ${address}
    Execute Command    sysbus AddWatchpointHook ${address} DoubleWord Write "cpu.Log(LogLevel.Info, 'EVENT WRITE address=%#x value=%#x time_ns=%d instructions=%d pc=%#x' % (address, value, self.Machine.ElapsedVirtualTime.TimeElapsed.Ticks, cpu.ExecutedInstructions, cpu.PC.RawValue))"

Log Exception Hooks
    [Documentation]    EVENT EXCEPTION_ENTRY / EXCEPTION_EXIT time_ns instructions pc xpsr, at each exception entry and exit.
    Execute Command    sysbus.cpu AddHookAtInterruptBegin "self.Log(LogLevel.Info, 'EVENT EXCEPTION_ENTRY time_ns=%d instructions=%d pc=%#x xpsr=%#x' % (machine.ElapsedVirtualTime.TimeElapsed.Ticks, self.ExecutedInstructions, self.PC.RawValue, self.GetRegister(25).RawValue))"
    Execute Command    sysbus.cpu AddHookAtInterruptEnd "self.Log(LogLevel.Info, 'EVENT EXCEPTION_EXIT time_ns=%d instructions=%d pc=%#x xpsr=%#x' % (machine.ElapsedVirtualTime.TimeElapsed.Ticks, self.ExecutedInstructions, self.PC.RawValue, self.GetRegister(25).RawValue))"

Log Unexpected Exception Hook
    [Documentation]    EVENT UNEXPECTED_EXCEPTION when the firmware reaches ${address} (unexpected_exception).
    [Arguments]    ${address}
    Execute Command    sysbus.cpu AddHook ${address} "self.Log(LogLevel.Info, 'EVENT UNEXPECTED_EXCEPTION')"

Log Record Hook
    [Documentation]    EVENT RECORD time_ns instructions words, at ${address} (record_complete): the
    ...                words of ${record} up to the length stored at ${length}.
    [Arguments]    ${address}    ${record}    ${length}
    Execute Command    sysbus.cpu AddHook ${address} "self.Log(LogLevel.Info, 'EVENT RECORD time_ns=%d instructions=%d words=' % (machine.ElapsedVirtualTime.TimeElapsed.Ticks, self.ExecutedInstructions) + ','.join('%d' % machine.SystemBus.ReadDoubleWord(${record} + 4*k) for k in range(machine.SystemBus.ReadDoubleWord(${length}))))"

Log Monitor Pause
    [Documentation]    EVENT MONITOR_PAUSE time_ns instructions words, with the words the monitor reads
    ...                at ${addresses} (a Python iterable of addresses).
    [Arguments]    ${addresses}
    Execute Command    python "m = monitor.Machine; c = m['sysbus.cpu']; c.Log(LogLevel.Info, 'EVENT MONITOR_PAUSE time_ns=%d instructions=%d words=' % (m.ElapsedVirtualTime.TimeElapsed.Ticks, c.ExecutedInstructions) + ','.join('%d' % m.SystemBus.ReadDoubleWord(a) for a in ${addresses}))"
