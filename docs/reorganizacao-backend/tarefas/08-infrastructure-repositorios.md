# 08 — Dividir `persistence/repositorios.py` em pacote e extrair `busca_textual.py`

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 03](../decisoes/03-corte-infrastructure.md), seções `persistence/repositorios/`, "Mapeadores ORM↔domínio compartilhados" e `persistence/busca_textual.py`

## Contexto

`backend/src/infrastructure/persistence/repositorios.py` tem 1910 linhas, com 9 repositórios, os mapeadores ORM↔domínio e `condicao_busca_textual`. `consulta_questoes.py` e `persistence/avaliacao.py` importam mapeadores privados do arquivo. Por isso esta tarefa é atômica: o pacote, o módulo de busca textual e a troca desses imports entram no mesmo commit, senão os testes falham.

## Entrega observável

- O pacote `backend/src/infrastructure/persistence/repositorios/` existe e `repositorios.py` não existe mais.
- `from infrastructure.persistence.repositorios import Repositorio<X>SqlAlchemy` continua válido para as 9 classes.
- `condicao_busca_textual` mora em `infrastructure/persistence/busca_textual.py`.
- `consulta_questoes.py` e `persistence/avaliacao.py` importam os mapeadores públicos dos submódulos donos.

## Organização-alvo

```text
infrastructure/persistence/
├── busca_textual.py     # novo: condicao_busca_textual; _escapar_like, _CARACTERES_TECNICOS_RE
└── repositorios/
    ├── __init__.py      # reexporta só as 9 classes Repositorio*SqlAlchemy, com __all__
    ├── prova.py         # RepositorioProvasSqlAlchemy, para_dominio_prova
    ├── ingestao.py      # RepositorioIngestoesSqlAlchemy; _para_dominio_ingestao, _parse_uuid_opcional,
    │                    # _para_dict_metadados_ingestao
    ├── questao.py       # RepositorioQuestoesSqlAlchemy, para_dominio_questao; _R   (exceção aceita, ~480)
    ├── ativo_visual.py  # RepositorioAtivosVisuaisSqlAlchemy, para_dominio_ativo, para_dict_bbox
    ├── taxonomia.py     # RepositorioTaxonomiasSqlAlchemy, para_dominio_taxonomia
    ├── perfil.py        # RepositorioPerfisClassificacaoSqlAlchemy, para_dominio_perfil
    ├── execucao.py      # RepositorioExecucoesClassificacaoSqlAlchemy; _para_dominio_execucao, _descongelar_json
    ├── classificacao.py # RepositorioClassificacoesSqlAlchemy, para_dominio_classificacao, para_modelo_classificacao
    ├── divergencia.py   # RepositorioDivergenciasReclassificacaoSqlAlchemy, para_dominio_divergencia
    └── _apoio.py        # _agora_utc (usado por 6 submódulos)
```

### Renomeações dos mapeadores compartilhados

Só muda o nome. O corpo é o mesmo.

| Hoje (em `repositorios.py`) | Depois | Submódulo dono | Importado por |
|---|---|---|---|
| `_para_dominio_prova` | `para_dominio_prova` | `prova.py` | `persistence/avaliacao.py` |
| `_para_dominio_questao` | `para_dominio_questao` | `questao.py` | `consulta_questoes.py`, `persistence/avaliacao.py` |
| `_para_dominio_ativo` | `para_dominio_ativo` | `ativo_visual.py` | `repositorios/questao.py` |
| `_para_dict_bbox` | `para_dict_bbox` | `ativo_visual.py` | `repositorios/questao.py` |
| `_para_dominio_taxonomia` | `para_dominio_taxonomia` | `taxonomia.py` | `persistence/avaliacao.py` |
| `_para_dominio_perfil` | `para_dominio_perfil` | `perfil.py` | `persistence/avaliacao.py` |
| `_para_dominio_classificacao` | `para_dominio_classificacao` | `classificacao.py` | `consulta_questoes.py`, `persistence/avaliacao.py` |
| `_para_modelo_classificacao` | `para_modelo_classificacao` | `classificacao.py` | `repositorios/divergencia.py` |
| `_para_dominio_divergencia` | `para_dominio_divergencia` | `divergencia.py` | `consulta_questoes.py` |

