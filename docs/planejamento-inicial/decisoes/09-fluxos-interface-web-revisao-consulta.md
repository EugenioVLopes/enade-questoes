# Definir fluxos da interface web de ingestão, revisão humana e consulta

Type: grilling
Status: resolved
Blocked by: 06, 08

## Question

Considerando o modelo de domínio de [Definir modelo de domínio extensível e glossário (GLOSSARY.md)](./06-modelo-de-dominio-e-glossario.md) e a arquitetura de [Definir arquitetura da aplicação, persistência e simplificação da stack](./08-arquitetura-e-simplificacao-stack.md), quais são as telas, interações e estados essenciais da interface web na v1?

1. **Ingestão**: como o usuário envia PDF da prova + PDF do gabarito, informa metadados mínimos (curso/ano/taxonomia alvo) e acompanha o progresso ou erros parciais de extração;
2. **Fila e tela de revisão humana**: como visualizar enunciado, alternativas, gabarito e imagens recortadas lado a lado, aceitar ou corrigir disciplina principal/secundárias e marcar a questão como revisada;
3. **Consulta e filtros**: como buscar e filtrar questões por disciplina (principal ou secundária), ano/edição, status de revisão, taxonomia ativa e texto livre;
4. **Taxonomias, reclassificação e divergências**: qual o fluxo mínimo na UI para cadastrar/editar uma `Taxonomia` (incluindo arquivar `Disciplina`s), disparar uma `Execução de Classificação` (com opção explícita de incluir revisadas ou filtrar questões com `disciplina arquivada`) e triar/resolver `Divergência de Reclassificação` (aceitar candidata, manter revisão humana ou editar).

## Answer

### 1. Arquitetura de informação, navegação global e estado inicial

- **4 seções principais na barra lateral** + **cabeçalho global fixo**:
  1. **`Questões`**: consulta, busca textual, filtros combináveis e atalho para entrar no modo de revisão sobre o recorte filtrado.
  2. **`Revisão`** *(com badge numérico de pendências/divergências sob a `Taxonomia` ativa)*: workspace dedicado de curadoria sequencial em 3 abas (**`Pendentes`**, **`Divergências`** e **`Disciplina arquivada`**).
  3. **`Provas`**: listagem de `Prova`s, envio de nova `Ingestão`, atualização independente de `Gabarito`, reprocessamento e acompanhamento de progresso/erros.
  4. **`Taxonomias`**: gestão de `Taxonomia`s e `Disciplina`s, versionamento assistido de `Perfil de Classificação`, disparo de `Execução de Classificação` e histórico de **`Execuções`**.
- **Seletor global de `Taxonomia` ativa no cabeçalho**: persiste na URL/sessão e define o contexto imediato de `Questões` e `Revisão`, evitando reselecionar a `Taxonomia` em cada tela.
- **Indicador global discreto do worker local no cabeçalho**: enquanto houver qualquer `Ingestão` ou `Execução de Classificação` em `pendente` ou `processando`, uma pílula compacta no topo exibe o progresso em tempo real via polling leve (~2 s no TanStack Query, ex.: *"Classificando ENADE 2023: 14/29"*) e leva ao detalhe ao clicar.
- **Primeiro acesso (seed inicial + vocabulário canônico)**: o banco já inicia semeado com a `Taxonomia` `ENADE Engenharia de Computação` (18 `Disciplina`s) e o `Perfil de Classificação` padrão (`v2-fronteiras`). Com 0 `Prova`s cadastradas, `Questões` e `Revisão` exibem estado vazio com CTA direto **"Ingerir primeira prova"**. Todos os rótulos da interface seguem estritamente os 14 termos canônicos de [GLOSSARY.md](../../../GLOSSARY.md).

### 2. Fluxo de `Ingestão`, atualização de `Gabarito` e reprocessamento (`Provas`)

- **Formulário enxuto de nova `Ingestão`** (em página/drawer na seção `Provas`):
  - Upload obrigatório do PDF da `Prova` e upload opcional do PDF de `Gabarito`.
  - Metadados mínimos: `exame` (padrão `ENADE`), `curso` (ex.: `Engenharia de Computação`) e `ano`, além da faixa de questões do Componente Específico pré-preenchida pela regra do ano (ex.: `09–35` em 2014–2019, `10–38` em 2023, `16–45` em 2026+) editável em **"Opções avançadas"**.
  - Checkbox ligado por padrão **"Classificar automaticamente ao concluir"**, usando a `Taxonomia` ativa e o `Perfil de Classificação` padrão (desmarcável pelo usuário).
  - Envia via `POST /api/v1/provas` (`202 Accepted`) e acompanha o progresso na lista de `Provas` (polling ~2 s) exibindo contagens de `Questão`s extraídas, `Alerta de Extração`s e status da classificação encadeada, com atalho direto **"Revisar questões desta prova"**. Falhas na API de LLM nunca impedem a persistência ou revisão da `Prova`.
