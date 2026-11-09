*** Settings ***
Documentation     C2 — interrupts and timer: each case repeated in Renode with a fresh machine.
...               Data (addresses, instants, points) come from scripts/c2.py as --variable; lists
...               arrive as comma-separated text. The firmware of the case records what it saw;
...               a case with hooks or requests by the monitor writes them out here.
Resource          ${RENODEKEYWORDS}
Resource          renode.resource
Suite Setup       Setup
Suite Teardown    Teardown
Test Teardown     Test Teardown

*** Test Cases ***
C2-01 pending and enable
    [Tags]    c2_01_pending_and_enable
    Run Case Without Stimulus

C2-02 priority and tie
    [Tags]    c2_02_priority_and_tie
    Run Case Without Stimulus

C2-03 nested preemption
    [Tags]    c2_03_nested_preemption
    Run Case Without Stimulus

C2-04 masks
    [Tags]    c2_04_masks
    Run Case Without Stimulus

C2-05 WFI and PRIMASK
    [Tags]    c2_05_wfi_and_primask
    ${sleep}=    Split String    ${SLEEP_TIMES}    ,
    ${request}=    Split String    ${REQUEST_TIMES}    ,
    FOR    ${run}    IN RANGE    1    ${REPS} + 1
        Start C2 Run    ${run}
        FOR    ${asleep_at}    ${request_at}    IN ZIP    ${sleep}    ${request}
            Run Until    ${asleep_at}
            Log C2 Pause    ${READS}
            Run Until    ${request_at}
            Log C2 Pause    ${READS}
            Execute Command    sysbus WriteDoubleWord ${LINE_ADDRESS} ${LINE_VALUE}
        END
        Finish Run    ${RUN_NS}
    END

C2-06 tail-chaining
    [Tags]    c2_06_tail_chaining
    FOR    ${run}    IN RANGE    1    ${REPS} + 1
        Start C2 Run    ${run}
        Log Address Hook    ${NOTE_SERVICE_HANDLER}
        Log Exception Hooks
        Finish Run    ${RUN_NS}
    END

C2-07 cost of an exception
    [Tags]    c2_07_exception_cost
    Run Case Without Stimulus

C2-08 timer period
    [Tags]    c2_08_timer_period
    FOR    ${run}    IN RANGE    1    ${REPS} + 1
        Start C2 Run    ${run}
        Log Address Hook    ${TIMER_SERVICE_HANDLER}
        Finish Run    ${RUN_NS}
    END

C2-09 request during the service
    [Tags]    c2_09_repeated_request
    Run Case Without Stimulus

C2-10 tie between two timers
    [Tags]    c2_10_timer_tie
    Run Case Without Stimulus

C2-11 coalescence during a mask
    [Tags]    c2_11_coalescence
    Run Case Without Stimulus

C2-12 timer count at the entry
    [Tags]    c2_12_timer_count_at_entry
    Run Case Without Stimulus

C2-13 flag clear before the return
    [Tags]    c2_13_flag_clear_before_return
    Run Case Without Stimulus

*** Keywords ***
Run Case Without Stimulus
    [Documentation]    The firmware runs its case; only the end and fault hooks.
    FOR    ${run}    IN RANGE    1    ${REPS} + 1
        Start C2 Run    ${run}
        Finish Run    ${RUN_NS}
    END

Start C2 Run
    [Arguments]    ${run}
    Start Case Run    ${OUT}/${CASE}/run-${run}    ${NUMBER}

Log C2 Pause
    [Arguments]    ${addresses}
    Log Monitor Pause    [${addresses}]
