# Mapa — Reorganização dos arquivos do backend

## Destination

Especificação da organização-alvo dos arquivos de `backend/src/`, com as camadas hexagonais no topo e subpacotes por agregado, e a sequência de tarefas de migração puramente estrutural, pronta para virar `plano.md` e `tarefas/`.

## Notes

- **Regras fixadas no alinhamento**: ver [task.md](task.md). Resumo: refatoração só estrutural (comportamento, OpenAPI e banco idênticos); teto orientativo de cerca de 400 linhas; `__init__.py` reexportando os nomes públicos; mapeadores junto do repositório; classe única acima do teto é exceção aceita; contratos do `import-linter` inalterados.
- **Planejar, não executar**: os tickets decidem onde cada símbolo vai morar. Mover código fica para as tarefas de implementação depois do mapa.
- **Como resolver um ticket de corte**: o agente levanta os símbolos e o tamanho de cada arquivo da camada, propõe a árvore-alvo (símbolo → arquivo), e o usuário valida. Usar as skills `grilling` e `codebase-design`.
- **Tracker local**: `docs/reorganizacao-backend/` (`mapa.md`, `decisoes/NN-<slug>.md`).

## Decisions so far

<!-- uma linha por ticket resolvido -->

- [Definir o corte dos arquivos de `domain/`](decisoes/01-corte-domain.md): `classificacao.py`, `prova.py` e `avaliacao.py` viram pacotes (3, 5 e 2 submódulos), os validadores privados ficam no submódulo que os usa ou em `_validacao.py` do pacote, e os demais arquivos de `domain/`, incluindo `__init__.py` e `alertas_extracao.py`, ficam como estão.

## Not yet specified

- Nenhuma névoa identificada além dos tickets abertos. Se um corte revelar acoplamento que impeça mover código sem mudar design (por exemplo, import circular entre submódulos), registrar aqui.

## Out of scope

- **Fatias verticais por contexto** (`provas/`, `questoes/`, `classificacao/`...): descartadas porque reabririam a [decisão 08](../planejamento-inicial/decisoes/08-arquitetura-e-simplificacao-stack.md) e o problema descrito é só o tamanho dos arquivos.
- **Dividir classes grandes** (`WorkerLocal`, `ClienteOpenAICompativel`, `RepositorioQuestoesSqlAlchemy`) ou extrair lógica e mudar interfaces: são mudanças de design, não estruturais.
- **Reorganizar `backend/tests/`**: neste esforço os testes recebem apenas ajustes de import.
- **Contratos novos do `import-linter`** entre subpacotes.
- **Frontend, protótipos e migrações Alembic.**
