# Definir a sequência das tarefas de migração

Type: grilling
Status: open
Blocked by: 01, 02, 03, 04

## Question

Com a organização-alvo de cada camada definida em [Definir o corte dos arquivos de `domain/`](01-corte-domain.md), [Definir o corte dos arquivos de `application/`](02-corte-application.md), [Definir o corte dos arquivos de `infrastructure/`](03-corte-infrastructure.md) e [Definir o corte dos arquivos de `presentation/`](04-corte-presentation.md):

- Em que ordem as tarefas de migração devem ser executadas?
- Quais pares de arquivos acoplados precisam migrar juntos (por exemplo, `models.py` com `repositorios.py`)?
- Como fica o portão concreto de cada tarefa? Ele precisa trazer os comandos exatos de `pytest`, `ruff`, `lint-imports`, a comparação do OpenAPI exportado e a verificação do teto de linhas.
- Quais trechos de `README.md` e `explicacao.md` cada tarefa atualiza?

O resultado deve deixar o esforço pronto para gerar `plano.md`, `explicacao.md`, `validacao.md` e `tarefas/NN-<slug>.md`.
