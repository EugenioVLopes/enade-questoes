# 01 — Dividir `domain/prova.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 01](../decisoes/01-corte-domain.md), seção `domain/prova/`

## Contexto

`backend/src/domain/prova.py` tem 481 linhas e junta Prova, Ingestão, Questão e Alerta de Extração. A tarefa transforma o arquivo no pacote `domain/prova/`, um submódulo por entidade, sem mudar comportamento.

## Entrega observável

O pacote `backend/src/domain/prova/` existe, `domain/prova.py` não existe mais, e `from domain.prova import <nome>` continua válido para os 13 nomes públicos de hoje.

## Organização-alvo

```text
domain/prova/
├── __init__.py          # reexporta os 13 nomes, com __all__
├── prova.py             # Prova, FaixaQuestoes
├── ingestao.py          # Ingestao, MetadadosIngestao
├── questao.py           # Questao, Alternativa, Gabarito, AtivoVisual, BoundingBox, _copiar_lista_validada
├── alerta_extracao.py   # AlertaExtracao, SEVERIDADE_POR_CODIGO, ALERTAS_ESTRUTURAIS, ALERTAS_INSPECAO
└── _validacao.py        # _validar_inteiro_positivo, _validar_inteiro_nao_negativo
```

A tabela símbolo → submódulo, com as linhas estimadas, está na [decisão 01](../decisoes/01-corte-domain.md).

## Passos

1. Rode o portão "antes" de [validacao.md](../validacao.md#1-antes-de-editar) com `PORTAO=…/reorganizacao-backend-01` e os argumentos:
   - arquivos antigos: `src/domain/prova.py`
2. `git mv src/domain/prova.py src/domain/prova/questao.py`. `questao.py` é o submódulo que fica com a maior parte do código.
3. Crie `prova.py`, `ingestao.py`, `alerta_extracao.py` e `_validacao.py` movendo os símbolos de `questao.py`, sem alterar o corpo de classes e funções.
4. Em cada submódulo, deixe só os imports usados e importe os outros submódulos pelo caminho direto (por exemplo, `from domain.prova.alerta_extracao import AlertaExtracao`), nunca por `domain.prova`.
5. Escreva `__init__.py` reexportando, com `__all__` explícito: `ALERTAS_ESTRUTURAIS`, `ALERTAS_INSPECAO`, `AlertaExtracao`, `Alternativa`, `AtivoVisual`, `BoundingBox`, `FaixaQuestoes`, `Gabarito`, `Ingestao`, `MetadadosIngestao`, `Prova`, `Questao`, `SEVERIDADE_POR_CODIGO`. Os privados não entram.
6. Não altere `domain/__init__.py` nem `domain/alertas_extracao.py`. Os dois continuam importando de `domain.prova`.
7. Rode o portão "depois" com o pacote `domain.prova` e sem `--fora`.
8. Em `docs/planejamento-inicial/explicacao.md`, troque `backend/src/domain/prova.py:34` (início de `ALERTAS_ESTRUTURAIS`) por `backend/src/domain/prova/alerta_extracao.py:<linha de ALERTAS_ESTRUTURAIS>`.
9. Registre as saídas em [validacao.md](../validacao.md), marque esta tarefa e a linha do [plano](../plano.md) como `concluida` e faça o commit `refactor(domain): dividir prova.py em pacote`.

## Dependências

- Nenhuma tarefa anterior. Comece com a árvore limpa no commit em que o planejamento foi registrado.

## Critérios de aceite

- [ ] `domain/prova.py` removido e os 5 submódulos criados com os símbolos da decisão 01.
- [ ] `__init__.py` com `__all__` dos 13 nomes; o script de reexportação sai com 0 falhas.
- [ ] `cmp` do OpenAPI antes/depois sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` (3 contratos mantidos) passando, sem mudança em `tests/`.
- [ ] `git diff --exit-code HEAD -- src/domain/__init__.py src/domain/alertas_extracao.py` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas.
- [ ] Referência de `explicacao.md` corrigida.

## Verificação

Comandos do portão em [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/domain/prova/*.py
git diff --exit-code HEAD -- src/domain/__init__.py src/domain/alertas_extracao.py
```

## Evidências e pendências

Nenhuma ainda.
