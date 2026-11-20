# Levantar matriz de referência oficial do ENADE e DCNs de Engenharia de Computação

Type: research
Status: resolved
Blocked by: none

## Question

Qual é a estrutura oficial de conteúdos/competências do Componente Específico nas diretrizes do **ENADE de Engenharia de Computação** (Portarias do INEP das últimas edições, ex.: 2017, 2019, 2023) e nas **Diretrizes Curriculares Nacionais (DCNs)** de Engenharia de Computação (Resolução CNE/CES), e qual catálogo inicial enxuto de disciplinas/áreas pode ser derivado diretamente dessas fontes primárias para servir como taxonomia semente da v1?

Investigar em fontes primárias (INEP, MEC/CNE, SBC):
1. Quais edições recentes do ENADE avaliaram Engenharia de Computação e qual a estrutura típica da prova (quantas questões objetivas no Componente Específico e sua numeração).
2. Lista oficial dos conteúdos do Componente Específico nas diretrizes do INEP e eixos das DCNs.
3. Proposta de taxonomia inicial (10 a 18 disciplinas com nome canônico, código/slug e breve ementa/escopo) claramente rastreável às fontes oficiais, destacando áreas de fronteira frequentes entre disciplinas (ex.: Arquitetura × Sistemas Operacionais, Eletrônica Digital × Sistemas Embarcados).

## Answer

- **Edições recentes e estrutura da prova (numeração variável por edição):**
  - **2014** (Portaria Inep nº 245/2014), **2017** (Portaria Inep nº 486/2017) e **2019** (Portaria Inep nº 497/2019): 40 questões (4 h), sendo Formação Geral = 10 (2 discursivas + 8 objetivas: Q01–Q08) e Componente Específico = 30 (3 discursivas + **27 objetivas: Q09–Q35**; em 2017, 10 das 27 objetivas seguiram a Portaria geral de Engenharia). Engenharia de Computação não integrou o Enade 2021.
  - **2023** (Portaria Inep nº 279/2023): 40 questões (4 h), sendo Formação Geral = 10 (1 discursiva + 9 objetivas: Q01–Q09) e Componente Específico = 30 (1 discursiva + **29 objetivas: Q10–Q38**).
  - **2026+** (Portaria Inep nº 161, de 14/04/2026, vigente a partir da edição 2026): 46 questões (4 h), sendo Formação Geral = 15 objetivas (sem discursivas) e Componente Específico = **30 objetivas + 1 discursiva** (faixa objetiva prevista Q16–Q45).
- **Base oficial de conteúdos e DCNs:** as listas do INEP mantêm núcleo altamente estável (20 itens em 2019, 21 em 2023 e **20 objetos de conhecimento no Art. 6º da Portaria nº 161/2026**), ancoradas na dupla vinculação normativa da **Resolução CNE/CES nº 5/2016** (DCNs da Computação — 11 competências específicas de EC no Art. 5º, § 2º), da **Resolução CNE/CES nº 2/2019** (DCNs de Engenharia — 8 competências gerais e núcleo básico no Art. 9º, § 1º) e dos **5 Eixos de Formação da SBC (2017)**. Na matriz do INEP, cada questão articula 1 característica de perfil, 1 competência e **até 3 conteúdos**.
- **Taxonomia semente proposta (v1):** **18 disciplinas canônicas** com slug, ementa e rastreabilidade direta às Portarias 2017–2026, DCNs e SBC (`matematica-e-estatistica`, `fisica-e-materiais`, `matematica-discreta-e-grafos`, `pesquisa-operacional-e-otimizacao`, `algoritmos-e-estruturas-de-dados`, `linguagens-formais-e-compiladores`, `engenharia-de-software-e-ihc`, `banco-de-dados`, `circuitos-e-eletronica`, `sistemas-digitais-e-embarcados`, `arquitetura-de-computadores`, `sistemas-operacionais`, `redes-e-comunicacoes`, `sistemas-distribuidos-e-paralelos`, `seguranca-computacional`, `ia-e-ciencia-de-dados`, `sinais-controle-e-automacao`, `gestao-viabilidade-e-etica`), acompanhadas de **14 pares de fronteira interdisciplinar** e recomendação de modelagem com `1 disciplina principal + 0 a 2 secundárias`.

[Relatório completo](../pesquisas/matriz-enade-dcns-eng-computacao.md)
