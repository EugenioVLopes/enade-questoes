# 11 — Dividir `api/v1/questoes.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 04](../decisoes/04-corte-presentation.md), seção `api/v1/questoes/`

## Contexto

`backend/src/presentation/api/v1/questoes.py` tem 489 linhas: getters de injeção de dependência, serializadores e 8 rotas de um único recurso. O corte é por papel: rotas de um lado, serialização do outro. As rotas ficam num só módulo e na ordem atual, para preservar a ordem de `paths` no OpenAPI.

Esta é a última tarefa do esforço. O portão inclui a varredura global do teto de linhas.

## Entrega observável

O pacote `backend/src/presentation/api/v1/questoes/` existe, `v1/questoes.py` não existe mais, o `__all__` continua `["router", "serializar_ativo"]`, e `api/app.py` e `v1/ativos_visuais.py` não mudam.

## Organização-alvo

```text
presentation/api/v1/questoes/
├── __init__.py          # reexporta router e serializar_ativo (mesmo __all__ de hoje)
├── rotas.py             # router, _resolver_state, os 8 get_*_use_case, _correcao e as 8 rotas, na ordem atual
└── serializacao.py      # serializar_ativo, serializar_alerta, serializar_classificacao, serializar_divergencia,
                         # serializar_detalhe, serializar_item, serializar_contadores, TAMANHO_TRECHO
```

### Renomeações dos serializadores

Os serializadores passam a ser importados por `rotas.py`, então perdem o `_` ([decisão 04](../decisoes/04-corte-presentation.md)). Só muda o nome.

| Hoje | Depois |
|---|---|
| `_serializar_alerta` | `serializar_alerta` |
| `_serializar_classificacao` | `serializar_classificacao` |
| `_serializar_divergencia` | `serializar_divergencia` |
| `_serializar_detalhe` | `serializar_detalhe` |
| `_serializar_item` | `serializar_item` |
| `_serializar_contadores` | `serializar_contadores` |

`serializar_ativo` já é público e mantém o nome. Fora ele, nenhum serializador entra no `__all__`.

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-11` e os argumentos:
   - arquivos antigos: `src/presentation/api/v1/questoes.py` (o script usa o `__all__` existente)
2. `git mv src/presentation/api/v1/questoes.py src/presentation/api/v1/questoes/rotas.py`. `rotas.py` é o submódulo que fica com a maior parte do código.
3. Crie `serializacao.py` movendo os 7 serializadores e `TAMANHO_TRECHO`, sem alterar o corpo. Aplique as renomeações da tabela nas definições e nas chamadas.
4. Em `rotas.py`, importe os serializadores de `presentation.api.v1.questoes.serializacao`. Não mude a ordem, os nomes, os decoradores nem as assinaturas das rotas.
5. `__init__.py` com `from presentation.api.v1.questoes.rotas import router`, `from presentation.api.v1.questoes.serializacao import serializar_ativo` e `__all__ = ["router", "serializar_ativo"]`.
6. Portão "depois" com o pacote `presentation.api.v1.questoes` e sem `--fora`.
7. Varredura global do teto ([validacao.md](../validacao.md#3-varredura-global-do-teto-só-na-tarefa-11)). A saída só pode listar as 6 exceções aceitas.
8. Em `docs/planejamento-inicial/explicacao.md`, troque `backend/src/presentation/api/v1/questoes.py:345` (decorador `@router.post` de `aprovar_classificacao`) por `backend/src/presentation/api/v1/questoes/rotas.py:<linha>`.
9. Registre as saídas, marque a tarefa e o [plano](../plano.md) como `concluida` e faça o commit `refactor(presentation): dividir v1/questoes.py em pacote`.

## Dependências

- [10 — Unir `schemas.py` e `schemas_questoes.py` no pacote `api/schemas/`](10-presentation-schemas.md) commitada.

## Critérios de aceite

- [ ] `v1/questoes.py` removido e os 2 submódulos criados.
- [ ] `__all__ == ["router", "serializar_ativo"]`; script de reexportação com 0 falhas.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] `api/app.py` e `api/v1/ativos_visuais.py` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas.
- [ ] Varredura global lista só as 6 exceções aceitas.
- [ ] Referência de `explicacao.md` corrigida.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/presentation/api/v1/questoes/*.py
git diff --exit-code HEAD -- src/presentation/api/app.py src/presentation/api/v1/ativos_visuais.py
find src -name '*.py' -exec wc -l {} + | awk '$2 != "total" && $1 > 400' | sort -rn
```

## Evidências e pendências

Nenhuma ainda.
