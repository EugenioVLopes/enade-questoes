# Plano — Reorganização dos arquivos do backend

Status: **pendente** (0 de 11 tarefas concluídas).

Pedido e regras do esforço: [task.md](task.md) · Mapa de decisões (5 de 5 tickets resolvidos): [mapa.md](mapa.md) · Organização-alvo e regras de import: [explicacao.md](explicacao.md) · Portão e evidências: [validacao.md](validacao.md).

## Objetivo

Dividir os arquivos grandes de `backend/src/` em subpacotes por agregado ou recurso, dentro das 4 camadas hexagonais, sem mudar comportamento. Ao final do esforço:

- o OpenAPI exportado é idêntico ao do commit inicial;
- o schema de banco, as migrações Alembic e os termos do [GLOSSARY.md](../../GLOSSARY.md) não mudam;
- `pytest`, `ruff` e `lint-imports` (3 contratos) passam;
- só as 6 exceções aceitas passam de cerca de 400 linhas.

## Estratégia

- **Uma tarefa por arquivo grande, um commit por tarefa.** Só dois grupos migram juntos: a tarefa 08 (`repositorios.py`, `busca_textual.py` e os imports dos mapeadores) e a tarefa 10 (`schemas.py` com `schemas_questoes.py`). Ver [decisão 05](decisoes/05-sequencia-migracao.md).
- **Ordem de baixo para cima**: `domain/` → `application/` → `infrastructure/` → `presentation/`. Os `__init__.py` reexportam os nomes públicos, então nenhuma tarefa depende tecnicamente de outra. A ordem estabiliza uma camada antes da seguinte.
- **Movimento, não reescrita.** O corpo de cada classe e função é copiado sem alteração. Mudam apenas os imports, o local dos símbolos, o prefixo `_` dos mapeadores e serializadores que passam a ser importados entre submódulos, e os `__init__.py` novos.
- **Histórico.** Cada tarefa começa com `git mv` do arquivo antigo para o submódulo que fica com a maior parte do código e só depois cria os demais submódulos.
- **Testes.** Nenhum teste deve mudar de import (fatos verificados nas decisões 01 a 04). Um teste quebrado indica desvio do corte decidido: registre o desvio na tarefa antes de ajustar qualquer teste.

## Tarefas

| Nº | Tarefa | Camada | Commit | Status |
|---|---|---|---|---|
| 01 | [Dividir `domain/prova.py` em pacote](tarefas/01-domain-prova.md) | domain | `refactor(domain): dividir prova.py em pacote` | pendente |
| 02 | [Dividir `domain/classificacao.py` em pacote](tarefas/02-domain-classificacao.md) | domain | `refactor(domain): dividir classificacao.py em pacote` | pendente |
| 03 | [Dividir `domain/avaliacao.py` em pacote](tarefas/03-domain-avaliacao.md) | domain | `refactor(domain): dividir avaliacao.py em pacote` | pendente |
| 04 | [Dividir `application/questoes.py` em pacote](tarefas/04-application-questoes.md) | application | `refactor(application): dividir questoes.py em pacote` | pendente |
| 05 | [Dividir `application/classificacao.py` em pacote](tarefas/05-application-classificacao.md) | application | `refactor(application): dividir classificacao.py em pacote` | pendente |
| 06 | [Dividir `application/avaliacao.py` em pacote](tarefas/06-application-avaliacao.md) | application | `refactor(application): dividir avaliacao.py em pacote` | pendente |
| 07 | [Dividir `persistence/models.py` em pacote](tarefas/07-infrastructure-models.md) | infrastructure | `refactor(infrastructure): dividir models.py em pacote` | pendente |
| 08 | [Dividir `persistence/repositorios.py` em pacote e extrair `busca_textual.py`](tarefas/08-infrastructure-repositorios.md) | infrastructure | `refactor(infrastructure): dividir repositorios.py em pacote` | pendente |
| 09 | [Dividir `persistence/avaliacao.py` em pacote](tarefas/09-infrastructure-avaliacao.md) | infrastructure | `refactor(infrastructure): dividir avaliacao.py em pacote` | pendente |
| 10 | [Unir `schemas.py` e `schemas_questoes.py` no pacote `api/schemas/`](tarefas/10-presentation-schemas.md) | presentation | `refactor(presentation): dividir schemas.py e schemas_questoes.py em pacote` | pendente |
| 11 | [Dividir `api/v1/questoes.py` em pacote](tarefas/11-presentation-v1-questoes.md) | presentation | `refactor(presentation): dividir v1/questoes.py em pacote` | pendente |

Dependências: cada tarefa começa com a árvore limpa no commit da tarefa anterior. A tarefa 09 vem depois da 08 porque a 08 troca os imports dos mapeadores ainda no `persistence/avaliacao.py` antigo, e a 09 só divide o arquivo. A tarefa 11 faz a varredura global do teto de linhas.

## Portão de cada tarefa

O procedimento completo, com comandos e o script de reexportação, está em [validacao.md](validacao.md#procedimento-do-portão). Em resumo:

1. Exportar o OpenAPI e capturar os nomes públicos do módulo antigo **antes** de editar.
2. Migrar conforme a tarefa.
3. Exportar o OpenAPI de novo e comparar com `cmp`; conferir os nomes reexportados.
4. Rodar `pytest` completo (inclui `enade_real`), `ruff check`, `ruff format --check` e `lint-imports`.
5. Medir as linhas dos arquivos novos.
6. Corrigir as referências `arquivo:linha` de [`docs/planejamento-inicial/explicacao.md`](../planejamento-inicial/explicacao.md) listadas na tarefa.
7. Registrar as saídas em [validacao.md](validacao.md), marcar a tarefa como `concluida` e atualizar a tabela acima.
8. Commitar código e documentos juntos, com a mensagem da tabela.

Não há tarefa extra de verificação final. O portão da tarefa 11 inclui a varredura global do teto.

## Documentos que não mudam

- `README.md`: a árvore em `README.md:131-135` mostra só as camadas, e a referência a `worker.py` em `README.md:111` aponta para um arquivo que fica onde está.
- `docs/planejamento-inicial/validacao.md` e `docs/planejamento-inicial/tarefas/`: são registros históricos e ficam intocados, mesmo com caminhos antigos.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Um nome público deixa de ser importável pelo caminho antigo | Script de reexportação no portão ([validacao.md](validacao.md#script-de-reexportação)) |
| O OpenAPI muda de forma silenciosa (nome de componente, ordem de `paths`) | `cmp` do OpenAPI antes/depois em toda tarefa. Nomes de classes e funções de rota não mudam, e as rotas de `v1/questoes` ficam num só módulo, na ordem atual ([decisão 04](decisoes/04-corte-presentation.md)) |
| Import circular entre submódulos | Os cortes não têm ciclos verificados (decisões 01 a 04). Um ciclo novo indica desvio do corte e deve ser registrado na tarefa |
| `alembic/env.py` deixa de ver algum modelo | O `__init__.py` de `models/` importa todos os submódulos (tarefa 07) |
| `monkeypatch` em atributo de módulo deixa de surtir efeito | `application/provas.py` fica como está; nenhum outro módulo afetado sofre `patch` ([decisão 02](decisoes/02-corte-application.md), [decisão 03](decisoes/03-corte-infrastructure.md)) |
| `git log --follow` perde o histórico | `git mv` para o maior submódulo antes de criar os demais. A detecção de renomeação depende de semelhança e não é garantida |
