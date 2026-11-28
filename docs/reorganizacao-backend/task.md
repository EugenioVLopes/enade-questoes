# Task — Reorganização dos arquivos do backend

## Pedido original

> gostaria de melhorar a separação do que esta nos arquivos do backend. Estendo a diferença entre as entidades, mas os arquivos estão muito grande. Queria uma forma melhor de organizar

## Esclarecimentos aprovados (rodada de alinhamento de 2026-11-28)

1. **Destino**: uma especificação da organização-alvo dos arquivos do backend, com a sequência de migração, pronta para decomposição em `plano.md` e `tarefas/`. A refatoração em si não acontece dentro deste mapa.
2. **Eixo de organização**: as 4 camadas hexagonais (`domain`, `application`, `infrastructure`, `presentation`) continuam no topo, conforme a [decisão 08 do planejamento inicial](../planejamento-inicial/decisoes/08-arquitetura-e-simplificacao-stack.md). Os arquivos grandes viram subpacotes por agregado ou recurso dentro de cada camada. Fatias verticais por contexto foram consideradas e descartadas.
3. **Escopo**: somente `backend/src/`. Em `backend/tests/` muda apenas o necessário para os imports continuarem funcionando. Frontend, protótipos e migrações Alembic ficam fora.
4. **Refatoração puramente estrutural**: o comportamento fica idêntico. O contrato OpenAPI, o schema de banco e os termos do [GLOSSARY.md](../../GLOSSARY.md) não mudam, e a suíte de testes continua verde.
5. **Critério de tamanho**: coesão, com teto orientativo de cerca de 400 linhas por arquivo, verificado ao final.
6. **Reexportação**: o módulo que vira pacote reexporta seus nomes públicos no `__init__.py`, então `from domain.prova import Questao` continua válido. Dentro do pacote, os submódulos importam uns aos outros diretamente.
7. **Mapeadores ORM↔domínio**: ficam no mesmo arquivo do repositório do seu agregado. Os compartilhados se tornam públicos no módulo do agregado dono. `condicao_busca_textual` vai para um módulo próprio de busca textual.
8. **Regra de corte**: o arquivo é quebrado se tiver mais de cerca de 400 linhas ou se misturar dois ou mais agregados ou recursos. Arquivos coesos entre 400 e 470 linhas são avaliados um a um.
9. **Classe única acima do teto** (por exemplo, `WorkerLocal` e `ClienteOpenAICompativel`): é uma exceção aceita. Só saem do arquivo os tipos e funções auxiliares, e a classe em si não é dividida.
10. **Nomes**: o pacote mantém o nome do módulo atual. Cada submódulo leva o nome, no singular, da entidade ou do grupo de casos de uso que contém, e o arquivo da raiz do agregado pode repetir o nome do pacote.
11. **`import-linter`**: os 3 contratos atuais devem continuar passando, sem contratos novos entre subpacotes.
12. **Fatiamento e verificação**: cada tarefa de migração cobre um arquivo grande, ou um par muito acoplado, e vira um commit independente. O portão de cada tarefa:
    - `pytest`, `ruff` e `lint-imports` passando;
    - diff zero no OpenAPI exportado;
    - `README.md` e `explicacao.md` com os caminhos atualizados;
    - documentos históricos de `tarefas/` e `validacao.md` intocados.

## Critérios de aceite deste planejamento

- [x] Organização-alvo definida arquivo a arquivo para `domain/` ([decisão 01](decisoes/01-corte-domain.md)).
- [x] Organização-alvo definida arquivo a arquivo para `application/` ([decisão 02](decisoes/02-corte-application.md)).
- [x] Organização-alvo definida arquivo a arquivo para `infrastructure/` ([decisão 03](decisoes/03-corte-infrastructure.md)).
- [x] Organização-alvo definida arquivo a arquivo para `presentation/` ([decisão 04](decisoes/04-corte-presentation.md)).
- [x] Sequência de tarefas de migração definida, com portão de verificação por tarefa ([decisão 05](decisoes/05-sequencia-migracao.md)).
