Implementar a Tarefa 02 do Enade Questões (`docs/planejamento-inicial/tarefas/02-nucleo-dominio-regras-deterministicas.md`): o núcleo de domínio puro em `backend/src/domain/`, as regras determinísticas de negócio, o calculador de métricas e as portas (`Protocol`) em `backend/src/application/ports/`, totalmente cobertos por testes unitários puros em `backend/tests/unit/`, além da atualização de status e evidências no documento da tarefa.

Integrity mode: development

Material de referência:
- `docs/planejamento-inicial/tarefas/02-nucleo-dominio-regras-deterministicas.md`
- `GLOSSARY.md`
- `docs/planejamento-inicial/decisoes/06-modelo-de-dominio-e-glossario.md`
- `docs/planejamento-inicial/decisoes/07-estrategia-classificacao-e-reclassificacao.md`
- `docs/planejamento-inicial/decisoes/10-tratamento-edicao-midia-e-casos-borda.md`
- `docs/planejamento-inicial/decisoes/11-metricas-qualidade-e-conjunto-ouro.md`

## Requirements

### R1. Entidades e Value Objects de domínio (`backend/src/domain/`)
Implementar as entidades, enums e value objects em `backend/src/domain/` aderentes aos 16 termos canônicos de `GLOSSARY.md`, livres de frameworks e I/O:
- Conteúdo de Prova: `Prova` (unicidade `(exame, curso, ano)`), `Ingestão` (status `pendente | processando | concluida | erro | interrompida`), `Questão` (`numero`, `componente`, `tipo`, `enunciado`, `paginas`, `editada_manualmente`), `Alternativa` (`A`–`E`), `AtivoVisual` (`origem: picture_docling | formula_recorte | upload_manual`, vínculo opcional à `Alternativa`, `ordem`, `pagina`, `bbox`), `Gabarito` (`situacao_gabarito: valida | anulada | pendente`, `alternativa_correta`), `AlertaExtracao` (`codigo`, `severidade: critico | informativo`, `status: aberto | resolvido`, `mensagem`, `resolvido_em`).
- Taxonomia Curricular: `Taxonomia`, `Disciplina` (`codigo`, `nome`, `ementa`, `ativa`), `Tópico`.
- Classificação e Revisão: `PerfilClassificacao` (`codigo`, `versao`, `diretrizes_gerais`, `guia_fronteiras`, `template_prompt`), `ExecucaoClassificacao` (snapshot congelado + status + métricas), `Classificacao` (`1` principal + `0..2` secundárias + `topicos` + `justificativa` + `confianca` + `origem: automatica | humana` + `status: pendente_revisao | aprovada` + `vigente` + `revisao_prioritaria`), `DivergenciaReclassificacao`.
- Avaliação offline: `ConjuntoOuro` (chave natural `(exame, curso, ano, numero)`) e `AvaliacaoClassificacao`.

### R2. Regras determinísticas puras de negócio
Implementar as regras determinísticas puras em `backend/src/domain/`:
- Faixa padrão do Componente Específico por edição (`2014–2019: 09–35`, `2023: 10–38`, `2026+: 16–45`, com override explícito; tratamento de anos fora dessas faixas sem override explícito fica a critério da equipe).
- Avaliador determinístico dos 6 `AlertaExtracao` (4 críticos: `formula_nao_decodificada`, `alternativas_incompletas`, `pdf_via_ocr`, `enunciado_suspeito`; 2 informativos: `fonte_symbol_detectada`, `gabarito_ausente_na_prova`) e reavaliação automática dos 4 estruturais (`formula_nao_decodificada`, `alternativas_incompletas`, `enunciado_suspeito`, `gabarito_ausente_na_prova`) após edição de conteúdo, mantendo alertas de inspeção (`pdf_via_ocr`, `fonte_symbol_detectada`) até verificação explícita (o limiar mínimo de texto legível para `enunciado_suspeito` fica a critério da equipe).
- Travas pós-LLM: rejeitar `disciplina_principal` fora do catálogo ativo (sinalizando elegibilidade a 1 retry corretivo); sanear `disciplinas_secundarias` (remover duplicatas, igual à principal, slugs fora do catálogo e limitar a 2, marcando alerta/`revisao_prioritaria`); normalizar `Tópico`s em `kebab-case` ASCII curto (1–4 itens, até 32 chars sem cortar palavras); calcular `revisao_prioritaria` (qualquer `AlertaExtracao` crítico aberto OU saneamento de trava OU `confianca < 0.75`).
- Critério de `DivergenciaReclassificacao`: comparar exclusivamente `(disciplina_principal, set(disciplinas_secundarias))`, ignorando variações de justificativa, confiança e `Tópico`s.
- Política de Reprocessar `Prova`: preservar `Questão`s com `editada_manualmente = true` quando `sobrescrever_editadas = false`.
- Calculador determinístico das 3 camadas de métricas de `AvaliacaoClassificacao` (acurácia principal, Macro-F1 principal, Jaccard/F1 secundárias com `∅ == ∅ → 1.0`, exact match, matriz de confusão, validade 1ª tentativa, erro em alta confiança `>= 0.85`) e avaliador de gate (`baseline` vs `candidato`, padrão e `--modo-migracao`).

