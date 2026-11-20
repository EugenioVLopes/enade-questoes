# Task — Planejamento inicial da aplicação Enade Questões

## Pedido original

> Eu quero iniciar um projeto em que eu vou criar uma aplicação ponta a ponta que vai processar as questões e categorizar elas de acordo com as disciplinas. Meu foco inicial é fazer isso para as provas do ENADE de Engenharia de Computação. Tecnologias que eu acredito que possam ser úteis seria a lib Docling para conversão dos PDFs, mas pode sugerir outra coisa. Quero primeiro preparar o plano antes de ir iniciando. Não tenho experiência com esse tipo de aplicação.

## Esclarecimentos aprovados (rodadas de alinhamento)

1. **Destino do planejamento**: produzir uma especificação completa de produto, domínio e arquitetura, validada com pequenos protótipos descartáveis nos pontos de maior risco técnico (extração de PDF real do ENADE e classificação estruturada), pronta para decomposição em tarefas de implementação (`plano.md` + `tarefas/`).
2. **Recorte da aplicação ponta a ponta (v1)**: ingestão de PDFs de provas e gabaritos do ENADE, extração e sugestão automática de disciplinas, interface web para revisão/correção humana e busca/filtro de questões categorizadas por disciplina, ano e tema.
3. **Taxonomia de disciplinas**: iniciar pela matriz oficial do ENADE / Diretrizes Curriculares Nacionais (DCNs) de Engenharia de Computação, porém modelada de forma extensível para suportar múltiplas taxonomias/grades curriculares, outros cursos no futuro e reclassificação com novas regras sem destruir revisões anteriores.
4. **Cardinalidade da classificação**: em cada taxonomia/grade, uma questão recebe **1 disciplina principal** + **disciplinas secundárias opcionais**, acompanhadas de justificativa e grau de confiança.
5. **Escopo das questões na v1**: questões **objetivas do Componente Específico** de Engenharia de Computação, preservando figuras, tabelas, código e vinculando o gabarito oficial do INEP.
6. **Dados de validação**: usar provas e gabaritos oficiais reais do INEP (2 a 3 edições de Engenharia de Computação).
7. **Referência de stack e execução**: rodar localmente primeiro, adotando uma arquitetura enxuta em Python 3.13, `uv`, FastAPI (arquitetura hexagonal separando núcleo determinístico e adaptadores de PDF/IA) no backend e Vite, React, TypeScript, Tailwind e shadcn/ui no frontend.
8. **Provedor de LLM**: avaliar APIs oficiais de baixo custo ou tier gratuito via adaptador intercambiável (permitindo apontar futuramente para um servidor Qwen/vLLM próprio, sem adotar o servidor Qwen como primeira opção na v1).
9. **Organização documental**: manter o mapa e os tickets do Wayfinder em `docs/planejamento-inicial/` com rastreabilidade em Markdown local (sem `.scratch/`).

## Critérios de aceite desta fase de planejamento

- [x] Provas e gabaritos reais do ENADE de Engenharia de Computação coletados para validação.
- [x] Extração de PDF validada em prova real (comparando Docling e alternativa viável) com decisão registrada.
- [x] Modelo de domínio e `GLOSSARY.md` definidos para suportar múltiplas grades/regras e reclassificação.
- [x] Provedor de LLM e estratégia de classificação/reclassificação validados em amostra real de questões.
- [x] Arquitetura simplificada (backend, persistência, armazenamento de imagens, contratos de API) definida.
- [x] Fluxos principais da interface web de ingestão, revisão humana e consulta especificados.
- [x] Mapa do Wayfinder sem tickets abertos nem itens pendentes em `Not yet specified`, pronto para gerar `plano.md` e `tarefas/` de implementação.
