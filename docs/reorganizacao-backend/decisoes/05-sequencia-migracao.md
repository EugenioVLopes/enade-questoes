# Definir a sequência das tarefas de migração

Type: grilling
Status: resolved
Blocked by: 01, 02, 03, 04

## Question

Com a organização-alvo de cada camada definida em [Definir o corte dos arquivos de `domain/`](01-corte-domain.md), [Definir o corte dos arquivos de `application/`](02-corte-application.md), [Definir o corte dos arquivos de `infrastructure/`](03-corte-infrastructure.md) e [Definir o corte dos arquivos de `presentation/`](04-corte-presentation.md):

- Em que ordem as tarefas de migração devem ser executadas?
- Quais pares de arquivos acoplados precisam migrar juntos (por exemplo, `models.py` com `repositorios.py`)?
- Como fica o portão concreto de cada tarefa? Ele precisa trazer os comandos exatos de `pytest`, `ruff`, `lint-imports`, a comparação do OpenAPI exportado e a verificação do teto de linhas.
- Quais trechos de `README.md` e `explicacao.md` cada tarefa atualiza?

O resultado deve deixar o esforço pronto para gerar `plano.md`, `explicacao.md`, `validacao.md` e `tarefas/NN-<slug>.md`.

## Answer

Resolvido em 2026-11-28 (grilling com o usuário, todas as recomendações aceitas).

### Ordem das tarefas

As tarefas seguem as camadas de baixo para cima, com um commit por tarefa. Como os `__init__.py` reexportam os nomes públicos, nenhuma tarefa depende de outra para funcionar. A ordem serve para estabilizar uma camada antes de mexer na de cima.

| Nº | Tarefa | Corte |
|---|---|---|
| 1 | `domain/prova.py` → pacote | [decisão de `domain/`](01-corte-domain.md) |
| 2 | `domain/classificacao.py` → pacote | [decisão de `domain/`](01-corte-domain.md) |
| 3 | `domain/avaliacao.py` → pacote | [decisão de `domain/`](01-corte-domain.md) |
| 4 | `application/questoes.py` → pacote | [decisão de `application/`](02-corte-application.md) |
| 5 | `application/classificacao.py` → pacote | [decisão de `application/`](02-corte-application.md) |
| 6 | `application/avaliacao.py` → pacote | [decisão de `application/`](02-corte-application.md) |
| 7 | `infrastructure/persistence/models.py` → pacote | [decisão de `infrastructure/`](03-corte-infrastructure.md) |
| 8 | `infrastructure/persistence/repositorios.py` → pacote, com `busca_textual.py` e os imports novos em `consulta_questoes.py` e `persistence/avaliacao.py` | [decisão de `infrastructure/`](03-corte-infrastructure.md) |
| 9 | `infrastructure/persistence/avaliacao.py` → pacote | [decisão de `infrastructure/`](03-corte-infrastructure.md) |
| 10 | `presentation/api/schemas.py` e `schemas_questoes.py` → pacote `api/schemas/` | [decisão de `presentation/`](04-corte-presentation.md) |
| 11 | `presentation/api/v1/questoes.py` → pacote | [decisão de `presentation/`](04-corte-presentation.md) |

### Arquivos que migram juntos

Só há dois grupos atômicos:

- **Tarefa 8**: o pacote `repositorios/`, o módulo novo `persistence/busca_textual.py` e a troca dos imports dos mapeadores privados pelos mapeadores públicos dos submódulos donos, em `consulta_questoes.py` e em `persistence/avaliacao.py`. Sem essa troca, os testes falham.
- **Tarefa 10**: `schemas.py` e `schemas_questoes.py`, que formam um só pacote de destino. `schemas_questoes.py` é apagado.

`models.py` migra sozinho. `repositorios.py` importa os modelos por `infrastructure.persistence.models`, e o `__init__.py` do novo pacote reexporta todos eles. A tarefa 9 vem depois da 8, então os imports dos mapeadores mudam uma única vez, ainda no arquivo antigo, e a tarefa 9 só divide o arquivo.

### Portão de cada tarefa

Os comandos rodam em `backend/`, com o PostgreSQL ligado (`make db-up`). `tests/integration/conftest.py` cria o banco `<db>_test` a partir de `Settings().database_url`.

