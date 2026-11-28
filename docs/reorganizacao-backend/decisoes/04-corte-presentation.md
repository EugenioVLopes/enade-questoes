# Definir o corte dos arquivos de `presentation/`

Type: grilling
Status: resolved
Blocked by: none

## Question

Seguindo as regras de [task.md](../task.md), qual é a organização-alvo de `backend/src/presentation/`, símbolo por símbolo?

Arquivos candidatos (contagem de linhas de 2026-11-28):

- `api/schemas.py` (303 linhas): mistura schemas de health, erros, provas e ingestão, taxonomias, perfis e execuções de classificação. Entra pela regra de "mistura recursos".
- `api/schemas_questoes.py` (237 linhas): já separado por recurso. Ele se junta ao novo pacote de schemas?
- `api/v1/questoes.py` (489 linhas): getters de injeção de dependência, serializadores e 8 rotas.
- `cli/eval_cli.py` (365 linhas), `main.py` (300 linhas), `api/v1/provas.py` (280 linhas) e `api/app.py` (240 linhas): abaixo do teto, avaliar só se misturarem responsabilidades.

Restrição: o OpenAPI exportado deve ser idêntico, inclusive nomes de schemas e `operationId`. Confirmar se mover um modelo Pydantic de módulo altera o nome do componente gerado.

## Answer

Resolvido em 2026-11-28 (grilling com o usuário). As contagens de linhas são aproximadas: spans medidos por AST nos arquivos atuais, mais uma estimativa dos imports.

### `api/schemas/` (substitui `schemas.py`, 303 linhas, e `schemas_questoes.py`, 237 linhas)

Um submódulo por roteador de `api/v1/`, com nomes no singular, seguindo `domain/`.

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `erro.py` | `ErroDetalheResponse` (usado pelos 6 roteadores) | 10 |
| `health.py` | `WorkerHealthResponse`, `HealthResponse` | 20 |
| `prova.py` | `ConflitoProvaResponse`, `MetadadosIngestaoResponse`, `IngestaoResumoResponse`, `ContagemQuestoesResponse`, `ContagemAlertasResponse`, `ClassificacaoEncadeadaResponse`, `ProvaDetalheResponse`, `ListaProvasResponse`, `ProvaIngestaoAceitaResponse`, `ResumoAtualizacaoGabaritoResponse`, `ReprocessarProvaRequest`, `ReprocessarProvaAceitaResponse` | 115 |
| `taxonomia.py` | `DisciplinaCriacaoInput`, `TaxonomiaCriarRequest`, `TaxonomiaAtualizarRequest`, `DisciplinaCriarRequest`, `DisciplinaAtualizarRequest`, `DisciplinaResponse`, `TaxonomiaResponse`, `ListaTaxonomiasResponse` | 70 |
| `perfil.py` | `PerfilClassificacaoCriarRequest`, `PerfilClassificacaoResponse`, `ListaPerfisClassificacaoResponse` | 30 |
| `execucao.py` | `ExecucaoClassificacaoCriarRequest`, `ExecucaoClassificacaoAceitaResponse`, `SnapshotTaxonomiaResumoResponse`, `SnapshotPerfilResumoResponse`, `SnapshotExecucaoResumoResponse`, `ExecucaoClassificacaoResumoResponse`, `ExecucaoClassificacaoDetalheResponse`, `ListaExecucoesClassificacaoResponse` | 85 |
| `questao.py` | todo o conteúdo atual de `schemas_questoes.py`: as constantes `LIMITE_*` e `MAX_*` e as 20 classes, incluindo `AtivoVisualResponse` | 237 |

