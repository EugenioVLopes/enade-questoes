# 15 — Validação ponta a ponta em provas reais (2017/2019/2023), `validacao.md` e guia local

Status: `em andamento`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Mapa: [mapa.md](../mapa.md)

## Contexto

Com todas as camadas do backend, da interface web e do CLI `enade-eval` implementadas, precisamos exercitar o sistema inteiro contra as 3 provas oficiais reais do ENADE de Engenharia de Computação (`2017`, `2019`, `2023` em `data/enade/`), registrar todas as evidências e limitações em `docs/planejamento-inicial/validacao.md`, reconciliar `explicacao.md` (de **proposto** para **implementado** citando arquivos e linhas reais) e entregar o `README.md` na raiz com o guia enxuto de execução local.

## Entrega observável

Aplicação validada ponta a ponta nas provas reais locais do INEP, `docs/planejamento-inicial/validacao.md` preenchido com matriz de critérios/evidências, `docs/planejamento-inicial/explicacao.md` reconciliado com o código real e `README.md` na raiz documentando setup, execução e uso do `enade-eval`.

## Escopo e limites

- **Execução de suítes completas automatizadas**:
  - Backend: `uv run ruff check .`, `uv run lint-imports`, `uv run pytest` (unitários + integração PostgreSQL + `enade_real`).
  - Contratos: `make types` sem diff pendente.
  - Frontend: `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build`.
- **Roteiro de validação ponta a ponta em provas reais (`data/enade/{2017,2019,2023}/`)**:
  - Ingerir `ENADE 2023` (+ gabarito `***`), `ENADE 2019` (+ gabarito com `ANULADA` e alternativas em 2 colunas) e `ENADE 2017` (acionando fallback automático `force_full_page_ocr=True` + alerta `pdf_via_ocr`).
  - Verificar casos de borda reais: recorte automático `formula_recorte` na Q13/2023, alerta informativo `fonte_symbol_detectada` na Q10/2023, edição de alternativas na Q15/2023 com reavaliação automática de `alternativas_incompletas` e conferência de página original do PDF.
  - Executar classificação multimodal em amostra ou edição completa, revisar/aprovar/corrigir na `Revisão`, testar busca `TSVECTOR`+`pg_trgm` em `Questões`, testar reclassificação com `Divergência de Reclassificação` e testar atualização independente de `Gabarito` + `Reprocessar Prova` preservando `editada_manualmente`.
  - Rodar `enade-eval exportar-ouro`, `enade-eval avaliar`, `enade-eval comparar` e `enade-eval historico`.
- **Documentação de encerramento**:
  - Criar `docs/planejamento-inicial/validacao.md` com matriz de critérios, comandos exatos executados, resultados obtidos e limitações/pendências de aceite manual.
  - Atualizar `docs/planejamento-inicial/explicacao.md` reconciliando texto e diagramas com o código implementado (com referências a arquivos e linhas, distinguindo implementado de aceite manual).
  - Criar `README.md` na raiz com pré-requisitos (`uv`, `pnpm`, Docker), setup (`.env`, `make db-up`, `make migrate`, `make dev`), arquitetura resumida e comandos do `enade-eval`.
- **Fora de escopo**: commits/push automáticos (exigem autorização explícita) ou inclusão de `data/` e artefatos de IA/MCP no Git.

## Dependências

- [09 — Shell global da SPA e seção Provas (Ingestão, Gabarito e Reprocessamento)](09-frontend-shell-e-ingestao-provas.md)
- [10 — Seção Taxonomias, Perfis de Classificação e Execuções](10-frontend-taxonomias-perfis-execucoes.md)
- [11 — Seção Questões (consulta combinada, busca e filtros)](11-frontend-consulta-questoes.md)
- [12 — Seção Revisão (tela dividida 60/40, fila priorizada, divergências e atalhos)](12-frontend-revisao-humana-e-divergencias.md)
- [13 — Edição sob demanda de conteúdo/mídia, conferência do PDF e alertas na Revisão](13-frontend-edicao-conteudo-midia-e-pdf.md)
- [14 — CLI de avaliação offline (`enade-eval`), Conjunto-Ouro e histórico IA × Humano](14-cli-avaliacao-conjunto-ouro-e-historico.md)

## Critérios de aceite

- [ ] Todas as suítes automatizadas (`make lint`, `make test`, `make types`, `pnpm build`) passam com exit code `0`.
- [ ] Ingestão real das 3 edições (`2017`, `2019`, `2023`) conclui sem vazamento de memória do Docling, registrando corretamente alertas esperados (`pdf_via_ocr` em 2017, `formula_nao_decodificada` + `formula_recorte` em Q13/2023, `ANULADA` em 2019).
- [ ] Fluxos de revisão, edição de conteúdo/mídia, divergências, busca textual e `enade-eval` verificados com evidências registradas em `docs/planejamento-inicial/validacao.md`.
- [ ] `docs/planejamento-inicial/explicacao.md` reconciliado com o código real e `README.md` criado na raiz.
- [ ] Itens que dependem de aceite visual/manual do usuário claramente separados como pendentes até confirmação explícita.

## Verificação

- Executar `make lint && make test && make types` + build do frontend + roteiro E2E local e registrar todas as saídas em `docs/planejamento-inicial/validacao.md`.

## Evidências e pendências

Pendente de execução.
