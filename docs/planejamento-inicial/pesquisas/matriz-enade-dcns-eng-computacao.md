# Matriz de Referência Oficial do ENADE e DCNs — Engenharia de Computação

Levantamento em fontes primárias (Portarias do INEP publicadas no DOU, Relatórios Síntese de Área do INEP, Resoluções CNE/CES do MEC e Referenciais de Formação da SBC) para fundamentar a taxonomia semente de disciplinas da v1 do banco de questões do ENADE de Engenharia de Computação.

---

## 1. Edições Recentes do ENADE e Estrutura Oficial da Prova

O curso de **Bacharelado em Engenharia de Computação** (rótulo CINE Brasil `0714E04`) integrou o ciclo trienal da área de Computação até 2017, foi reposicionado para o ciclo das Engenharias em 2019 (por isso ocorreu em 2017 e novamente em 2019, não integrando o Enade 2021) e voltou a ser avaliado em 2023 (ciclo das Engenharias postergado em 1 ano após a pandemia). Em abril de 2026, o INEP publicou nova portaria estrutural válida **a partir da edição 2026**.

| Edição | Norma do Componente Específico (INEP) | Duração | Formação Geral (FG) | Componente Específico (CE) | Faixa das Objetivas do CE | Observações estruturais |
|---|---|---:|---|---|---|---|
| **2014** | Portaria Inep nº 245, de 02/06/2014 ([Legislação INEP 2014](https://www.gov.br/inep/pt-br/centrais-de-conteudo/legislacao/enade/2014)) | 4 h | 10 questões (2 disc. + 8 obj.: Q01–Q08) | 30 questões (3 disc. + **27 obj.**) | **Q09–Q35** | Modelo clássico de 40 questões. |
| **2017** | Portaria Inep nº 486, de 06/06/2017 — DOU nº 109, 08/06/2017, Seção 1, p. 32 ([PDF DOU/ABMES](https://abmes.org.br/arquivos/legislacoes/Portaria-Inep-486-2017-06-06.pdf)) | 4 h | 10 questões (2 disc. + 8 obj.: Q01–Q08) | 30 questões (3 disc. + **27 obj.**) | **Q09–Q35** | Art. 4º, § 2º: **10 das 27 objetivas do CE** referenciadas pela Portaria Enade 2017 da área de Engenharia. Numeração confirmada no Anexo VIII do [Relatório Síntese 2017](https://ec.ufc.br/wp-content/uploads/2023/05/7.-enade-relatorioarea-2017.pdf). |
| **2019** | Portaria Inep nº 497, de 31/05/2019 — DOU nº 105, 03/06/2019, Seção 1, p. 41 ([PDF INEP](https://download.inep.gov.br/educacao_superior/enade/legislacao/2019/portaria_n497_31052019_engenharia_de_computacao_enade2019.pdf) / [ABMES](https://abmes.org.br/arquivos/legislacoes/Portaria-Enade-497-2019-05-31.pdf)) | 4 h | 10 questões (2 disc. + 8 obj.: Q01–Q08) | 30 questões (3 disc. + **27 obj.**) | **Q09–Q35** | Elimina a cota formal de 10 questões comuns de Engenharia e adota lista unificada de 20 conteúdos (Art. 6º). |
| **2023** | Portaria Inep nº 279, de 26/06/2023 — DOU nº 120, 27/06/2023, Seção 1, p. 29 ([PDF DOU/ABMES](https://abmes.org.br/arquivos/legislacoes/Portaria-Inep-279-2023-06-26.pdf) / [Legislação INEP 2023](https://www.gov.br/inep/pt-br/centrais-de-conteudo/legislacao/enade/2023)) | 4 h | 10 questões (1 disc. + 9 obj.: Q01–Q09) | 30 questões (1 disc. + **29 obj.**) | **Q10–Q38** | Reduz discursivas (de 5 para 2 no total) e amplia objetivas do CE para 29. Confirmado na [Prova 2023](https://download.inep.gov.br/enade/provas_e_gabaritos/2023_PV_engenharia_da_computacao.pdf) e no [Gabarito 2023](https://download.inep.gov.br/enade/provas_e_gabaritos/2023_GB_engenharia_da_computacao.pdf). |
| **2026+** | Portaria Inep nº 161, de 14/04/2026 — DOU nº 72, 16/04/2026, Seção 1, p. 93 ([PDF DOU/ABMES](https://abmes.org.br/arquivos/legislacoes/Portaria-inep-161-2026-04-14.pdf)) | 4 h | 15 questões (0 disc. + **15 obj.**) | 31 questões (1 disc. + **30 obj.**) | **Q16–Q45** *(previsto)* | Novo formato (total de 46 questões — Arts. 2º e 3º). Numeração sequencial exata a confirmar no caderno oficial da aplicação de 2026. |

> **Implicação para ingestão de provas:** o parser/importador **não** deve fixar uma única faixa de numeração para o Componente Específico; deve parametrizar por edição (`2014/2017/2019`: Q09–Q35; `2023`: Q10–Q38; `2026+`: 30 objetivas a partir de Q16).

### Repositórios oficiais do INEP (Provas, Gabaritos e Relatórios)
- **Índice oficial de Provas e Gabaritos (todas as edições):** <https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enade/provas-e-gabaritos>
- **Página dedicada do Enade 2023:** <https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enade/provas-e-gabaritos/2023>
- **Arquivos diretos Enade 2023 (Engenharia de Computação):**
  - Caderno de prova: <https://download.inep.gov.br/enade/provas_e_gabaritos/2023_PV_engenharia_da_computacao.pdf>
  - Gabarito definitivo: <https://download.inep.gov.br/enade/provas_e_gabaritos/2023_GB_engenharia_da_computacao.pdf>
  - Registro no Repositório Institucional do Inep (RIEP): <https://riep.inep.gov.br/items/7502e22d-5c0e-4430-ace7-c9d0b9357ecb/full> (Handle: <https://hdl.handle.net/20.500.14135/1447>)
- **Relatórios Síntese de Área (INEP):**
  - Enade 2019: <https://download.inep.gov.br/educacao_superior/enade/relatorio_sintese/2019/Enade_2019_Relatorios_Sintese_Area_Engenharia_de_Computacao.pdf> (RIEP: <https://riep.inep.gov.br/items/686c03bc-f38a-4934-a57b-f73446ba518d>)
  - Enade 2017 (espelho UFC): <https://ec.ufc.br/wp-content/uploads/2023/05/7.-enade-relatorioarea-2017.pdf>

---

## 2. Conteúdos Oficiais do INEP, DCNs (MEC/CNE) e Referenciais da SBC

### 2.1 Lista oficial de conteúdos / objetos de conhecimento nas Portarias do INEP

As matrizes de conteúdo das edições de **2019, 2023 e 2026** são altamente estáveis, com ajustes pontuais de granularidade e nomenclatura em relação a **2017**:

#### Portaria Inep nº 161/2026 (Art. 6º — vigente a partir do Enade 2026: 20 objetos de conhecimento)
Fonte: [Portaria Inep nº 161/2026, Art. 6º](https://abmes.org.br/arquivos/legislacoes/Portaria-inep-161-2026-04-14.pdf) (DOU 16/04/2026, p. 93).

1. **I** — matemática e estatística;
2. **II** — física e ciência dos materiais;
3. **III** — matemática discreta e teoria dos grafos;
4. **IV** — pesquisa operacional e otimização;
5. **V** — algoritmos, fundamentos de programação e estruturas de dados;
6. **VI** — linguagens formais e autômatos;
7. **VII** — engenharia de software;
8. **VIII** — interação humano-computador;
9. **IX** — banco de dados;
10. **X** — circuitos elétricos e eletrônicos;
11. **XI** — sistemas digitais e sistemas embarcados;
12. **XII** — organização e arquitetura de computadores;
13. **XIII** — sistemas operacionais;
14. **XIV** — ciência de dados;
15. **XV** — processamento de sinais;
16. **XVI** — inteligência artificial;
17. **XVII** — automação e sistemas de controle;
18. **XVIII** — redes de comunicação e redes de computadores;
19. **XIX** — segurança de sistemas de computação;
20. **XX** — sistemas distribuídos e processamento paralelo.

#### Evolução comparativa (2017 → 2019 → 2023 → 2026)
- **2017 ([Portaria Inep nº 486/2017, Art. 7º](https://abmes.org.br/arquivos/legislacoes/Portaria-Inep-486-2017-06-06.pdf)):** separava os conteúdos em **§ 1º Núcleo de Conteúdos Básicos (13 itens)** (*Administração; Ciências do Ambiente; Ciência e Tecnologia dos Materiais; Economia; Eletricidade Aplicada; Expressão Gráfica; Fenômenos de Transporte; Física; Informática; Matemática e Estatística; Mecânica dos Sólidos; Metodologia Científica e Tecnológica; Química*) e **§ 2º Núcleo de Conteúdos Profissionalizantes (20 itens)** — incluindo explicitamente *Compiladores* (II), *Computação gráfica* (X) e *Ética, empreendedorismo, computador e sociedade* (XI), e agrupando *Redes de computadores e sistemas distribuídos* (XX).
- **2019 ([Portaria Inep nº 497/2019, Art. 6º](https://abmes.org.br/arquivos/legislacoes/Portaria-Enade-497-2019-05-31.pdf)):** unificou a lista em **20 conteúdos (I–XX)**, removeu *Compiladores* e *Computação gráfica* como itens autônomos, introduziu *Segurança de sistemas de computação* (XIX), separou *Sistemas de comunicação e redes de computadores* (XVIII) de *Sistemas distribuídos e processamento paralelo* (XX), e agrupou *Análise de dados e processamento de sinais* (XV).
- **2023 ([Portaria Inep nº 279/2023, Art. 6º](https://abmes.org.br/arquivos/legislacoes/Portaria-Inep-279-2023-06-26.pdf)):** manteve a lista de 2019 em **21 conteúdos (I–XXI)**, desdobrando *Análise de dados e processamento de sinais* em **XV — Ciência de dados** e **XVI — Processamento de sinais**, e ampliando *Automação industrial e sistemas de controle* para **XVIII — Automação e sistemas de controle**.
- **2026 ([Portaria Inep nº 161/2026, Art. 6º](https://abmes.org.br/arquivos/legislacoes/Portaria-inep-161-2026-04-14.pdf)):** consolidou **V + VI** de 2023 em um único item (**V — algoritmos, fundamentos de programação e estruturas de dados**), atualizou nomenclaturas (**XII — organização e arquitetura de computadores**; **XVIII — redes de comunicação e redes de computadores**) e reestruturou o Art. 5º em **2 Competências gerais e 11 habilidades** (incluindo avaliação de estudos de viabilidade técnica, social e econômica — Competência II, habilidade 5).

> **Regra de construção de itens do INEP:** segundo o Anexo IX (*Concepção e Elaboração das Provas do Enade*) do [Relatório Síntese de Área Enade 2017 (p. 387)](https://ec.ufc.br/wp-content/uploads/2023/05/7.-enade-relatorioarea-2017.pdf), cada questão da matriz de prova é formulada pela articulação entre **1 característica de perfil, 1 competência e até 3 conteúdos** — o que explica a natureza frequentemente interdisciplinar das questões do exame.

### 2.2 Diretrizes Curriculares Nacionais (MEC/CNE)

A Engenharia de Computação possui **dupla vinculação normativa** explícita:

1. **DCNs da Área de Computação — Resolução CNE/CES nº 5, de 16/11/2016** (DOU nº 220, 17/11/2016, Seção 1, pp. 22–24 — [PDF MEC/Gov.br](https://www.gov.br/mec/pt-br/cne/pdf/normas-classificadas-por-assunto/diretrizes-curriculares-cursos-de-graduacao/rces005_16.pdf) / [ABMES](https://abmes.org.br/arquivos/legislacoes/Res-CES-CNE-005-2016-11-16.pdf) / [MEC Normas](https://mecnormas.mec.gov.br/pesquisa/detalhar/5128)):
   - **Art. 1º, parágrafo único:** a formação em Engenharia de Computação pode seguir esta Resolução **ou** as DCNs gerais de Engenharia (originalmente Res. CNE/CES nº 11/2002, depois substituída pela Res. CNE/CES nº 2/2019).
   - **Art. 4º, § 2º (Perfil do egresso de EC):** sólida formação em **Ciência da Computação, Matemática e Eletrônica** voltada à análise e projeto de sistemas de computação, automação e controle de processos industriais/comerciais, sistemas e dispositivos embarcados, telecomunicações e instrumentação eletrônica; domínio de propriedade intelectual, impactos sociais, gestão/qualidade e inovação.
   - **Art. 5º, § 2º (11 competências específicas de EC, I–XI):** (I) planejar/projetar/validar sistemas digitais, computadores, microprocessadores, comunicações e automação; (II) segurança de sistemas; (III) gerenciar projetos e manter sistemas; (IV) direitos e propriedade intelectual; (V) processadores específicos, sistemas integrados e embarcados (HW + SW); (VI) arquiteturas de computadores, inclusive paralelas e distribuídas, e otimização de software; (VII) software para sistemas de comunicação; (VIII) plataformas HW/SW para aplicações e sistemas embarcados de tempo real; (IX) selecionar/configurar plataformas de hardware; (X) projetar, implantar, administrar e gerenciar redes de computadores; (XI) estudos de viabilidade técnico-econômica.
   - **Art. 6º:** exige conteúdos básicos e tecnológicos comuns à Computação e específicos de cada curso, sem impor rol rígido de disciplinas obrigatórias (§ 1º). Carga horária mínima: 3.200 h (Art. 11).

2. **DCNs de Engenharia — Resolução CNE/CES nº 2, de 24/04/2019** (DOU nº 80, 26/04/2019, Seção 1, p. 43 — [PDF ABMES](https://abmes.org.br/arquivos/legislacoes/Resolucao-CNE-CES-002-2019-04-24.pdf)):
   - Revogou a Res. CNE/CES nº 11/2002 (Art. 18) e organizou o curso em torno de **8 competências gerais (Art. 4º, I–VIII)** (formular/conceber soluções; modelar fenômenos físicos/químicos; projetar sistemas/produtos/processos; implantar/supervisionar/controlar; comunicar-se; trabalhar/liderar equipes multidisciplinares; atuar com ética e legislação; aprender autonomamente).
   - **Art. 9º:** organiza os conteúdos em **básicos, profissionais e específicos** vinculados às competências. O **§ 1º** define o núcleo básico comum a todas as engenharias: *Administração e Economia; Algoritmos e Programação; Ciência dos Materiais; Ciências do Ambiente; Eletricidade; Estatística; Expressão Gráfica; Fenômenos de Transporte; Física; Informática; Matemática; Mecânica dos Sólidos; Metodologia Científica e Tecnológica; Química* (posteriormente acrescido de *Desenho Universal* pela Res. CNE/CES nº 1/2021, mencionada no Art. 8º da Portaria Inep nº 279/2023).

### 2.3 Referenciais de Formação da SBC (2017)

Nos *Referenciais de Formação para os Cursos de Graduação em Computação* (Zorzo et al., SBC, 2017, Cap. III — Bacharelado em Engenharia de Computação, pp. 40–55 — [Catálogo SBC](https://books-sol.sbc.org.br/index.php/sbc/catalog/book/134), DOI: <https://doi.org/10.5753/sbc.ref.2017.134>), a formação em EC é estruturada em **5 Eixos de Formação** diretamente rastreados às competências da Res. CNE/CES nº 5/2016:

1. **Eixo 1 — Fundamentos de Sistemas de Computação (C.1.1–C.1.11):** programação, estruturas de dados, complexidade, LFA, lógica, mapeamento programa–arquitetura, compilação, sistemas operacionais, avaliação de desempenho, cálculo/cálculo numérico, probabilidade e estatística, matemática discreta/grafos, eletricidade e magnetismo, análise de circuitos e eletrônica digital/geral.
2. **Eixo 2 — Desenvolvimento de Sistemas Computacionais (C.2.1–C.2.4):** projeto de hardware (circuitos digitais, arquitetura, microprocessadores, eletrônica analógica, microeletrônica); engenharia de software, confiabilidade/segurança e programação paralela/distribuída; integração HW/SW (software básico, periféricos, compiladores, SO, tempo real, sistemas embarcados); telecomunicações, redes, tratamento digital de sinais e controle/automação industrial.
3. **Eixo 3 — Gerenciamento de Sistemas Computacionais (C.3.1–C.3.4):** gestão de projetos, serviços, riscos, portfólios, normas, documentação técnica e especificação de requisitos.
4. **Eixo 4 — Inovação e Empreendedorismo (C.4.1–C.4.6):** simulação, metodologia científica, desenvolvimento de produtos, economia, viabilidade técnico-econômica, projetos multidisciplinares, administração e empreendedorismo.
5. **Eixo 5 — Desenvolvimento Pessoal e Profissional (C.5.1–C.5.3):** legislação/propriedade intelectual, ética/cidadania e engenharia ambiental/impactos socioambientais.

---

## 3. Taxonomia Semente Proposta para a v1 (18 Disciplinas)

Para equilibrar **cobertura 100% rastreável** às Portarias do INEP (2017–2026), às DCNs e à SBC com **enxugamento operacional** para busca, estatísticas e rotulagem de questões, propõe-se um catálogo inicial de **18 disciplinas canônicas**.

> **Recomendação de modelagem:** como o INEP constrói cada questão a partir de **até 3 conteúdos**, recomenda-se que cada questão no banco tenha **1 disciplina principal** (obrigatória, para agrupamento e estatísticas sem dupla contagem) e **0 a 2 disciplinas secundárias** (opcionais, capturando interdisciplinaridade).

### 3.1 Catálogo Canônico Inicial

| # | Código / Slug | Nome Canônico | Escopo / Ementa Resumida | Rastreabilidade Oficial (INEP / DCNs / SBC) |
|---|---|---|---|---|
| 1 | `matematica-e-estatistica` | Matemática, Probabilidade e Estatística | Cálculo diferencial/integral, equações diferenciais, álgebra linear, cálculo numérico, probabilidade, variáveis aleatórias, inferência e estatística aplicada. | INEP 2026 (I), 2023 (I), 2019 (I), 2017 (§1º X); DCN 2/2019 (Art. 9º §1º); SBC (C.1.6, C.1.7) |
| 2 | `fisica-e-materiais` | Física e Ciência dos Materiais | Mecânica, eletromagnetismo, ondas/óptica, termodinâmica básica, propriedades elétricas/semicondutoras de materiais e fundamentos físicos de Engenharia (inclui itens residuais do núcleo comum de 2017: química, mecânica dos sólidos e fenômenos de transporte). | INEP 2026 (II), 2023 (II), 2019 (II), 2017 (§1º III, VII, VIII, XI, XIII); DCN 2/2019 (Art. 9º §1º); SBC (C.1.9) |
| 3 | `matematica-discreta-e-grafos` | Matemática Discreta, Lógica e Teoria dos Grafos | Lógica proposicional e de predicados, conjuntos, relações, indução, combinatória, recorrências, teoria dos números e teoria dos grafos (caminhos, árvores, conectividade, coloração). | INEP 2026 (III), 2023 (III), 2019 (III), 2017 (§2º IV, XIV); SBC (C.1.2, C.1.8) |
| 4 | `pesquisa-operacional-e-otimizacao` | Pesquisa Operacional e Otimização | Programação linear (modelagem, Simplex, dualidade), programação inteira, otimização combinatória, fluxos em redes, teoria de filas e simulação de eventos discretos. | INEP 2026 (IV), 2023 (IV), 2019 (IV), 2017 (§2º XV); SBC (C.1.5) |
| 5 | `algoritmos-e-estruturas-de-dados` | Algoritmos, Programação e Estruturas de Dados | Paradigmas e fundamentos de programação (estruturada, OO, funcional), estruturas lineares/árvores/hashing/heaps, ordenação, busca, projeto e análise de complexidade de algoritmos (divisão e conquista, guloso, programação dinâmica). | INEP 2026 (V), 2023 (V, VI), 2019 (V, VI), 2017 (§2º III, V); DCN 5/2016 (Art. 5º I, III); DCN 2/2019 (Art. 9º §1º); SBC (C.1.1, C.2.2) |
| 6 | `linguagens-formais-e-compiladores` | Linguagens Formais, Autômatos e Compiladores | Hierarquia de Chomsky, expressões regulares, autômatos finitos e de pilha, gramáticas livres de contexto, máquinas de Turing, decidibilidade/computabilidade e fases de compilação (análise léxica, sintática, semântica e geração de código). | INEP 2026 (VI), 2023 (VII), 2019 (VII), 2017 (§2º I, II); DCN 5/2016 (Art. 5º II); SBC (C.1.2, C.1.3, C.2.3) |
| 7 | `engenharia-de-software-e-ihc` | Engenharia de Software e Interação Humano-Computador | Processos e ciclo de vida (ágeis e tradicionais), engenharia de requisitos, modelagem (UML), arquitetura e padrões de projeto, qualidade, verificação/validação/testes, manutenção, usabilidade, acessibilidade e avaliação de IHC. | INEP 2026 (VII, VIII), 2023 (VIII, IX), 2019 (VIII, IX), 2017 (§2º VI, VII); DCN 5/2016 (Art. 5º §2º I, III); SBC (C.2.2, C.3.4) |
| 8 | `banco-de-dados` | Banco de Dados | Modelagem conceitual (MER/EER), modelo relacional, álgebra relacional, SQL, normalização, indexação, processamento de consultas, transações (ACID), controle de concorrência, recuperação e bancos NoSQL. | INEP 2026 (IX), 2023 (X), 2019 (X), 2017 (§2º VIII); SBC (C.2.2) |
| 9 | `circuitos-e-eletronica` | Circuitos Elétricos e Eletrônica | Leis de Kirchhoff, análise nodal/malhas, teoremas (Thévenin/Norton), circuitos RC/RL/RLC (DC/AC, fasores), diodos, transistores (BJT/MOSFET), amplificadores operacionais, fontes e condicionamento analógico de sinais. | INEP 2026 (X), 2023 (XI), 2019 (XI), 2017 (§1º V, §2º XVII); DCN 5/2016 (Art. 4º §2º I); DCN 2/2019 (Art. 9º §1º); SBC (C.1.10, C.2.1) |
| 10 | `sistemas-digitais-e-embarcados` | Sistemas Digitais e Sistemas Embarcados | Álgebra booleana, simplificação (Karnaugh), circuitos combinacionais e sequenciais (flip-flops, contadores, FSMs), VHDL/Verilog/FPGA, microcontroladores, interfaces/periféricos (GPIO, PWM, ADC/DAC, UART/SPI/I2C), firmware e sistemas de tempo real. | INEP 2026 (XI), 2023 (XII), 2019 (XII), 2017 (§2º XVI); DCN 5/2016 (Art. 5º §2º I, V, VIII); SBC (C.1.10, C.2.1, C.2.3) |
| 11 | `arquitetura-de-computadores` | Organização e Arquitetura de Computadores | Representação de dados e aritmética computacional, conjunto de instruções (ISA), caminho de dados e controle, pipeline e hazards, hierarquia de memória (cache), E/S, DMA, arquiteturas superescalares, multicore e avaliação de desempenho (CPI, lei de Amdahl). | INEP 2026 (XII), 2023 (XIII), 2019 (XIII), 2017 (§2º XIII); DCN 5/2016 (Art. 5º §2º VI, IX); SBC (C.1.3, C.1.5, C.2.1) |
| 12 | `sistemas-operacionais` | Sistemas Operacionais | Processos e threads, escalonamento de CPU (incluindo tempo real), sincronização e concorrência (semáforos, mutex, deadlock), gerência de memória (paginação, segmentação, memória virtual), sistemas de arquivos, gerência de E/S e virtualização. | INEP 2026 (XIII), 2023 (XIV), 2019 (XIV), 2017 (§2º XII); DCN 5/2016 (Art. 5º §2º VIII, IX); SBC (C.1.4, C.2.3) |
| 13 | `redes-e-comunicacoes` | Redes de Computadores e Sistemas de Comunicação | Camada física e princípios de telecomunicações (modulação, multiplexação, meios de transmissão), modelos OSI e TCP/IP, enlace/Ethernet/Wi-Fi, roteamento e endereçamento IP (CIDR/sub-redes), transporte (TCP/UDP, controle de congestionamento) e protocolos de aplicação (DNS, HTTP). | INEP 2026 (XVIII), 2023 (XIX), 2019 (XVIII), 2017 (§2º XX); DCN 5/2016 (Art. 5º §2º I, VII, X); SBC (C.2.1, C.2.4) |
| 14 | `sistemas-distribuidos-e-paralelos` | Sistemas Distribuídos e Processamento Paralelo | Arquiteturas paralelas (memória compartilhada/distribuída, OpenMP, MPI, GPU), comunicação entre processos (RPC, REST, mensageria), relógios lógicos, coordenação/consenso, tolerância a falhas, replicação, consistência e computação em nuvem. | INEP 2026 (XX), 2023 (XXI), 2019 (XX), 2017 (§2º XX); DCN 5/2016 (Art. 5º §2º VI); SBC (C.2.2, C.2.3) |
| 15 | `seguranca-computacional` | Segurança de Sistemas de Computação | Tríade CIA, criptografia simétrica e assimétrica, hashes, assinatura digital e PKI/certificados, autenticação e controle de acesso, segurança de redes (TLS, firewall, IDS/VPN), vulnerabilidades de software/web e gestão de riscos/normas (LGPD, ISO 27001). | INEP 2026 (XIX), 2023 (XX), 2019 (XIX); DCN 5/2016 (Art. 5º §2º II); INEP 2026 (Art. 5º II.b.3); SBC (C.2.2) |
| 16 | `ia-e-ciencia-de-dados` | Inteligência Artificial e Ciência de Dados | Busca heurística, representação de conhecimento, aprendizado de máquina (supervisionado, não supervisionado, redes neurais), avaliação de modelos, ciência de dados (coleta, limpeza, análise exploratória, mineração e visualização de dados). | INEP 2026 (XIV, XVI), 2023 (XV, XVII), 2019 (XV, XVI), 2017 (§2º IX); SBC (C.2.2) |
| 17 | `sinais-controle-e-automacao` | Processamento de Sinais, Controle e Automação | Sinais e sistemas lineares invariantes no tempo, séries/transformadas de Fourier, Laplace e Z, teorema da amostragem, filtros digitais/DSP, modelagem de sistemas dinâmicos, função de transferência, estabilidade, controladores (PID), automação industrial (CLPs, sensores/atuadores, SCADA). | INEP 2026 (XV, XVII), 2023 (XVI, XVIII), 2019 (XV, XVII), 2017 (§2º XVIII, XIX); DCN 5/2016 (Art. 4º §2º I, Art. 5º §2º I); SBC (C.2.4) |
| 18 | `gestao-viabilidade-e-etica` | Gestão de Projetos, Viabilidade Técnico-Econômica e Ética Profissional | Gestão de projetos e ciclo de vida, estudos de viabilidade técnica/social/econômica (engenharia econômica: VPL, TIR, payback), administração/empreendedorismo, metodologia científica, propriedade intelectual, legislação profissional, ética e sustentabilidade ambiental. | INEP 2026 (Art. 5º II.b.5), 2023 (Art. 5º XIX), 2019 (Art. 5º IX), 2017 (§1º I, II, IV, XII; §2º XI); DCN 5/2016 (Art. 4º §2º II–VI, Art. 5º §2º III, IV, XI); DCN 2/2019 (Art. 4º IV, VII; Art. 9º §1º); SBC (Eixos 3, 4 e 5) |

> **Tópicos históricos de 2014/2017 removidos das Portarias 2019–2026:** questões isoladas de *Computação Gráfica* (2017 §2º X) podem ser classificadas conforme o foco predominante em `matematica-e-estatistica` (transformações geométricas/álgebra linear), `sinais-controle-e-automacao` (processamento de imagens) ou `algoritmos-e-estruturas-de-dados` (rasterização/estruturas espaciais), recebendo uma tag livre `computacao-grafica` se houver recorrência.

---

### 3.2 Fronteiras Interdisciplinares Frequentes (Guia de Desambiguação)

Os pares abaixo concentram os casos mais recorrentes de sobreposição em provas do ENADE e servem como regra editorial de desambiguação entre `disciplina_principal` e `disciplina_secundaria`:

| Fronteira frequente | Temas típicos na interseção | Critério sugerido para `disciplina_principal` |
|---|---|---|
| **Organização e Arquitetura de Computadores × Sistemas Operacionais** | Memória virtual, paginação/TLB, hierarquia de cache, DMA, interrupções, escalonamento multicore. | Se o foco é organização de hardware, endereçamento físico/cache ou métricas de CPU (CPI/miss rate) → `arquitetura-de-computadores`; se o foco é política de escalonamento, tabelas de páginas, troca de contexto ou sincronização do kernel → `sistemas-operacionais`. |
| **Circuitos Elétricos e Eletrônica × Sistemas Digitais e Embarcados** | Portas lógicas em nível transistor (CMOS/TTL), conversores ADC/DAC, condicionamento de sensores, acionamento PWM. | Se exige análise de tensões, correntes, ganho ou resposta analógica de componentes → `circuitos-e-eletronica`; se exige lógica booleana, resolução em bits, temporização digital ou programação de periféricos → `sistemas-digitais-e-embarcados`. |
| **Sistemas Digitais e Embarcados × Arquitetura de Computadores** | ULA, datapath, unidade de controle/FSM, barramentos, FPGA/SoC. | Se o foco é síntese lógica, portas, flip-flops, FSM ou hardware dedicado/microcontrolador → `sistemas-digitais-e-embarcados`; se o foco é ISA, pipeline, organização de processadores de propósito geral e desempenho → `arquitetura-de-computadores`. |
| **Sistemas Digitais e Embarcados × Sistemas Operacionais** | RTOS, escalonamento de tempo real (RM/EDF), tratamento de interrupções (ISR), drivers e restrições de deadline. | Se o foco está no hardware/periféricos/firmware embarcado → `sistemas-digitais-e-embarcados`; se o foco está em algoritmos de escalonamento, inversão de prioridade ou abstrações de kernel → `sistemas-operacionais`. |
| **Redes e Comunicações × Sistemas Distribuídos e Paralelos** | Sockets, RPC/REST, balanceamento de carga, latência, replicação e tolerância a falhas em rede. | Se trata de camadas OSI/TCP-IP, roteamento, sub-redes ou protocolos de transporte/enlace → `redes-e-comunicacoes`; se trata de coordenação, consenso, consistência, paralelismo ou arquitetura distribuída → `sistemas-distribuidos-e-paralelos`. |
| **Redes e Comunicações × Segurança Computacional** | TLS/HTTPS, VPN, firewalls, ataques de rede (DDoS, MITM, spoofing), autenticação e PKI. | Se o objetivo avaliado é vulnerabilidade, confidencialidade/integridade/autenticidade ou mecanismo criptográfico → `seguranca-computacional`; se o foco é funcionamento estrutural do protocolo de rede → `redes-e-comunicacoes`. |
| **Sistemas Operacionais × Sistemas Distribuídos e Paralelos** | Threads, exclusão mútua, deadlock, OpenMP/MPI, virtualização e contêineres. | Concorrência em nó único / gerência local de recursos → `sistemas-operacionais`; paralelismo de alto desempenho (speedup/escalabilidade em múltiplos nós) ou sistemas distribuídos → `sistemas-distribuidos-e-paralelos`. |
| **Algoritmos e ED × Matemática Discreta e Grafos** | Algoritmos em grafos (BFS/DFS, Dijkstra, árvores geradoras), recorrências e análise assintótica. | Se o foco é propriedade estrutural/prova matemática/combinatória → `matematica-discreta-e-grafos`; se o foco é implementação, estrutura de dados ou complexidade algorítmica → `algoritmos-e-estruturas-de-dados`. |
| **Algoritmos e ED × Pesquisa Operacional e Otimização** | Programação dinâmica, algoritmos gulosos, branch-and-bound, meta-heurísticas e fluxos. | Se há formulação de modelo matemático de decisão (função objetivo + restrições, Simplex, filas) → `pesquisa-operacional-e-otimizacao`; se o foco é técnica algorítmica e complexidade → `algoritmos-e-estruturas-de-dados`. |
| **Matemática e Estatística × IA e Ciência de Dados** | Regressão, probabilidade bayesiana, álgebra linear (PCA/matrizes), métricas e validação estatística. | Se avalia teoria/cálculo probabilístico ou estatístico geral → `matematica-e-estatistica`; se avalia pipeline de dados, treinamento/generalização ou algoritmos de aprendizado de máquina → `ia-e-ciencia-de-dados`. |
| **Banco de Dados × IA e Ciência de Dados** | Data warehouse, OLAP, consultas analíticas SQL, ETL e mineração de dados. | Modelagem, integridade, SQL e armazenamento/indexação → `banco-de-dados`; modelagem preditiva, descoberta de padrões ou análise exploratória → `ia-e-ciencia-de-dados`. |
| **Circuitos e Eletrônica × Sinais, Controle e Automação** | Circuitos RLC modelados por Laplace, filtros analógicos vs digitais, diagrama de Bode. | Cálculo de grandezas elétricas do circuito → `circuitos-e-eletronica`; análise de resposta em frequência, estabilidade, espectro ou malha de controle → `sinais-controle-e-automacao`. |
| **Linguagens Formais e Compiladores × Sistemas Digitais e Embarcados** | Máquinas de Estados Finitos (Mealy/Moore), minimização de estados e reconhecimento de sequências. | Reconhecimento de linguagens/gramáticas/análise léxica → `linguagens-formais-e-compiladores`; síntese de circuito sequencial com flip-flops/HDL → `sistemas-digitais-e-embarcados`. |
| **Engenharia de Software e IHC × Banco de Dados / Segurança / Gestão** | Modelagem UML × MER, requisitos de segurança, cronograma/custos de projeto de software. | Engenharia de requisitos, arquitetura, testes e usabilidade → `engenharia-de-software-e-ihc`; viabilidade financeira/gestão corporativa/propriedade intelectual → `gestao-viabilidade-e-etica`. |

---

## 4. Fontes Primárias Consultadas

1. **INEP — Portaria nº 161, de 14 de abril de 2026** (Diretrizes de prova do Componente Específico de Bacharelado em Engenharia de Computação a partir do Enade 2026; DOU nº 72, 16/04/2026, Seção 1, p. 93): <https://abmes.org.br/arquivos/legislacoes/Portaria-inep-161-2026-04-14.pdf>
2. **INEP — Portaria nº 279, de 26 de junho de 2023** (Diretrizes de prova e Componente Específico de Engenharia de Computação — Enade 2023; DOU nº 120, 27/06/2023, Seção 1, p. 29): <https://abmes.org.br/arquivos/legislacoes/Portaria-Inep-279-2023-06-26.pdf> e <https://www.gov.br/inep/pt-br/centrais-de-conteudo/legislacao/enade/2023>
3. **INEP — Portaria nº 497, de 31 de maio de 2019** (Componente Específico de Engenharia de Computação — Enade 2019; DOU nº 105, 03/06/2019, Seção 1, p. 41): <https://download.inep.gov.br/educacao_superior/enade/legislacao/2019/portaria_n497_31052019_engenharia_de_computacao_enade2019.pdf> e <https://abmes.org.br/arquivos/legislacoes/Portaria-Enade-497-2019-05-31.pdf>
4. **INEP — Portaria nº 486, de 6 de junho de 2017** (Diretrizes de prova de Engenharia de Computação — Enade 2017; DOU nº 109, 08/06/2017, Seção 1, p. 32): <https://abmes.org.br/arquivos/legislacoes/Portaria-Inep-486-2017-06-06.pdf>
5. **INEP — Legislação do Enade 2014** (Portaria Inep nº 245, de 02/06/2014): <https://www.gov.br/inep/pt-br/centrais-de-conteudo/legislacao/enade/2014>
6. **INEP — Provas e Gabaritos do Enade (Portal Oficial):** <https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enade/provas-e-gabaritos> e edição 2023 em <https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enade/provas-e-gabaritos/2023>
7. **INEP — Caderno de Prova e Gabarito Definitivo Enade 2023 (Engenharia de Computação):** <https://download.inep.gov.br/enade/provas_e_gabaritos/2023_PV_engenharia_da_computacao.pdf>, <https://download.inep.gov.br/enade/provas_e_gabaritos/2023_GB_engenharia_da_computacao.pdf> e RIEP <https://riep.inep.gov.br/items/7502e22d-5c0e-4430-ace7-c9d0b9357ecb/full>
8. **INEP — Relatórios Síntese de Área (Engenharia de Computação):** 2019 (<https://download.inep.gov.br/educacao_superior/enade/relatorio_sintese/2019/Enade_2019_Relatorios_Sintese_Area_Engenharia_de_Computacao.pdf>) e 2017 (<https://ec.ufc.br/wp-content/uploads/2023/05/7.-enade-relatorioarea-2017.pdf>)
9. **MEC / CNE — Resolução CNE/CES nº 5, de 16 de novembro de 2016** (DCNs para os cursos de graduação na área da Computação; DOU nº 220, 17/11/2016, Seção 1, pp. 22–24): <https://www.gov.br/mec/pt-br/cne/pdf/normas-classificadas-por-assunto/diretrizes-curriculares-cursos-de-graduacao/rces005_16.pdf> e <https://mecnormas.mec.gov.br/pesquisa/detalhar/5128>
10. **MEC / CNE — Resolução CNE/CES nº 2, de 24 de abril de 2019** (DCNs do Curso de Graduação em Engenharia; DOU nº 80, 26/04/2019, Seção 1, p. 43): <https://abmes.org.br/arquivos/legislacoes/Resolucao-CNE-CES-002-2019-04-24.pdf>
11. **SBC — Referenciais de Formação para os Cursos de Graduação em Computação** (Zorzo et al., 2017, ISBN 978-85-7669-424-3, Cap. III — Bacharelado em Engenharia de Computação): <https://books-sol.sbc.org.br/index.php/sbc/catalog/book/134> (DOI: <https://doi.org/10.5753/sbc.ref.2017.134>)
