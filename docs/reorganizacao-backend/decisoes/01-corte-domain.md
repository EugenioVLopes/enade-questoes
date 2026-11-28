# Definir o corte dos arquivos de `domain/`

Type: grilling
Status: open
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
