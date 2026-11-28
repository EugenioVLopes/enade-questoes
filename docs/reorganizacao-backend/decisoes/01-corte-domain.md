# Definir o corte dos arquivos de `domain/`

Type: grilling
Status: resolved
Blocked by: none

## Question

Seguindo as regras de [task.md](../task.md), qual é a organização-alvo de `backend/src/domain/`, símbolo por símbolo?

Arquivos candidatos (contagem de linhas de 2026-11-28):

- `classificacao.py` (613 linhas): `PerfilClassificacao`, `ExecucaoClassificacao`, `Classificacao`, `DivergenciaReclassificacao`, além de validadores privados compartilhados.
- `prova.py` (481 linhas): `FaixaQuestoes`, `BoundingBox`, `Gabarito`, `MetadadosIngestao`, `Alternativa`, `AtivoVisual`, `AlertaExtracao`, `Questao`, `Ingestao`, `Prova`.
- `avaliacao.py` (407 linhas): coeso, avaliar se é preciso cortar.
- Relação entre `AlertaExtracao` (em `prova.py`) e as regras de `alertas_extracao.py`: as regras vão para o mesmo subpacote?
- `domain/__init__.py` (175 linhas de reexportação): continua igual?

Decidir também onde ficam os validadores privados compartilhados entre entidades do mesmo pacote (por exemplo, `_validar_confianca`).

## Answer

Resolvido em 2026-11-28 (grilling com o usuário). Contagens de linhas aproximadas, medidas sobre os arquivos atuais.

### `domain/classificacao/` (substitui `classificacao.py`, 613 linhas)

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `perfil.py` | `PerfilClassificacao` | 100 |
| `execucao.py` | `ExecucaoClassificacao`; privados `_congelar_valor`, `_validar_colecao_uuids`, `_validar_nao_negativo_int` | 290 |
| `classificacao.py` | `Classificacao`, `normalizar_topicos_curadoria`, `criar_classificacao_humana`, `DivergenciaReclassificacao`; privados `_validar_confianca`, `_validar_secundarias`, `_validar_colecao_strings` | 250 |

`DivergenciaReclassificacao` fica junto de `Classificacao` porque representa o conflito entre duas classificações, e assim cada validador privado fica no único submódulo que o usa. `execucao.py` importa `PerfilClassificacao` de `perfil.py` (`reconstruir_perfil_snapshot`).

### `domain/prova/` (substitui `prova.py`, 481 linhas)

| Submódulo | Símbolos | Linhas (aprox.) |
|---|---|---|
| `prova.py` | `Prova`, `FaixaQuestoes` | 55 |
| `ingestao.py` | `Ingestao`, `MetadadosIngestao` | 95 |
| `questao.py` | `Questao`, `Alternativa`, `Gabarito`, `AtivoVisual`, `BoundingBox`; privado `_copiar_lista_validada` | 190 |
| `alerta_extracao.py` | `AlertaExtracao`, `SEVERIDADE_POR_CODIGO`, `ALERTAS_ESTRUTURAIS`, `ALERTAS_INSPECAO` | 105 |
| `_validacao.py` | privados `_validar_inteiro_positivo`, `_validar_inteiro_nao_negativo` | 20 |

`AtivoVisual` e `BoundingBox` ficam em `questao.py`, sem submódulo próprio. Não há ciclo: `Questao` não referencia `Prova` como tipo.

### `domain/avaliacao/` (substitui `avaliacao.py`, 407 linhas)

| Submódulo | Símbolos |
|---|---|
| `conjunto_ouro.py` | `ChaveQuestaoOuro`, `ItemConjuntoOuro`, `ConjuntoOuro` (cerca de 195 linhas) |
| `avaliacao.py` | `PredicaoClassificacao`, `ResultadoItemAvaliacao`, `ParConfusao`, `DivergenciaAvaliacao`, `MetricasCamada1`, `MetricasCamada2`, `MetricasCamada3`, `AvaliacaoClassificacao`, `ItemDiffGate`, `ResultadoGate` (cerca de 195 linhas) |

O arquivo é dividido mesmo estando na faixa de 400 a 470 linhas, porque mistura dois agregados: o conjunto-ouro (a referência versionada) e a avaliação (o histórico persistido). Os tipos do gate ficam em `avaliacao.py`.

### Arquivos que não mudam

- `alertas_extracao.py` fica em `domain/` e continua importando `ALERTAS_ESTRUTURAIS`, `AlertaExtracao` e `Questao` de `domain.prova`. O arquivo não passa do teto nem mistura agregados. Aceita-se a semelhança de nomes com `domain/prova/alerta_extracao.py`.
- `metricas_avaliacao.py`, `travas_classificacao.py`, `reprocessamento.py`, `taxonomia.py`, `enums.py`, `exceptions.py` e `faixas_enade.py` ficam como estão.
- `domain/__init__.py` fica byte a byte igual.

### Regras gerais

- **Validadores privados**: o helper usado por um só submódulo vai junto dele. O helper usado por dois ou mais submódulos do mesmo pacote vai para `_validacao.py` nesse pacote e não é reexportado. As duplicatas entre pacotes ficam como estão, sem unificação: `_validar_nao_negativo_int` e `_validar_inteiro_nao_negativo`, e a validação de secundárias repetida em `ItemConjuntoOuro` e `PredicaoClassificacao`.
- **`__init__.py` dos pacotes novos**: reexporta todos os nomes públicos do antigo módulo, constantes incluídas, com `__all__` explícito. Assim `from domain.prova import Questao` e os demais imports atuais continuam válidos.

### Fatos verificados

- Nenhum código de `src/` ou `tests/` importa nomes privados de `domain.*`, faz `patch` com caminho de módulo de `domain` ou depende de `__module__`, `__qualname__` ou pickle.
- `pyproject.toml` empacota `src/domain` inteiro, então os subpacotes entram sem configuração extra.
