# 14 — CLI de avaliação offline (`enade-eval`), Conjunto-Ouro e histórico IA × Humano

Status: `pendente`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Glossário: [GLOSSARY.md](../../../GLOSSARY.md) · Decisão: [métricas de qualidade e conjunto-ouro](../decisoes/11-metricas-qualidade-e-conjunto-ouro.md)

## Contexto

Antes de promover um novo `Perfil de Classificação` ou migrar a aplicação para um servidor **Qwen/vLLM** futuro, precisamos de um protocolo determinístico, reproduzível e barato para medir acurácia e detectar regressões sem poluir o banco de dados da aplicação. Esta tarefa implementa o CLI local `enade-eval` e seus alvos no `Makefile`.

## Entrega observável

Entrypoint CLI `uv run enade-eval` (e atalhos no `Makefile`) com os 4 subcomandos operacionais — `exportar-ouro`, `avaliar`, `comparar` e `historico` — operando 100% em modo somente-leitura no PostgreSQL, gravando snapshots versionáveis em `evals/golden/<taxonomia_codigo>.json` e relatórios descartáveis em `DATA_DIR/evals/`.

## Escopo e limites

- **Entrypoint CLI em `backend/src/presentation/cli/eval_cli.py`** registrado em `[project.scripts]` (`enade-eval`) no `backend/pyproject.toml`, consumindo serviços de aplicação e o calculador de métricas de `src/domain/`:
  1. **`enade-eval exportar-ouro --taxonomia <codigo> --saida evals/golden/<codigo>.json`**:
     - Consulta no PostgreSQL todas as `Questão`s com `Classificação` vigente `status = aprovada` sob a `Taxonomia` alvo e **zero `Alerta de Extração` crítico aberto** (incluindo `ANULADA`s revisadas, registrando `situacao_gabarito`).
     - Exporta JSON enxuto ordenado deterministicamente por `(exame, curso, ano, numero)` com `versao_schema`, `taxonomia_codigo`, `exportado_em`, contagem de itens/edições e vereditos esperados (`disciplina_principal`, `disciplinas_secundarias`, `situacao_gabarito`, `notas`), sem UUIDs nem mídia.
  2. **`enade-eval avaliar --ouro <arquivo.json> --perfil <codigo@versao | arquivo.yaml> [--base-url ...] [--model ...] [--api-key ...] [--no-cache] [--repeticoes N]`**:
     - Executa **checagem *preflight* obrigatória** antes de chamar o LLM: verifica se todas as `Questão`s do `Conjunto-Ouro` existem no PostgreSQL local, têm zero `Alerta de Extração` crítico aberto e se todas as `Disciplina`s referenciadas estão ativas na `Taxonomia` alvo (abortando com relatório exato dos itens defasados em caso de falha).
     - Reutiliza exatamente `ClassificadorMultimodal` (`ClienteOpenAICompativel`) e as travas determinísticas da aplicação em modo **100% somente-leitura no PostgreSQL** (nunca grava `Execução de Classificação`, `Classificação` nem `Divergência de Reclassificação`).
     - Calcula o pacote de métricas determinísticas em **3 camadas** (Acurácia Curricular: principal, Macro-F1, Jaccard/F1 secundárias, Exact Match; Diagnóstico de Fronteiras: matriz de confusão + lista por questão divergente; Saúde Operacional: conclusão válida, validade na 1ª tentativa, `revisao_prioritaria`, taxa de erro em alta confiança `>= 0,85`, tokens, cache hits e latência média/p95; além de estabilidade entre passadas quando `--repeticoes > 1`).
     - Grava relatório estruturado `JSON` + resumo `Markdown` em `DATA_DIR/evals/` e imprime sumário legível no terminal.
  3. **`enade-eval comparar <baseline.json> <candidato.json> [--modo-migracao]`**:
     - Valida que ambos os runs usam o **mesmo snapshot do `Conjunto-Ouro` e `Taxonomia`**.
     - Aplica o **gate híbrido**: piso estrutural duro (`conclusao_valida == 100%` e `validade_primeira_tentativa >= 95%`) + deltas relativos (`acuracia_principal >= baseline`, `macro_f1 >= baseline - 2,0 p.p.`, `jaccard_secundarias >= baseline - 3,0 p.p.`; ou `-2,0 p.p.` principal e `-5,0 p.p.` secundárias sob `--modo-migracao`).
     - Exibe tabela comparativa + lista explícita de **ganhos** e **regressões** questão-a-questão e retorna `exit code 0` (aprovado) ou `1` (regressão).
  4. **`enade-eval historico [--taxonomia <codigo>]`**:
     - Consulta somente-leitura no PostgreSQL que calcula, a partir das `Classificação`s preservadas (sem chamar LLM), taxa de aprovação direta sem alteração, taxa de correção na `Disciplina` principal e taxa de correção apenas nas secundárias, agrupadas por `Perfil de Classificação` e modelo.
- **Atalhos no `Makefile`**: `golden-export`, `eval-run`, `eval-compare`, `eval-history`.
- **Fora de escopo**: telas de benchmark na interface web e *LLM-as-a-judge*.

## Dependências

- [03 — Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial](03-persistencia-postgres-alembic-seed.md)
- [06 — Classificador multimodal OpenAI-compatível, cache determinístico e travas](06-classificador-multimodal-cache-travas.md)
- [07 — API de Taxonomias, Perfis de Classificação e Execuções de Classificação](07-api-taxonomias-perfis-execucoes.md)

## Critérios de aceite

- [ ] `exportar-ouro` gera JSON determinístico por chave natural excluindo questões com `Alerta de Extração` crítico aberto e mantendo `ANULADA`s revisadas com `situacao_gabarito`.
- [ ] `avaliar` aborta no *preflight* sem chamar o LLM se detectar `Disciplina` arquivada, `Questão` ausente ou alerta crítico aberto; quando válido, roda sem alterar uma única linha no PostgreSQL.
- [ ] `avaliar` aceita perfil do banco ou rascunho local em YAML/JSON, respeita `--no-cache`, `--repeticoes N` e overrides `--base-url`/`--model`, e grava JSON + Markdown em `DATA_DIR/evals/`.
- [ ] `comparar` rejeita runs de snapshots diferentes, aplica corretamente o gate padrão e `--modo-migracao`, imprime ganhos/regressões por questão e retorna exit code `0` ou `1`.
- [ ] `historico` calcula concordância IA × Humano direto do PostgreSQL agrupada por `Perfil de Classificação` e modelo.

## Verificação

- `uv run pytest tests/integration/test_cli_eval.py` (usando PostgreSQL 16 real + `ClassificadorMultimodal` fake determinístico) e `uv run ruff check .`.

## Evidências e pendências

Pendente de execução.
