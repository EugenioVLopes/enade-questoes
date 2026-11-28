# 03 — Dividir `domain/avaliacao.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 01](../decisoes/01-corte-domain.md), seção `domain/avaliacao/`

## Contexto

`backend/src/domain/avaliacao.py` tem 407 linhas e mistura dois agregados: o Conjunto-Ouro (referência versionada) e a Avaliação de Classificação (histórico persistido). Por isso é dividido mesmo estando na faixa de 400 a 470 linhas.

## Entrega observável

O pacote `backend/src/domain/avaliacao/` existe, `domain/avaliacao.py` não existe mais, e `from domain.avaliacao import <nome>` continua válido para os 13 nomes públicos de hoje.

## Organização-alvo

```text
domain/avaliacao/
├── __init__.py          # reexporta os 13 nomes, com __all__
├── conjunto_ouro.py     # ChaveQuestaoOuro, ItemConjuntoOuro, ConjuntoOuro
└── avaliacao.py         # PredicaoClassificacao, ResultadoItemAvaliacao, ParConfusao, DivergenciaAvaliacao,
                         # MetricasCamada1, MetricasCamada2, MetricasCamada3, AvaliacaoClassificacao,
                         # ItemDiffGate, ResultadoGate
```

A validação de secundárias repetida em `ItemConjuntoOuro` e `PredicaoClassificacao` continua duplicada ([decisão 01](../decisoes/01-corte-domain.md), regras gerais).

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-03` e os argumentos:
   - arquivos antigos: `src/domain/avaliacao.py`
2. `git mv src/domain/avaliacao.py src/domain/avaliacao/avaliacao.py`. Os dois submódulos têm cerca de 195 linhas; o que repete o nome do pacote recebe o `git mv`.
3. Crie `conjunto_ouro.py` movendo os 3 símbolos do Conjunto-Ouro, sem alterar o corpo. Se `avaliacao.py` usar algum tipo do Conjunto-Ouro, importe de `domain.avaliacao.conjunto_ouro`.
4. `__init__.py` com `__all__`: `AvaliacaoClassificacao`, `ChaveQuestaoOuro`, `ConjuntoOuro`, `DivergenciaAvaliacao`, `ItemConjuntoOuro`, `ItemDiffGate`, `MetricasCamada1`, `MetricasCamada2`, `MetricasCamada3`, `ParConfusao`, `PredicaoClassificacao`, `ResultadoGate`, `ResultadoItemAvaliacao`.
5. Portão "depois" com o pacote `domain.avaliacao` e sem `--fora`.
6. Não há referência a corrigir em `docs/planejamento-inicial/explicacao.md`.
7. Registre as saídas, marque a tarefa como `concluida` e faça o commit `refactor(domain): dividir avaliacao.py em pacote`.

## Dependências

- [02 — Dividir `domain/classificacao.py` em pacote](02-domain-classificacao.md) commitada.

## Critérios de aceite

- [ ] `domain/avaliacao.py` removido e os 2 submódulos criados.
- [ ] `__all__` com os 13 nomes; script de reexportação com 0 falhas.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] `domain/metricas_avaliacao.py` e `domain/__init__.py` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/domain/avaliacao/*.py
git diff --exit-code HEAD -- src/domain/__init__.py src/domain/metricas_avaliacao.py
```

## Evidências e pendências

Nenhuma ainda.
