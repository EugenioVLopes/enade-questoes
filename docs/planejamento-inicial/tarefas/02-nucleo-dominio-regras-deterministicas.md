# 02 — Núcleo de domínio, regras determinísticas e portas

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Glossário: [GLOSSARY.md](../../../GLOSSARY.md) · Decisões: [modelo de domínio](../decisoes/06-modelo-de-dominio-e-glossario.md), [estratégia de classificação](../decisoes/07-estrategia-classificacao-e-reclassificacao.md), [tratamento de mídia e alertas](../decisoes/10-tratamento-edicao-midia-e-casos-borda.md), [métricas e conjunto-ouro](../decisoes/11-metricas-qualidade-e-conjunto-ouro.md)

## Contexto

Toda a lógica de negócio crítica do **Enade Questões** (vocabulário canônico, faixas de questões do ENADE por ano, ciclo de alertas de extração, travas determinísticas pós-LLM, política de divergência de reclassificação e cálculo de métricas do `Conjunto-Ouro`) deve viver isolada em `backend/src/domain/`, livre de frameworks e I/O, para ser testada rapidamente com TDD e evoluir sem acoplamento a curso, grade curricular ou provedor de LLM.

## Entrega observável

Camada `backend/src/domain/` completa (entidades, enums, regras determinísticas e calculador de métricas) + portas (`Protocol`) em `backend/src/application/ports/`, totalmente cobertas por testes unitários puros em `backend/tests/unit/` e aprovadas pelo `import-linter`.

## Escopo e limites

- **Entidades e Value Objects em `backend/src/domain/`** (aderentes aos 16 termos de [GLOSSARY.md](../../../GLOSSARY.md)):
  - `Prova` (unicidade `(exame, curso, ano)`), `Ingestão` (status `pendente | processando | concluida | erro | interrompida`), `Questão` (`numero`, `componente`, `tipo`, `enunciado`, `paginas`, `editada_manualmente`), `Alternativa` (`A`–`E`), `AtivoVisual` (`origem: picture_docling | formula_recorte | upload_manual`, vínculo opcional à `Alternativa`, `ordem`, `pagina`, `bbox`), `Gabarito` (`situacao_gabarito: valida | anulada | pendente`, `alternativa_correta`), `AlertaExtracao` (`codigo`, `severidade: critico | informativo`, `status: aberto | resolvido`, `mensagem`, `resolvido_em`).
  - `Taxonomia`, `Disciplina` (`codigo`, `nome`, `ementa`, `ativa`), `Tópico`.
  - `PerfilClassificacao` (`codigo`, `versao`, `diretrizes_gerais`, `guia_fronteiras`, `template_prompt`), `ExecucaoClassificacao` (snapshot congelado + status + métricas), `Classificacao` (`1` principal + `0..2` secundárias + `topicos` + `justificativa` + `confianca` + `origem: automatica | humana` + `status: pendente_revisao | aprovada` + `vigente` + `revisao_prioritaria`), `DivergenciaReclassificacao`.
  - Estruturas de `ConjuntoOuro` (chave natural `(exame, curso, ano, numero)`) e `AvaliacaoClassificacao`.
- **Regras determinísticas puras**:
  - Faixa padrão do Componente Específico por edição (`2014–2019: 09–35`, `2023: 10–38`, `2026+: 16–45`, com override explícito).
  - Avaliador determinístico dos 6 `Alerta de Extração` (4 críticos: `formula_nao_decodificada`, `alternativas_incompletas`, `pdf_via_ocr`, `enunciado_suspeito`; 2 informativos: `fonte_symbol_detectada`, `gabarito_ausente_na_prova`) e reavaliação automática dos 4 estruturais após edição de conteúdo.
  - Travas pós-LLM: rejeitar `disciplina_principal` fora do catálogo ativo (sinalizando elegibilidade a 1 retry corretivo); sanear `disciplinas_secundarias` (remover duplicatas, igual à principal, slugs fora do catálogo e limitar a 2, marcando alerta/prioritária); normalizar `Tópico`s em `kebab-case` ASCII curto (1–4 itens, até 32 chars sem cortar palavras); calcular `revisao_prioritaria` (qualquer `Alerta de Extração` crítico aberto OU saneamento de trava OU `confianca < 0.75`).
  - Critério de `Divergência de Reclassificação`: compara exclusivamente `(disciplina_principal, set(disciplinas_secundarias))`, ignorando variações de justificativa, confiança e `Tópico`s.
  - Política de `Reprocessar Prova`: preservar `Questão`s com `editada_manualmente = true` quando `sobrescrever_editadas = false`.
  - Calculador determinístico das 3 camadas de métricas de `Avaliação de Classificação` (acurácia principal, Macro-F1 principal, Jaccard/F1 secundárias com `∅ == ∅ → 1.0`, exact match, matriz de confusão, validade 1ª tentativa, erro em alta confiança `>= 0.85`) e avaliador de gate (`baseline` vs `candidato`, padrão e `--modo-migracao`).
