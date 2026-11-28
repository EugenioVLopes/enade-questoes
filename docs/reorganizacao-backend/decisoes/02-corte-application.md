# Definir o corte dos arquivos de `application/`

Type: grilling
Status: resolved
Blocked by: none

## Question

Seguindo as regras de [task.md](../task.md), qual é a organização-alvo de `backend/src/application/`, símbolo por símbolo?

Arquivos candidatos (contagem de linhas de 2026-11-28):

- `avaliacao.py` (738 linhas): serialização JSON (`avaliacao_para_dict`, `avaliacao_de_dict`), relatório Markdown, carregamento de perfil e 4 casos de uso.
- `worker.py` (559 linhas): `WorkerLocal` (classe única, exceção aceita), além dos Protocols `ClassificacaoEncadeadaHook`, `ExecutorClassificacao` e das tarefas `TarefaIngestao` e `TarefaClassificacao`. O que sai do arquivo?
- `questoes.py` (535 linhas): consulta, detalhe, edição, resolução de alerta e gestão de ativos visuais.
- `classificacao.py` (459 linhas): montagem de prompt e schema, além de `ClassificarQuestaoService`. Avaliar se o corte compensa.
- `provas.py` (434 linhas) e `execucoes_classificacao.py` (412 linhas): coesos, avaliar um a um.

Também decidir para onde vão os auxiliares privados repetidos entre módulos (por exemplo, `_agora_utc`, que aparece em vários arquivos). Eles ficam duplicados como hoje, já que a refatoração é só estrutural?

## Answer

Resolvido em 2026-11-28 (grilling com o usuário). Contagens de linhas aproximadas: spans medidos por AST sobre os arquivos atuais mais estimativa dos imports.

### `application/avaliacao/` (substitui `avaliacao.py`, 738 linhas)

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `relatorio.py` | `VERSAO_RELATORIO_AVALIACAO`, `avaliacao_para_dict`, `avaliacao_de_dict`, `carregar_relatorio_avaliacao`, `renderizar_relatorio_markdown`; privados `_parse_datetime_iso`, `_chave_de_mapping` | 345 |
| `avaliacao.py` | `PreflightConjuntoOuroError`, `ResultadoExportacaoOuro`, `ResultadoAvaliacaoOffline`, `ResultadoComparacaoAvaliacoes`, `carregar_perfil_avaliacao`, `ExportarConjuntoOuroUseCase`, `AvaliarConjuntoOuroUseCase`, `CompararAvaliacoesUseCase`; privados `_agora_utc`, `_sanitizar_segmento`, `_SLUG_SAFE_RE` | 310 |
| `historico.py` | `GrupoHistoricoConcordancia`, `ResultadoHistoricoConcordancia`, `ConsultarHistoricoConcordanciaUseCase` | 75 |

Exportar e Avaliar ficam juntos porque são os únicos que usam `_agora_utc`, e assim nenhum privado é compartilhado. `avaliacao.py` importa de `relatorio.py`.

### `application/questoes/` (substitui `questoes.py`, 535 linhas)

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `consulta.py` | `ANO_MINIMO`, `ANO_MAXIMO`, `PAGINA_MAXIMA`, `ParametrosConsultaQuestoes`, `ResultadoConsultaQuestoes`, `ConsultarQuestoesUseCase` | 135 |
| `detalhe.py` | `ClassificacaoOutraTaxonomia`, `DetalheQuestao`, `DetalharQuestaoUseCase` | 100 |
| `edicao.py` | `AlternativaEdicao`, `GabaritoEdicao`, `EditarConteudoQuestaoUseCase`, `ResolverAlertaExtracaoUseCase`, `recalcular_revisao_prioritaria_pendentes`; privado `_agora_utc` | 135 |
| `ativo_visual.py` | `TAMANHO_MAXIMO_IMAGEM_BYTES`, `AdicionarAtivoVisualUseCase`, `AtualizarAtivoVisualUseCase`, `RemoverAtivoVisualUseCase`; privados `_GestaoAtivosBase`, `_chave_ativo`, `_validar_tamanho_imagem` | 155 |
| `_apoio.py` | privado `_buscar_questao` (usado por detalhe, edição e ativo visual) | 12 |

`ResolverAlertaExtracaoUseCase` fica em `edicao.py` porque, como `EditarConteudoQuestaoUseCase`, usa `recalcular_revisao_prioritaria_pendentes`.

### `application/classificacao/` (substitui `classificacao.py`, 459 linhas)

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `prompt.py` | `construir_json_schema_plano`, `montar_prompts_classificacao`; privados `_ORDEM_LETRAS`, `_PLACEHOLDER_RE`, `_renderizar_template_seguro`, `_formatar_catalogo_disciplinas`, `_formatar_alternativas`, `_formatar_alertas_extracao`, `_formatar_bloco_ativos`, `_normalizar_snapshot_taxonomia`, `_normalizar_snapshot_perfil`, `_hash_snapshot_canonico`, `_extrair_secoes_template` | 225 |
| `classificacao.py` | `MetricasClassificacao`, `ErroClassificacaoEstruturado`, `ResultadoClassificacaoQuestao`, `ClassificarQuestaoService`; privado `_ordenar_ativos_visuais` | 230 |

O arquivo está na faixa de 400 a 470 linhas e trata um só agregado, mas é dividido pela seam entre a montagem pura (schema e prompt) e a orquestração do serviço. `classificacao.py` importa de `prompt.py`. `infrastructure/llm/__init__.py` continua importando `construir_json_schema_plano` de `application.classificacao`.

### Arquivos que não mudam

- `worker.py` (559): é a exceção da regra 9, e nada sai do arquivo. Os auxiliares somam cerca de 40 linhas, então tirá-los deixaria o arquivo ainda acima do teto, com cerca de 515. Além disso, o pacote teria de reexportar o privado `_SENTINELA_PARAR`, que `tests/integration/test_worker_local.py` importa. `ClassificacaoEncadeadaHook` também não vai para `ports/`, porque é implementado dentro da própria aplicação (`HookClassificacaoEncadeada`).
- `provas.py` (434): trata um só agregado. Virar pacote quebraria o `monkeypatch.setattr(provas_mod, "aplicar_gabarito_na_prova", ...)` de `tests/integration/test_concorrencia_sistema.py`, porque o patch no pacote não alcança a referência no submódulo.
- `execucoes_classificacao.py` (412): trata um só agregado e passa do teto por cerca de 12 linhas.
- `__init__.py`, `taxonomias.py`, `seed.py`, `revisao.py`, `midia.py`, `health.py`, `busca.py`, `exceptions.py` e todo o `ports/` (o maior é `repositorios.py`, com 229 linhas).

### Regras gerais

- **Auxiliares privados**: o helper usado por um só submódulo vai junto dele. O helper usado por dois ou mais submódulos do mesmo pacote vai para `_apoio.py` nesse pacote e não é reexportado. As duplicatas entre módulos ou pacotes diferentes ficam como estão, sem unificação, e isso inclui as cópias de `_agora_utc`.
- **`__init__.py` dos pacotes novos**: reexporta todos os nomes públicos do antigo módulo, constantes incluídas, com `__all__` explícito.

### Fatos verificados

- Nenhum código de `src/` ou `tests/` importa nomes privados dos módulos que viram pacote nem faz `patch` neles por caminho de string. Também não há dependência de `__module__`, `__qualname__` ou pickle.
- O único monkeypatch em atributo de módulo de `application` é o de `application.provas`, que fica intacto.
- `pyproject.toml` empacota `src/application` inteiro, então os subpacotes entram sem configuração extra.

