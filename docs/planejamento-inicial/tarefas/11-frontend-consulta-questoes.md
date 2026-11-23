# 11 — Seção Questões (consulta combinada, busca e filtros)

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Decisões: [fluxos de consulta e filtros](../decisoes/09-fluxos-interface-web-revisao-consulta.md)

## Contexto

A seção **`Questões`** é o ponto de consulta interativa da base sob a `Taxonomia` ativa no cabeçalho global, permitindo encontrar questões por texto livre, `Disciplina` (principal ou secundária), `Prova`/ano, status de revisão e flags de qualidade, além de abrir diretamente a revisão sobre o recorte filtrado.

## Entrega observável

Seção `Questões` implementada com barra de 4 filtros principais, popover *"Mais filtros"*, listagem em cards enxutos com badges de estado, paginação, estado vazio guiado e ação **"Revisar este recorte (N)"**.

## Escopo e limites

- **Visibilidade e sincronização de estado (`frontend/src/features/questoes/`)**:
  - Exibe todas as `Questão`s sob a `Taxonomia` ativa por padrão (incluindo pendentes), mantendo filtros sincronizados na URL para compartilhamento/navegação de volta.
  - Estado vazio com 0 `Prova`s cadastradas exibindo CTA **"Ingerir primeira prova"**; estado vazio de filtro exibindo botão **"Limpar filtros"**.
- **Barra de filtros**:
  - **4 controles sempre visíveis**: `Busca textual` (com debounce leve), `Disciplina` (com toggle **"Somente principal"**, desligado por padrão para incluir secundárias), `Prova / Ano` e `Status de revisão`.
  - **Popover "Mais filtros"** (com contador de filtros ativos): `Tópico`, `Situação do gabarito` (`valida | anulada | pendente`), `Com alerta de extração`, `Revisão prioritária`, `Com divergência` e `Usa disciplina arquivada`.
- **Listagem em cards enxutos e navegação**:
  - Cada card exibe: `Prova`/ano + nº oficial, snippet (~2 linhas) do enunciado sem quebrar layout com Markdown/código, badges de `Disciplina` principal e secundárias, `Tópico`s, status de revisão (`Pendente`, `Prioritária`, `Aprovada`, `Divergência`, `Anulada`, `Disciplina arquivada`), situação do `Gabarito` e ícones indicando `Ativo Visual`s e `Alerta de Extração`s abertos.
  - Cabeçalho da listagem exibe contador total e botão **"Revisar este recorte (N)"**, que navega para a tela de `Revisão` passando o recorte filtrado atual. Clicar em um card abre aquela `Questão` diretamente no detalhe/revisão.
- **Fora de escopo**: exportação em lote (explicitamente fora da v1) e a tela dividida de revisão (Tarefa 12).

## Dependências

- [08 — API de Questões, busca textual/trigrama, revisão humana e edição de conteúdo/mídia](08-api-questoes-busca-revisao-edicao-midia.md)
- [09 — Shell global da SPA e seção Provas (Ingestão, Gabarito e Reprocessamento)](09-frontend-shell-e-ingestao-provas.md)

## Critérios de aceite

- [x] Filtros principais e popover "Mais filtros" mapeiam corretamente para os query params de `GET /api/v1/questoes` e permanecem sincronizados com a `Taxonomia` ativa.
- [x] Filtro de `Disciplina` envia `incluir_secundarias=true` por padrão e alterna para `false` ao ativar "Somente principal".
- [x] Cards exibem todos os badges previstos (`Pendente`, `Prioritária`, `Aprovada`, `Divergência`, `Anulada`, `Disciplina arquivada`) e ícones de `Ativo Visual` / `Alerta de Extração`.
- [x] Botão **"Revisar este recorte (N)"** navega para `Revisão` preservando o recorte filtrado atual.
- [x] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro.

## Verificação

- Testes Vitest + Testing Library em `frontend/src/features/questoes/` cobrindo combinação de filtros, toggle "Somente principal", renderização de badges, estados vazios e navegação para revisão do recorte.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

