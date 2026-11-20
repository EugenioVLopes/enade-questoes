# Definir tratamento e edição de mídia extraída e casos de borda do parser

Type: grilling
Status: resolved
Blocked by: 05, 06, 08

## Question

Agora que [Prototipar extração em uma prova real do ENADE (Docling vs alternativa)](./05-prototipar-extracao-prova-real.md) fechou **Docling 2.151.1** (`DoclingDocument` com `PictureItem` + `prov/bbox` + `TableItem` + fallback `force_full_page_ocr` para CMap corrompido) e expôs os casos de borda concretos do INEP (`formula-not-decoded` como Q13/2023, alternativas de código agrupadas em bloco único como Q15/2023, fonte `Symbol` como `ρ` → `r` na Q10/2023 e barcodes/logos em margem), qual política de produto e UX devemos adotar na v1 para:

1. **Edição do conteúdo extraído na revisão humana**: o revisor poderá editar enunciado, alternativas (A–E), tabelas Markdown e blocos de código diretamente na tela de revisão, ou apenas marcar/corrigir classificações?
2. **Correção de mídia (`AtivoVisual`)**: como lidar com figuras mal recortadas, faltantes ou descartadas indevidamente pelo filtro de margem — visualizar recorte da página original do PDF (`pypdfium2`), fazer upload de substituição, ou re-recortar por bounding box na UI?
3. **Sinalização de alertas do parser**: quais anomalias determinísticas (ex.: menos de 5 alternativas A–E detectadas, presença de `<!-- formula-not-decoded -->`, PDF processado via `force_full_page_ocr`) devem abrir uma flag de revisão obrigatória no fluxo de curadoria?

## Answer

### 1. Edição do conteúdo extraído na revisão humana e renderização

- **Edição sob demanda na coluna esquerda da `Revisão`** (modo leitura como padrão para preservar velocidade na curadoria):
  - Botão **"Editar conteúdo"** libera edição inline de `enunciado` em Markdown, texto de cada `Alternativa` (`A`–`E`, permitindo criar ou separar alternativas faltantes como na Q15/2023) e `Gabarito` individual (`situacao_gabarito` e `alternativa_correta`), com alternância `Editar / Preview` e persistência via `PATCH /api/v1/questoes/{id}`.
- **Renderização segura de texto técnico**:
  - Frontend renderiza **Markdown GFM** (tabelas e blocos de código com destaque de sintaxe) + **fórmulas LaTeX via KaTeX** (`$...$` / `$$...$$`), sempre sanitizado (sem HTML arbitrário), cobrindo equações, tabelas verdade e trechos de código (C, Java, Verilog, VHDL, SQL).
- **Sem reclassificação automática ao editar**:
  - Salvar alterações em texto, `Alternativa`s ou `Ativo Visual`s **não** dispara o LLM automaticamente (evitando consumo de cota em ajustes cosméticos e corrida de estado na tela de revisão). A UI exibe aviso discreto com botão explícito **"Reclassificar esta questão"**, aproveitando a invalidação natural do cache LLM pelo novo hash de conteúdo.

### 2. Visualização do PDF original, gestão de `Ativo Visual` e fallback de fórmulas

- **Referência direta à página original do PDF**:
  - Endpoint `GET /api/v1/provas/{id}/paginas/{pagina}/imagem` renderiza sob demanda a página original de `prova.pdf` via `pypdfium2` (com cache/ETag), acessível em modal/painel na coluna esquerda da `Revisão` para conferência imediata de fórmulas, símbolos gregos e figuras sem sair da aplicação.
- **Gestão manual de `Ativo Visual` (sem crop interativo no navegador na v1)**:
  - Ações manuais disponíveis no modo de edição de conteúdo: **upload de novo `Ativo Visual`**, **substituição do arquivo**, **reordenação**, **vínculo/desvínculo à `Alternativa` (`A`–`E` ou enunciado)** e **exclusão** de falsos positivos que escaparem do filtro.
  - Endpoints adicionados ao grupo de Questões e `Ativo Visual`:
    - `POST /api/v1/questoes/{id}/ativos-visuais` (upload manual com `alternativa_letra` opcional).
    - `PATCH /api/v1/ativos-visuais/{id}` (reordenar, alterar `alternativa_letra` ou substituir imagem).
    - `DELETE /api/v1/ativos-visuais/{id}` (excluir ativo descartável/falso positivo).
  - Editor de recorte retangular (bounding box) sobre o canvas do PDF no browser fica fora da v1.
