*** Settings ***
Documentation     C3 — GPIO and EXTI: each case repeated in Renode with a fresh machine. The
...               links of the bench are GPIO links (renode/c3_links.repl). The record hook at
...               record_complete reads the record. Data come from scripts/c3.py as --variable.
Resource          ${RENODEKEYWORDS}
Resource          renode.resource
Suite Setup       Setup
Suite Teardown    Teardown
Test Teardown     Test Teardown

*** Variables ***
${LINKS}          ${CURDIR}/../renode/c3_links.repl

*** Test Cases ***
C3-01 output registers and input isolation
    [Tags]    c3_01_output_registers
    Run C3 Case    c3_01_output_registers    1

C3-02 internal pull on a free pin
    [Tags]    c3_02_input_pull
    Run C3 Case    c3_02_input_pull    2

C3-03 driven line between pins
    [Tags]    c3_03_driven_line
    Run C3 Case    c3_03_driven_line    3

C3-04 AFIO routing and EXTI0 edges
    [Tags]    c3_04_exti_routing
    Run C3 Case    c3_04_exti_routing    4

C3-05 EXTI pending and lost events
    [Tags]    c3_05_exti_pending
    Run C3 Case    c3_05_exti_pending    5

C3-06 input capture and filter
    [Tags]    c3_06_input_capture
    Run C3 Case    c3_06_input_capture    6

C3-07 response time to an event
    [Tags]    c3_07_event_response
    Run C3 Case    c3_07_event_response    7

*** Keywords ***
Run C3 Case
    [Arguments]    ${case}    ${number}
    FOR    ${run}    IN RANGE    1    ${REPS} + 1
        Start Case Run    ${OUT}/${case}/run-${run}    ${number}
        Execute Command    machine LoadPlatformDescription @${LINKS}
        Finish Run    ${RUN_NS}
    END
