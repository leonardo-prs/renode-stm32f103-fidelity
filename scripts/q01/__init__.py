"""Q-01 — verificação do observador externo (material-base c2-c4,
03-quadro-comum.typ, §"No Renode: observação externa").

Caso #oD, só no Renode, perfil R1 (8 MIPS, quantum 125 ns). Três medidas dos
mesmos pontos marcados (src/q01/q01.S) têm de concordar:

  Δ tempo virtual no gancho / 125 ns  =  Δ DWT_CYCCNT  =  instruções no traço

Os casos #oD temporais de C2–C4 dependem deste: se ele não for IGUAL, ficam
com EVIDÊNCIA INVÁLIDA até a discordância ser entendida.
"""