- `perfil.py` e `execucao.py` ficam separados, sem um `classificacao.py` combinado, para que cada roteador leia de um só submódulo.
- `schemas_questoes.py` é apagado, sem módulo de compatibilidade. `AtivoVisualResponse` fica em `questao.py` porque ativos visuais são um sub-recurso da questão.
- As classes usadas só dentro de outra classe (`DisciplinaCriacaoInput`, `AlternativaEdicaoRequest`, `GabaritoEdicaoRequest`) ficam no mesmo submódulo da classe que as contém.
- O `__init__.py` reexporta todos os nomes públicos dos 7 submódulos, constantes incluídas, com `__all__` explícito.
- **Imports:** os `from presentation.api.schemas import ...` atuais (em `provas`, `taxonomias`, `perfis_classificacao`, `execucoes_classificacao`, `health`, `questoes` e `ativos_visuais`) não mudam. Só `v1/questoes` e `v1/ativos_visuais` trocam `presentation.api.schemas_questoes` por `presentation.api.schemas`.

### `api/v1/questoes/` (substitui `v1/questoes.py`, 489 linhas)

O corte é por papel, porque o arquivo trata um único recurso.

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `rotas.py` | `router`, privado `_resolver_state`, os 8 `get_*_use_case`, privado `_correcao` (converte o request no DTO de aplicação) e as 8 rotas, na ordem atual | 300 |
| `serializacao.py` | `serializar_ativo`, `serializar_alerta`, `serializar_classificacao`, `serializar_divergencia`, `serializar_detalhe`, `serializar_item`, `serializar_contadores`, `TAMANHO_TRECHO` (usado só por `serializar_item`) | 195 |

- Os serializadores perdem o prefixo `_` porque `rotas.py` os importa de outro módulo, o mesmo precedente dos mapeadores da [decisão de `infrastructure/`](03-corte-infrastructure.md). Fora `serializar_ativo`, eles não são reexportados.
- O `__init__.py` reexporta `router` e `serializar_ativo`, o mesmo `__all__` de hoje. `api/app.py` e `v1/ativos_visuais.py` não mudam.
- As rotas continuam num só módulo e na mesma ordem, para preservar a ordem de `paths` no OpenAPI. A divisão das rotas por grupo de casos de uso foi rejeitada porque exige um `router` compartilhado entre submódulos.

### Arquivos que não mudam

- **`cli/eval_cli.py` (365 linhas):** impressores e comandos da mesma CLI, abaixo do teto.
- **`main.py` (300 linhas):** composition root, quase só `build_app`.
- **`api/v1/provas.py` (280 linhas):** um recurso só.
- **`api/app.py` (240 linhas):** `create_app`.
- **Ficam como estão:** `cli/bootstrap.py`, `openapi_export.py`, `api/tipos.py`, `api/v1/_http_cache.py`, `health.py`, `ativos_visuais.py`, `taxonomias.py`, `perfis_classificacao.py`, `execucoes_classificacao.py` e os `__init__.py` existentes.

### Fatos verificados

- **Nomes no OpenAPI:** mover um modelo Pydantic de módulo não muda o nome do componente. Testei com FastAPI 0.165.0 e Pydantic 2.14.4: a mesma classe `XResponse` em dois módulos diferentes gerou o componente `XResponse` e o `operationId` `ler_x_x_get` nos dois casos. O nome vem do `__name__` da classe. O `operationId` e os componentes `Body_*` vêm do nome da função, do path e do método, e `src/presentation` não define `generate_unique_id_function`.
- **Condição para o diff zero:** os nomes das classes e das funções de rota não mudam e continuam únicos. Hoje são 74 componentes, sem nomes repetidos. A ordem de registro dos roteadores em `create_app` e a ordem das rotas dentro de cada roteador também se mantêm.
- **Testes:** nenhum teste importa de `presentation.api.v1.questoes`, `schemas` ou `schemas_questoes`, e nenhum usa `dependency_overrides`. O `monkeypatch` em `presentation.cli.bootstrap` e o import de `_serializar_snapshot_resumo` de `v1/execucoes_classificacao` não são afetados.
- **`import-linter`:** `ignore_imports` cita só `presentation.main` e `presentation.cli.bootstrap`, e nenhum dos dois muda.
