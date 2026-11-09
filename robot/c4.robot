*** Settings ***
Documentation     C4 — serial link: each case repeated in Renode with a fresh machine. The link
...               L1 (USART2 TX → USART3 RX) is a UART hub, the connection the Renode
...               documentation offers between two UARTs; ${STRICT} selects its mode (False =
...               UH-A, the default; True = UH-E). Data come from scripts/c4.py as --variable.
Resource          ${RENODEKEYWORDS}
Resource          renode.resource
Suite Setup       Setup
Suite Teardown    Teardown
Test Teardown     Test Teardown

*** Variables ***
${STRICT}         False

*** Test Cases ***
C4-01 link enable
    [Tags]    c4_01_link_enable
    Run C4 Case    c4_01_link_enable    1

C4-02 equal link
    [Tags]    c4_02_equal_link
    Run C4 Case    c4_02_equal_link    2

C4-03 frame format
    [Tags]    c4_03_frame_format
    Run C4 Case    c4_03_frame_format    3

C4-04 slow consumer
    [Tags]    c4_04_slow_consumer
    Run C4 Case    c4_04_slow_consumer    4

C4-05 receive interrupt
    [Tags]    c4_05_receive_interrupt
    Run C4 Case    c4_05_receive_interrupt    5

C4-06 line mismatch
    [Tags]    c4_06_line_mismatch
    Run C4 Case    c4_06_line_mismatch    6

*** Keywords ***
Run C4 Case
    [Arguments]    ${case}    ${number}
    FOR    ${run}    IN RANGE    1    ${REPS} + 1
        Start Case Run    ${OUT}/${case}/run-${run}    ${number}
        Connect Wire L1
        Finish Run    ${RUN_NS}
    END

Connect Wire L1
    [Documentation]    UART hub between USART2 and USART3 (Machine-to-machine connections page).
    Execute Command    emulation CreateUARTHub "l1"
    Execute Command    connector Connect sysbus.usart2 l1
    Execute Command    connector Connect sysbus.usart3 l1
    Execute Command    l1 StrictMode ${STRICT}
