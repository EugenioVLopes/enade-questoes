# 13 — Edição sob demanda de conteúdo/mídia, conferência do PDF e alertas na Revisão

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Decisões: [tratamento e edição de mídia e casos de borda](../decisoes/10-tratamento-edicao-midia-e-casos-borda.md)

## Contexto

Casos reais das provas do INEP (como `formula-not-decoded` na Q13/2023, alternativas de código coladas na Q15/2023, fonte `Symbol` na Q10/2023 e OCR do ENADE 2017) exigem que o revisor consiga conferir a página original do PDF, corrigir enunciado/alternativas/gabarito, gerenciar `Ativo Visual`s manualmente e confirmar alertas de inspeção diretamente na coluna esquerda da tela de `Revisão`, sem sair da aplicação e sem disparar reclassificação automática indesejada.

## Entrega observável

Modo **"Editar conteúdo"** integrado à coluna esquerda da `Revisão` com editor `Editar / Preview` (Markdown + KaTeX), edição de `Alternativa`s `A`–`E` e `Gabarito` individual, modal/painel da página original do PDF (`pypdfium2`), gestão manual de `Ativo Visual`s, confirmação de alertas de inspeção e CTA explícito **"Reclassificar esta questão"**.

## Escopo e limites

- **Edição inline sob demanda (`frontend/src/features/revisao/edicao/`)**:
  - Botão **"Editar conteúdo"** na coluna esquerda da `Revisão` (leitura permanece como modo padrão).
  - Edição de `enunciado` com alternância **`Editar / Preview`** usando o mesmo renderizador sanitizado Markdown GFM + KaTeX da Tarefa 12.
  - Edição individual de cada `Alternativa` (`A`–`E`, permitindo adicionar/separar alternativas faltantes) e do `Gabarito` da questão (`situacao_gabarito: valida | anulada | pendente` e `alternativa_correta`), salvando via `PATCH /api/v1/questoes/{id}`.
  - Após salvar qualquer alteração de conteúdo ou mídia: atualiza os badges de `Alerta de Extração` reavaliados pelo backend, **não** dispara o LLM automaticamente e exibe banner discreto com botão explícito **"Reclassificar esta questão"** (disparando `Execução de Classificação` individual sob demanda).
- **Conferência da página original do PDF**:
  - Botão **"Ver página original do PDF"** abrindo modal/painel lateral com a imagem renderizada por `GET /api/v1/provas/{id}/paginas/{pagina}/imagem` (com seletor de página quando a `Questão` atravessa mais de uma página, ex.: Q25/2023 p.28–29).
- **Gestão manual de `Ativo Visual`s** (sem crop interativo no canvas do navegador na v1):
  - No modo edição: **upload de novo `Ativo Visual`** (`POST /api/v1/questoes/{id}/ativos-visuais`), **substituição do arquivo**, **reordenação**, **vínculo/desvínculo à `Alternativa` (`A`–`E` ou enunciado)** (`PATCH /api/v1/ativos-visuais/{id}`) e **exclusão** (`DELETE /api/v1/ativos-visuais/{id}`), exibindo badge discreto da `origem` (`picture_docling | formula_recorte | upload_manual`).
- **Ciclo de `Alerta de Extração` de inspeção**:
  - Nos badges de alertas de inspeção abertos (`pdf_via_ocr`, `fonte_symbol_detectada`), oferecer ação explícita **"Marcar como verificado"** (`PATCH /api/v1/questoes/{id}/alertas/{alerta_id}`), atualizando o estado da questão e o indicador de `revisao_prioritaria`.

## Dependências

- [08 — API de Questões, busca textual/trigrama, revisão humana e edição de conteúdo/mídia](08-api-questoes-busca-revisao-edicao-midia.md)
- [12 — Seção Revisão (tela dividida 60/40, fila priorizada, divergências e atalhos)](12-frontend-revisao-humana-e-divergencias.md)

## Critérios de aceite

- [x] Modo "Editar conteúdo" permite editar enunciado (com aba `Preview` Markdown+KaTeX), `Alternativa`s `A`–`E` e `Gabarito` individual, persistindo via `PATCH /api/v1/questoes/{id}` sem disparar chamada automática de classificação.
- [x] Após salvar edição, o banner exibe CTA explícito **"Reclassificar esta questão"** que dispara `POST /api/v1/execucoes-classificacao` para aquela questão quando clicado.
- [x] "Ver página original do PDF" carrega a página correspondente (e permite alternar páginas em questões multipágina).
- [x] Gestão manual de `Ativo Visual` executa upload, substituição, reordenação, vínculo à alternativa e exclusão refletindo imediatamente na galeria.
- [x] "Marcar como verificado" resolve `pdf_via_ocr` / `fonte_symbol_detectada` e atualiza os badges da questão.
- [x] Atalhos de teclado da `Revisão` permanecem desabilitados durante a edição de texto.
- [x] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro.

