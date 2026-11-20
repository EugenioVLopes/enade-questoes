# 13 — Edição sob demanda de conteúdo/mídia, conferência do PDF e alertas na Revisão

Status: `pendente`

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

- [ ] Modo "Editar conteúdo" permite editar enunciado (com aba `Preview` Markdown+KaTeX), `Alternativa`s `A`–`E` e `Gabarito` individual, persistindo via `PATCH /api/v1/questoes/{id}` sem disparar chamada automática de classificação.
- [ ] Após salvar edição, o banner exibe CTA explícito **"Reclassificar esta questão"** que dispara `POST /api/v1/execucoes-classificacao` para aquela questão quando clicado.
- [ ] "Ver página original do PDF" carrega a página correspondente (e permite alternar páginas em questões multipágina).
- [ ] Gestão manual de `Ativo Visual` executa upload, substituição, reordenação, vínculo à alternativa e exclusão refletindo imediatamente na galeria.
- [ ] "Marcar como verificado" resolve `pdf_via_ocr` / `fonte_symbol_detectada` e atualiza os badges da questão.
- [ ] Atalhos de teclado da `Revisão` permanecem desabilitados durante a edição de texto.
- [ ] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro.

## Verificação

- Testes Vitest + Testing Library em `frontend/src/features/revisao/edicao/` cobrindo edição + preview, não-disparo automático de LLM, CTA de reclassificação, visualizador multipágina, CRUD de `Ativo Visual` e confirmação de alerta de inspeção.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

Pendente de execução.
