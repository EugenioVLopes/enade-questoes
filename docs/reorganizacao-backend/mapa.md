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
- [Definir o corte dos arquivos de `application/`](decisoes/02-corte-application.md): `avaliacao.py`, `questoes.py` e `classificacao.py` viram pacotes (3, 4 e 2 submódulos, com `_apoio.py` privado em `questoes/`), enquanto `worker.py`, `provas.py`, `execucoes_classificacao.py`, `ports/` e os demais ficam como estão.
- [Definir o corte dos arquivos de `infrastructure/`](decisoes/03-corte-infrastructure.md): `persistence/repositorios.py` vira pacote com 9 submódulos e `_apoio.py`, `models.py` com 3 submódulos e `base.py`, e `persistence/avaliacao.py` com 2. Os mapeadores compartilhados ficam públicos no submódulo dono, `condicao_busca_textual` vai para `persistence/busca_textual.py`, e `cliente_openai.py` e `posprocessamento.py` ficam como estão.
- [Definir o corte dos arquivos de `presentation/`](decisoes/04-corte-presentation.md): `api/schemas.py` e `schemas_questoes.py` viram o pacote `api/schemas/` com 7 submódulos, um por roteador, e `schemas_questoes.py` é apagado. `api/v1/questoes.py` vira pacote com `rotas.py` e `serializacao.py`, com os serializadores públicos. Os demais arquivos ficam como estão, e mover modelos Pydantic de módulo não altera o OpenAPI.
- [Definir a sequência das tarefas de migração](decisoes/05-sequencia-migracao.md): 11 tarefas, um commit por tarefa, de `domain/` até `presentation/`. Só `repositorios.py`, com `busca_textual.py` e os imports dos mapeadores, e o par `schemas.py` + `schemas_questoes.py` migram juntos. O portão de cada tarefa tem cmp do OpenAPI antes/depois, checagem de nomes reexportados, `pytest` completo, `ruff`, `lint-imports` e o teto de linhas, e cada tarefa atualiza as referências `arquivo:linha` de `docs/planejamento-inicial/explicacao.md`, sem mexer no `README.md`.

## Not yet specified

- Nenhuma. O caminho até o destino está claro, e o próximo passo é gerar `plano.md`, `explicacao.md`, `validacao.md` e `tarefas/` a partir das decisões 01 a 05.

## Out of scope

- **Fatias verticais por contexto** (`provas/`, `questoes/`, `classificacao/`...): descartadas porque reabririam a [decisão 08](../planejamento-inicial/decisoes/08-arquitetura-e-simplificacao-stack.md) e o problema descrito é só o tamanho dos arquivos.
- **Dividir classes grandes** (`WorkerLocal`, `ClienteOpenAICompativel`, `RepositorioQuestoesSqlAlchemy`) ou extrair lógica e mudar interfaces: são mudanças de design, não estruturais.
- **Reorganizar `backend/tests/`**: neste esforço os testes recebem apenas ajustes de import.
- **Contratos novos do `import-linter`** entre subpacotes.
- **Frontend, protótipos e migrações Alembic.**
