# Validação — Reorganização dos arquivos do backend

Status: **pendente** (linha de base registrada; nenhuma tarefa executada).

Plano: [plano.md](plano.md) · Explicação: [explicacao.md](explicacao.md) · Pedido: [task.md](task.md) · Sequência e portão decididos em: [decisão 05](decisoes/05-sequencia-migracao.md).

Este documento traz o procedimento do portão de cada tarefa e as evidências registradas depois de cada execução. Só entra aqui o que foi executado de fato. Os arquivos gerados pelo portão (OpenAPI exportado, listas de nomes) ficam fora do Git.

## Procedimento do portão

Rode tudo em `backend/`, com o PostgreSQL ligado (`make db-up` na raiz do repositório). `tests/integration/conftest.py` cria o banco `<db>_test` a partir de `Settings().database_url`.

### 1. Antes de editar

Com a árvore limpa no commit da tarefa anterior:

```sh
git status --short                    # precisa sair vazio
export PORTAO="${TMPDIR:-/tmp}/reorganizacao-backend-NN"   # NN = número da tarefa
mkdir -p "$PORTAO"
# copie o script da seção "Script de reexportação" para "$PORTAO/verificar_reexportacao.py"
uv run python -m presentation.openapi_export "$PORTAO/openapi-antes.json"
uv run python -I "$PORTAO/verificar_reexportacao.py" antes "$PORTAO/nomes.json" <arquivos antigos da tarefa>
```

### 2. Depois de migrar

```sh
uv run python -m presentation.openapi_export "$PORTAO/openapi-depois.json"
cmp "$PORTAO/openapi-antes.json" "$PORTAO/openapi-depois.json"     # sem saída, exit 0
uv run python -I "$PORTAO/verificar_reexportacao.py" depois "$PORTAO/nomes.json" <pacote> [--fora NOME=MODULO ...]
uv run pytest                          # suíte completa, incluindo enade_real
uv run ruff check .
uv run ruff format --check .
uv run lint-imports                    # "Contracts: 3 kept, 0 broken"
wc -l <arquivos novos da tarefa>       # cada um com até cerca de 400 linhas
```

Os argumentos de cada tarefa (arquivos antigos, pacote e `--fora`) estão no arquivo da tarefa em [tarefas/](tarefas/).

Como cada tarefa compara o OpenAPI com o do commit anterior, a igualdade vale para o esforço inteiro, mesmo com tarefas feitas em sessões diferentes.

### 3. Varredura global do teto (só na tarefa 11)

```sh
find src -name '*.py' -exec wc -l {} + | awk '$2 != "total" && $1 > 400' | sort -rn
```

