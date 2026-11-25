# Enade Questões

Plataforma para ingestão, curadoria e classificação curricular de questões de provas acadêmicas. O sistema separa o conteúdo oficial de cada Prova das Taxonomias curriculares e protege revisões humanas contra sobrescrita em reclassificações.

## Funcionalidades

O backend em Python (FastAPI) e o frontend em React (Vite e TypeScript) entregam os fluxos abaixo:

- **Ingestão de Provas e Gabaritos.** Extração de Questões, Alternativas, Ativos Visuais e Alertas de Extração a partir de PDFs usando Docling e `pdfplumber`, com suporte a reprocessamento e atualização independente do Gabarito.
- **Taxonomias e Perfis de Classificação.** Cadastro de múltiplas Taxonomias, gerenciamento e arquivamento de Disciplinas, versionamento de Perfis de Classificação e execução assíncrona de classificações em um worker local.
- **Classificação multimodal com travas determinísticas.** Integração com provedores compatíveis com a API OpenAI (Google Gemini por padrão) usando cache local por hash SHA-256, controle de taxa, validação de domínio e priorização de itens incertos.
- **Consulta de Questões.** Busca textual híbrida no PostgreSQL (`TSVECTOR` combinado com `pg_trgm`) e filtros por Prova, Taxonomia, Disciplina, estado de revisão, confiança e alertas.
- **Revisão humana e Divergências de Reclassificação.** Interface dividida com renderização de Markdown e KaTeX, atalhos de teclado, histórico de classificações, aprovação condicional e resolução de divergências sem perder o histórico revisado.
- **Edição de conteúdo, Ativos Visuais, conferência de PDF e alertas na Revisão.** Modo sob demanda para editar enunciado (`Editar / Preview` em Markdown GFM e KaTeX), Alternativas `A`–`E` e Gabarito individual, gerenciar Ativos Visuais manualmente (upload, substituição, reordenação, vínculo e exclusão), visualizar páginas originais do PDF, confirmar alertas de inspeção (`pdf_via_ocr` e `fonte_symbol_detectada`) e disparar reclassificação individual explícita.
- **Avaliação offline (`enade-eval`), Conjunto-Ouro e histórico IA × Humano.** CLI somente-leitura no PostgreSQL para exportar snapshots de Conjunto-Ouro (`exportar-ouro`), executar avaliações com checagem *preflight* e métricas em 3 camadas (`avaliar`), validar regressões com gate híbrido (`comparar`) e consultar concordância entre predições da IA e revisões humanas (`historico`).

Recursos ainda planejados para a próxima entrega do projeto: relatório de validação ponta a ponta em provas reais (tarefa 15).

## Pré-requisitos

Instale as ferramentas abaixo antes de subir o ambiente local:

- Python 3.13 e `uv`
- Node.js 22 ou superior e `pnpm` (`pnpm@12.21.0` configurado em `frontend/package.json`)
- Docker e Docker Compose (para o PostgreSQL 16)
- Uma chave de API do Google AI Studio (`GEMINI_API_KEY`) ou um endpoint compatível com a API OpenAI que suporte entrada multimodal

## Como executar localmente

1. Crie o arquivo `.env` a partir do modelo e preencha `GEMINI_API_KEY` (ou configure outro provedor compatível com OpenAI):

```bash
cp .env.example .env
```

2. Suba o banco de dados PostgreSQL 16 em segundo plano:

```bash
make db-up
```

3. Instale as dependências do backend e do frontend:

```bash
cd backend && uv sync
cd ../frontend && pnpm install
```

4. Aplique as migrações do Alembic e carregue a Taxonomia e o Perfil de Classificação iniciais:

```bash
make migrate
make seed
```

5. Inicie a API e a interface web em paralelo:

```bash
make dev
```

Após a inicialização, os serviços ficam disponíveis nos endereços abaixo:

- Interface web: `http://127.0.0.1:5173` (o Vite encaminha requisições de `/api` para o backend)
- API REST: `http://127.0.0.1:8000`
- Documentação OpenAPI interativa: `http://127.0.0.1:8000/docs`

## Variáveis de ambiente

O arquivo `.env.example` lista todas as variáveis aceitas pelo backend e pelo `compose.yaml`:

| Variável            | Padrão                                                           | Descrição                                                               |
| ------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `POSTGRES_USER`     | `enade`                                                          | Usuário do PostgreSQL no container local.                               |
| `POSTGRES_PASSWORD` | `enade`                                                          | Senha do PostgreSQL no container local.                                 |
| `POSTGRES_DB`       | `enade_questoes`                                                 | Nome do banco criado no container local.                                |
| `POSTGRES_PORT`     | `5432`                                                           | Porta local exposta pelo PostgreSQL.                                    |
| `DATABASE_URL`      | `postgresql+psycopg://enade:enade@localhost:5432/enade_questoes` | String de conexão usada pelo SQLAlchemy e pelo Alembic.                 |
| `DATA_DIR`          | `./data/app`                                                     | Diretório local para PDFs, Ativos Visuais e cache de classificações.    |
| `GEMINI_API_KEY`    | vazio                                                            | Chave do Google AI Studio usada quando `LLM_API_KEY` não está definida. |
| `LLM_PROVIDER`      | `gemini_openai`                                                  | Identificador do provedor registrado nas execuções de classificação.    |
| `LLM_BASE_URL`      | `https://generativelanguage.googleapis.com/v1beta/openai/`       | URL base do endpoint compatível com a API OpenAI.                       |
| `LLM_API_KEY`       | vazio                                                            | Chave genérica que sobrescreve `GEMINI_API_KEY` para outros provedores. |
| `LLM_MODEL`         | `gemini-2.5-flash-lite`                                          | Nome do modelo multimodal usado nas classificações.                     |
| `LLM_MAX_RPM`       | `10`                                                             | Limite local de requisições por minuto (`0` desativa o limitador).      |
| `LLM_TIMEOUT_S`     | `60`                                                             | Tempo limite por chamada ao provedor, em segundos.                      |
| `LLM_MAX_TOKENS`    | `4096`                                                           | Limite de tokens de saída (piso mínimo aplicado pelo backend: `4096`).  |

Para trocar o Gemini por um servidor local compatível com OpenAI (como vLLM com Qwen), altere `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` e `LLM_MAX_RPM` no `.env`.

## Comandos do Makefile

Execute os comandos abaixo a partir da raiz do repositório:

| Comando             | Ação                                                                              |
| ------------------- | --------------------------------------------------------------------------------- |
| `make db-up`        | Sobe o container do PostgreSQL 16 e aguarda o healthcheck.                        |
| `make db-down`      | Para e remove os containers definidos em `compose.yaml`.                          |
| `make migrate`      | Executa `alembic upgrade head` no backend.                                        |
| `make seed`         | Popula a Taxonomia padrão e o Perfil de Classificação inicial.                    |
| `make dev-backend`  | Sobe o FastAPI com reload em `127.0.0.1:8000`.                                    |
| `make dev-frontend` | Sobe o Vite em `127.0.0.1:5173`.                                                  |
| `make dev`          | Executa `dev-backend` e `dev-frontend` em paralelo.                               |
| `make lint`         | Executa `ruff check`, `ruff format --check`, `lint-imports`, `tsc -b` e `eslint`. |
| `make test`         | Executa `pytest` no backend e `vitest run` no frontend.                           |
| `make types`         | Exporta o esquema OpenAPI do backend e regenera `frontend/src/api/schema.d.ts`.   |
| `make golden-export` | Exporta o Conjunto-Ouro da Taxonomia (`TAXONOMIA`, `SAIDA`) para JSON versionado. |
| `make eval-run`      | Executa avaliação offline (`OURO`, `PERFIL`, `EVAL_ARGS`) sem gravar no banco.    |
| `make eval-compare`  | Compara dois relatórios (`BASELINE`, `CANDIDATO`, `MODO_MIGRACAO=1`) via gate.    |
| `make eval-history`  | Exibe métricas históricas de concordância IA × Humano (`TAXONOMIA`).              |

Para rodar apenas os testes unitários do backend sem depender do banco de dados nem de chaves de API, execute:

```bash
cd backend && uv run pytest tests/unit -q
```

## Arquitetura e estrutura do repositório

O backend segue arquitetura hexagonal, com fronteiras de importação verificadas automaticamente por `import-linter` (configurado em `backend/pyproject.toml`). O frontend consome tipos gerados a partir do esquema OpenAPI do backend.

```text
enade-questoes/
├── backend/
│   ├── alembic/                 # Migrações de banco de dados
│   ├── src/
│   │   ├── domain/              # Regras de negócio puras, travas e métricas de avaliação
│   │   ├── application/         # Casos de uso, worker local e portas (Protocol)
│   │   ├── infrastructure/      # PostgreSQL, armazenamento local, extração de PDF e cliente LLM
│   │   └── presentation/        # Rotas FastAPI v1, esquemas Pydantic e exportação OpenAPI
│   └── tests/                   # Testes unitários e de integração
├── frontend/
│   └── src/
│       ├── api/                 # Cliente HTTP, React Query keys e schema.d.ts gerado
│       ├── app/                 # Shell global e roteamento
│       ├── components/          # Primitivos UI (Radix e Tailwind) e renderização Markdown
│       └── features/            # Seções Provas, Taxonomias, Questões e Revisão
├── docs/planejamento-inicial/   # Plano, decisões arquiteturais e tarefas do projeto
├── compose.yaml                 # PostgreSQL 16 local
├── GLOSSARY.md                  # Vocabulário canônico do domínio
└── Makefile                     # Comandos de desenvolvimento, testes e geração de tipos
```

## Documentação adicional

- [GLOSSARY.md](GLOSSARY.md): definições canônicas dos termos de domínio usados no código e na interface.
- [docs/planejamento-inicial/plano.md](docs/planejamento-inicial/plano.md): plano técnico completo e divisão das tarefas.
- [docs/planejamento-inicial/explicacao.md](docs/planejamento-inicial/explicacao.md): contexto de arquitetura e decisões de desenho do sistema.
- [docs/planejamento-inicial/mapa.md](docs/planejamento-inicial/mapa.md): índice das decisões e investigações da fase de planejamento.
