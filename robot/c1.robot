*** Settings ***
Documentation     C1 — the core: each case repeated in Renode with a fresh machine. The firmware
...               runs its case and the record hook at record_complete reads the record. No wire, no
...               external stimulus. Data come from scripts/c1.py as --variable.
Resource          ${RENODEKEYWORDS}
Resource          renode.resource
Suite Setup       Setup
Suite Teardown    Teardown
Test Teardown     Test Teardown

*** Test Cases ***
C1-01 arithmetic and flags
    [Tags]    c1_01_arithmetic
    Run C1 Case    c1_01_arithmetic    1

C1-02 conversions and comparisons
    [Tags]    c1_02_conversions
    Run C1 Case    c1_02_conversions    2

C1-03 memory access and addressing
    [Tags]    c1_03_memory
    Run C1 Case    c1_03_memory    3

C1-04 DWT_CYCCNT timebase
    [Tags]    c1_04_timebase
    Run C1 Case    c1_04_timebase    4

C1-05 instruction and bus cycle cost
    [Tags]    c1_05_instruction_cost
    Run C1 Case    c1_05_instruction_cost    5

C1-06 exception frame and return
    [Tags]    c1_06_exception_frame
    Run C1 Case    c1_06_exception_frame    6

*** Keywords ***
Run C1 Case
    [Arguments]    ${case}    ${number}
    FOR    ${run}    IN RANGE    1    ${REPS} + 1
        Start Case Run    ${OUT}/${case}/run-${run}    ${number}
        Finish Run    ${RUN_NS}
    END
