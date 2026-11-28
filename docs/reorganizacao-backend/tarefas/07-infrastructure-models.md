# 07 — Dividir `persistence/models.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 03](../decisoes/03-corte-infrastructure.md), seção `persistence/models/`

## Contexto

`backend/src/infrastructure/persistence/models.py` tem 526 linhas e declara os 13 modelos ORM de agregados diferentes. O corte espelha os módulos de `domain/`. O `metadata` de `Base` precisa continuar completo para o Alembic (`alembic/env.py` importa `Base` de `infrastructure.persistence.models`).

## Entrega observável

O pacote `backend/src/infrastructure/persistence/models/` existe, `models.py` não existe mais, `from infrastructure.persistence.models import <nome>` continua válido para `Base` e os 13 modelos, e `Base.metadata` tem as mesmas tabelas de antes.

## Organização-alvo

```text
infrastructure/persistence/models/
├── __init__.py          # importa todos os submódulos e reexporta Base e os 13 modelos, com __all__
├── base.py              # Base
├── prova.py             # ProvaModel, IngestaoModel, QuestaoModel, AlternativaModel, AtivoVisualModel,
│                        # AlertaExtracaoModel
├── taxonomia.py         # TaxonomiaModel, DisciplinaModel
└── classificacao.py     # PerfilClassificacaoModel, ExecucaoClassificacaoModel, ClassificacaoModel,
                         # DivergenciaReclassificacaoModel
```

Nenhum `relationship` cruza arquivos. Entre agregados só há `ForeignKey` com o nome da tabela em string, sem import circular ([decisão 03](../decisoes/03-corte-infrastructure.md)).

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-07` e os argumentos:
   - arquivos antigos: `src/infrastructure/persistence/models.py`

   Registre também as tabelas do `metadata`:

   ```sh
   uv run python -c "from infrastructure.persistence.models import Base; print('\n'.join(sorted(Base.metadata.tables)))" > "$PORTAO/tabelas-antes.txt"
   ```

2. `git mv src/infrastructure/persistence/models.py src/infrastructure/persistence/models/classificacao.py`. `classificacao.py` é o submódulo que fica com a maior parte do código.
3. Crie `base.py`, `prova.py` e `taxonomia.py` movendo os símbolos, sem alterar as declarações. Cada submódulo importa `Base` de `infrastructure.persistence.models.base`.
4. `__init__.py` importa os 4 submódulos e define `__all__`: `AlertaExtracaoModel`, `AlternativaModel`, `AtivoVisualModel`, `Base`, `ClassificacaoModel`, `DisciplinaModel`, `DivergenciaReclassificacaoModel`, `ExecucaoClassificacaoModel`, `IngestaoModel`, `PerfilClassificacaoModel`, `ProvaModel`, `QuestaoModel`, `TaxonomiaModel`.
5. Não altere `alembic/env.py`, `repositorios.py` nem as migrações.
6. Portão "depois" com o pacote `infrastructure.persistence.models` e sem `--fora`, mais:

   ```sh
   uv run python -c "from infrastructure.persistence.models import Base; print('\n'.join(sorted(Base.metadata.tables)))" > "$PORTAO/tabelas-depois.txt"
   cmp "$PORTAO/tabelas-antes.txt" "$PORTAO/tabelas-depois.txt"
   ```

7. Não há referência a corrigir em `docs/planejamento-inicial/explicacao.md`.
8. Registre as saídas, marque a tarefa como `concluida` e faça o commit `refactor(infrastructure): dividir models.py em pacote`.

## Dependências

- [06 — Dividir `application/avaliacao.py` em pacote](06-application-avaliacao.md) commitada.

## Critérios de aceite

- [ ] `models.py` removido e os 4 submódulos criados.
- [ ] `__all__` com `Base` e os 13 modelos; script de reexportação com 0 falhas.
- [ ] Lista de tabelas de `Base.metadata` idêntica antes/depois.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] `alembic/` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/infrastructure/persistence/models/*.py
git diff --exit-code HEAD -- alembic/
```

## Evidências e pendências

Nenhuma ainda.
