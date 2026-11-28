# 05 — Dividir `application/classificacao.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 02](../decisoes/02-corte-application.md), seção `application/classificacao/`

## Contexto

`backend/src/application/classificacao.py` tem 459 linhas e trata um só agregado. É dividido pela seam entre a montagem pura (JSON Schema e prompts) e a orquestração de `ClassificarQuestaoService`.

## Entrega observável

O pacote `backend/src/application/classificacao/` existe, `application/classificacao.py` não existe mais, e `from application.classificacao import <nome>` continua válido para os 6 nomes públicos de hoje, incluindo o import de `construir_json_schema_plano` em `infrastructure/llm/__init__.py`.

## Organização-alvo

```text
application/classificacao/
├── __init__.py          # reexporta os 6 nomes, com __all__
├── prompt.py            # construir_json_schema_plano, montar_prompts_classificacao e 11 privados
│                        # (_ORDEM_LETRAS, _PLACEHOLDER_RE, _renderizar_template_seguro, _formatar_*,
│                        #  _normalizar_snapshot_*, _hash_snapshot_canonico, _extrair_secoes_template)
└── classificacao.py     # MetricasClassificacao, ErroClassificacaoEstruturado, ResultadoClassificacaoQuestao,
                         # ClassificarQuestaoService; _ordenar_ativos_visuais
```

A lista completa dos privados de `prompt.py` está na [decisão 02](../decisoes/02-corte-application.md).

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-05` e os argumentos:
   - arquivos antigos: `src/application/classificacao.py`
2. `git mv src/application/classificacao.py src/application/classificacao/classificacao.py`. `classificacao.py` é o submódulo que fica com a maior parte do código.
3. Crie `prompt.py` movendo os símbolos de montagem, sem alterar o corpo. `classificacao.py` importa de `application.classificacao.prompt` o que usar.
4. `__init__.py` com `__all__`: `ClassificarQuestaoService`, `ErroClassificacaoEstruturado`, `MetricasClassificacao`, `ResultadoClassificacaoQuestao`, `construir_json_schema_plano`, `montar_prompts_classificacao`.
5. Não altere `infrastructure/llm/__init__.py`.
6. Portão "depois" com o pacote `application.classificacao` e sem `--fora`.
7. Em `docs/planejamento-inicial/explicacao.md`, troque `backend/src/application/classificacao.py:380` (`retry_corretivo = False` em `ClassificarQuestaoService.classificar`) por `backend/src/application/classificacao/classificacao.py:<linha>`.
8. Registre as saídas, marque a tarefa como `concluida` e faça o commit `refactor(application): dividir classificacao.py em pacote`.

## Dependências

- [04 — Dividir `application/questoes.py` em pacote](04-application-questoes.md) commitada.

## Critérios de aceite

- [ ] `application/classificacao.py` removido e os 2 submódulos criados.
- [ ] `__all__` com os 6 nomes; script de reexportação com 0 falhas.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] `infrastructure/llm/__init__.py` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas.
- [ ] Referência de `explicacao.md` corrigida.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/application/classificacao/*.py
git diff --exit-code HEAD -- src/infrastructure/llm/__init__.py
```

## Evidências e pendências

Nenhuma ainda.
