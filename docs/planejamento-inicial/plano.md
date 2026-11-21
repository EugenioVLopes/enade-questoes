# Plano — Enade Questões (v1)

Status: **em andamento** (Fase 1 / Checkpoint 1 concluídos: Tarefas 01, 02 e 03 entregues; Fase 2 em andamento: Tarefas 04 e 05 concluídas).

Pedido original e critérios de aceite da fase de planejamento: [task.md](task.md).
Mapa de decisões (11/11 tickets resolvidos): [mapa.md](mapa.md).
Arquitetura detalhada e fluxos propostos (com diagramas Mermaid): [explicacao.md](explicacao.md).
Vocabulário canônico do domínio (16 termos): [GLOSSARY.md](../../GLOSSARY.md).

## Visão geral e estratégia

Construir a v1 local do **Enade Questões** como um monorepo (`backend/` + `frontend/`) com execução nativa orquestrada por `Makefile` e banco **PostgreSQL 16** em `compose.yaml`. A estratégia prioriza **fatias verticais entregáveis**, respeitando a fronteira hexagonal de 4 camadas no backend (`domain`, `application`, `infrastructure`, `presentation`) verificada por `import-linter`, sincronização automática de tipos OpenAPI → TypeScript (`openapi-typescript`) e reaproveitamento dos dois protótipos já validados em provas reais do INEP ([protótipo 05](../../prototypes/05-extracao-pdf/run_prototype.py) e [protótipo 07](../../prototypes/07-classificacao-llm/run_prototype.py)).

### Decisões arquiteturais consolidadas (referência rápida)

- **Extração documental** ([decisão 05](decisoes/05-prototipar-extracao-prova-real.md), [decisão 10](decisoes/10-tratamento-edicao-midia-e-casos-borda.md)): Docling 2.151.1 (`PyPdfiumDocumentBackend`, `pytorch-cpu`, sem `CodeFormulaV2`) executado em **subprocesso isolado** + `pdfplumber` para gabaritos + `pypdfium2` para recorte automático de `formula_nao_decodificada` e visualização sob demanda da página original do PDF.
- **Domínio agnóstico e append-only** ([decisão 06](decisoes/06-modelo-de-dominio-e-glossario.md), [GLOSSARY.md](../../GLOSSARY.md)): conteúdo oficial de `Prova`/`Questão`/`Alternativa`/`Ativo Visual`/`Gabarito` desacoplado de múltiplas `Taxonomia`s; `Disciplina`s arquiváveis (`ativa = false`); `Classificação` imutável quando corrigida por humano (aprovação in-place, correção cria registro `origem = humana`); `Divergência de Reclassificação` aberta apenas quando mudam `Disciplina` principal ou secundárias.
- **Classificação multimodal e resiliência** ([decisão 04](decisoes/04-avaliar-provedores-api-llm.md), [decisão 07](decisoes/07-estrategia-classificacao-e-reclassificacao.md)): porta única `ClassificadorMultimodal` com `ClienteOpenAICompativel` (Google Gemini AI Studio Free Tier na v1, pronto para `Qwen/vLLM` via `.env`), JSON Schema plano dinâmico, envio obrigatório de `Ativo Visual`s em PNG base64, `temperature=0`, `max_tokens >= 4096`, cache determinístico em `DATA_DIR/cache/llm/`, rate-limiting + backoff e travas determinísticas com `revisao_prioritaria` guiada também por `Alerta de Extração` crítico.
- **Persistência, busca e execução local** ([decisão 08](decisoes/08-arquitetura-e-simplificacao-stack.md)): PostgreSQL 16 (`TSVECTOR` `portuguese`+`unaccent` + `pg_trgm` com índices GIN), `DATA_DIR` atrás de `ArmazenamentoArquivos`, worker local sequencial sem Redis/Celery com recuperação de `interrompida` no boot e polling TanStack Query (~2 s).
- **Interface web v1** ([decisão 09](decisoes/09-fluxos-interface-web-revisao-consulta.md), [decisão 10](decisoes/10-tratamento-edicao-midia-e-casos-borda.md)): SPA React/Vite/Tailwind/shadcn em 4 seções (`Questões`, `Revisão`, `Provas`, `Taxonomias`), seletor global de `Taxonomia` ativa, pílula do worker local, tela dividida 60/40 na `Revisão` com Markdown GFM + KaTeX sanitizado, edição sob demanda de conteúdo/mídia sem disparo automático de LLM e atalhos de teclado.
- **Qualidade e avaliação offline** ([decisão 11](decisoes/11-metricas-qualidade-e-conjunto-ouro.md)): `Conjunto-Ouro` por `Taxonomia` exportado para `evals/golden/<taxonomia_codigo>.json` via chave natural e CLI `enade-eval` 100% somente-leitura no PostgreSQL (`exportar-ouro`, `avaliar`, `comparar`, `historico`) com métricas determinísticas em 3 camadas e gate híbrido para novos perfis e migração `Qwen/vLLM`.

