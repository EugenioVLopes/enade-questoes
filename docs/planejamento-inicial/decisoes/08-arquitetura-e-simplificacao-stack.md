# Definir arquitetura da aplicação, persistência e simplificação da stack

Type: grilling
Status: resolved
Blocked by: 05, 06

## Question

Buscando uma arquitetura limpa e sem complexidade desnecessária para um projeto local v1, qual arquitetura devemos fechar para:

1. **Estrutura do repositório e camadas** (monorepo com `backend/` em Python 3.13 + `uv` + FastAPI hexagonal enxuta e `frontend/` em Vite + React + TypeScript + Tailwind + shadcn/ui);
2. **Persistência de dados e arquivos**: SQLite vs PostgreSQL (via Docker Compose), SQLAlchemy + Alembic, armazenamento local de PDFs originais e imagens recortadas;
3. **Execução do processamento**: processamento assíncrono simples no próprio backend (ex.: `BackgroundTasks` / job table em banco) vs fila externa (Celery + RabbitMQ/Redis);
4. **Contratos HTTP principais** entre frontend e API (upload/ingestão, status do processamento, listagem/busca, revisão humana, gerenciamento de taxonomias e disparo de reclassificação).

## Answer

### 1. Estrutura do monorepo, camadas e execução local

- **Monorepo (`backend/` + `frontend/`) com execução local nativa como padrão**:
  - `Makefile` na raiz orquestra o dia a dia (`make dev`, `make test`, `make lint`, `make migrate`, `make types`), subindo apenas o serviço `postgres` via `compose.yaml` (`docker compose up -d postgres`) enquanto backend (`uv`) e frontend (`pnpm` + Vite) rodam nativamente — evitando rebuilds pesados de imagem Python com PyTorch/Docling e reaproveitando o cache local dos modelos. Empacotamento Docker da aplicação fica opcional.
- **Backend (`backend/`) — Arquitetura hexagonal enxuta em 4 camadas**:
  - Python 3.13, `uv`, FastAPI, Pydantic v2, `ruff`, `pytest` e `import-linter` garantindo fronteiras mecânicas (mantendo a organização enxuta, sem fragmentar em dezenas de subcontextos DDD):
    - `src/domain/`: entidades, regras determinísticas, `Alerta de Extração`, travas pós-LLM e política de `Divergência de Reclassificação` (zero imports de FastAPI, SQLAlchemy, Docling, `pdfplumber` ou OpenAI).
    - `src/application/`: casos de uso e portas (`Protocol`) — `ExtratorProva`, `ExtratorGabarito`, `ClassificadorMultimodal`, `ArmazenamentoArquivos`, repositórios de domínio e controle do worker local.
    - `src/infrastructure/`: adaptadores concretos (Docling 2.151.1 em subprocesso, `pdfplumber`, `ClienteOpenAICompativel`, SQLAlchemy 2 + PostgreSQL, armazenamento em `DATA_DIR` e cache LLM em disco).
    - `src/presentation/`: rotas FastAPI (`/api/v1/...`), schemas HTTP Pydantic e `composition root`.
- **Frontend (`frontend/`)**:
  - Vite + React + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query + React Router + Zod (validação de formulários) + Vitest, gerenciado com **`pnpm`**.
  - **Sincronização de tipos Backend↔Frontend**: geração automática dos tipos TypeScript a partir do esquema OpenAPI do FastAPI via `openapi-typescript` (`make types`), eliminando drift manual entre DTOs.

### 2. Persistência relacional, busca textual e arquivos locais

- **Banco de dados relacional**: **PostgreSQL 16** via `compose.yaml` enxuto + `psycopg[binary]` + **SQLAlchemy 2** + **Alembic** (tipos nativos `JSONB`/`UUID`, escrita concorrente nativa e recursos de busca full-text).
- **Busca textual nativa no PostgreSQL**: combinação de **`TSVECTOR` (dicionário `portuguese` + extensão `unaccent`)** com **`pg_trgm`** e índices GIN sobre enunciado, alternativas e `Tópico`s — cobrindo flexões/acentuação em português e termos técnicos exatos/código (`OSPF`, `VHDL`, `TCP`, `O(n log n)`) sem motor de busca externo.
- **Armazenamento de arquivos locais (`DATA_DIR` fora do Git, atrás da porta `ArmazenamentoArquivos`)**:
  - Duráveis em `DATA_DIR/storage/provas/{prova_id}/`: `prova.pdf`, `gabarito.pdf`, `extracao_bruta.json` (saída bruta do Docling preservada como fonte da verdade) e `ativos/{ativo_id}.png` (`Ativo Visual`s recortados).
  - Descartáveis em `DATA_DIR/cache/llm/{sha256}.json`: cache determinístico de respostas LLM, limpável sem afetar o banco relacional.
  - Entrega de mídia via endpoint controlado `GET /api/v1/ativos-visuais/{id}/arquivo` (com `ETag` e `Cache-Control`), sem expor `data/` diretamente por `StaticFiles`.

### 3. Execução assíncrona local (sem Redis/RabbitMQ/Celery)

