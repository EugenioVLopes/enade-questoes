# Definir estratégia de classificação multimodal, reclassificação e validação

Type: prototype
Status: resolved
Blocked by: 04, 05, 06

## Question

Combinando o provedor escolhido a partir de [Avaliar provedores e custos de API de LLM multimodal para classificação](./04-avaliar-provedores-api-llm.md), uma amostra real de 10 a 15 questões extraídas em [Prototipar extração em uma prova real do ENADE (Docling vs alternativa)](./05-prototipar-extracao-prova-real.md) e o modelo definido em [Definir modelo de domínio extensível e glossário (GLOSSARY.md)](./06-modelo-de-dominio-e-glossario.md):

1. Qual contrato de entrada/saída estruturada (prompt versionado, JSON Schema, envio de imagens da questão, `temperature=0`, cache de resposta) produz classificações consistentes em 1 disciplina principal + secundárias opcionais com justificativa?
2. Como modelar regras/perfis de classificação versionados para permitir reclassificar um lote sob outra grade ou regra de negócio?
3. Quais modos de falha práticos aparecem na amostra real (ex.: questões interdisciplinares, figuras essenciais ao enunciado, alucinação de disciplina fora do catálogo) e quais travas determinísticas devemos impor?

## Answer

### Decisão aprovada

Adotar a porta única `ClassificadorMultimodal` com adaptador `ClienteOpenAICompativel`, contrato JSON Schema plano com `enum` dinâmico derivado da `Taxonomia` ativa, envio obrigatório de todos os `Ativo Visual` filtrados da questão, `temperature=0`, orçamento `max_tokens >= 4096` com controle de *thinking/reasoning* por provedor, cache determinístico por hash de conteúdo e camada de travas determinísticas pós-LLM com sinalização de `revisao_prioritaria`.

### 1. Contrato de entrada/saída estruturada, multimodalidade e cache

- **Porta e adaptador único (`ClassificadorMultimodal` + `ClienteOpenAICompativel`)**: protocolo OpenAI Chat Completions (`openai.OpenAI(base_url, api_key)`), validado na prática trocando de provedor 100% via `.env` (rodando via OpenRouter com `particle-ai/particle-1:free` no protótipo e pronto para Gemini AI Studio ou futuro `vllm_qwen`).
- **JSON Schema plano e portátil**: gerado dinamicamente a partir das `Disciplina`s **ativas** da `Taxonomia`, sem `$defs`/`$ref` nem `title`, contendo `disciplina_principal` (`enum`), `disciplinas_secundarias` (array `enum`, `maxItems: 2`), `topicos` (array 1–4 slugs curtos em `kebab-case` sem acentos), `justificativa` (2–4 frases técnicas) e `confianca` (`0.0..1.0`). Degradação controlada em caso de endpoint incompatível: `json_schema` (strict) → `json_object` → JSON via prompt, sempre com validação local via Pydantic.
- **Envio multimodal obrigatório**: todos os `Ativo Visual` reais da `Questão` (já filtrados de barcodes/logos) são anexados como `image_url` PNG em base64 na mensagem do usuário. O protótipo comprovou que o custo adicional é baixo (~202–244 tokens/imagem) e evita perda de informação técnica essencial (na Q24, omitir o esquema elétrico fez o modelo perder a disciplina secundária `circuitos-e-eletronica`; na Q23, reduziu confiança de `0,96` para `0,82` e eliminou a leitura da topologia RC).
- **Determinismo e controle de *reasoning***: `temperature=0`, `max_tokens >= 4096` e perfil por provedor (`extra_body={"chat_template_kwargs": {"enable_thinking": False}}` para `vllm_qwen`; `extra_body={"reasoning": {"effort": "low"}}` para modelos *reasoning* em OpenRouter/nuvem).
- **Cache determinístico e resiliência de lote**:
  - Chave de cache: `sha256(identidade_provedor_modelo + snapshot_taxonomia + snapshot_perfil + prompt_usuario + sha256_imagens + schema)`.
  - Controle de taxa local (`LLM_MAX_RPM`) + backoff exponencial em `HTTP 429/5xx` (absorveu 11 respostas `429` no protótipo com 100% de conclusão).

### 2. Modelagem de `Perfil de Classificação` e reclassificação multi-taxonomia

