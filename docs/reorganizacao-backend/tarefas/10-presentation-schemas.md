# 10 — Unir `schemas.py` e `schemas_questoes.py` no pacote `api/schemas/`

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 04](../decisoes/04-corte-presentation.md), seção `api/schemas/`

## Contexto

`backend/src/presentation/api/schemas.py` (303 linhas) mistura os schemas HTTP de health, erros, provas e ingestão, taxonomias, perfis e execuções de classificação. `schemas_questoes.py` (237 linhas) já é separado por recurso. Os dois viram um só pacote, com um submódulo por roteador de `api/v1/`, e `schemas_questoes.py` é apagado sem módulo de compatibilidade.

Mover um modelo Pydantic de módulo não muda o nome do componente no OpenAPI: o nome vem do `__name__` da classe (teste com FastAPI 0.165.0 e Pydantic 2.14.4 registrado na [decisão 04](../decisoes/04-corte-presentation.md)).

## Entrega observável

O pacote `backend/src/presentation/api/schemas/` existe, `schemas.py` e `schemas_questoes.py` não existem mais, e `from presentation.api.schemas import <nome>` vale para os 62 nomes públicos dos dois arquivos antigos.

## Organização-alvo

```text
presentation/api/schemas/
├── __init__.py          # reexporta os 62 nomes, com __all__
├── erro.py              # ErroDetalheResponse
├── health.py            # WorkerHealthResponse, HealthResponse
├── prova.py             # 12 classes de provas e ingestão (ConflitoProvaResponse ... ReprocessarProvaAceitaResponse)
├── taxonomia.py         # 8 classes de taxonomias e disciplinas, incluindo DisciplinaCriacaoInput
├── perfil.py            # PerfilClassificacaoCriarRequest, PerfilClassificacaoResponse, ListaPerfisClassificacaoResponse
├── execucao.py          # 8 classes de execuções de classificação e snapshots
└── questao.py           # todo o conteúdo atual de schemas_questoes.py (constantes LIMITE_* e MAX_* e 20 classes)
```

A lista de classes de cada submódulo está na [decisão 04](../decisoes/04-corte-presentation.md).

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-10` e os argumentos:
   - arquivos antigos: `src/presentation/api/schemas.py src/presentation/api/schemas_questoes.py`
2. Dois `git mv`, nesta ordem:
   - `git mv src/presentation/api/schemas_questoes.py src/presentation/api/schemas/questao.py` (conteúdo inteiro, sem alteração);
   - `git mv src/presentation/api/schemas.py src/presentation/api/schemas/prova.py` (`prova.py` é o maior submódulo que sai de `schemas.py`).
3. Crie `erro.py`, `health.py`, `taxonomia.py`, `perfil.py` e `execucao.py` movendo as classes de `prova.py`, sem alterar o corpo e sem mudar nomes de classes.
4. Imports entre submódulos pelo caminho direto (por exemplo, `from presentation.api.schemas.erro import ErroDetalheResponse`), nunca por `presentation.api.schemas`.
5. `__init__.py` com `__all__` contendo todos os nomes públicos de `schemas.py` e `schemas_questoes.py`, constantes incluídas. O arquivo `$PORTAO/nomes.json` do passo 1 traz a lista completa.
6. Troque `presentation.api.schemas_questoes` por `presentation.api.schemas` nos dois únicos consumidores: `api/v1/questoes.py` e `api/v1/ativos_visuais.py`. Os demais `from presentation.api.schemas import ...` não mudam.
7. Portão "depois" com o pacote `presentation.api.schemas` e sem `--fora`.
8. Não há referência a corrigir em `docs/planejamento-inicial/explicacao.md`.
9. Registre as saídas, marque a tarefa como `concluida` e faça o commit `refactor(presentation): dividir schemas.py e schemas_questoes.py em pacote`.

## Dependências

- [09 — Dividir `persistence/avaliacao.py` em pacote](09-infrastructure-avaliacao.md) commitada.

## Critérios de aceite

- [ ] `schemas.py` e `schemas_questoes.py` removidos e os 7 submódulos criados.
- [ ] `__all__` com os 62 nomes; script de reexportação com 0 falhas.
- [ ] `grep -rn schemas_questoes src tests` sem saída.
- [ ] `cmp` do OpenAPI sem diferença: mesmos 74 componentes, mesmos `operationId` e mesma ordem de `paths`.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] Fora do pacote novo, só `api/v1/questoes.py` e `api/v1/ativos_visuais.py` mudam, e só na linha do import.
- [ ] Cada arquivo novo com até cerca de 400 linhas.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/presentation/api/schemas/*.py
grep -rn schemas_questoes src tests                   # sem saída
git diff --stat HEAD -- src/presentation/api/v1/      # só questoes.py e ativos_visuais.py
```

## Evidências e pendências

Nenhuma ainda.