### Skills previstas por etapa

- **Planejamento e documentação**: `planning-and-task-breakdown` (decomposição vertical com checkpoints) e `design-doc-mermaid` (diagramas Mermaid em [explicacao.md](explicacao.md)).
- **Implementação backend**: `tdd` (testes primeiro nas regras de domínio, travas, alertas, reconciliação e métricas), `python-patterns`, `python-testing` e `postgres-patterns`.
- **Implementação frontend**: `react-patterns`, `vite-patterns` e `frontend-patterns`.
- **Revisão e validação**: revisão de código separada para requisitos/padrões ao fim de cada checkpoint antes de qualquer commit.

## Componentes e estrutura prevista no repositório

```text
enade-questoes/
├── compose.yaml                     # PostgreSQL 16 local
├── Makefile                         # dev, db-up, migrate, seed, test, lint, types, golden-*
├── .env.example                     # DATABASE_URL, DATA_DIR, LLM_*
├── GLOSSARY.md                      # 16 termos canônicos
├── evals/golden/                    # Snapshots JSON versionados de Conjunto-Ouro
├── backend/
│   ├── pyproject.toml               # Python 3.13, uv, FastAPI, SQLAlchemy 2, Alembic, Docling, pdfplumber, ruff, pytest, import-linter
│   ├── alembic/                     # Migrations PostgreSQL (unaccent, pg_trgm, TSVECTOR)
│   ├── src/
│   │   ├── domain/                  # Entidades, VOs, alertas, travas pós-LLM, divergência, métricas
│   │   ├── application/             # Casos de uso, portas (Protocol), worker local, serviços de avaliação
│   │   ├── infrastructure/          # PostgreSQL/SQLAlchemy, DATA_DIR, Docling subprocesso, pdfplumber, pypdfium2, ClienteOpenAICompativel
│   │   └── presentation/            # FastAPI /api/v1/..., schemas HTTP, composition root, CLI enade-eval
│   └── tests/                       # unit/ (domínio/aplicação), integration/ (Postgres/API/extração)
└── frontend/
    ├── package.json                 # pnpm, React, TypeScript, Vite, Tailwind, shadcn/ui, TanStack Query, React Router, Zod, KaTeX, Vitest
    └── src/
        ├── api/                     # Tipos gerados por openapi-typescript + cliente HTTP
        ├── components/              # Layout shell, seletor global de Taxonomia, pílula do worker, Markdown/KaTeX
        └── features/                # provas/, taxonomias/, questoes/, revisao/
```

## Decomposição em tarefas e ordem de execução

Cada tarefa é um arquivo independente em `tarefas/` executável em uma sessão focada. Estados e checklists detalhados vivem apenas dentro de cada arquivo de tarefa.

### Fase 1 — Fundação, Domínio e Persistência

| Ordem | Tarefa | Componente | Depende de |
|---|---|---|---|
| 01 | [Scaffolding do monorepo, infraestrutura local e healthcheck](tarefas/01-scaffolding-monorepo-infra-local.md) | Monorepo | — |
| 02 | [Núcleo de domínio, regras determinísticas e portas](tarefas/02-nucleo-dominio-regras-deterministicas.md) | Backend | 01 |
| 03 | [Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial](tarefas/03-persistencia-postgres-alembic-seed.md) | Backend | 02 |