## Verificação

- Testes Vitest + Testing Library em `frontend/src/features/revisao/edicao/` cobrindo edição + preview, não-disparo automático de LLM, CTA de reclassificação, visualizador multipágina, CRUD de `Ativo Visual` e confirmação de alerta de inspeção.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

**Implementação (orquestrada via `run_workflow`)**:
- **Cliente HTTP e hooks (`frontend/src/api/edicaoQuestao.ts`)**: `urlPaginaProvaImagem`, `editarConteudoQuestao`, `resolverAlertaExtracao`, `adicionarAtivoVisual`, `atualizarAtivoVisual` (garantindo exclusão mútua entre `alternativa_letra` e `remover_alternativa_letra`), `reordenarAtivosVisuais` (sequencial), `removerAtivoVisual` e hooks TanStack Query com atualização do detalhe e invalidação de `queryKeys.questoes.all`.
- **Módulo de edição na Revisão (`frontend/src/features/revisao/edicao/`)**:
  - `editorUtils.ts`: validações de enunciado/alternativas/gabarito (`LIMITE_ENUNCIADO`, `LIMITE_ALTERNATIVA`) e imagem PNG/JPEG (`TAMANHO_MAXIMO_IMAGEM_BYTES`), cálculo determinístico de reordenação (`calcularReordenacaoAtivos`), cache-busting pós-substituição (`urlAtivoComRevisao`) e classificação de alertas de inspeção (`ehAlertaInspecao`).
  - `BadgesAlertaExtracao.tsx`: exibe badges críticos/informativos mantendo compatibilidade com `QuestaoLeitura` e botão **"Marcar como verificado"** exclusivo para `pdf_via_ocr` e `fonte_symbol_detectada`.
  - `VisualizadorPdfPagina.tsx`: painel lateral (`Sheet`) para `GET /api/v1/provas/{id}/paginas/{pagina}/imagem` com seletor multipágina, controle de zoom (150%), link para nova aba e fallback com nova tentativa em erro de carregamento.
  - `BannerReclassificacao.tsx`: aviso discreto pós-edição de conteúdo ou mídia com CTA explícito **"Reclassificar esta questão"** (`incluir_revisadas: true`) sem disparo automático do LLM.
  - `GerenciadorAtivosVisuais.tsx`: upload manual (PNG/JPEG), substituição de arquivo (com revisão de URL), reordenação sequencial, vínculo/desvínculo a `Enunciado` ou `Alternativa` `A`–`E`, exclusão com `AlertDialog` de confirmação e badge de `origem` (`Docling`, `Recorte de fórmula`, `Upload manual`).
  - `EditorConteudoQuestao.tsx`: edição inline de enunciado com abas `Editar / Preview` (`MarkdownContent` sanitizado + KaTeX), `Alternativa`s `A`–`E` (com adição/remoção), `Gabarito` individual e tratamento de conflito HTTP `409` preservando o rascunho digitado com opção **"Recarregar dados atuais"**.
- **Integração (`frontend/src/features/revisao/`)**: `GaleriaAtivos.tsx` (revisões de URL após substituição), `QuestaoLeitura.tsx` (badges com verificação de alertas de inspeção) e `RevisaoPage.tsx` (botões **"Ver página original do PDF"** e **"Editar conteúdo"**, bloqueio de atalhos durante edição/PDF, fixação da questão na URL ao editar/alterar mídia/verificar alerta para evitar troca involuntária da fila no refetch).

**Revisão e correções pós-revisão**:
- Revisão paralela de contratos/requisitos e UX/acessibilidade/testes apontou perda de foco da questão quando `RevisaoPage` era aberta sem `?questao=` na URL após refetch de edição/verificação; corrigido em `RevisaoPage.tsx` com `fixarQuestao` e limpeza ao trocar busca da URL, além de 4 testes de regressão adicionados em `EdicaoConteudoMidia.test.tsx`.

**Verificação executada**:
- `frontend/`: `pnpm type-check`, `pnpm lint`, `pnpm build` (exit 0) e `pnpm test` (exit 0 — 15 arquivos, 175 testes passando, incluindo 17 em `editorUtils.test.ts`, 12 em `EdicaoConteudoMidia.test.tsx` e 35 em `RevisaoPage.test.tsx`).

**Pendências registradas**:
- Validação manual no navegador contra o backend real fica para a Tarefa 15.
- Melhorias menores não bloqueantes anotadas pela revisão: feedback explícito no banner se `usePerfisClassificacaoQuery` falhar (`isError`), passagem de `exigirAlternativa` por tipo discursivo em `EditorConteudoQuestao.tsx`, atributos `aria-controls`/`role="tabpanel"` nas abas `Editar / Preview`, capitalização uniforme de `Alternativa` em alguns rótulos e remoção do subtítulo redundante em `GerenciadorAtivosVisuais.tsx`.
