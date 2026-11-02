"""C2 — interrupções (tcc/documentacao/fundamentacao/04-c2.typ).

Pacote do firmware #oD do C2 (preset `c2-od`, só Renode, perfil R1):

  catalog   fonte única: casos, pontos, linhas, fases e o oráculo documental
  gen       gera build/c2-od/gen/c2_catalog.h a partir do catálogo (CMake)
  gate      conferência estática do ELF (vetores, pontos marcados, literais)
  collect   uma execução no Renode: .resc gerado, ganchos, arquivos brutos
  analysis  funções puras: validade do observador e vereditos por caso
  report    relatório Markdown a partir de analysis/results.json

Os IDs de caso (C2-09, …) são os da fundamentação e aparecem iguais no
firmware (C2_CASE_09), nos dados e na análise.
"""
