# 10 — Seção Taxonomias, Perfis de Classificação e Execuções

Status: `pendente`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Decisões: [modelo de domínio](../decisoes/06-modelo-de-dominio-e-glossario.md), [fluxos de taxonomias e execuções](../decisoes/09-fluxos-interface-web-revisao-consulta.md)

## Contexto

O núcleo do produto suporta múltiplas `Taxonomia`s (ex.: matriz ENADE e PPC de uma universidade), arquivamento seguro de `Disciplina`s, versionamento imutável de `Perfil de Classificação` e disparo/retomada de `Execução de Classificação`. Esta tarefa implementa toda a seção **`Taxonomias`** na SPA sobre os endpoints da Tarefa 07.

## Entrega observável

Seção `Taxonomias` operacional no frontend permitindo gerenciar `Taxonomia`s e `Disciplina`s (com arquivamento seguro), criar novas versões de `Perfil de Classificação`, disparar `Execução de Classificação` com controle de escopo e `incluir_revisadas`, e acompanhar/retomar rodadas na aba `Execuções`.

## Escopo e limites

- **Gestão de `Taxonomia`s e `Disciplina`s (`frontend/src/features/taxonomias/`)**:
  - Listagem e criação/edição de `Taxonomia` (`nome`, `curso_referencia`), mantendo o seletor global do cabeçalho sincronizado após criações/edições.
  - Listagem, criação e edição de `Disciplina`s (`codigo`, `nome`, `ementa`) dentro da `Taxonomia` selecionada.
  - Ação **Arquivar / Reativar `Disciplina`** (`ativa = false | true`, sem botão de exclusão física), exibindo no diálogo de confirmação quantas `Classificação`s vigentes serão marcadas com o indicador passivo *"usa disciplina arquivada"*.
- **Versionamento assistido de `Perfil de Classificação`**:
  - Listagem dos perfis existentes com versão e visualização de `diretrizes_gerais`, `guia_fronteiras` e `template_prompt`.
  - Ação **"Criar nova versão"** a partir de um perfil base (pré-preenchendo campos), com edição direta de `diretrizes_gerais` e `guia_fronteiras`, e `template_prompt` recolhido em seção **"Avançado"**.
- **Disparo e acompanhamento de `Execução de Classificação`**:
  - Modal/formulário **"Nova Execução de Classificação"** escolhendo `Taxonomia`, `Perfil de Classificação`, **escopo** (*todas as questões*, *por `Prova`*, *apenas não classificadas/pendentes* ou *com `Disciplina` arquivada*) e checkbox desligado por padrão **"Incluir questões já revisadas por humano"** (`incluir_revisadas = false`), explicando que revisões humanas nunca são sobrescritas automaticamente.
  - Aba **`Execuções`** listando cada rodada com snapshot resumido (`Taxonomia`, `Perfil`, escopo, data, progresso `processadas/total`, erros, divergências abertas, hits de cache e tokens), polling automático enquanto ativa e botão **"Retomar / Reprocessar falhas"** para status `interrompida` ou `concluida_com_erros`.
- **Fora de escopo**: telas de `Questões` e `Revisão`.

## Dependências

- [07 — API de Taxonomias, Perfis de Classificação e Execuções de Classificação](07-api-taxonomias-perfis-execucoes.md)
- [09 — Shell global da SPA e seção Provas (Ingestão, Gabarito e Reprocessamento)](09-frontend-shell-e-ingestao-provas.md)

## Critérios de aceite

- [ ] É possível criar/editar `Taxonomia` e `Disciplina`, e arquivar/reativar `Disciplina` vendo no modal de confirmação o número de `Classificação`s vigentes impactadas.
- [ ] "Criar nova versão" de `Perfil de Classificação` herda os campos do perfil base, mantém `template_prompt` em seção "Avançado" e gera nova versão imutável.
- [ ] Formulário de `Execução de Classificação` envia `incluir_revisadas = false` por padrão e suporta todos os escopos acordados.
- [ ] Aba `Execuções` exibe métricas da rodada e habilita **"Retomar / Reprocessar falhas"** apenas para status `interrompida` ou `concluida_com_erros`.
- [ ] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro.

## Verificação

- Testes Vitest + Testing Library em `frontend/src/features/taxonomias/` cobrindo CRUD, diálogo de arquivamento com contagem, versionamento de perfil, disparo com `incluir_revisadas = false` e retomada parcial.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

Pendente de execução.