**Implementação**:
- **Seção `Questões` (`frontend/src/features/questoes/`)**: `QuestoesPage.tsx` (rota `questoes` em `frontend/src/app/router.tsx`), `FiltrosBar.tsx` (busca com debounce de 300 ms, `Disciplina` com "Somente principal", `Prova`, `Ano` e `Status de revisão`), `MaisFiltrosPopover.tsx` (contador de filtros ativos), `QuestaoCard.tsx`, `filtrosUrl.ts` (filtros ↔ URL, saneamento de valores inválidos e hrefs de revisão) e `questoesStatus.ts` (derivação dos badges).
- **Cliente HTTP (`frontend/src/api/`)**: `questoes.ts` (`listarQuestoes`, `useQuestoesQuery` com `placeholderData` restrito à mesma `Taxonomia`) e `queryKeys.questoes.list`.
- **UI**: `frontend/src/components/ui/popover.tsx` sobre `@radix-ui/react-popover` (dependência nova em `frontend/package.json`, autorizada).
- **Backend (mudança mínima, autorizada)**: campo `possui_ativos_visuais` em `ItemQuestaoResponse` (`backend/src/presentation/api/schemas_questoes.py`), preenchido em `_serializar_item` (`backend/src/presentation/api/v1/questoes.py`) com os Ativos Visuais já carregados em lote pela consulta, sem N+1. Teste de integração em `backend/tests/integration/test_api_questoes.py`. `frontend/src/api/schema.d.ts` regenerado com `make types`.
- **Contrato de navegação para a Tarefa 12**: "Revisar este recorte (N)" leva a `/revisao?<filtros do recorte>&taxonomia=<id>`; o card acrescenta `questao=<id>`. A rota `revisao` continua placeholder.

**Decisões tomadas durante a execução**:
- Toda consulta envia `taxonomia_id` da `Taxonomia` ativa. Trocar a `Taxonomia` limpa `disciplina_id`, `topico`, `incluir_secundarias` e `pagina`.
- `Prova / Ano` virou dois seletores (`Prova` e `Ano`).
- Os cards mostram o nome da `Disciplina`, mapeado do código devolvido pela API.

**Gate de verificação**: cinco iterações. As iterações r4 e r5 foram autorizadas pelo usuário além do limite de três gates, com ondas reduzidas.
- r1: reprovada. Achados: página além do total sem saída, parâmetros inválidos enviados ao backend, "Somente principal" preso, enums digitados à mão, carregamento eterno sem `Taxonomia`, consulta intermediária na troca de `Taxonomia`, contador "(0)" durante o carregamento, ajustes de padrão e lacunas de teste.
- r2: reprovada. Achados: `pagina` acima de 100000, `disciplina_id` em maiúsculas descartado, rótulo "Página 2 de 1", total e botão sumindo durante o recarregamento.
- r3: reprovada. Durante o recarregamento, o botão mostrava o N antigo com o link dos filtros novos, e o estado vazio antigo continuava na tela.
- r4: reprovada por um Minor. O cabeçalho "0 questão(ões)" ainda aparecia ao recarregar a partir de um recorte vazio.
- r5: aprovada. Reviewer de requisitos `APPROVE` e auditor forense `CLEAN`. Em todas as iterações, desfazer cada correção derrubou o teste de regressão correspondente.
- Victory audit independente: `VICTORY CONFIRMED`, com os resultados reexecutados conferindo com os alegados.

**Comandos reexecutados no victory audit**:
- `frontend/`: `pnpm type-check`, `pnpm lint` e `pnpm build` com exit 0. `pnpm test` com exit 0, 8 arquivos e 93 testes. Em `features/questoes/`: `QuestoesPage.test.tsx` 29, `filtrosUrl.test.ts` 14, `questoesStatus.test.ts` 4.
- `backend/`: `uv run pytest` com 308 passed.
- Raiz: `make lint` e `make types` com exit 0, e `schema.d.ts` idêntico antes e depois.

**Pendências**:
- Validação manual no navegador contra o backend real fica para a Tarefa 15.
- Durante o recarregamento por troca de página, Anterior e Próxima usam o total de páginas da resposta anterior (`QuestoesPage.tsx`).
- Voltar no histórico para uma entrada de outra `Taxonomia` não restaura `Disciplina`, `Tópico` e página dessa entrada, porque a limpeza usa `replace`.
- Um `Ano` da URL que não pertence a nenhuma `Prova` deixa o seletor de `Ano` vazio, embora o filtro seja aplicado.
- Ajustes de padrão não feitos:
  - constante `TODAS` duplicada em `FiltrosBar.tsx` e `MaisFiltrosPopover.tsx`;
  - `SITUACOES` sem `Record`;
  - `FLAGS` repete `FLAG_KEYS`;
  - export sem uso em `filtrosUrl.ts`;
  - leitura posicional da query key em `api/questoes.ts`;
  - opções repetidas no helper `renderQuestoes`.
- A exaustividade dos enums de filtro (`StatusRevisao`, `SituacaoGabarito`) é garantida por `pnpm type-check`, sem teste Vitest.
- O ramo `questoes` de `PlaceholderSectionPage.tsx` ficou sem uso.
- Os contadores de revisão do backend (`contadores`) são globais da `Taxonomia` e ignoram os filtros. Por isso o N do recorte usa `total`.
- Decisão do usuário: trabalho feito na branch `main`, como nas Tarefas 09 e 10.