A saída só pode listar as 6 exceções aceitas: `application/worker.py`, `infrastructure/llm/cliente_openai.py`, `infrastructure/persistence/repositorios/questao.py`, `infrastructure/extracao/posprocessamento.py`, `application/provas.py` e `application/execucoes_classificacao.py` (ver [explicacao.md](explicacao.md#exceções-aceitas-ao-teto-de-cerca-de-400-linhas)). Um arquivo fora da lista com 400 a 470 linhas é registrado para avaliação e não reprova o portão sozinho. Acima de 470 linhas, o portão reprova.

### 4. Documentação e registro

- Corrija as referências `arquivo:linha` de [`docs/planejamento-inicial/explicacao.md`](../planejamento-inicial/explicacao.md) listadas na tarefa. Confira a linha nova pelo símbolo indicado, não por deslocamento.
- Registre neste arquivo, na seção da tarefa, o resultado de cada comando: exit code e linha final relevante (por exemplo, `N passed`, `Contracts: 3 kept, 0 broken`, contagem de linhas).
- Se algum teste precisar de ajuste, registre o desvio do corte antes de alterar o teste.

## Script de reexportação

O script fica fora do Git (em `$PORTAO`). No modo `antes`, ele lê pela AST os nomes públicos definidos no topo dos arquivos antigos: classes, funções e atribuições sem prefixo `_`. Se o arquivo define `__all__`, usa o `__all__`. No modo `depois`, importa o pacote e confere, para cada nome, que ele está no `__all__` e que `getattr(pacote, nome)` resolve. `--fora NOME=MODULO` marca um nome que sai do pacote de propósito e confere que ele existe no módulo de destino.

Testado em 2026-11-28 no commit `269d957`: o modo `antes` leu 2 nomes de `presentation/api/v1/questoes.py` (o `__all__`) e 10 de `infrastructure/persistence/repositorios.py`. O modo `depois` passou em `presentation.api.v1.questoes`, que já tem `__all__`, e reprovou `infrastructure.persistence.repositorios`, que ainda não tem.

```python
"""Confere se um pacote novo reexporta os nomes públicos do módulo antigo.

Uso (rodar em backend/):
  antes:  python verificar_reexportacao.py antes NOMES.json ARQUIVO.py [ARQUIVO.py ...]
  depois: python verificar_reexportacao.py depois NOMES.json PACOTE [--fora NOME=MODULO ...]
"""

from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path


def nomes_publicos(arquivo: Path) -> list[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes: list[str] = []
    for no in arvore.body:
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id == "__all__":
                    return list(ast.literal_eval(no.value))
                if isinstance(alvo, ast.Name):
                    nomes.append(alvo.id)
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            nomes.append(no.target.id)
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nomes.append(no.name)
    return [n for n in nomes if not n.startswith("_")]


def antes(saida: Path, arquivos: list[str]) -> int:
    nomes = sorted({n for a in arquivos for n in nomes_publicos(Path(a))})
    saida.write_text(json.dumps(nomes, indent=2) + "\n", encoding="utf-8")
    print(f"{len(nomes)} nomes públicos gravados em {saida}")
    return 0


def depois(entrada: Path, pacote: str, fora: dict[str, str]) -> int:
    esperados = json.loads(entrada.read_text(encoding="utf-8"))
    modulo = importlib.import_module(pacote)
    exportados = set(getattr(modulo, "__all__", ()))
    falhas: list[str] = []
    if not exportados:
        falhas.append(f"{pacote} não define __all__")
    for nome in esperados:
        if nome in fora:
            if not hasattr(importlib.import_module(fora[nome]), nome):
                falhas.append(f"{nome}: não encontrado em {fora[nome]}")
            continue
        if nome not in exportados:
            falhas.append(f"{nome}: ausente do __all__ de {pacote}")
        if not hasattr(modulo, nome):
            falhas.append(f"{nome}: getattr({pacote}, {nome!r}) falhou")
    for nome in sorted(fora.keys() - set(esperados)):
        falhas.append(f"--fora {nome}: o nome não estava no módulo antigo")
    extras = sorted(exportados - set(esperados))
    for falha in falhas:
        print(f"FALHA {falha}")
    if extras:
        print(f"aviso: nomes no __all__ que não existiam no módulo antigo: {extras}")
    print(f"{len(esperados)} esperados, {len(fora)} fora do pacote, {len(falhas)} falhas")
    return 1 if falhas else 0


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == "antes":
        return antes(Path(argv[1]), argv[2:])
    if len(argv) >= 3 and argv[0] == "depois":
        fora: dict[str, str] = {}
        resto = argv[3:]
        while resto:
            if resto[0] != "--fora" or len(resto) < 2 or "=" not in resto[1]:
                print(__doc__)
                return 2
            nome, destino = resto[1].split("=", 1)
            fora[nome] = destino
            resto = resto[2:]
        return depois(Path(argv[1]), argv[2], fora)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

## Linha de base

Medida em 2026-11-28 no commit `269d957`, com `find src -name '*.py' -exec wc -l {} + | awk '$2 != "total" && $1 > 400' | sort -rn` em `backend/`. São 14 arquivos acima de 400 linhas:

| Linhas | Arquivo | Destino |
|---|---|---|
| 1910 | `infrastructure/persistence/repositorios.py` | tarefa 08 |
| 738 | `application/avaliacao.py` | tarefa 06 |
| 613 | `domain/classificacao.py` | tarefa 02 |
| 559 | `application/worker.py` | exceção aceita |
| 535 | `application/questoes.py` | tarefa 04 |
| 526 | `infrastructure/persistence/models.py` | tarefa 07 |
| 526 | `infrastructure/llm/cliente_openai.py` | exceção aceita |
| 489 | `presentation/api/v1/questoes.py` | tarefa 11 |
| 481 | `domain/prova.py` | tarefa 01 |
| 471 | `infrastructure/extracao/posprocessamento.py` | exceção aceita |
| 459 | `application/classificacao.py` | tarefa 05 |
| 434 | `application/provas.py` | exceção aceita |
| 412 | `application/execucoes_classificacao.py` | exceção aceita |
| 407 | `domain/avaliacao.py` | tarefa 03 |

As tarefas 09 (`persistence/avaliacao.py`, 397 linhas) e 10 (`api/schemas.py`, 303, e `api/schemas_questoes.py`, 237) dividem arquivos abaixo do teto porque eles misturam agregados ou recursos.

A suíte, o `ruff`, o `lint-imports` e o OpenAPI não foram executados nesta etapa de planejamento. A primeira medição vale como linha de base e entra no portão da tarefa 01.

## Matriz tarefa → evidência

| Tarefa | OpenAPI (`cmp`) | Reexportação | `pytest` | `ruff` | `lint-imports` | Teto | `explicacao.md` | Status |
|---|---|---|---|---|---|---|---|---|
| [01](tarefas/01-domain-prova.md) | — | — | — | — | — | — | — | pendente |
| [02](tarefas/02-domain-classificacao.md) | — | — | — | — | — | — | — | pendente |
| [03](tarefas/03-domain-avaliacao.md) | — | — | — | — | — | — | não se aplica | pendente |
| [04](tarefas/04-application-questoes.md) | — | — | — | — | — | — | — | pendente |
| [05](tarefas/05-application-classificacao.md) | — | — | — | — | — | — | — | pendente |
| [06](tarefas/06-application-avaliacao.md) | — | — | — | — | — | — | — | pendente |
| [07](tarefas/07-infrastructure-models.md) | — | — | — | — | — | — | não se aplica | pendente |
| [08](tarefas/08-infrastructure-repositorios.md) | — | — | — | — | — | — | — | pendente |
| [09](tarefas/09-infrastructure-avaliacao.md) | — | — | — | — | — | — | não se aplica | pendente |
| [10](tarefas/10-presentation-schemas.md) | — | — | — | — | — | — | não se aplica | pendente |
| [11](tarefas/11-presentation-v1-questoes.md) | — | — | — | — | — | — (inclui varredura global) | — | pendente |

## Evidências por tarefa

Cada tarefa acrescenta aqui uma seção `### Tarefa NN` com os comandos e as saídas, no momento em que o portão é executado.
