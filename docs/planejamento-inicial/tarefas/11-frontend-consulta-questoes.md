# 11 — Seção Questões (consulta combinada, busca e filtros)

Status: `pendente`

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

- [ ] Filtros principais e popover "Mais filtros" mapeiam corretamente para os query params de `GET /api/v1/questoes` e permanecem sincronizados com a `Taxonomia` ativa.
- [ ] Filtro de `Disciplina` envia `incluir_secundarias=true` por padrão e alterna para `false` ao ativar "Somente principal".
- [ ] Cards exibem todos os badges previstos (`Pendente`, `Prioritária`, `Aprovada`, `Divergência`, `Anulada`, `Disciplina arquivada`) e ícones de `Ativo Visual` / `Alerta de Extração`.
- [ ] Botão **"Revisar este recorte (N)"** navega para `Revisão` preservando o recorte filtrado atual.
- [ ] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro.

## Verificação

- Testes Vitest + Testing Library em `frontend/src/features/questoes/` cobrindo combinação de filtros, toggle "Somente principal", renderização de badges, estados vazios e navegação para revisão do recorte.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

Pendente de execução.