- **Portas (`Protocol`) em `backend/src/application/ports/`**: `ExtratorProva`, `ExtratorGabarito`, `RenderizadorPaginaPdf`, `ClassificadorMultimodal`, `ArmazenamentoArquivos` e repositórios de domínio.
- **Fora de escopo**: SQLAlchemy, migrations, FastAPI, Docling ou chamadas HTTP reais.

## Dependências

- [01 — Scaffolding do monorepo, infraestrutura local e healthcheck](01-scaffolding-monorepo-infra-local.md)

## Critérios de aceite

- [x] `import-linter` confirma zero dependências externas ou de camadas superiores em `backend/src/domain/`.
- [x] Travas pós-LLM rejeitam principal inválida, saneiam secundárias (duplicatas, igual à principal, slug fantasma, > 2 itens), normalizam `Tópico`s e acionam `revisao_prioritaria` mesmo com `confianca = 0.99` quando houver `Alerta de Extração` crítico aberto.
- [x] Reavaliação de `Alerta de Extração` fecha automaticamente alertas estruturais corrigidos (`formula_nao_decodificada`, `alternativas_incompletas`, `enunciado_suspeito`, `gabarito_ausente_na_prova`) e mantém alertas de inspeção (`pdf_via_ocr`, `fonte_symbol_detectada`) até verificação explícita.
- [x] Critério de `Divergência de Reclassificação` abre divergência apenas quando mudam `disciplina_principal` ou `set(disciplinas_secundarias)`.
- [x] Calculador de métricas e gate de regressão cobrem casos de borda (`∅ == ∅ → 1.0` em secundárias, disciplinas raras no Macro-F1, piso estrutural `100%/95%` e modo migração).

## Verificação

- Executar `uv run lint-imports`, `uv run ruff check .` e `uv run pytest tests/unit/`.

## Evidências e pendências

- **Núcleo de domínio (`backend/src/domain/`)**:
  - Entidades, objetos de valor, enums e exceções puras (Python 3.13 stdlib, sem frameworks ou I/O): `backend/src/domain/exceptions.py`, `backend/src/domain/enums.py`, `backend/src/domain/prova.py`, `backend/src/domain/taxonomia.py`, `backend/src/domain/classificacao.py`, `backend/src/domain/avaliacao.py` e `backend/src/domain/__init__.py`.
  - Regras determinísticas e calculador de métricas: `backend/src/domain/faixas_enade.py`, `backend/src/domain/alertas_extracao.py`, `backend/src/domain/reprocessamento.py`, `backend/src/domain/travas_classificacao.py` e `backend/src/domain/metricas_avaliacao.py`.
- **Portas de aplicação (`backend/src/application/ports/`)**:
  - Contratos `@runtime_checkable` (`Protocol`) e DTOs: `backend/src/application/ports/extracao.py` (`ExtratorProva`, `ExtratorGabarito`, `RenderizadorPaginaPdf`), `backend/src/application/ports/classificacao.py` (`ClassificadorMultimodal`), `backend/src/application/ports/armazenamento.py` (`ArmazenamentoArquivos`), `backend/src/application/ports/repositorios.py` (repositórios de domínio) e `backend/src/application/ports/__init__.py`.
- **Verificações executadas (`backend/`)**:
  - `cd backend && uv run python --version` → `Python 3.13.15`
  - `cd backend && uv run lint-imports` → exit code `0` (`Analyzed 50 files, 154 dependencies.`, `Contracts: 3 kept, 0 broken.`: `Camadas hexagonais`, `Isolamento do dominio`, `Isolamento da aplicacao`)
  - `cd backend && uv run ruff check . && uv run ruff format --check .` → `All checks passed!`, `48 files already formatted`
  - `cd backend && uv run pytest tests/unit/` → `110 passed, 1 warning` (`tests/unit/test_alertas_extracao.py`, `tests/unit/test_application_ports.py`, `tests/unit/test_divergencia_reclassificacao.py`, `tests/unit/test_domain_prova.py`, `tests/unit/test_domain_taxonomia_classificacao.py`, `tests/unit/test_faixas_enade.py`, `tests/unit/test_health.py`, `tests/unit/test_metricas_avaliacao.py`, `tests/unit/test_reprocessamento.py`, `tests/unit/test_settings.py`, `tests/unit/test_travas_classificacao.py`)
- **Pendências**: nenhuma na Tarefa 02 (persistência PostgreSQL e adaptadores concretos previstos nas Tarefas 03, 04 e 06).