- **Unicidade `(exame, curso, ano)` e ciclo de vida seguro**:
  - Se a `Prova` já existir, a UI informa claramente a duplicidade e direciona para **Atualizar `Gabarito`** ou **Reprocessar `Prova`**.
  - **Atualizar `Gabarito`** (`PUT /api/v1/provas/{id}/gabarito`): botão direto no card da `Prova` (suporta `Gabarito` ausente → preliminar → definitivo) com exibição de resumo imediato das diferenças (*mantidas / alteradas / anuladas*), preservando 100% das `Classificação`s.
  - **Reprocessar `Prova`** (`POST /api/v1/provas/{id}/reprocessar`): exige diálogo de confirmação explícita. Quando a `Prova` já possui `Questão`s salvas, reconcilia por **`numero` oficial** (atualizando enunciado, `Alternativa`s, `Ativo Visual`s e `Alerta de Extração`s sem apagar `Classificação`s nem `Gabarito` vinculados àquele `numero`, alertando que edições manuais de texto naquelas questões serão substituídas pelo novo parse). Em status de erro ou `interrompida`, exibe o motivo e botão **"Tentar novamente"**.

### 3. Fila e tela de Revisão Humana (`Revisão`) e Triagem de `Divergência de Reclassificação`

- **3 abas na seção `Revisão`**:
  - **`Pendentes`**: `Questão`s com `Classificação` em `pendente_revisao` ou sem classificação sob a `Taxonomia` ativa, ordenadas deterministicamente por **1º `revisao_prioritaria = true`** (`Alerta de Extração` crítico, saneamento de trava ou baixa confiança) → **2º menor `confianca`** → **3º `(ano desc, numero asc)`**.
  - **`Divergências`**: `Questão`s com `Divergência de Reclassificação` aberta na `Taxonomia` ativa, ordenadas por execução mais recente e `(ano desc, numero asc)`.
  - **`Disciplina arquivada`**: `Questão`s cuja `Classificação` vigente aponta para uma `Disciplina` arquivada (`ativa = false`), permitindo correção manual imediata ou atalho para reclassificação em lote.
- **Layout em tela dividida (2 colunas fixas no desktop) com navegação sequencial**:
  - **Coluna esquerda (~60%, rolável — leitura da `Questão`)**: cabeçalho com `Prova`/ano, `numero` oficial, situação de `Gabarito`/`ANULADA` e badges de `Alerta de Extração`; enunciado renderizado em Markdown (tabelas e blocos de código); `Ativo Visual`s com clique para ampliação em lightbox; `Alternativa`s `A`–`E` (com destaque discreto para a correta e `Ativo Visual` vinculado quando existir); botão **"Copiar questão em Markdown"**. *(As ações de edição do conteúdo extraído e correção de mídia se encaixam nesta coluna e serão fechadas em [Definir tratamento e edição de mídia extraída e casos de borda do parser](./10-tratamento-edicao-midia-e-casos-borda.md).)*
  - **Coluna direita (~40%, fixa — veredito sob a `Taxonomia` ativa)**:
    - *Modo padrão (`Pendentes` / revisão individual)*: exibe sugestão da IA (`Disciplina` principal, 0–2 `Disciplina`s secundárias, `Tópico`s, justificativa, confiança e banner de `revisao_prioritaria` quando aplicável) + 2 ações primárias: **Aprovar sugestão** (1 clique in-place via `POST .../aprovar`) ou **Corrigir e aprovar** (edita principal, até 2 secundárias e `Tópico`s, gravando nova `Classificação` `origem=humana` via `POST .../corrigir`), avançando automaticamente para a próxima questão da fila (`Anterior / Próxima` + contador `X de N`).
    - *Questão sem classificação ou já aprovada*: quando não há sugestão automática, exibe o formulário manual direto (+ opção de disparar `Execução de Classificação` individual); quando já aprovada (ex.: aberta a partir de `Questões`), exibe o veredito vigente com ação **"Editar classificação"** preservando o histórico.
    - *Modo `Divergências`*: exibe **comparador lado a lado (Vigente humana × Candidata da IA)** destacando exatamente o que mudou em `Disciplina` principal/secundárias, a nova justificativa e a `Execução de Classificação` de origem, com 3 ações: **Manter humana**, **Aceitar candidata** ou **Editar manualmente** (que cria a nova `Classificação` humana e encerra a divergência atomicamente — refinando o contrato de `POST /api/v1/questoes/{id}/divergencias/{divergencia_id}/resolver` para aceitar `acao: aceitar_candidata | manter_humana | editar_manualmente`).
    - *Rastreabilidade multi-taxonomia*: abaixo do formulário, um **acordeão recolhido por padrão ("Outras taxonomias (N) e histórico")** permite consultar sem trocar de tela como a mesma `Questão` foi classificada em outras `Taxonomia`s e inspecionar o histórico imutável (predição original da IA vs revisões humanas).
  - **Atalhos de teclado básicos**: `A` (aprovar), `E` (editar/corrigir), `←`/`→` (anterior/próxima) e `Esc` (fechar lightbox/edição), automaticamente desabilitados quando o foco estiver em campos de texto.

