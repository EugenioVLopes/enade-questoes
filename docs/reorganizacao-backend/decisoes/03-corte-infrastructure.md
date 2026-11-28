# Definir o corte dos arquivos de `infrastructure/`

Type: grilling
Status: open
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
