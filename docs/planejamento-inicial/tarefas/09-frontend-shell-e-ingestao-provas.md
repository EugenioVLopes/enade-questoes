# 09 — Shell global da SPA e seção Provas (Ingestão, Gabarito e Reprocessamento)

Status: `pendente`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Glossário: [GLOSSARY.md](../../../GLOSSARY.md) · Decisões: [fluxos da interface web](../decisoes/09-fluxos-interface-web-revisao-consulta.md), [reprocessamento seguro](../decisoes/10-tratamento-edicao-midia-e-casos-borda.md)

## Contexto

Com a API de `Provas`, `Ingestão`, `Gabarito` e `Taxonomias` pronta e tipada via `openapi-typescript`, esta tarefa entrega a estrutura global da SPA (navegação em 4 seções, seletor global de `Taxonomia` ativa, pílula do worker local) e a primeira seção funcional ponta a ponta: **`Provas`**, permitindo ingerir PDFs reais do ENADE, acompanhar progresso e atualizar gabaritos pelo navegador.

## Entrega observável

Aplicação web navegável com layout fixo (`Questões`, `Revisão` com badge, `Provas`, `Taxonomias`), seletor global de `Taxonomia` ativa persistido na URL/sessão, pílula de progresso do worker via polling (~2 s) e seção `Provas` completa consumindo a API real.

## Escopo e limites

- **Cliente HTTP tipado e camada TanStack Query** (`frontend/src/api/`):
  - Wrapper fino sobre os tipos gerados em `make types`, tratando erros estruturados da API (incluindo `409 Conflict` de unicidade de `Prova`).
- **Shell global (`frontend/src/components/layout/`)**:
  - Barra lateral com as 4 seções canônicas: `Questões`, `Revisão` (com badge numérico de pendências + divergências sob a `Taxonomia` ativa), `Provas` e `Taxonomias`.
  - Cabeçalho global fixo com **seletor de `Taxonomia` ativa** (carregado de `GET /api/v1/taxonomias`, persistido na URL/sessão) e **pílula discreta do worker local** (visível enquanto houver `Ingestão` ou `Execução de Classificação` em `pendente | processando`, com polling TanStack Query a cada ~2 s e clique navegando ao detalhe).
  - Rótulos 100% aderentes aos termos canônicos de [GLOSSARY.md](../../../GLOSSARY.md).
- **Seção `Provas` (`frontend/src/features/provas/`)**:
  - Estado vazio inicial com CTA direto **"Ingerir primeira prova"**.
  - Formulário único de nova `Ingestão` (drawer/página) validado com Zod: upload obrigatório do PDF da `Prova`, upload opcional do PDF de `Gabarito`, campos `exame` (default `ENADE`), `curso` (`Engenharia de Computação`) e `ano`; seção **"Opções avançadas"** com faixa de questões CE pré-preenchida pela regra do ano (`09–35`, `10–38`, `16–45`); checkbox ligado por padrão **"Classificar automaticamente ao concluir"** usando a `Taxonomia` ativa e o `Perfil de Classificação` padrão.
  - Tratamento de duplicidade (`409 Conflict`): informa a `Prova` existente e oferece atalhos diretos para **Atualizar `Gabarito`** ou **Reprocessar `Prova`**.
  - Lista de `Prova`s com polling em tempo real (~2 s enquanto ativa), exibindo status, contagens de `Questão`s extraídas, `Alerta de Extração`s abertos, status da classificação encadeada e ações: **Atualizar `Gabarito`** (exibindo resumo imediato *mantidas / alteradas / anuladas*), **Reprocessar `Prova`** (diálogo de confirmação explícita com checkbox desligado por padrão *"Sobrescrever questões editadas manualmente"*), **"Tentar novamente"** em erro/interrompida e atalho **"Revisar questões desta prova"**.
- **Fora de escopo**: telas internas de `Taxonomias`, `Questões` e `Revisão` (apenas rotas placeholder limpas para as Tarefas 10–12).

## Dependências

- [01 — Scaffolding do monorepo, infraestrutura local e healthcheck](01-scaffolding-monorepo-infra-local.md)
- [05 — Worker local sequencial e API de Provas, Ingestão, Gabarito e Mídia](05-worker-local-api-provas-ingestao.md)
- [07 — API de Taxonomias, Perfis de Classificação e Execuções de Classificação](07-api-taxonomias-perfis-execucoes.md)

## Critérios de aceite

- [ ] Seletor global de `Taxonomia` ativa sincroniza com a URL/sessão e carrega automaticamente a `Taxonomia` semeada (`ENADE Engenharia de Computação`).
- [ ] Pílula do worker local aparece durante `Ingestão`/`Execução de Classificação` ativa com polling ~2 s e desaparece ao concluir.
- [ ] Formulário de nova `Ingestão` pré-preenche a faixa CE conforme o ano digitado (`2017`/`2019` → `9–35`, `2023` → `10–38`, `2026` → `16–45`), valida PDFs com Zod e envia `POST /api/v1/provas`.
- [ ] Duplicidade `409` orienta o usuário para atualizar `Gabarito` ou reprocessar a `Prova` existente.
- [ ] Diálogo de **Reprocessar `Prova`** mantém `sobrescrever_editadas = false` por padrão e modal de **Atualizar `Gabarito`** exibe o resumo *mantidas / alteradas / anuladas*.
- [ ] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro.

## Verificação

- Testes Vitest + Testing Library em `frontend/src/features/provas/` e `frontend/src/components/layout/` cobrindo estado vazio, regra de faixa por ano, duplicidade `409`, atualização de `Gabarito`, confirmação de reprocessamento e polling do worker.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

Pendente de execução.
