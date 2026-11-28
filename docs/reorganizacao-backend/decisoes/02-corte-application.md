# Definir o corte dos arquivos de `application/`

Type: grilling
Status: open
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
