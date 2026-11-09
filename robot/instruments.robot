*** Settings ***
Documentation     Verification of the Renode instruments. Each run is either a reference run
...               (only the case protocol, the stimuli and the record dump at record_complete) or an
...               instrumented run (also every instrument under verification). Data (addresses,
...               values, instants) come from scripts/instruments.py as --variable.
Resource          ${RENODEKEYWORDS}
Resource          renode.resource
Suite Setup       Setup
Suite Teardown    Teardown
Test Teardown     Test Teardown

*** Test Cases ***
Instruments
    [Tags]    instruments
    FOR    ${variant}    IN    reference    instrumented
        FOR    ${run}    IN RANGE    1    ${REPS} + 1
            ${directory}=    Set Variable    ${OUT}/${variant}/run-${run}
            Start Case Run    ${directory}    ${BOOT_VALUE}
            Execute Command    sysbus.cpu AddHook ${TRIGGER} "machine.SystemBus.WriteDoubleWord(${HOOK_MAILBOX}, ${HOOK_VALUE})"
            IF    '${variant}' == 'instrumented'    All Instruments    ${directory}
            Monitor Pauses
            Finish Run    ${RUN_NS}
            IF    '${variant}' == 'instrumented'    Stop Execution Trace
        END
    END

*** Keywords ***
All Instruments
    [Documentation]    Every instrument under verification, including the opcode trace.
    [Arguments]    ${directory}
    Log Address Hook    ${MARK}
    Log Address Hook    ${STORE}
    Log Address Hook    ${PENDSV_HANDLER}
    Log Address Hook    ${SYSTICK_HANDLER}
    Log Address Hook    ${EXTERNAL_HANDLER}
    Log Address Hook    ${STRESS}
    Log Address Hook    ${PHASE_MARK}
    Log Write Hook    ${SINK}
    Log Write Hook    ${ICSR}
    Log Exception Hooks
    Execute Command    sysbus.cpu CreateExecutionTracing "trace" @${directory}/trace.txt PCAndOpcode

Stop Execution Trace
    [Documentation]    Close trace.txt. Renode logs the file's absolute path when it stops, so the
    ...                log level is raised for that one message (it would put the host path in renode.log).
    Execute Command    logLevel 3
    Execute Command    sysbus.cpu DisableExecutionTracing
    Execute Command    logLevel 1

Monitor Pauses
    [Documentation]    At each pause the monitor logs record_length and the record so far, requests the
    ...                external line through ISPR and writes the next value to `mailbox`.
    ${times}=    Split String    ${PAUSE_TIMES}    ,
    ${values}=    Split String    ${PAUSE_VALUES}    ,
    FOR    ${t}    ${value}    IN ZIP    ${times}    ${values}
        Run Until    ${t}
        Log Monitor Pause    [${RECORD_LENGTH}] + [${RECORD} + 4*k for k in range(m.SystemBus.ReadDoubleWord(${RECORD_LENGTH}))]
        Execute Command    sysbus WriteDoubleWord ${ISPR0} 1
        Execute Command    sysbus WriteDoubleWord ${MAILBOX} ${value}
    END