### 4. Consulta e filtros (`Questões`)

- **Visibilidade e filtros padrão**:
  - Exibe **todas as `Questão`s sob a `Taxonomia` ativa** por padrão (sem esconder pendentes), identificadas por badges claros (`Pendente`, `Prioritária`, `Aprovada`, `Divergência`, `Anulada`, `Disciplina arquivada`).
  - **Barra de filtros principais (4 controles sempre visíveis)**: `Busca textual` (full-text + trigrama sobre enunciado, alternativas e `Tópico`s), `Disciplina` (incluindo **principal + secundárias por padrão**, acompanhada de toggle **"Somente principal"**), `Prova / Ano` e `Status de revisão`.
  - **Popover "Mais filtros"**: `Tópico`, `Situação do gabarito` (`valida | anulada | pendente`), `Com alerta de extração`, `Revisão prioritária`, `Com divergência` e `Usa disciplina arquivada`.
- **Listagem e ações sobre o recorte**:
  - **Cards enxutos** exibindo `Prova`/ano + nº oficial, snippet de ~2 linhas do enunciado, badges de `Disciplina` principal/secundárias, `Tópico`s, status de revisão, `Gabarito`/`ANULADA` e ícones de `Ativo Visual`/`Alerta de Extração`.
  - No topo da listagem: contador total e botão **"Revisar este recorte (N)"**, que abre a mesma tela dividida de `Revisão` sobre o conjunto filtrado atual. Clicar em qualquer card abre a `Questão` no mesmo layout de detalhe/revisão.
  - Sem exportação em lote na v1 (apenas consulta interativa + **"Copiar questão em Markdown"** no detalhe individual).

### 5. Gestão de `Taxonomia`s, `Perfil de Classificação` e `Execução de Classificação` (`Taxonomias`)

- **`Taxonomia`s e `Disciplina`s**:
  - CRUD completo na UI para criar/editar `Taxonomia` (`nome`, `curso_referencia`) e adicionar/editar `Disciplina`s (`codigo`, `nome`, `ementa`).
  - Ação de **arquivar/reativar `Disciplina`** (`ativa = false`, nunca exclusão física), exibindo no diálogo de confirmação quantas `Classificação`s vigentes utilizam aquela `Disciplina` (que passam a exibir o indicador passivo **"usa disciplina arquivada"**).
- **`Perfil de Classificação` (versionamento assistido)**:
  - Visualização dos perfis existentes e ação **"Criar nova versão"** a partir de um perfil base (gerando nova versão imutável via `POST /api/v1/perfis-classificacao`), com edição direta de `diretrizes_gerais` e `guia_fronteiras` e `template_prompt` em seção **"Avançado"** (herdado do perfil base por padrão).
- **Disparo e acompanhamento de `Execução de Classificação`**:
  - Modal/formulário dedicado para disparar `Execução de Classificação` (`POST /api/v1/execucoes-classificacao`), escolhendo `Taxonomia`, `Perfil de Classificação`, **escopo** (*todas as questões*, *por `Prova`*, *apenas não classificadas/pendentes* ou *com `Disciplina` arquivada*) e checkbox desligado por padrão **"Incluir questões já revisadas por humano"** (`incluir_revisadas = false`).
  - Aba **`Execuções`** listando cada rodada com seu snapshot resumido (`Taxonomia`, `Perfil`, escopo, data, `processadas/total`, erros, divergências abertas, hits de cache e tokens) e botão **"Retomar / Reprocessar falhas"** (`POST /api/v1/execucoes-classificacao/{id}/retomar`) sempre que o status for `interrompida` ou `concluida_com_erros`, reprocessando apenas pendentes/falhas com reaproveitamento do cache LLM.

### 6. Glossário e ADRs

- Todos os elementos da interface mapeiam 1:1 para os 14 termos canônicos já registrados em [GLOSSARY.md](../../../GLOSSARY.md); nenhum termo novo foi necessário.
- Nenhum ADR em `docs/adr/` foi aberto por se tratarem de decisões de fluxo e ergonomia de interface facilmente iteráveis na implementação.
