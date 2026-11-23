# 10 — Seção Taxonomias, Perfis de Classificação e Execuções

Status: `em andamento` (implementação verificada pelo gate; victory audit interrompido, pendente de reexecução)

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

- [x] É possível criar/editar `Taxonomia` e `Disciplina`, e arquivar/reativar `Disciplina` vendo no modal de confirmação o número de `Classificação`s vigentes impactadas. (Coberto por `TaxonomiasPage.test.tsx`; validação manual no navegador fica na Tarefa 15.)
- [x] "Criar nova versão" de `Perfil de Classificação` herda os campos do perfil base, mantém `template_prompt` em seção "Avançado" e gera nova versão imutável. (Coberto por `TaxonomiasPage.test.tsx`.)
- [x] Formulário de `Execução de Classificação` envia `incluir_revisadas = false` por padrão e suporta todos os escopos acordados. (Coberto por `TaxonomiasPage.test.tsx`; compara o corpo exato da requisição.)
- [x] Aba `Execuções` exibe métricas da rodada e habilita **"Retomar / Reprocessar falhas"** apenas para status `interrompida` ou `concluida_com_erros`. (Coberto por `TaxonomiasPage.test.tsx`.)
- [x] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro. (Executados na rodada r3: todos com exit code 0; `pnpm test` com 46 testes.)

## Verificação

- Testes Vitest + Testing Library em `frontend/src/features/taxonomias/` cobrindo CRUD, diálogo de arquivamento com contagem, versionamento de perfil, disparo com `incluir_revisadas = false` e retomada parcial.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

**Implementação** (`frontend/src/features/taxonomias/`, `frontend/src/api/taxonomias.ts`, `frontend/src/api/execucoes.ts`, `frontend/src/api/operacao.ts`, `frontend/src/components/ui/textarea.tsx`, `frontend/src/app/router.tsx`). Nenhuma alteração no backend.

**Gate de verificação**: três iterações.
- Iteração r1 (worker, verificação): reprovada. Achados: teste de métricas instável, aba Execuções mostrando rodadas de outra Taxonomia, retomada concorrente, criação com refetch falho e schema de nova versão sem campos obrigatórios.
- Iteração r2: reprovada. Achados: teste de regressão que não protegia a correção, erro silencioso no refetch, retomada concorrente que sobrevivia mal à troca de aba e edição de Disciplina após troca de Taxonomia.
- Iteração r3: aprovada. Reviewers `APPROVE` (requisitos e padrões), challengers `CONFIRMED` (entradas e contratos; estado e tempo) e auditor forense `CLEAN`. Mutações nas correções de M2, C1, C2 e C4 derrubaram os testes correspondentes.

**Comandos executados na r3** (em `frontend/`):
- `pnpm type-check`: exit 0
- `pnpm lint`: exit 0
- `pnpm test`: exit 0, 5 arquivos, 46 testes
- `pnpm build`: exit 0 (aviso de tamanho de chunk)
- `pnpm exec vitest run src/features/taxonomias`: 5 execuções seguidas, exit 0 em todas (20/20)

**Pendências**:
- Victory audit (independente, Fase 7) interrompido antes de concluir. Sem veredito `VICTORY CONFIRMED`. Reexecução pendente.
- Validação manual no navegador contra o backend real: fora desta tarefa (Tarefa 15).
- Lacunas de cobertura: três guardas (`api/execucoes.ts`, duplicata do cache de retomada e reset do diálogo Arquivar) sem teste que as discrimine.
- Baixas do challenger de estado: aba Execuções com Taxonomias vazia e listagem falhando mostra erro em vez de "Selecione uma Taxonomia"; erro de retomada com aba desmontada se perde; fechar diálogo de criar Taxonomia durante o POST descarta o aviso de refetch falho.
- Teste do POST de perfil usa `toMatchObject`, que não pega campo extra no corpo.
- Divergências registradas, fora de escopo: `divergencias_abertas` é contador da rodada e nunca decrementa no backend (`backend/src/domain/classificacao.py:344-345`); a pílula do worker não filtra execuções por Taxonomia (`WorkerStatusPill.tsx:11`); o indicador "usa disciplina arquivada" nas Classificações só existe na API de Questões (Tarefa 11).
- Formatação (prettier ausente no projeto) e rótulos de escopo duplicados não corrigidos.
- Decisão de escopo do usuário: `codigo` obrigatório na criação de Taxonomia; `codigo` de Disciplina somente leitura na edição.
- Decisão do usuário: trabalho feito na branch `main`, sem branch própria, como orientado.
