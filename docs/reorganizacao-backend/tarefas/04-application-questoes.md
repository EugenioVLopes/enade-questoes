# 04 — Dividir `application/questoes.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 02](../decisoes/02-corte-application.md), seção `application/questoes/`

## Contexto

`backend/src/application/questoes.py` tem 535 linhas e junta quatro grupos de casos de uso: consulta, detalhe, edição de conteúdo com resolução de alerta, e gestão de ativos visuais. A tarefa transforma o arquivo no pacote `application/questoes/`, um submódulo por grupo.

## Entrega observável

O pacote `backend/src/application/questoes/` existe, `application/questoes.py` não existe mais, e `from application.questoes import <nome>` continua válido para os 18 nomes públicos de hoje.

## Organização-alvo

```text
application/questoes/
├── __init__.py          # reexporta os 18 nomes, com __all__
├── consulta.py          # ANO_MINIMO, ANO_MAXIMO, PAGINA_MAXIMA, ParametrosConsultaQuestoes,
│                        # ResultadoConsultaQuestoes, ConsultarQuestoesUseCase
├── detalhe.py           # ClassificacaoOutraTaxonomia, DetalheQuestao, DetalharQuestaoUseCase
├── edicao.py            # AlternativaEdicao, GabaritoEdicao, EditarConteudoQuestaoUseCase,
│                        # ResolverAlertaExtracaoUseCase, recalcular_revisao_prioritaria_pendentes; _agora_utc
├── ativo_visual.py      # TAMANHO_MAXIMO_IMAGEM_BYTES, AdicionarAtivoVisualUseCase, AtualizarAtivoVisualUseCase,
│                        # RemoverAtivoVisualUseCase; _GestaoAtivosBase, _chave_ativo, _validar_tamanho_imagem
└── _apoio.py            # _buscar_questao (usado por detalhe, edição e ativo visual)
```

Detalhes e linhas estimadas na [decisão 02](../decisoes/02-corte-application.md).

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-04` e os argumentos:
   - arquivos antigos: `src/application/questoes.py`
2. `git mv src/application/questoes.py src/application/questoes/ativo_visual.py`. `ativo_visual.py` é o submódulo que fica com a maior parte do código.
3. Crie `consulta.py`, `detalhe.py`, `edicao.py` e `_apoio.py` movendo os símbolos, sem alterar o corpo. `_buscar_questao` vai para `_apoio.py` e mantém o nome.
4. Imports entre submódulos pelo caminho direto (por exemplo, `from application.questoes._apoio import _buscar_questao`), nunca por `application.questoes`.
5. `__init__.py` com `__all__`: `ANO_MAXIMO`, `ANO_MINIMO`, `AdicionarAtivoVisualUseCase`, `AlternativaEdicao`, `AtualizarAtivoVisualUseCase`, `ClassificacaoOutraTaxonomia`, `ConsultarQuestoesUseCase`, `DetalharQuestaoUseCase`, `DetalheQuestao`, `EditarConteudoQuestaoUseCase`, `GabaritoEdicao`, `PAGINA_MAXIMA`, `ParametrosConsultaQuestoes`, `RemoverAtivoVisualUseCase`, `ResolverAlertaExtracaoUseCase`, `ResultadoConsultaQuestoes`, `TAMANHO_MAXIMO_IMAGEM_BYTES`, `recalcular_revisao_prioritaria_pendentes`.
6. Portão "depois" com o pacote `application.questoes` e sem `--fora`.
7. Em `docs/planejamento-inicial/explicacao.md`, troque `backend/src/application/questoes.py:355` (chamada a `reavaliar_alertas_estruturais` em `EditarConteudoQuestaoUseCase.execute`) por `backend/src/application/questoes/edicao.py:<linha>`.
8. Registre as saídas, marque a tarefa como `concluida` e faça o commit `refactor(application): dividir questoes.py em pacote`.

## Dependências

- [03 — Dividir `domain/avaliacao.py` em pacote](03-domain-avaliacao.md) commitada.

## Critérios de aceite

- [ ] `application/questoes.py` removido e os 5 submódulos criados.
- [ ] `__all__` com os 18 nomes; script de reexportação com 0 falhas.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] Cada arquivo novo com até cerca de 400 linhas.
- [ ] Referência de `explicacao.md` corrigida.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/application/questoes/*.py
```

## Evidências e pendências

Nenhuma ainda.
