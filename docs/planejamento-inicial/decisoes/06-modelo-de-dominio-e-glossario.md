# Definir modelo de domínio extensível e glossário (GLOSSARY.md)

Type: grilling
Status: resolved
Blocked by: 03

## Question

Com base na estrutura oficial levantada em [Levantar matriz de referência oficial do ENADE e DCNs de Engenharia de Computação](./03-levantar-matriz-enade-eng-computacao.md), qual modelo de domínio e qual vocabulário canônico (`GLOSSARY.md`) garantem que:

1. O conteúdo extraído da prova (`Prova`, `Questão`, `Alternativa`, `AtivoVisual`/figura, `Gabarito`) fique desacoplado das classificações;
2. Múltiplas taxonomias/grades curriculares (ex.: matriz ENADE Eng. de Computação, PPC de uma universidade, outro curso no futuro) coexistam sem conflito;
3. Cada classificação suporte **1 disciplina principal + disciplinas secundárias opcionais**, justificativa, grau de confiança e rastreabilidade da regra/prompt/modelo que a gerou;
4. Uma reclassificação por nova regra ou nova grade preserve histórico e revisões humanas anteriores de forma clara e auditável?

## Answer

### Vocabulário canônico

Consolidado em [GLOSSARY.md](../../../GLOSSARY.md) com 13 termos canônicos distribuídos em três agrupamentos (**Conteúdo de Prova**, **Taxonomia Curricular** e **Classificação e Revisão**), eliminando sinônimos ambíguos como "grade/matriz" (→ `Taxonomia`), "regra" (→ `Perfil de Classificação`), "tag/subtema" (→ `Tópico`) e "figura/anexo" (→ `Ativo Visual`).

### 1. Núcleo de Conteúdo de Prova (desacoplado de classificações)

- **`Prova`**: identidade única por `(exame, curso, ano)` (ex.: `ENADE / Engenharia de Computação / 2023`), evitando duplicação silenciosa e exigindo ação explícita para reprocessamento. Guarda referência ao PDF original e ao artefato bruto da ingestão.
- **`Questão`**: pertence a uma `Prova`, identificada por `numero` oficial, com metadados `componente` (v1: `componente_especifico`) e `tipo` (v1: `objetiva`) já preparados para expansão futura. Mantém o conteúdo curado atual (`enunciado` em Markdown preservando tabelas/código), proveniência (`paginas`, `alertas_extracao`) e vínculo de **`Gabarito`**, sem duplicar colunas separadas de texto bruto vs editado (o PDF original e a saída bruta da ingestão seguem como fonte da verdade).
- **`Alternativa`**: pertence a uma `Questão`, identificada por `letra` (`A`–`E`) e texto em Markdown.
- **`Ativo Visual`**: pertence a uma `Questão`, com vínculo opcional à `Alternativa` (`A`–`E`) para suportar circuitos/gráficos dentro de alternativas; preserva `ordem`, `pagina` e `bbox` no PDF de origem.
- **`Gabarito`**: vinculado à `Questão` com `situacao_gabarito` (`valida | anulada | pendente`) e `alternativa_correta` (`A..E | null`). Questões `ANULADA`s permanecem no banco (filtráveis na consulta) e o `Gabarito` de uma `Prova` pode ser atualizado de forma independente (ex.: preliminar → definitivo) sem reingerir o PDF nem perder classificações.
- **`Alerta de Extração`**: lista estruturada de sinalizações determinísticas por `Questão` (ex.: `formula_nao_decodificada`, `alternativas_incompletas`, `pdf_via_ocr`).

### 2. Taxonomia Curricular (multi-taxonomia e evolução segura)

- **`Taxonomia`**: catálogo nomeado e editável de `Disciplina`s (com `curso_referencia` apenas informativo), livremente aplicável a questões de qualquer `Prova` (ex.: classificar ENADE Eng. Computação sob a matriz ENADE e sob o PPC de outro curso sem conflito).
- **`Disciplina`**: pertence a uma `Taxonomia` (`codigo`/slug, `nome`, `ementa`, `ativa`). Catálogo plano na v1 (iniciando pelas 18 disciplinas canônicas de [Levantar matriz de referência oficial do ENADE e DCNs de Engenharia de Computação](./03-levantar-matriz-enade-eng-computacao.md)).
- **Evolução sem quebra**: `Taxonomia` é editável no lugar com arquivamento seguro (`ativa = false`, nunca exclusão física). Quando uma `Disciplina` é arquivada, classificações vigentes que apontam para ela permanecem legíveis e válidas com indicador passivo de **"usa disciplina arquivada"** para filtragem e reclassificação gradual.
- **`Tópico`**: tags livres opcionais registradas na `Classificação` (geradas pelo modelo e editáveis na revisão) para busca/filtro granular por tema (ex.: `pipeline`, `computacao-grafica`, `pid`) sem introduzir hierarquia fechada de subdisciplinas na v1.

### 3. Classificação, Perfis, Histórico e Política de Conflito

- **`Perfil de Classificação`**: conjunto versionado de diretrizes textuais para o LLM (ementas da taxonomia + guia de desambiguação de fronteiras + instruções editoriais) combinado ao template de prompt e modelo de IA — sem motor simbólico `if/then` na v1.
- **`Execução de Classificação`**: rodada registrada de classificação automática sobre um conjunto de `Questão`s, armazenando o **snapshot congelado** da `Taxonomia` (disciplinas + ementas) e do `Perfil de Classificação` aplicados naquela execução.
- **`Classificação`**: veredito para um par `(Questão, Taxonomia)` com `1 Disciplina principal` + `0 a 2 Disciplinas secundárias` + `Tópicos` opcionais + `justificativa` + `confiança` + `origem` (`automatica | humana`) + referência opcional à `Execução de Classificação` e à classificação anterior substituída.
- **Imutabilidade de veredito e preservação da predição da IA**:
  - Aprovar uma sugestão da IA sem alterações atualiza apenas seu estado (`pendente_revisao` → `aprovada`, com timestamp de revisão), evitando duplicação de registros.
  - Corrigir manualmente uma classificação **nunca edita o registro da IA in-place**: cria uma nova `Classificação` (`origem = humana`, `vigente = true`, `status = aprovada`) apontando para a sugestão substituída, preservando intacta a saída original da IA para auditoria e métricas futuras de acurácia.
- **Política de conflito na reclassificação (mesma `Taxonomia`)**:
  - Por padrão, uma reclassificação **pula questões já revisadas por humano** (processando apenas não revisadas ou sem classificação), economizando cota de API.
  - Caso o usuário opte explicitamente por **incluir questões já revisadas**, a decisão humana permanece **vigente** (nunca é sobrescrita automaticamente).
  - **Critério de `Divergência de Reclassificação`**: abre alerta de sugestão candidata em conflito **apenas** quando a nova execução difere na **Disciplina principal** ou no conjunto de **Disciplinas secundárias** (variações só de justificativa, confiança ou `Tópicos` livres ficam registradas no histórico como concordantes, sem gerar ruído na fila).
  - O fluxo de UI para triagem/aceite/descarte de `Divergência de Reclassificação` e filtragem por `disciplina arquivada` segue para [Definir fluxos da interface web de ingestão, revisão humana e consulta](./09-fluxos-interface-web-revisao-consulta.md).
