# 02 — Dividir `domain/classificacao.py` em pacote

Status: `aguardando aceite` (executada e verificada; falta validação manual e aceite)

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

- [x] `domain/classificacao.py` removido e os 3 submódulos criados com os símbolos da decisão 01.
- [x] `__all__` com os 6 nomes; script de reexportação com 0 falhas.
- [x] `cmp` do OpenAPI sem diferença.
- [x] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [x] `domain/__init__.py` sem diferença.
- [x] Cada arquivo novo com até cerca de 400 linhas.
- [x] As duas referências de `explicacao.md` corrigidas.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/domain/classificacao/*.py
git diff --exit-code HEAD -- src/domain/__init__.py
```

## Evidências e pendências

Executada em 2026-11-28 sobre o commit `76b0cfb`, com o workflow teamwork (2 iterações, `VICTORY CONFIRMED`). As saídas do portão estão em [validacao.md](../validacao.md#tarefa-02).

- `wc -l src/domain/classificacao/*.py`: `execucao.py` 270, `classificacao.py` 253, `perfil.py` 112, `__init__.py` 21.
- Corpos dos 12 símbolos de topo (6 funções privadas, 4 classes e 2 funções públicas) iguais aos de `HEAD` pelo texto-fonte com decorators. Os 169 cenários de runtime comparados com `HEAD` deram saídas e exceções iguais.
- Única dependência entre submódulos: `execucao.py` importa `PerfilClassificacao` de `domain.classificacao.perfil`. Sem ciclo.
- `docs/planejamento-inicial/explicacao.md:118` passou a citar `backend/src/domain/classificacao/classificacao.py:114` (`def substituir_por_correcao(`) e `:180` (`origem=OrigemClassificacao.HUMANA,` em `criar_classificacao_humana`, a mesma instrução que a antiga `:540` apontava). A iteração 1 corrigiu só a primeira referência, e o gate reprovou. A iteração 2 corrigiu a segunda.
- `__module__` das classes passou de `domain.classificacao` para o submódulo, e `domain.classificacao` deixou de expor como atributo os nomes que o módulo antigo só importava (`math`, `Any`, `Taxonomia`, enums). Nenhum código em `src/` ou `tests/` depende disso.
- Validação manual e aceite: pendentes.