**Checkpoint 1 — Fundação e Persistência** (**concluído**):
- [x] `import-linter` verde garantindo isolamento de `src/domain/` (3/3 contratos mantidos);
- [x] `pytest` verde no domínio e nos repositórios contra PostgreSQL 16 real (`compose.yaml`) (`138 passed`);
- [x] Migration sobe limpa (`0001_schema_inicial`) e `make seed` da `Taxonomia` ENADE (`enade-eng-computacao`, 18 `Disciplina`s) + `Perfil de Classificação` `v2-fronteiras:v1` é idempotente;
- [x] `GET /api/v1/health` responde `200` com banco conectado e frontend compila limpo.

### Fase 2 — Ingestão Documental e Classificação Multimodal (Backend ponta a ponta)

| Ordem | Tarefa | Componente | Depende de |
|---|---|---|---|
| 04 | [Adaptadores de extração documental (Docling em subprocesso, pdfplumber e pypdfium2)](tarefas/04-adaptadores-extracao-docling-pdfplumber.md) | Backend | 02, 03 |
| 05 | [Worker local sequencial e API de Provas, Ingestão, Gabarito e Mídia](tarefas/05-worker-local-api-provas-ingestao.md) | Backend | 03, 04 |
| 06 | [Classificador multimodal OpenAI-compatível, cache determinístico e travas](tarefas/06-classificador-multimodal-cache-travas.md) | Backend | 02, 03 |
| 07 | [API de Taxonomias, Perfis de Classificação e Execuções de Classificação](tarefas/07-api-taxonomias-perfis-execucoes.md) | Backend | 03, 05, 06 |

**Checkpoint 2 — Pipeline Backend Ponta a Ponta**:
- Ingestão de prova real (`data/enade/2023/`) via `POST /api/v1/provas` extrai 29 questões do CE, gabarito, `Ativo Visual`s e `Alerta de Extração`s devolvendo RAM do subprocesso Docling ao SO;
- Encadeamento e disparo isolado de `Execução de Classificação` gravam classificações com snapshot congelado, cache LLM e tratamento de `Divergência de Reclassificação`;
- `make types` gera os tipos TypeScript sem erros a partir do OpenAPI.

### Fase 3 — Consulta, Revisão Humana, Edição de Conteúdo/Mídia e Interface Web

| Ordem | Tarefa | Componente | Depende de |
|---|---|---|---|
| 08 | [API de Questões, busca textual/trigrama, revisão humana e edição de conteúdo/mídia](tarefas/08-api-questoes-busca-revisao-edicao-midia.md) | Backend | 03, 05, 07 |
| 09 | [Shell global da SPA e seção Provas (Ingestão, Gabarito e Reprocessamento)](tarefas/09-frontend-shell-e-ingestao-provas.md) | Frontend | 01, 05, 07 |
| 10 | [Seção Taxonomias, Perfis de Classificação e Execuções](tarefas/10-frontend-taxonomias-perfis-execucoes.md) | Frontend | 07, 09 |
| 11 | [Seção Questões (consulta combinada, busca e filtros)](tarefas/11-frontend-consulta-questoes.md) | Frontend | 08, 09 |
| 12 | [Seção Revisão (tela dividida 60/40, fila priorizada, divergências e atalhos)](tarefas/12-frontend-revisao-humana-e-divergencias.md) | Frontend | 08, 09 |
| 13 | [Edição sob demanda de conteúdo/mídia, conferência do PDF e alertas na Revisão](tarefas/13-frontend-edicao-conteudo-midia-e-pdf.md) | Frontend | 08, 12 |

**Checkpoint 3 — Aplicação Web Completa**:
- Todas as 4 seções da SPA (`Questões`, `Revisão`, `Provas`, `Taxonomias`) funcionando contra a API local;
- Testes Vitest cobrindo renderização Markdown+KaTeX sanitizada, filtros, fluxos de revisão/divergência e edição de conteúdo/mídia;
- Verificação manual do fluxo completo em navegador com uma prova real ingerida.

### Fase 4 — Qualidade, Avaliação Offline (`enade-eval`) e Aceite Final

| Ordem | Tarefa | Componente | Depende de |
|---|---|---|---|
| 14 | [CLI de avaliação offline (`enade-eval`), Conjunto-Ouro e histórico IA × Humano](tarefas/14-cli-avaliacao-conjunto-ouro-e-historico.md) | Backend / CLI | 03, 06, 07 |
| 15 | [Validação ponta a ponta em provas reais (2017/2019/2023), `validacao.md` e guia local](tarefas/15-validacao-e2e-provas-reais-e-documentacao.md) | Monorepo / Docs | 09, 10, 11, 12, 13, 14 |

