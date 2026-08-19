cmake_minimum_required(VERSION 3.22)

#
# ════════════════════════════════════════════════════════════════════════════
# ROOT CMAKE — USER-OWNED, preservado pelo CubeMX em regen
# ════════════════════════════════════════════════════════════════════════════
#
# O CubeMX documenta este arquivo como "one-time generated, user change
# is kept after project regeneration". Modifica à vontade.
#
# O que o CubeMX SOBRESCREVE em regen:
#   - cmake/stm32cubemx/CMakeLists.txt    (sources, defines, includes do .ioc)
#   - cmake/gcc-arm-none-eabi.cmake      (toolchain file)
#   - Core/, Drivers/, startup, linker   (código gerado)
#
# O que o CubeMX NÃO toca:
#   - Este CMakeLists.txt
#   - src/, inc/, lib/, renode/, scripts/, flake.nix
#
# Se regen via CubeMX quebrar o build (raro — só em mudança de toolchain
# ou project name), restaura do git:
#   git checkout HEAD -- CMakeLists.txt
# ════════════════════════════════════════════════════════════════════════════

# ── Compiler settings (override CubeMX's C11 com C17 GNU) ──
set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)

# ── Build type (default Debug) ──
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug" CACHE STRING "Build type" FORCE)
endif()

# ── Project name ──
set(CMAKE_PROJECT_NAME stm32-renode-fidelity)
project(${CMAKE_PROJECT_NAME} LANGUAGES C ASM)

# ── Export compile_commands.json para clangd ──
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

message(STATUS "════════════════════════════════════════════════")
message(STATUS "Build type : ${CMAKE_BUILD_TYPE}")
message(STATUS "Project    : ${CMAKE_PROJECT_NAME}")
message(STATUS "════════════════════════════════════════════════")

# ── SCENARIO flag (SANDBOX | A | B) ──
# Define qual cenário compilar. Determina:
#   - qual arquivo em src/ é linkado
#   - qual bloco é ativado em Core/Src/main.c via SCENARIO_<X> define
#
# Cenários disponíveis: SANDBOX (src/sandbox.c), A (src/scenario_a.c),
#                       B (src/scenario_b.c)
set(SCENARIO "" CACHE STRING "Cenário a compilar: SANDBOX | A | B")
if(NOT SCENARIO)
    message(FATAL_ERROR
        "Defina -DSCENARIO=SANDBOX|A|B\n"
        "Exemplo: cmake -B build/sandbox -DSCENARIO=SANDBOX")
endif()
string(TOLOWER "${SCENARIO}" SCENARIO_LOWER)
add_compile_definitions(SCENARIO_${SCENARIO})

set(APP_SOURCE "${CMAKE_SOURCE_DIR}/src/${SCENARIO_LOWER}.c")
if(NOT EXISTS "${APP_SOURCE}")
    message(FATAL_ERROR
        "Arquivo de cenário não encontrado: ${APP_SOURCE}\n"
        "Cenários disponíveis: sandbox.c, scenario_a.c, scenario_b.c")
endif()

# ── CubeMX-gerado: INTERFACE lib com paths, defines, sources do vendor ──
add_subdirectory(cmake/stm32cubemx)

# ── Executable: nosso .c do cenário + main.c do CubeMX ──
add_executable(${CMAKE_PROJECT_NAME}
    ${APP_SOURCE}
)

# ── Include path: nosso inc/ na raiz (sempre disponível) ──
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    ${CMAKE_SOURCE_DIR}/inc
)

# ── Compiler hardening no nosso código (não toca vendor) ──
target_compile_options(${CMAKE_PROJECT_NAME} PRIVATE
    -Wall
    -Wextra
    -Wmissing-prototypes
    -Wstrict-prototypes
    -ffunction-sections
    -fdata-sections
)
# -Werror fica DEPOIS que o toolchain validar (vendor tem warnings legítimos)

# ── Linker hardening ──
target_link_options(${CMAKE_PROJECT_NAME} PRIVATE
    -Wl,--gc-sections
)

# ── Link com a lib CubeMX (traz Core, Drivers, system, startup, linker) ──
target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE
    stm32cubemx
    STM32_Drivers
    m   # newlib libm
)

# ── Output naming ──
set_target_properties(${CMAKE_PROJECT_NAME} PROPERTIES
    OUTPUT_NAME "firmware"
)

# ── Limpar .map com `ninja clean` ──
set_target_properties(${CMAKE_PROJECT_NAME} PROPERTIES
    ADDITIONAL_CLEAN_FILES "${CMAKE_PROJECT_NAME}.map"
)

# ── Gera .clangd automaticamente (aponta para compile_commands.json) ──
# O template cmake/clangd.in é processado a cada configure. clangd lê
# .clangd na raiz e usa CompilationDatabase para encontrar os flags.
# Mudou o nome do build dir? Reconfigure.
configure_file(
    ${CMAKE_SOURCE_DIR}/cmake/clangd.in
    ${CMAKE_SOURCE_DIR}/.clangd
    @ONLY
)
