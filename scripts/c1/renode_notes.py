"""Explicações das divergências no código-fonte do Renode 1.17.0 instalado.

O material-base trata a leitura do código como etapa declarada do método
(análise estática → hipótese → experimento): estas notas EXPLICAM uma
divergência já medida; nunca são oráculo nem decidem veredito. Caminhos
relativos a `lib/renode/src/Infrastructure/src/Emulator/Cores/` do pacote
Nix; linhas da versão 1.17.0 (build ab721d88).
"""
from __future__ import annotations

NOTES = {
    "FD-03": "NVIC.cs: a propriedade FilterCcrDiv0Write (padrão true) descarta a escrita de "
             "CCR.DIV_0_TRP \"so CPU wouldn't fault on integer division by 0\"; a tlib sabe gerar "
             "a falta (tlib/arch/arm/helper.c:795). Corrigido no perfil renode-doc.",
    "FC-08": "tlib/arch/arm/helper.c, HELPER(v8m_bx_update_pc): um BX/BLX para endereço par gera "
             "EXCP_INVSTATE com cpu_loop_exit ANTES de atualizar o PC — a falta é atribuída à "
             "instrução de desvio, com T = 1. O ARMv7-M manda trocar EPSR.T e faltar na instrução "
             "seguinte (no alvo).",
    "FC-10": "Mesmo caminho de FC-08 (LoadWritePC → v8m_bx_update_pc).",
    "FC-11": "tlib/arch/arm/translate.c:13319 (Thumb-2, \"Saturating add/subtract\"): QADD/QSUB "
             "decodificados sem verificar a extensão DSP; o modelo cortex-m3 não tem DSP, mas a "
             "decodificação não consulta a característica.",
    "FEN-05": "QADD e SEL (DSP) e SETEND executam sem UNDEFINSTR: a decodificação Thumb da tlib não "
              "consulta a ausência de DSP no cortex-m3 (ver FC-11), e SETEND, que o TRM r1p1 lista entre "
              "as instruções que sempre falham (Tab. 2-4), também não falta. MRC → NOCP confere.",
    "FEN-06": "FEN-06.div depende de CCR.DIV_0_TRP, descartado pelo FilterCcrDiv0Write (ver FD-03); o "
              "escalonamento em si (FEN-06.udf) confere.",
    "FAL-03": "tlib/arch/arm/cpu.h:1320 declara o campo V7M_CCR.UNALIGN_TRP, mas nenhum código de "
              "tlib/arch/arm/ o lê: acesso desalinhado nunca falta.",
    "FAL-04": "Nenhuma verificação de alinhamento para LDM/STM/LDRD/STRD/LDREX no perfil M da tlib "
              "(as cargas são emitidas como acessos comuns).",
    "FEX-04": "tlib/arch/arm/translate.c:7839 (gen_load_exclusive) reserva o endereço; "
              "do_interrupt_v7m (helper.c:1876) e do_v7m_exception_exit (helper.c:1150) não chamam "
              "cancel_reservation: o monitor local não volta a Open Access na entrada/saída de "
              "exceção (ARM ARM §A3.4.4). Consequência: o registrador de eventos FID3 de C2–C4, que "
              "obtém tickets por LDREX/STREX, não tem no Renode a garantia em que se apoia.",
    "FSY-02": "tlib/arch/arm/helper.c:3740 (HELPER(v7m_mrs)): EPSR lido com a máscara 0x0700FC00 e "
              "xPSR com 0xFF00FDFF — expõem T e ITSTATE, que o ARM ARM manda ler como zero.",
    "FSY-03": "tlib/arch/arm/helper.c (HELPER(v7m_msr), FAULTMASK): escreve FAULTMASK sem a condição "
              "\"ExecutionPriority() > −1\" do ARM ARM §B5.2.3, então liga dentro do HardFault.",
    "FSY-04": "tlib/arch/arm/helper.c (HELPER(v7m_msr), BASEPRI): guarda val & 0xff; o priorityMask "
              "0xF0 da plataforma vale para o NVIC, não para o registrador BASEPRI da CPU.",
    "FSY-08": "NVIC.cs/SCB: as leituras do PPB não verificam privilégio; a tlib também não gera "
              "BusFault para acesso sem privilégio ao PPB (ARM ARM §B3.1.1).",
    "FEN-08": "Ver FSY-08.",
    "FEN-04": "tlib/arch/arm/helper.c:2024: o SP é alinhado a 8 em toda entrada de exceção, com o "
              "comentário \"??? Should do this if Configuration Control Register STACKALIGN bit is "
              "set\" — CCR.STKALIGN = 0 (reset da r1p1) é ignorado.",
    "FEN-07": "A tlib aborta a máquina ao buscar instrução fora de RAM/ROM (\"Trying to execute code "
              "outside RAM or ROM\") em vez de gerar MemManage IACCVIOL na região XN.",
    "FID-01": "tlib/arch/arm/cpu.h:910: ARM_CPUID_CORTEXM3 = 0x410fc231 (r0p1); a placa é r1p1.",
    "FID-02": "Os registradores de características (0xE000ED40..ED70) não são modelados no "
              "NVIC.cs: leem 0.",
    "FID-03": "CortexM.cs (InitPCAndSP): sem InitVectorTableOffset, o VTOR é \"adivinhado\" como o "
              "endereço da primeira seção carregada (0x08000000); o TRM fixa o reset em 0. AIRCR "
              "lido com bits além de VECTKEYSTAT.",
    "FID-05": "NVIC.cs:804: ICTR (InterruptControllerType) devolve 0b0111 fixo; o modelo cortex-m3 "
              "da tlib liga a característica MPU (MPU_TYPER com 8 regiões); DWT_CTRL.NUMCOMP é só "
              "uma tag no DWT.cs.",
    "LAY-01": "A plataforma do projeto registra a flash só em 0x08000000; o alias de boot em 0x0 "
              "(RM0008 §3.4) existe só no perfil renode-doc.",
    "LAY-04": "Sem o alias de boot, SYSRESETREQ reinicia a máquina com VTOR = 0 e o núcleo busca os "
              "vetores em 0x0, onde não há memória: fica preso em 0x0 (perfil renode). Com o alias "
              "(renode-doc), o firmware reinicia e a SRAM é preservada.",
    "LAY-07": "CortexM.cs (VectorTableOffset): escrita mascarada com 0xFFFFFF80 e ignorada se o "
              "endereço não estiver mapeado; os bits [31:30] não são forçados a zero como no TRM.",
    "LAY-09": "Leitura de endereço não mapeado no sysbus devolve 0 com um aviso (\"non existing "
              "peripheral\"), sem BusFault.",
    "LAY-10": "Ver LAY-04 (o lote de reset não volta a main sem o alias de boot).",
    "FBB-01": "A plataforma do projeto não declara o periférico BitBanding: escritas no alias são "
              "ignoradas e leituras devolvem 0. Corrigido no perfil renode-doc.",
    "FBB-02": "Ver FBB-01.",
    "FBB-03": "Ver FBB-01.",
    "FBB-04": "Sem modelo de RCC para o F1: RCC_APB2ENR não existe (lê 0). O alias de periférico do "
              "renode-doc funciona para o GPIOB.",
    "FID-04": "LR = 0 no reset: a tlib não inicializa LR com 0xFFFFFFFF no reset do perfil M "
              "(ARM ARM §B1.5.5).",
    "FID-06": "A área de informação da flash (F_SIZE, UID) não é declarada na plataforma: lê 0.",
}
