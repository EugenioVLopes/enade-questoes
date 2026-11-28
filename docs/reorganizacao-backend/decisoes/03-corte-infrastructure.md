# Definir o corte dos arquivos de `infrastructure/`

Type: grilling
Status: resolved
Blocked by: none

## Question

Seguindo as regras de [task.md](../task.md), qual é a organização-alvo de `backend/src/infrastructure/`, símbolo por símbolo?

Arquivos candidatos (contagem de linhas de 2026-11-28):

- `persistence/repositorios.py` (1910 linhas): 9 repositórios (Provas, Ingestões, Questões, Ativos Visuais, Taxonomias, Perfis, Execuções, Classificações, Divergências), os mapeadores ORM↔domínio e `condicao_busca_textual`. É importado por `persistence/__init__.py`, `persistence/avaliacao.py`, `persistence/consulta_questoes.py`, `persistence/seed.py` e `presentation/main.py`.
- `persistence/models.py` (526 linhas): 13 modelos ORM de agregados diferentes. Decidir como manter `Base` e o registro de todos os modelos visível para o Alembic (`alembic/env.py`) depois do corte.
- `llm/cliente_openai.py` (526 linhas): `ClienteOpenAICompativel` (classe única, exceção aceita), além de `SaidaBrutaLLMSchema` e erros auxiliares.
- `extracao/posprocessamento.py` (471 linhas): coeso, avaliar.
- `persistence/avaliacao.py` (397 linhas): no limite, avaliar.

Mapeadores compartilhados já conhecidos: `_para_dominio_ativo` (usado pelo mapeador de Questão e pelo repositório de Ativos) e `condicao_busca_textual` (usado por `consulta_questoes.py`).

## Answer

Resolvido em 2026-11-28 (grilling com o usuário). As contagens de linhas são aproximadas: spans medidos por AST nos arquivos atuais, mais uma estimativa dos imports.

### `persistence/repositorios/` (substitui `repositorios.py`, 1910 linhas)

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `prova.py` | `RepositorioProvasSqlAlchemy`, `para_dominio_prova` | 100 |
| `ingestao.py` | `RepositorioIngestoesSqlAlchemy`; privados `_para_dominio_ingestao`, `_parse_uuid_opcional`, `_para_dict_metadados_ingestao` | 145 |
| `questao.py` | `RepositorioQuestoesSqlAlchemy`, `para_dominio_questao`; privado `_R` | 480 |
| `ativo_visual.py` | `RepositorioAtivosVisuaisSqlAlchemy`, `para_dominio_ativo`, `para_dict_bbox` | 95 |
| `taxonomia.py` | `RepositorioTaxonomiasSqlAlchemy`, `para_dominio_taxonomia` | 315 |
| `perfil.py` | `RepositorioPerfisClassificacaoSqlAlchemy`, `para_dominio_perfil` | 90 |
| `execucao.py` | `RepositorioExecucoesClassificacaoSqlAlchemy`; privados `_para_dominio_execucao`, `_descongelar_json` | 150 |
| `classificacao.py` | `RepositorioClassificacoesSqlAlchemy`, `para_dominio_classificacao`, `para_modelo_classificacao` | 250 |
| `divergencia.py` | `RepositorioDivergenciasReclassificacaoSqlAlchemy`, `para_dominio_divergencia` | 300 |
| `_apoio.py` | privado `_agora_utc` (usado por 6 submódulos) | 8 |

- Os nomes dos submódulos seguem `domain/`.
- `questao.py` passa do teto porque só a classe tem 399 linhas. É a exceção da regra 9 de [task.md](../task.md), e a classe não é dividida.
- O `__init__.py` reexporta as 9 classes `Repositorio*SqlAlchemy` com `__all__` explícito. Com isso, `presentation/main.py`, `persistence/seed.py`, `persistence/__init__.py` e os testes não mudam.

### Mapeadores ORM↔domínio compartilhados

Pela regra 7, cada mapeador compartilhado fica público, sem o `_`, no submódulo do repositório dono. Nenhum deles é reexportado pelo `__init__.py` do pacote.

- `para_dominio_ativo` e `para_dict_bbox` ficam em `ativo_visual.py`. `questao.py` importa de lá.
- `para_modelo_classificacao` fica em `classificacao.py`. `divergencia.py` importa de lá.
- `para_dominio_questao`, `para_dominio_prova`, `para_dominio_classificacao`, `para_dominio_divergencia`, `para_dominio_perfil` e `para_dominio_taxonomia` são hoje importados como privados por `persistence/consulta_questoes.py` e `persistence/avaliacao.py`. Esses dois módulos passam a importá-los do submódulo dono, por exemplo `from infrastructure.persistence.repositorios.questao import para_dominio_questao`.
- Os mapeadores usados por um só submódulo continuam privados e ficam junto dele.

