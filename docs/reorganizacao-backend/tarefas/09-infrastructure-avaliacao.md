# 09 — Dividir `persistence/avaliacao.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 03](../decisoes/03-corte-infrastructure.md), seção `persistence/avaliacao/`

## Contexto

`backend/src/infrastructure/persistence/avaliacao.py` tem 397 linhas, abaixo do teto, mas mistura dois adaptadores de agregados diferentes: o repositório do Conjunto-Ouro e a consulta somente-leitura da avaliação. Os dois não compartilham símbolos. A [tarefa 08](08-infrastructure-repositorios.md) já trocou os imports dos mapeadores neste arquivo, então aqui só se divide o arquivo.

## Entrega observável

O pacote `backend/src/infrastructure/persistence/avaliacao/` existe, `persistence/avaliacao.py` não existe mais, e `from infrastructure.persistence.avaliacao import <nome>` continua válido para os 3 nomes públicos.

## Organização-alvo

```text
infrastructure/persistence/avaliacao/
├── __init__.py          # reexporta os 3 nomes, com __all__
├── conjunto_ouro.py     # VERSAO_SCHEMA_CONJUNTO_OURO, RepositorioConjuntoOuroSqlAlchemy;
│                        # _serializar_conjunto_ouro, _parse_datetime_iso
└── consulta.py          # ConsultaAvaliacaoSqlAlchemy
```

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-09` e os argumentos:
   - arquivos antigos: `src/infrastructure/persistence/avaliacao.py`
2. `git mv src/infrastructure/persistence/avaliacao.py src/infrastructure/persistence/avaliacao/conjunto_ouro.py`. `conjunto_ouro.py` é o submódulo que fica com a maior parte do código.
3. Crie `consulta.py` movendo `ConsultaAvaliacaoSqlAlchemy`, sem alterar o corpo. Cada submódulo mantém só os imports que usa, incluindo os mapeadores públicos dos submódulos de `repositorios/`.
4. `__init__.py` com `__all__`: `ConsultaAvaliacaoSqlAlchemy`, `RepositorioConjuntoOuroSqlAlchemy`, `VERSAO_SCHEMA_CONJUNTO_OURO`.
5. Não altere `persistence/__init__.py` nem `presentation/cli/bootstrap.py`.
6. Portão "depois" com o pacote `infrastructure.persistence.avaliacao` e sem `--fora`.
7. Não há referência a corrigir em `docs/planejamento-inicial/explicacao.md`.
8. Registre as saídas, marque a tarefa como `concluida` e faça o commit `refactor(infrastructure): dividir avaliacao.py em pacote`.

## Dependências

- [08 — Dividir `persistence/repositorios.py` em pacote](08-infrastructure-repositorios.md) commitada. A ordem é obrigatória.

## Critérios de aceite

- [ ] `persistence/avaliacao.py` removido e os 2 submódulos criados.
- [ ] `__all__` com os 3 nomes; script de reexportação com 0 falhas.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] `persistence/__init__.py` e `presentation/cli/bootstrap.py` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/infrastructure/persistence/avaliacao/*.py
git diff --exit-code HEAD -- src/infrastructure/persistence/__init__.py src/presentation/cli/bootstrap.py
```

## Evidências e pendências

Nenhuma ainda.