- **Fallback automático para `formula_nao_decodificada`**:
  - Quando o Docling emitir `FormulaItem` não decodificado (`<!-- formula-not-decoded -->`), a `Ingestão` recorta automaticamente o `bbox` correspondente no PDF via `pypdfium2` e o anexa como `Ativo Visual` (`origem = formula_recorte`), mantendo o alerta `formula_nao_decodificada`. Assim tanto o `ClassificadorMultimodal` quanto o revisor enxergam a fórmula original sem depender de `CodeFormulaV2`.
- **Rastreabilidade de origem e filtro conservador de margem**:
  - Cada `Ativo Visual` registra `origem` (`picture_docling | formula_recorte | upload_manual`).
  - O filtro determinístico de margem/barcode da `Ingestão` descarta barcodes e logos de cabeçalho/rodapé (registrando apenas estatísticas agregadas nos metadados da `Ingestão`, nunca gerando alerta por questão).

### 3. Catálogo determinístico e ciclo de vida do `Alerta de Extração`

- **Dois níveis de severidade**:
  - **Críticos** *(forçam `revisao_prioritaria = true` enquanto estiverem `aberto`)*:
    1. `formula_nao_decodificada`: presença de `<!-- formula-not-decoded -->`.
    2. `alternativas_incompletas`: número diferente de 5 alternativas `A`–`E` válidas/ordenadas ou alternativa vazia.
    3. `pdf_via_ocr`: `Prova` processada com fallback `force_full_page_ocr=True` (ex.: CMap corrompido do ENADE 2017).
    4. `enunciado_suspeito`: enunciado vazio ou abaixo do limiar mínimo de texto legível.
  - **Informativos** *(exibidos como badge na revisão, sem forçar `revisao_prioritaria` sozinhos)*:
    1. `fonte_symbol_detectada`: página de origem no PDF utiliza fonte `Symbol`/`MT-Extra` (sinalizando risco de letras gregas como `ρ→r` na Q10/2023).
    2. `gabarito_ausente_na_prova`: PDF de `Gabarito` foi enviado na `Ingestão`, mas não trouxe entrada para o `numero` daquela `Questão`.
- **Ciclo de vida `aberto | resolvido`**:
  - Cada `Alerta de Extração` registra `(codigo, severidade, status: aberto | resolvido, mensagem, resolvido_em)`.
  - **Reavaliação automática dos alertas estruturais** (`formula_nao_decodificada`, `alternativas_incompletas`, `enunciado_suspeito`, `gabarito_ausente_na_prova`): ao salvar `PATCH /api/v1/questoes/{id}`, o domínio reavalia essas condições deterministicamente e marca como `resolvido` as que deixaram de ocorrer (ou reabre se uma edição quebrar a invariante).
  - **Confirmação explícita dos alertas de inspeção** (`pdf_via_ocr`, `fonte_symbol_detectada`): ação manual **"Marcar como verificado"** (`PATCH /api/v1/questoes/{id}/alertas/{alerta_id}`) limpa o alerta sem apagar o registro histórico, removendo a questão do filtro *"Com alerta de extração"* (alertas abertos) e de `revisao_prioritaria` quando não restarem alertas críticos abertos.

### 4. Proteção de edições manuais no `Reprocessar Prova`

- `Questão` mantém marcador booleano `editada_manualmente` (ativado em qualquer edição de texto, `Alternativa`s, `Ativo Visual` manual ou resolução de alerta).
- Refinando a regra de reconciliação por `numero` oficial de [Definir fluxos da interface web de ingestão, revisão humana e consulta](./09-fluxos-interface-web-revisao-consulta.md), `POST /api/v1/provas/{id}/reprocessar` adota `sobrescrever_editadas: bool = false` como padrão: preserva intactas as `Questão`s com `editada_manualmente = true` e atualiza apenas as não editadas, exibindo no diálogo de confirmação um checkbox explícito caso o usuário deseje sobrescrever todas.

### 5. Glossário e ADRs

- Refinadas as definições canônicas de **`Ativo Visual`** (incluindo itens anexados na curadoria e fórmulas) e **`Alerta de Extração`** (incluindo resolução após correção/verificação) em [GLOSSARY.md](../../../GLOSSARY.md); nenhum termo novo foi necessário.
- Nenhum ADR em `docs/adr/` foi aberto por se tratarem de políticas de curadoria, parser e endpoints isolados atrás das portas já definidas.