### `persistence/busca_textual.py` (módulo novo)

- **Conteúdo:** `condicao_busca_textual` e os privados `_escapar_like` e `_CARACTERES_TECNICOS_RE`, em cerca de 85 linhas.
- **Local:** fica ao lado de `predicados.py`.
- **Consumidores:** `repositorios/questao.py` e `consulta_questoes.py` importam de lá.
- **Reexportação:** o pacote `repositorios/` não reexporta a função, porque o único consumidor é interno.

### `persistence/models/` (substitui `models.py`, 526 linhas)

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `base.py` | `Base` | 10 |
| `prova.py` | `ProvaModel`, `IngestaoModel`, `QuestaoModel`, `AlternativaModel`, `AtivoVisualModel`, `AlertaExtracaoModel` | 235 |
| `taxonomia.py` | `TaxonomiaModel`, `DisciplinaModel` | 55 |
| `classificacao.py` | `PerfilClassificacaoModel`, `ExecucaoClassificacaoModel`, `ClassificacaoModel`, `DivergenciaReclassificacaoModel` | 260 |

- O corte espelha os módulos de `domain/`, não os repositórios: os modelos são declarações finas.
- Nenhum `relationship` cruza arquivos. Entre agregados só há `ForeignKey` com o nome da tabela em string, então não há import circular nem `TYPE_CHECKING`.
- O `__init__.py` importa todos os submódulos e reexporta `Base` e os 13 modelos. Assim, `from infrastructure.persistence.models import Base`, em `alembic/env.py`, continua registrando o `metadata` completo.

### `persistence/avaliacao/` (substitui `avaliacao.py`, 397 linhas)

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `conjunto_ouro.py` | `VERSAO_SCHEMA_CONJUNTO_OURO`, `RepositorioConjuntoOuroSqlAlchemy`; privados `_serializar_conjunto_ouro`, `_parse_datetime_iso` | 215 |
| `consulta.py` | `ConsultaAvaliacaoSqlAlchemy` | 185 |

- O arquivo é dividido mesmo abaixo do teto. Pela regra 8, ele mistura dois agregados, com o mesmo precedente de `domain/avaliacao/`, e os dois adaptadores não compartilham símbolos.
- O `__init__.py` reexporta os 3 nomes públicos. `persistence/__init__.py` e `presentation/cli/bootstrap.py` não mudam.

### Arquivos que não mudam

- **`llm/cliente_openai.py` (526 linhas):** é a exceção da regra 9, como `worker.py`, e nada sai do arquivo. Tirar os auxiliares deixaria o arquivo com cerca de 435 linhas, ainda acima do teto. A classe usa 4 desses privados, que teriam de virar públicos para serem importados de outro módulo.
- **`extracao/posprocessamento.py` (471 linhas):** é um pipeline único, em que `posprocessar_elementos` orquestra todas as outras funções. Trata um só recurso.
- **Mudam só os imports:** `consulta_questoes.py` (246 linhas) e `persistence/avaliacao/` ajustam os imports dos mapeadores e da busca textual, sem outra mudança.
- **Ficam como estão:** `predicados.py`, `database.py`, `seed.py`, `llm/perfis.py`, `llm/__init__.py`, o restante de `extracao/`, `storage/`, `config.py`, `imagem.py` e os `__init__.py` existentes.

### Regras gerais

- **Auxiliares privados:** seguem a regra da [decisão de `application/`](02-corte-application.md). O helper usado por um só submódulo vai junto dele. O helper usado por dois ou mais submódulos do mesmo pacote vai para `_apoio.py` desse pacote. O prefixo `_` no nome do arquivo é mantido, coerente com `_validacao.py`, `_apoio.py` e `extracao/_worker.py`. As duplicatas entre pacotes ficam como estão.
- **Mapeadores:** a regra 7 prevalece sobre `_apoio.py`. O mapeador compartilhado fica público no submódulo dono, e não em `_apoio.py`.

### Fatos verificados

- Nenhum código de `src/`, `tests/` ou `alembic/` faz `monkeypatch` ou `patch` em `repositorios`, `models`, `persistence/avaliacao`, `cliente_openai` ou `posprocessamento`.
- Os testes importam desses módulos apenas nomes públicos: as classes `Repositorio*`, os `*Model`, `ClienteOpenAICompativel` e as funções públicas de `posprocessamento`.
- Os únicos imports de nomes privados de `repositorios.py` estão em `persistence/consulta_questoes.py` e `persistence/avaliacao.py`, e são os mapeadores tratados acima.