A coluna "Importado por" lista os consumidores fora do submódulo dono, conforme a [decisão 03](../decisoes/03-corte-infrastructure.md). Os mapeadores continuam fora do `__all__` do pacote.

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-08` e os argumentos:
   - arquivos antigos: `src/infrastructure/persistence/repositorios.py`
2. `git mv src/infrastructure/persistence/repositorios.py src/infrastructure/persistence/repositorios/questao.py`. `questao.py` é o submódulo que fica com a maior parte do código.
3. Crie `busca_textual.py` em `persistence/`, ao lado de `predicados.py`, com `condicao_busca_textual`, `_escapar_like` e `_CARACTERES_TECNICOS_RE`.
4. Crie os outros 8 submódulos e `_apoio.py` movendo os símbolos, sem alterar o corpo. Aplique as renomeações da tabela acima em todas as definições e chamadas.
5. Imports entre submódulos pelo caminho direto (por exemplo, `from infrastructure.persistence.repositorios.ativo_visual import para_dominio_ativo`), nunca por `infrastructure.persistence.repositorios`.
6. `__init__.py` com `__all__`: `RepositorioAtivosVisuaisSqlAlchemy`, `RepositorioClassificacoesSqlAlchemy`, `RepositorioDivergenciasReclassificacaoSqlAlchemy`, `RepositorioExecucoesClassificacaoSqlAlchemy`, `RepositorioIngestoesSqlAlchemy`, `RepositorioPerfisClassificacaoSqlAlchemy`, `RepositorioProvasSqlAlchemy`, `RepositorioQuestoesSqlAlchemy`, `RepositorioTaxonomiasSqlAlchemy`.
7. Troque os imports dos consumidores. Hoje são:
   - `consulta_questoes.py`: `from infrastructure.persistence.repositorios import (_para_dominio_classificacao, _para_dominio_divergencia, _para_dominio_questao, condicao_busca_textual)`;
   - `persistence/avaliacao.py`: `from infrastructure.persistence.repositorios import (_para_dominio_classificacao, _para_dominio_perfil, _para_dominio_prova, _para_dominio_questao, _para_dominio_taxonomia)`.

   Cada nome passa a vir do submódulo dono, sem o `_`, e `condicao_busca_textual` vem de `infrastructure.persistence.busca_textual`. Atualize também os usos desses nomes no corpo dos dois arquivos. Não mude mais nada neles.
8. Não altere `persistence/__init__.py`, `persistence/seed.py`, `presentation/main.py` nem `tests/`.
9. Portão "depois" com os argumentos:
   - pacote: `infrastructure.persistence.repositorios`
   - `--fora condicao_busca_textual=infrastructure.persistence.busca_textual`
10. Em `docs/planejamento-inicial/explicacao.md`:
    - troque `backend/src/infrastructure/persistence/repositorios.py:1733` (`RepositorioDivergenciasReclassificacaoSqlAlchemy.resolver_atomicamente`) por `backend/src/infrastructure/persistence/repositorios/divergencia.py:<linha>`;
    - recalcule `backend/src/infrastructure/persistence/consulta_questoes.py:139-145` (bloco de ordenação da `FILA_REVISAO`, de `if filtro.ordenacao == OrdenacaoConsulta.FILA_REVISAO:` até `ordenacao.extend([ProvaModel.ano.desc(), QuestaoModel.numero.asc()])`), porque a troca dos imports desloca as linhas.
11. Registre as saídas, marque a tarefa como `concluida` e faça o commit `refactor(infrastructure): dividir repositorios.py em pacote`.

## Dependências

- [07 — Dividir `persistence/models.py` em pacote](07-infrastructure-models.md) commitada.

## Critérios de aceite

- [ ] `repositorios.py` removido; os 10 arquivos do pacote e `busca_textual.py` criados.
- [ ] `__all__` com as 9 classes; script de reexportação com 0 falhas, com `condicao_busca_textual` encontrada em `busca_textual`.
- [ ] Os 9 mapeadores da tabela sem `_`; nenhum import de nome privado de `repositorios` fora do pacote.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] `persistence/__init__.py`, `persistence/seed.py` e `presentation/main.py` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas, exceto `repositorios/questao.py` (exceção aceita).
- [ ] As duas referências de `explicacao.md` corrigidas.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/infrastructure/persistence/repositorios/*.py src/infrastructure/persistence/busca_textual.py
grep -rn "from infrastructure.persistence.repositorios[a-z_.]* import" src tests | grep "import.*\b_"   # sem saída
grep -rn "_para_dominio_\(prova\|questao\|ativo\|taxonomia\|perfil\|classificacao\|divergencia\)\b\|_para_modelo_classificacao\|_para_dict_bbox" src   # sem saída
git diff --exit-code HEAD -- src/infrastructure/persistence/__init__.py src/infrastructure/persistence/seed.py src/presentation/main.py
```

O primeiro `grep` cobre imports em uma linha. Confira também os blocos com parênteses em `consulta_questoes.py` e `persistence/avaliacao.py`.

## Evidências e pendências

Nenhuma ainda.
