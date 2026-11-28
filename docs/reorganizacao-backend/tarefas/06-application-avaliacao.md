# 06 — Dividir `application/avaliacao.py` em pacote

Status: `pendente`

Plano: [plano.md](../plano.md) · Explicação: [explicacao.md](../explicacao.md) · Validação: [validacao.md](../validacao.md) · Corte: [decisão 02](../decisoes/02-corte-application.md), seção `application/avaliacao/`

## Contexto

`backend/src/application/avaliacao.py` tem 738 linhas e junta a serialização JSON e o relatório Markdown da avaliação, o carregamento de perfil e 4 casos de uso da CLI `enade-eval`. A tarefa transforma o arquivo no pacote `application/avaliacao/`.

## Entrega observável

O pacote `backend/src/application/avaliacao/` existe, `application/avaliacao.py` não existe mais, e `from application.avaliacao import <nome>` continua válido para os 16 nomes públicos de hoje.

## Organização-alvo

```text
application/avaliacao/
├── __init__.py          # reexporta os 16 nomes, com __all__
├── relatorio.py         # VERSAO_RELATORIO_AVALIACAO, avaliacao_para_dict, avaliacao_de_dict,
│                        # carregar_relatorio_avaliacao, renderizar_relatorio_markdown;
│                        # _parse_datetime_iso, _chave_de_mapping
├── avaliacao.py         # PreflightConjuntoOuroError, ResultadoExportacaoOuro, ResultadoAvaliacaoOffline,
│                        # ResultadoComparacaoAvaliacoes, carregar_perfil_avaliacao, ExportarConjuntoOuroUseCase,
│                        # AvaliarConjuntoOuroUseCase, CompararAvaliacoesUseCase;
│                        # _agora_utc, _sanitizar_segmento, _SLUG_SAFE_RE
└── historico.py         # GrupoHistoricoConcordancia, ResultadoHistoricoConcordancia,
                         # ConsultarHistoricoConcordanciaUseCase
```

Nenhum privado é compartilhado entre submódulos, então o pacote não tem `_apoio.py`. `avaliacao.py` importa de `application.avaliacao.relatorio`. Detalhes na [decisão 02](../decisoes/02-corte-application.md).

## Passos

1. Portão "antes" com `PORTAO=…/reorganizacao-backend-06` e os argumentos:
   - arquivos antigos: `src/application/avaliacao.py`
2. `git mv src/application/avaliacao.py src/application/avaliacao/relatorio.py`. `relatorio.py` é o submódulo que fica com a maior parte do código.
3. Crie `avaliacao.py` e `historico.py` movendo os símbolos, sem alterar o corpo.
4. `__init__.py` com `__all__`: `AvaliarConjuntoOuroUseCase`, `CompararAvaliacoesUseCase`, `ConsultarHistoricoConcordanciaUseCase`, `ExportarConjuntoOuroUseCase`, `GrupoHistoricoConcordancia`, `PreflightConjuntoOuroError`, `ResultadoAvaliacaoOffline`, `ResultadoComparacaoAvaliacoes`, `ResultadoExportacaoOuro`, `ResultadoHistoricoConcordancia`, `VERSAO_RELATORIO_AVALIACAO`, `avaliacao_de_dict`, `avaliacao_para_dict`, `carregar_perfil_avaliacao`, `carregar_relatorio_avaliacao`, `renderizar_relatorio_markdown`.
5. Portão "depois" com o pacote `application.avaliacao` e sem `--fora`.
6. Em `docs/planejamento-inicial/explicacao.md`, troque `backend/src/application/avaliacao.py:651`-`:672` (`executado_em=instante` e `chave_md_salva = ...` em `AvaliarConjuntoOuroUseCase.execute`) por `backend/src/application/avaliacao/avaliacao.py:<linha>`-`:<linha>`.
7. Registre as saídas, marque a tarefa como `concluida` e faça o commit `refactor(application): dividir avaliacao.py em pacote`.

## Dependências

- [05 — Dividir `application/classificacao.py` em pacote](05-application-classificacao.md) commitada.

## Critérios de aceite

- [ ] `application/avaliacao.py` removido e os 3 submódulos criados.
- [ ] `__all__` com os 16 nomes; script de reexportação com 0 falhas.
- [ ] `cmp` do OpenAPI sem diferença.
- [ ] `pytest`, `ruff check`, `ruff format --check` e `lint-imports` passando, sem mudança em `tests/`.
- [ ] `presentation/cli/` sem diferença.
- [ ] Cada arquivo novo com até cerca de 400 linhas.
- [ ] Referência de `explicacao.md` corrigida.

## Verificação

Portão de [validacao.md](../validacao.md#procedimento-do-portão), mais:

```sh
wc -l src/application/avaliacao/*.py
git diff --exit-code HEAD -- src/presentation/cli/
```

## Evidências e pendências

Nenhuma ainda.
