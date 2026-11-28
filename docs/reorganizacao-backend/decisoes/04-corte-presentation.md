# Definir o corte dos arquivos de `presentation/`

Type: grilling
Status: open
Blocked by: none

## Question

Seguindo as regras de [task.md](../task.md), qual é a organização-alvo de `backend/src/presentation/`, símbolo por símbolo?

Arquivos candidatos (contagem de linhas de 2026-11-28):

- `api/schemas.py` (303 linhas): mistura schemas de health, erros, provas e ingestão, taxonomias, perfis e execuções de classificação. Entra pela regra de "mistura recursos".
- `api/schemas_questoes.py` (237 linhas): já separado por recurso. Ele se junta ao novo pacote de schemas?
- `api/v1/questoes.py` (489 linhas): getters de injeção de dependência, serializadores e 8 rotas.
- `cli/eval_cli.py` (365 linhas), `main.py` (300 linhas), `api/v1/provas.py` (280 linhas) e `api/app.py` (240 linhas): abaixo do teto, avaliar só se misturarem responsabilidades.

Restrição: o OpenAPI exportado deve ser idêntico, inclusive nomes de schemas e `operationId`. Confirmar se mover um modelo Pydantic de módulo altera o nome do componente gerado.