- **`Perfil de Classificação` versionado**: composto por `(codigo, versao, diretrizes_gerais, guia_fronteiras, template_prompt)`. Ao criar uma `Execução de Classificação`, o sistema congela o snapshot completo da `Taxonomia` ativa (disciplinas + ementas) e do `Perfil de Classificação` aplicados.
- **Efeito validado do guia de fronteiras**: o perfil `v2-fronteiras` (ementas + guia editorial de 14 fronteiras + regra anti-distrator de contexto) manteve 14/14 de concordância na disciplina principal contra `v1-ementas` e reduziu ruído de disciplinas secundárias em 3/14 questões (Q11 OSPF e Q35 TCP/UDP deixaram de anexar secundária de contexto; Q32 alinhou secundária de Grafos para Algoritmos).
- **Multi-taxonomia sem acoplamento**: a mesma porta reclassificou 14/14 questões sob uma segunda `Taxonomia` simulada (`ppc-enxuto-v1`, 9 núcleos) com 0 alterações de código e 0 slugs fora do catálogo — inclusive refletindo legitimamente a diferença de recorte curricular (ex.: Q16 em `sistemas-digitais-e-embarcados` no ENADE vs `ppc-programacao-ed` no PPC).

### 3. Modos de falha empíricos e travas determinísticas obrigatórias

1. **Consumo total de `max_tokens` por *thinking* oculto** *(descoberto no smoke test com `max_tokens=1024`, que gerou 3 respostas com `content=""`)* → exigir `max_tokens >= 4096`, limitar/desligar *thinking* por provedor e tratar `content` vazio como erro elegível a retry.
2. **Superconfiança sistemática do LLM (`0,90–0,99`)** *(mesmo em Q13 com `formula_nao_decodificada` e alternativas ausentes, o modelo retornou `0,96`)* → `revisao_prioritaria` nunca depende só de `confianca < 0.75`; dispara deterministicamente sempre que a `Questão` tiver `Alerta de Extração` crítico (`formula_nao_decodificada`, `alternativas_incompletas`, `pdf_via_ocr`) ou qualquer saneamento de trava.
3. **Alucinação ou inconsistência estrutural** *(validada em 3 cenários sintéticos)* → validação pós-LLM em Python/Pydantic:
   - `disciplina_principal` fora do catálogo ativo → rejeição + **1 retry corretivo** com mensagem explícita do erro (falhando novamente, marca erro na execução sem gravar classificação inválida).
   - `disciplinas_secundarias`: remover duplicatas, remover igual à principal, descartar slugs fora do catálogo (registrando alerta e ativando `revisao_prioritaria`) e limitar a no máximo 2.
4. **Variância de `Tópico`s livres e tamanho excessivo** *(estabilidade 3/3 em `temperature=0` para disciplinas, mas variação textual nos tópicos e tópicos > 48 chars no PPC)* → confirma que `Divergência de Reclassificação` compara **apenas** `(disciplina_principal, set(disciplinas_secundarias))`; normalizar tópicos em `kebab-case` ASCII curto (1–3 palavras, até 32 chars, sem cortar palavras ao meio).

### Evidências medidas no protótipo descartável

Protótipo executável em [prototypes/07-classificacao-llm/run_prototype.py](../../../prototypes/07-classificacao-llm/run_prototype.py), com painel HTML interativo em `data/prototype-07/relatorio-classificacao.html` e métricas em `data/prototype-07/summary.json` (ambos fora do Git via `.gitignore`):

| Experimento (14 questões reais ENADE 2023 CE, 7 com `Ativo Visual`) | Resultado medido (`particle-ai/particle-1:free`, custo US$ 0,00) |
| --- | --- |
| **Execução total** (`v1`, `v2`, `PPC`, ablação, estabilidade) | **48 / 48** válidas em `json_schema` estrito (121.691 prompt / 37.155 saída · média `6,94 s/chamada`) |
| **Aderência ao catálogo (18 ENADE + 9 PPC)** | **48 / 48 (100%)** sem slugs fora do catálogo |
| **Concordância `v1-ementas` × `v2-fronteiras`** | **14 / 14** na principal; **3 / 14** divergências nas secundárias (Q11, Q32, Q35) |
| **Ablação multimodal (com vs sem imagem em Q13, Q23, Q24)** | **1 / 3** mudou classificação (Q24 perdeu secundária `circuitos-e-eletronica`); custo da imagem `+202` a `+244` tokens |
| **Estabilidade `temperature=0` (2ª passada sem cache em Q11, Q23, Q28)** | **3 / 3 (100%)** idênticas em `(principal, secundárias)` |
| **Travas determinísticas (testes sintéticos de falha)** | **3 / 3** aprovados (alucinação principal → retry; secundária duplicada/fantasma/>2 → saneada; baixa confiança + alerta → prioritária) |
