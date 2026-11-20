# Regras do Enade Questões

## Raiz e acompanhamento de issues e tasks

- Mantenha todos os documentos de planejamento, decisão e acompanhamento dentro de `docs/<slug>/` (ou `docs/<id>-<slug>/` quando houver número) na raiz deste repositório. Não crie um segundo tracker em `.scratch/`.
- Estrutura dos documentos em `docs/<slug>/`:
  - `task.md`: preserva o pedido original, o escopo acordado e os critérios de aceite separados dos esclarecimentos posteriores.
  - `mapa.md`: mapa do Wayfinder (Destino, Notas, Decisões até agora, Ainda não especificado / névoa e Fora de escopo) — funciona como índice de baixa resolução, sem duplicar o detalhe dos tickets.
  - `decisoes/NN-<slug>.md`: tickets de decisão/investigação do Wayfinder (`Type: research | prototype | grilling | task`, `Status: open | claimed | resolved`, `Blocked by: ...`).
  - `pesquisas/<slug>.md`: relatórios de pesquisa com fontes primárias referenciados pelos tickets de `research`.
  - `plano.md`, `explicacao.md`, `validacao.md` e `tarefas/NN-<slug>.md`: criados somente na transição do planejamento para a implementação, mantendo rastreabilidade por links relativos entre plano, explicação, tarefas e evidências.
  - `artefatos/NN-<slug>.md`: prompts aprovados e relatórios resumidos de execuções do Teamwork (ou revisões), mantidos dentro do esforço sem caminhos absolutos locais.
- Crie `GLOSSARY.md` na raiz do projeto de forma preguiçosa assim que os termos de domínio forem consolidados; crie `docs/adr/` apenas para decisões arquiteturais difíceis de reverter com trade-offs reais.

## Operações do Wayfinder neste repositório

- **Mapa**: `docs/<esforco>/mapa.md`.
- **Tickets filhos**: `docs/<esforco>/decisoes/NN-<slug>.md`, numerados a partir de `01`.
- **Bloqueio**: linha `Blocked by: NN, NN` (ou `Blocked by: none`) no cabeçalho do ticket, sempre com links relativos pelo nome do ticket no corpo quando referenciado. Um ticket está desbloqueado quando todos os bloqueadores estão com `Status: resolved`.
- **Fronteira**: arquivos em `decisoes/` com `Status: open` e todos os bloqueadores resolvidos.
- **Claim**: alterar para `Status: claimed` antes de iniciar o trabalho.
- **Resolução**: acrescentar a resposta em `## Answer`, alterar para `Status: resolved` e incluir um ponteiro de uma linha em `## Decisions so far` no `mapa.md`.

## Diretrizes de comportamento

- **Pensar antes de codar**: explicite suposições; em caso de dúvida relevante, pergunte antes de assumir.
- **Simplicidade primeiro**: evite infraestrutura ou abstrações especulativas na v1; adote complexidade apenas quando justificada por necessidade real ou risco validado.
- **Execução orientada a objetivos**: transforme cada entrega em critérios verificáveis e só marque concluído com evidência obtida.
- **Documentação autocontida (sem referências externas privadas)**: nunca mencione nomes ou caminhos de outros repositórios privados/locais nem diretórios absolutos da máquina em arquivos `.md` do repositório.
- **Artefatos de IA/MCP fora do Git**: nunca inclua `.serena/`, `.codebase-memory/`, `.cbmignore`, `.claude/`, `.gemini/`, `.agents/` ou caches de IA em commits sem autorização explícita.
- **Sem push automático**: nunca execute `git push` nem crie/altere recursos remotos sem autorização explícita do usuário.
