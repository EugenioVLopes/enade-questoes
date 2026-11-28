# 02 — Dividir `domain/classificacao.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 01](../decisoes/01-corte-domain.md), seção `domain/classificacao/`

## Contexto

`backend/src/domain/classificacao.py` tem 613 linhas e junta Perfil de Classificação, Execução de Classificação, Classificação e Divergência de Reclassificação. A tarefa transforma o arquivo no pacote `domain/classificacao/`.

## Entrega observável

O pacote `backend/src/domain/classificacao/` existe, `domain/classificacao.py` não existe mais, e `from domain.classificacao import <nome>` continua válido para os 6 nomes públicos de hoje.

## Organização-alvo

```text
domain/classificacao/
├── __init__.py          # reexporta os 6 nomes, com __all__
├── perfil.py            # PerfilClassificacao
├── execucao.py          # ExecucaoClassificacao; _congelar_valor, _validar_colecao_uuids, _validar_nao_negativo_int
└── classificacao.py     # Classificacao, normalizar_topicos_curadoria, criar_classificacao_humana,
                         # DivergenciaReclassificacao; _validar_confianca, _validar_secundarias, _validar_colecao_strings
```

Cada validador privado é usado por um só submódulo, então o pacote não tem `_validacao.py`. `execucao.py` importa `PerfilClassificacao` de `domain.classificacao.perfil`. Detalhes na [decisão 01](../decisoes/01-corte-domain.md).

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-02` e os argumentos:
   - arquivos antigos: `src/domain/classificacao.py`
2. `git mv src/domain/classificacao.py src/domain/classificacao/execucao.py`. `execucao.py` é o submódulo que fica com a maior parte do código.
3. Crie `perfil.py` e `classificacao.py` movendo os símbolos de `execucao.py`, sem alterar o corpo.
4. Imports entre submódulos pelo caminho direto, nunca por `domain.classificacao`.
5. `__init__.py` com `__all__`: `Classificacao`, `DivergenciaReclassificacao`, `ExecucaoClassificacao`, `PerfilClassificacao`, `criar_classificacao_humana`, `normalizar_topicos_curadoria`.
6. Portão "depois" com o pacote `domain.classificacao` e sem `--fora`.
7. Em `docs/planejamento-inicial/explicacao.md`, na mesma frase, corrija as duas referências:
   - `backend/src/domain/classificacao.py:474` (`Classificacao.substituir_por_correcao`) → `backend/src/domain/classificacao/classificacao.py:<linha>`;
   - `:540` (`criar_classificacao_humana`) → linha nova no mesmo arquivo. Essa forma abreviada não aparece na tabela da [decisão 05](../decisoes/05-sequencia-migracao.md) e foi encontrada ao gerar esta tarefa.
8. Registre as saídas, marque a tarefa como `concluida` no arquivo e no plano e faça o commit `refactor(domain): dividir classificacao.py em pacote`.

## Dependências

- [01 — Dividir `domain/prova.py` em pacote](01-domain-prova.md) commitada.

## Critérios de aceite

- [ ] `domain/classificacao.py` removido e os 3 submódulos criados com os símbolos da decisão 01.
- [ ] `__all__` com os 6 nomes; script de reexportação com 0 falhas.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] `domain/__init__.py` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas.
- [ ] As duas referências de `explicacao.md` corrigidas.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/domain/classificacao/*.py
git diff --exit-code HEAD -- src/domain/__init__.py
```

## Evidências e pendências

Nenhuma ainda.