- **Estado persistido no PostgreSQL + worker local sequencial gerenciado pelo backend**:
  - Processa **1 tarefa pesada por vez** para proteger a máquina local contra estouro de RAM.
  - **Isolamento de memória do Docling**: cada `Ingestão` executa o Docling em **subprocesso dedicado**, garantindo devolução imediata dos ~2,3 GB de RAM do PyTorch ao SO ao final da extração.
  - **`Execução de Classificação` incremental**: processa questão a questão com rate-limiting (`LLM_MAX_RPM`), backoff exponencial e gravação incremental no PostgreSQL + cache em disco.
  - **Recuperação de reinício**: no boot do backend, qualquer `Ingestão` ou `Execução de Classificação` deixada em `processando` é marcada como `interrompida` para retomada segura sob demanda (reaproveitando questões já salvas e cache LLM).
- **Desacoplamento e acompanhamento pela UI**:
  - `Ingestão` e `Execução de Classificação` são fluxos independentes (`202 Accepted`); a `Ingestão` aceita opcionalmente `(taxonomia_id, perfil_id)` para encadear a classificação inicial ao concluir, mas falhas na API de LLM nunca bloqueiam a persistência e revisão da `Prova`.
  - A UI acompanha o progresso via **polling leve no TanStack Query** (`refetchInterval` ~2 s enquanto `status in (pendente, processando)`), sem SSE/WebSocket na v1.

### 4. Contratos HTTP principais (`/api/v1/...`)

1. **Provas, Ingestão e Gabarito**:
   - `POST /api/v1/provas` (`multipart/form-data`: PDF da prova, PDF de gabarito opcional, `exame`, `curso`, `ano`, e `taxonomia_id`/`perfil_id` opcionais) → `202 Accepted`.
   - `GET /api/v1/provas` e `GET /api/v1/provas/{id}` (estado/progresso da `Ingestão`, contagens de `Questão`s e `Alerta de Extração`).
   - `POST /api/v1/provas/{id}/reprocessar` (reprocessamento explícito respeitando unicidade `(exame, curso, ano)`).
   - `PUT /api/v1/provas/{id}/gabarito` (atualização independente de `Gabarito` preliminar → definitivo sem perder classificações).
2. **Questões e `Ativo Visual`**:
   - `GET /api/v1/questoes` (filtros combináveis: `q`, `prova_id`, `ano`, `taxonomia_id`, `disciplina_id`, `incluir_secundarias`, `topico`, `status_revisao`, `revisao_prioritaria`, `com_divergencia`, `usa_disciplina_arquivada`, `situacao_gabarito`, `com_alerta_extracao` + paginação).
   - `GET /api/v1/questoes/{id}` (enunciado, alternativas, `Ativo Visual`s, `Gabarito`, alertas, classificações vigentes e histórico/divergências por `Taxonomia`).
   - `PATCH /api/v1/questoes/{id}` (edição curada do conteúdo extraído/gabarito; operações específicas de mídia seguem para [Definir tratamento e edição de mídia extraída e casos de borda do parser](./10-tratamento-edicao-midia-e-casos-borda.md)).
   - `GET /api/v1/ativos-visuais/{id}/arquivo`.
3. **Revisão humana e `Divergência de Reclassificação`**:
   - `POST /api/v1/questoes/{id}/classificacoes/{taxonomia_id}/aprovar` (aprovação in-place da sugestão vigente da IA).
   - `POST /api/v1/questoes/{id}/classificacoes/{taxonomia_id}/corrigir` (nova `Classificação` `origem=humana`, preservando a predição da IA).
   - `POST /api/v1/questoes/{id}/divergencias/{divergencia_id}/resolver` (`aceitar_candidata | manter_humana`).
4. **Taxonomias, Disciplinas e Perfis**:
   - `GET/POST /api/v1/taxonomias`, `PATCH /api/v1/taxonomias/{id}`.
   - `POST /api/v1/taxonomias/{id}/disciplinas`, `PATCH /api/v1/disciplinas/{id}` (inclui arquivamento `ativa=false`, sem exclusão física).
   - `GET/POST /api/v1/perfis-classificacao` (versões imutáveis de `Perfil de Classificação`).
5. **`Execução de Classificação` (inicial e reclassificação)**:
   - `POST /api/v1/execucoes-classificacao` (`taxonomia_id`, `perfil_id`, escopo por `prova_id` ou filtros/IDs, `incluir_revisadas: bool = false`) → `202 Accepted`.
   - `GET /api/v1/execucoes-classificacao`, `GET /api/v1/execucoes-classificacao/{id}` (progresso `processadas/total`, erros, divergências abertas, métricas de cache/tokens).
   - `POST /api/v1/execucoes-classificacao/{id}/retomar`.
6. **Operação**:
   - `GET /api/v1/health` (conectividade PostgreSQL + estado do worker local).

### 5. Glossário e ADRs

- Formalizado o 14º termo canônico **`Ingestão`** em [GLOSSARY.md](../../../GLOSSARY.md) como par simétrico de `Execução de Classificação` (evitando *upload*, *importação* e *job de PDF*).
- Não foram abertos ADRs em `docs/adr/` nesta etapa porque as decisões de infraestrutura (PostgreSQL local, worker sequencial sem broker, armazenamento em `DATA_DIR`) estão isoladas atrás de portas hexagonais e permanecem reversíveis.