### R3. Portas (`Protocol`) na camada de aplicação (`backend/src/application/ports/`)
Definir os contratos (`Protocol`) em `backend/src/application/ports/`: `ExtratorProva`, `ExtratorGabarito`, `RenderizadorPaginaPdf`, `ClassificadorMultimodal`, `ArmazenamentoArquivos` e repositórios de domínio.

### R4. Escopo, limites e registro de conclusão da tarefa
- Fora de escopo: SQLAlchemy, migrations Alembic, FastAPI/endpoints HTTP, Docling, `pdfplumber`, `pypdfium2` ou chamadas HTTP/LLM reais.
- Ao concluir, atualizar `docs/planejamento-inicial/tarefas/02-nucleo-dominio-regras-deterministicas.md` com `Status: concluida`, critérios de aceite marcados e a seção `## Evidências e pendências` preenchida com as verificações executadas (seguindo o padrão da Tarefa 01).

## Verification Resources
- Especificações e decisões em `docs/planejamento-inicial/` (`GLOSSARY.md`, `plano.md`, `decisoes/06-*`, `07-*`, `10-*`, `11-*`) e protótipos de referência em `prototypes/05-extracao-pdf/` e `prototypes/07-classificacao-llm/`.
- Verificações automatizadas do backend em `backend/`: `uv run lint-imports`, `uv run ruff check .` e `uv run pytest tests/unit/`.

## Acceptance Criteria

### Isolamento arquitetural e qualidade de código
- [ ] `uv run lint-imports` passa com exit code 0 confirmando zero dependências externas ou de camadas superiores em `backend/src/domain/`.
- [ ] `uv run ruff check .` passa sem erros.

### Regras determinísticas e cobertura de testes unitários
- [ ] Travas pós-LLM rejeitam principal inválida, saneiam secundárias (duplicatas, igual à principal, slug fantasma, > 2 itens), normalizam `Tópico`s e acionam `revisao_prioritaria` mesmo com `confianca = 0.99` quando houver `Alerta de Extração` crítico aberto.
- [ ] Reavaliação de `Alerta de Extração` fecha automaticamente alertas estruturais corrigidos (`formula_nao_decodificada`, `alternativas_incompletas`, `enunciado_suspeito`, `gabarito_ausente_na_prova`) e mantém alertas de inspeção (`pdf_via_ocr`, `fonte_symbol_detectada`) até verificação explícita.
- [ ] Critério de `Divergência de Reclassificação` abre divergência apenas quando mudam `disciplina_principal` ou `set(disciplinas_secundarias)`.
- [ ] Calculador de métricas e gate de regressão cobrem casos de borda (`∅ == ∅ → 1.0` em secundárias, disciplinas raras no Macro-F1, piso estrutural `100%/95%` e modo migração).
- [ ] `uv run pytest tests/unit/` passa integralmente cobrindo entidades, regras determinísticas, portas e calculador de métricas sem I/O externo.

### Registro documental
- [ ] `docs/planejamento-inicial/tarefas/02-nucleo-dominio-regras-deterministicas.md` atualizado com `Status: concluida`, checklist marcado e `## Evidências e pendências` com as saídas reais das verificações.
