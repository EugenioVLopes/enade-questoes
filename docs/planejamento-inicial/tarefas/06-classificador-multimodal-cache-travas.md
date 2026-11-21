# 06 — Classificador multimodal OpenAI-compatível, cache determinístico e travas

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Protótipo base: [run_prototype.py](../../../prototypes/07-classificacao-llm/run_prototype.py) · Decisões: [provedores de API LLM](../decisoes/04-avaliar-provedores-api-llm.md), [estratégia de classificação multimodal](../decisoes/07-estrategia-classificacao-e-reclassificacao.md)

## Contexto

O protótipo da decisão 07 comprovou que o protocolo OpenAI Chat Completions permite trocar entre Google Gemini AI Studio (v1), OpenRouter e um futuro servidor `Qwen/vLLM` apenas alterando `.env`, desde que combinemos JSON Schema plano dinâmico, envio multimodal dos `Ativo Visual`s, controle de *thinking/reasoning*, orçamento `max_tokens >= 4096`, cache determinístico por hash de conteúdo e travas determinísticas em Python. Esta tarefa promove essa camada para `backend/src/infrastructure/llm/`.

## Entrega observável

Adaptador `ClienteOpenAICompativel` implementando a porta `ClassificadorMultimodal`, gerador de JSON Schema plano dinâmico, cache em disco (`DATA_DIR/cache/llm/{sha256}.json`), rate-limiting + backoff exponencial e integração com as travas determinísticas do domínio, cobertos por testes automatizados (sem rede na suíte padrão).

## Escopo e limites

- **Dependência**: adicionar `openai` ao `backend/pyproject.toml`.
- **Gerador de JSON Schema plano e portátil**:
  - Construído dinamicamente a partir das `Disciplina`s **ativas** da `Taxonomia` (sem `$defs`/`$ref` nem `title`).
  - Campos: `disciplina_principal` (`enum`), `disciplinas_secundarias` (`array` de `enum`, `maxItems: 2`), `topicos` (`array`, 1–4 strings), `justificativa` (string) e `confianca` (`0.0..1.0`).
  - Degradação controlada caso o endpoint rejeite `json_schema` strict: `json_schema` → `json_object` → JSON via prompt, sempre validado localmente via Pydantic + travas de domínio.
- **Montagem multimodal e controle de provedor**:
  - Envio obrigatório de todos os `Ativo Visual`s da `Questão` como `image_url` PNG em base64.
  - `temperature=0`, `max_tokens >= 4096` (configurável por `.env` respeitando piso mínimo `4096`).
  - Perfil por `LLM_PROVIDER`: `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` para `vllm_qwen`; `extra_body={"reasoning": {"effort": "low"}}` quando aplicável em modelos *reasoning*; cabeçalhos limpos para `gemini_openai`.
- **Resiliência e retry**:
  - Rate-limiter local respeitando `LLM_MAX_RPM` (desativado quando `0`).
  - Backoff exponencial em `HTTP 429` / `5xx` / timeout e em `content == ""` (consumo por *thinking* oculto).
  - **1 retry corretivo explícito** quando `disciplina_principal` vier fora do catálogo ativo (enviando o erro de validação ao modelo); persistindo inválido, retorna erro estruturado sem gravar classificação inválida.
- **Cache determinístico em disco**:
  - Chave: `sha256(identidade_provedor_modelo + snapshot_taxonomia + snapshot_perfil + prompt_usuario + sha256_imagens + schema)`.
  - Suporte explícito a `ignorar_cache: bool = False` (usado pelo `enade-eval --no-cache`).
  - Registra métricas de cada chamada (`prompt_tokens`, `completion_tokens`, `latencia_ms`, `cache_hit`, `tentativas`, `saneada`, `modo_schema`).
- **Fora de escopo**: endpoints HTTP de `Execução de Classificação` (Tarefa 07) e CLI `enade-eval` (Tarefa 14).

## Dependências

- [02 — Núcleo de domínio, regras determinísticas e portas](02-nucleo-dominio-regras-deterministicas.md)
- [03 — Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial](03-persistencia-postgres-alembic-seed.md)

## Critérios de aceite

- [x] JSON Schema gerado contém apenas `Disciplina`s ativas da `Taxonomia` e não contém `$defs`, `$ref` nem `title`.
- [x] Mensagem enviada ao cliente OpenAI inclui todos os `Ativo Visual`s da `Questão` em base64 PNG e respeita `temperature=0` e `max_tokens >= 4096`.
- [x] Chave de cache muda automaticamente quando qualquer entrada muda (enunciado, alternativa, imagem, `Taxonomia`, `Perfil de Classificação` ou modelo) e reaproveita resultado sem chamada HTTP quando idêntica.
- [x] Testes com cliente mockado cobrem: degradação `json_schema → json_object → prompt`, retry em `429`/`content=""`, 1 retry corretivo em principal alucinada, saneamento de secundárias/tópicos e `extra_body` específico de `vllm_qwen`.
- [x] Zero chamadas de rede externas na execução padrão do `pytest`.

## Verificação

- `uv run pytest tests/unit/test_classificador_multimodal.py tests/integration/test_cache_llm.py` e `uv run ruff check .`.

## Evidências e pendências

- **Artefatos locais do Teamwork (fora do Git)**: `docs/planejamento-inicial/artefatos/06-teamwork/` (`prompt.md`, `resultado.md` e relatórios de auditoria; veredito: `VICTORY CONFIRMED`).
- **Configuração e serviço de aplicação**: `backend/pyproject.toml`, `backend/uv.lock`, `.env.example`, `backend/src/infrastructure/config.py`, `backend/src/application/classificacao.py` e `backend/src/application/exceptions.py` implementando `construir_json_schema_plano`, `montar_prompts_classificacao`, `ClassificarQuestaoService` com aplicação das travas determinísticas do domínio (`validar_e_normalizar_classificacao`), 1 retry corretivo para `disciplina_principal` fora do catálogo ativo e erro estruturado `ClassificacaoLLMInvalidaError`.
- **Adaptador multimodal e cache determinístico**: `backend/src/infrastructure/llm/__init__.py`, `backend/src/infrastructure/llm/perfis.py` e `backend/src/infrastructure/llm/cliente_openai.py` implementando `ClienteOpenAICompativel` (envio multimodal PNG base64, perfis `gemini_openai`/`openrouter`/`vllm_qwen`/`openai_compatible`, degradação `json_schema -> json_object -> prompt_json`, rate-limiting `LLM_MAX_RPM`, backoff exponencial em `429`/`5xx`/timeout/`content=""` e cache atômico SHA-256 em `DATA_DIR/cache/llm/{sha256}.json`).
- **Testes automatizados (100% mockados)**: `backend/tests/unit/test_classificador_multimodal.py`, `backend/tests/integration/test_cache_llm.py` e `backend/tests/unit/test_settings.py`.
- **Verificações executadas**:
  - `cd backend && uv run pytest tests/unit/test_classificador_multimodal.py tests/integration/test_cache_llm.py -v` → `24 passed`
  - `make lint` → exit code `0` (`ruff check .`, `ruff format --check .`, `lint-imports` 3/3 contratos, `pnpm type-check`, `pnpm lint`)
  - `make test` → `202 passed` (backend) + `1 passed` (frontend)
- **Pendências**: nenhuma na Tarefa 06.