1. **OpenAPI**: exportar antes de editar, com a árvore limpa no commit anterior, e exportar de novo depois. Os arquivos ficam fora do Git e precisam ser idênticos. Como cada tarefa é comparada com a anterior, a igualdade vale para o esforço inteiro, mesmo com tarefas feitas em sessões diferentes.

   ```sh
   uv run python -m presentation.openapi_export "$TMPDIR/openapi-antes.json"
   # ... migração ...
   uv run python -m presentation.openapi_export "$TMPDIR/openapi-depois.json"
   cmp "$TMPDIR/openapi-antes.json" "$TMPDIR/openapi-depois.json"
   ```

2. **Nomes reexportados**: antes de editar, um script fora do Git lê pela AST os nomes públicos definidos no topo do módulo antigo. Depois da migração, ele confirma que cada nome está no `__all__` do pacote e que `getattr(pacote, nome)` resolve. O script é descrito em `validacao.md`.
3. **Testes e lint**: a suíte roda completa em toda tarefa, incluindo os testes `enade_real`, porque os PDFs de `data/enade/` estão disponíveis localmente.

   ```sh
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   uv run lint-imports   # os 3 contratos mantidos, 0 quebrados
   ```

4. **Teto de linhas**: cada arquivo novo da tarefa fica com até cerca de 400 linhas, exceto `repositorios/questao.py`, que já é exceção aceita. No portão da tarefa 11, a varredura global só pode listar as exceções aceitas: `application/worker.py` (559), `infrastructure/llm/cliente_openai.py` (526), `infrastructure/extracao/posprocessamento.py` (471), `persistence/repositorios/questao.py` (cerca de 480), `application/provas.py` (434) e `application/execucoes_classificacao.py` (412). Um arquivo fora da lista com 400 a 470 linhas é registrado para avaliação e não reprova o portão automaticamente.

   ```sh
   find src -name '*.py' -exec wc -l {} + | awk '$2 != "total" && $1 > 400' | sort -rn
   ```

5. **Documentação**: a tarefa corrige as referências da tabela abaixo e registra as saídas do portão em `docs/reorganizacao-backend/validacao.md`.

### Documentos que cada tarefa atualiza

O `explicacao.md` da regra 12 é `docs/planejamento-inicial/explicacao.md`, a explicação viva do sistema. Cada tarefa atualiza o caminho e a linha das referências aos arquivos que ela move ou cujos imports ela altera:

| Tarefa | Referência em `docs/planejamento-inicial/explicacao.md` |
|---|---|
| 1 | `backend/src/domain/prova.py:34` |
| 2 | `backend/src/domain/classificacao.py:474` |
| 4 | `backend/src/application/questoes.py:355` |
| 5 | `backend/src/application/classificacao.py:380` |
| 6 | `backend/src/application/avaliacao.py:651`-`:672` |
| 8 | `backend/src/infrastructure/persistence/repositorios.py:1733` e `backend/src/infrastructure/persistence/consulta_questoes.py:139-145`, cujas linhas mudam com a troca dos imports |
| 11 | `backend/src/presentation/api/v1/questoes.py:345` |

As tarefas 3, 7, 9 e 10 não têm referências a corrigir. `README.md` não muda em nenhuma tarefa: a árvore em `README.md:131-135` mostra só as camadas, e a referência a `worker.py` em `README.md:111` aponta para um arquivo que não muda. `validacao.md` e `tarefas/` de `docs/planejamento-inicial/` ficam intocados, mesmo com referências antigas.

### Execução de cada tarefa

- **Histórico**: fazer `git mv` do arquivo antigo para o submódulo que fica com a maior parte do código (por exemplo, `repositorios.py` → `repositorios/questao.py`) e só depois criar os demais submódulos. O Git detecta renomeação por semelhança, então isso aumenta a chance de `git log --follow` e `git blame` acompanharem o código, sem garantia.
- **Commit**: um por tarefa, com a mensagem `refactor(<camada>): dividir <arquivo> em pacote`, por exemplo `refactor(infrastructure): dividir repositorios.py em pacote`. O commit inclui as atualizações de `explicacao.md` e `validacao.md` da tarefa. Não há tarefa extra de verificação final.
- **Testes**: pelos fatos verificados nas decisões 01 a 04, nenhum teste precisa mudar de import. Se algum quebrar, isso indica um desvio do corte decidido e deve ser registrado antes de se ajustar o teste.