**Checkpoint 4 — Pronto para Uso Local (v1)**:
- Suítes completas (`make lint`, `make test`, `make types`, build frontend) verdes;
- Validação ponta a ponta executada nas 3 edições reais do ENADE (`2017`, `2019`, `2023`), com relatório consolidado em `validacao.md`;
- Fluxos de [explicacao.md](explicacao.md) reconciliados com o código implementado.

### Oportunidades de paralelismo

- Após a **Tarefa 03**: **Tarefa 04** (extração documental) e **Tarefa 06** (classificador multimodal) escrevem em módulos independentes e podem rodar em paralelo.
- Após as **Tarefas 08 e 09**: **Tarefa 10** (`Taxonomias`), **Tarefa 11** (`Questões`), **Tarefa 12** (`Revisão`) e **Tarefa 14** (CLI `enade-eval`) têm escopos de escrita independentes e podem rodar em paralelo.
- **Sequenciais obrigatórios**: cadeia `01 → 02 → 03`, migrations Alembic, e `12 → 13` (edição acoplada à tela dividida de revisão).

## Riscos e mitigações

| Risco | Impacto | Mitigação planejada |
|---|---|---|
| Consumo de RAM do Docling (~2,3 GB) travar a máquina local ou vazar no processo do FastAPI | Alto | Worker local sequencial (1 tarefa pesada por vez) + execução do Docling em subprocesso isolado encerrado ao fim da `Ingestão` (Tarefas 04 e 05). |
| CMap ToUnicode corrompido (como ENADE 2017) ou fórmulas não decodificadas (como Q13/2023) | Alto | Detector determinístico de mojibake acionando `force_full_page_ocr=True`, recorte automático de `FormulaItem` via `pypdfium2` (`formula_recorte`), `Alerta de Extração` crítico e edição/conferência do PDF na `Revisão` (Tarefas 04, 08 e 13). |
| Rate-limit `HTTP 429` ou *thinking* oculto consumindo `max_tokens` na API gratuita de LLM | Médio | `LLM_MAX_RPM` local + backoff exponencial + `max_tokens >= 4096` + controle de *reasoning* por provedor + cache determinístico em disco + retomada parcial de `Execução de Classificação` (Tarefas 06 e 07). |
| Drift de tipos entre FastAPI e React/TypeScript | Médio | Geração automática via `openapi-typescript` (`make types`) verificada em cada tarefa que altera endpoints (Tarefas 05, 07 e 08). |
| Superconfiança sistemática do LLM (`0,90–0,99`) mascarar erros na fila de revisão | Médio | `revisao_prioritaria` nunca depende só de `confianca`; é forçada por `Alerta de Extração` crítico e saneamentos pós-LLM, e a taxa de erro em alta confiança (`>= 0,85`) é medida no `enade-eval` (Tarefas 02, 06 e 14). |
| Reprocessamento de `Prova` destruir correções manuais de texto ou mídia | Médio | Marcador `editada_manualmente` na `Questão` e `sobrescrever_editadas = false` por padrão em `POST /api/v1/provas/{id}/reprocessar` (Tarefas 02, 05 e 09). |

## Verificações planejadas

- **Backend**: `ruff check` / `ruff format --check`, `import-linter`, `pytest` (unitários de domínio/aplicação sem I/O + integração contra PostgreSQL 16 real + testes de contrato de extração nos PDFs locais em `data/enade/`).
- **Contratos**: `make types` gerando tipos TypeScript limpos a partir do schema OpenAPI sem diff pendente.
- **Frontend**: `pnpm type-check`, `pnpm lint`, `pnpm test` (Vitest + Testing Library), `pnpm build`.
- **Avaliação offline**: `enade-eval` testado com fakes determinísticos na suíte automatizada e smoke test real em amostra curada na Tarefa 15.
- **Aceite manual**: revisão visual e funcional no navegador dos fluxos de `Provas`, `Taxonomias`, `Questões`, `Revisão` e edição de conteúdo/mídia (registrado em `validacao.md` na Tarefa 15).
