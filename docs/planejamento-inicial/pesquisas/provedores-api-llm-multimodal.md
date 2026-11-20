# Pesquisa: Provedores e Custos de API de LLM Multimodal para Classificação (v1 e Ponte para Qwen/vLLM)

Data da pesquisa: 2026-11-20  
Contexto: Classificação estruturada (JSON) de ~100 a 300 questões objetivas do ENADE (muitas com imagens, diagramas, circuitos e tabelas), buscando custo zero ou muito baixo na v1 e portabilidade direta para um servidor **Qwen/vLLM** próprio no futuro.

---

## Resumo executivo e recomendação

1. **Melhor ponto de partida para a v1 (custo zero, sem cartão)**: **Google Gemini API (Google AI Studio)** no **Free Tier** com `gemini-3.5-flash-lite` (ou `gemini-2.5-flash` enquanto disponível), usando o endpoint **OpenAI-compatível** (`https://generativelanguage.googleapis.com/v1beta/openai/`). Como as provas do ENADE são documentos públicos oficiais do INEP (sem PII nem conteúdo confidencial), a política de uso de dados do *Unpaid Services* não é bloqueante para a v1.
2. **Melhor opção paga de baixo custo (privacidade garantida e sem limite apertado de free tier)**:
   - **Google Gemini API (Paid Tier)** com `gemini-3.5-flash-lite` (~**US$ 0,44 a US$ 1,20** para 300 questões, *pay-as-you-go* sem recarga mínima pré-paga); ou
   - **OpenAI API** com `gpt-5-mini` (~**US$ 0,36 a US$ 0,98**) ou `gpt-5-nano` (~**US$ 0,07 a US$ 0,20**), exigindo recarga mínima pré-paga de **US$ 5**.
3. **Quando usar Anthropic, OpenRouter ou Groq**:
   - **Anthropic (`Claude Haiku 5.5`)** é muito barato por token (~**US$ 0,11 a US$ 0,30**), mas exige recarga pré-paga (~US$ 5) e não é nativamente OpenAI-compatível.
   - **OpenRouter** é útil como *fallback* único OpenAI-compatível, mas seu free tier sem recarga é limitado a **50 req/dia** (300 questões exigiriam 6 dias; o limite sobe para 1.000 req/dia após US$ 10 acumulados em créditos).
   - **Groq** descontinuou Llama 4 Scout/Maverick em julho de 2026; seu modelo multimodal ativo é `qwen/qwen3.8-27b`, excelente como **ambiente de ensaio remoto** para validar prompts do futuro servidor Qwen/vLLM local, mas o free tier limita a **200k tokens/dia** (quebra um lote de 300 questões em vários dias).
4. **Assinaturas pessoais de CLI (Antigravity CLI / Claude Code)** são **inviáveis** como backend de aplicação por proibição explícita nos Termos de Serviço (com bloqueio técnico e risco de suspensão de conta) e por inadequação arquitetural.
5. **Ponte limpa para Qwen/vLLM**: definir uma porta interna (`ClassificadorMultimodal`) com um único adaptador `ClienteOpenAICompativel` na v1 — trocando entre Gemini AI Studio, OpenAI, OpenRouter, Groq e vLLM/Qwen local apenas por variáveis de ambiente e um perfil mínimo de parâmetros por provedor.

---

## Premissas da estimativa de volume (300 questões do ENADE)

Para comparar provedores na mesma base, adotam-se dois cenários para **300 questões objetivas** (sem depender de *prompt caching* — o que torna os números conservadores):

- **Cenário base (1 passada completa, ~50% das questões com imagem)**:
  - Prompt de sistema + matriz/taxonomia do ENADE + instruções: ~1.200 tokens/chamada.
  - Texto da questão (enunciado + alternativas): ~400 tokens/chamada.
  - Imagem (média de ~800 tokens nas 150 questões com imagem → ~400 tokens na média global).
  - **Total de entrada**: `300 × 2.000` = **0,60 M tokens**.
  - **Total de saída** (JSON estruturado com códigos da matriz, nível cognitivo, justificativa concisa): `300 × 350` = **0,105 M tokens** (~0,25 M se houver *thinking* leve habilitado).
- **Cenário conservador (margem 2,5× para imagens em alta resolução, *thinking* moderado e reclassificações/retries)**:
  - **Total de entrada**: **1,50 M tokens** (~5.000 tokens/questão).
  - **Total de saída**: **0,30 M tokens** (~1.000 tokens/questão).

---

## 1. Google Gemini API (Google AI Studio)

### Modelos multimodais recomendados
- **`gemini-3.5-flash-lite`** (recomendado para novos projetos de alto volume/classificação multimodal) e **`gemini-3.8-flash`** (maior capacidade de raciocínio e leitura densa; recomendado se houver gráficos/circuitos muito complexos). Modelos legados como `gemini-2.5-flash` e `gemini-2.5-flash-lite` ainda aparecem em fluxos existentes, mas a documentação oficial direciona novos projetos à geração 3.5/3.8 ([Gemini API Models](https://ai.google.dev/gemini-api/docs/models)).
- Todos suportam entrada multimodal nativa (texto + imagens/PDFs) e janela de 1M tokens ([Gemini API Models](https://ai.google.dev/gemini-api/docs/models)).

### Limites do Free Tier e política de dados
- **Limites (por projeto Google Cloud, não por API key)**: medidos em **RPM**, **TPM** e **RPD** (reset diário à meia-noite horário do Pacífico). No Free Tier não é exigido cartão de crédito; os limites são dinâmicos por modelo/projeto e consultáveis em tempo real no painel do Google AI Studio ([Gemini API Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits), [AI Studio Rate Limit](https://aistudio.google.com/rate-limit)).
  - Modelos da família **Flash / Flash-Lite** tipicamente oferecem na faixa de **10–15 RPM** e até **~1.500 RPD** (enquanto modelos **Pro** ficam severamente restritos, ~2–5 RPM e ~50 RPD).
  - Na prática, **300 questões** no Free Tier de um modelo Flash rodam em **~25–35 minutos** com *rate limiting* simples no cliente (ex.: 10 req/min).
- **Política de dados (Free vs. Paid)** ([Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms)):
  - **Unpaid Services (Free Tier)**: a Google pode usar prompts, imagens enviadas e respostas — incluindo revisão por anotadores humanos (desvinculados da conta) — para melhorar produtos e treinar modelos. Os termos alertam explicitamente para **não enviar dados sensíveis, confidenciais ou pessoais**. *(Exceção regional: EEE, Suíça e Reino Unido recebem regras de privacidade do Paid Tier mesmo no uso gratuito.)*
  - **Paid Services (billing vinculado no Google Cloud)**: dados **não** são usados para treinamento de modelos (apenas retenção transitória para detecção de abuso/depuração).
  - **Impacto no `enade-questoes`**: provas oficiais do ENADE são domínio público governamental (INEP), sem PII. Logo, o Free Tier é **aceitável para a v1** com provas públicas; se o sistema passar a ingerir provas inéditas/privadas de docentes ou redações de alunos, deve ativar o Paid Tier ou migrar para o Qwen/vLLM local.

### Structured Outputs e contagem de tokens de imagem
- **Structured Outputs**: suporte nativo via decodificação restrita por JSON Schema (`response_mime_type="application/json"` + `response_json_schema` na SDK `google-genai`, ou `response_format` com `json_schema` / Pydantic via endpoint OpenAI-compatível `https://generativelanguage.googleapis.com/v1beta/openai/`) ([Structured Output](https://ai.google.dev/gemini-api/docs/structured-output), [OpenAI Compatibility](https://ai.google.dev/gemini-api/docs/openai)).
- **Contagem de tokens de imagem**: imagens até `384×384` px custam **258 tokens**; maiores são fatiadas em *tiles* de `768×768` px (258 tokens/tile). Nas gerações Gemini 3+, o parâmetro `media_resolution` (`low`, `medium`, `high`) permite controlar o orçamento de tokens por imagem ([Image Understanding](https://ai.google.dev/gemini-api/docs/image-understanding)).

### Preços (Paid Tier) e custo estimado para 300 questões
Fonte: [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing) (Batch API e Context Caching oferecem descontos adicionais de 50% a 90%).

| Modelo | Input (/1M) | Output (/1M)* | Base (300 q.) | Conservador (300 q.) |
|---|---:|---:|---:|---:|
| **Free Tier** (Flash / Flash-Lite) | US$ 0,00 | US$ 0,00 | **US$ 0,00** | **US$ 0,00** |
| `gemini-2.5-flash-lite` (legado) | US$ 0,10 | US$ 0,40 | **US$ 0,10** | **US$ 0,27** |
| `gemini-3.5-flash-lite` / `gemini-2.5-flash` | US$ 0,30 | US$ 2,50 | **US$ 0,44** | **US$ 1,20** |
| `gemini-3.8-flash` (introd. até 31/12/2026) | US$ 0,75 | US$ 3,75 | **US$ 0,84** | **US$ 2,25** |
| `gemini-3.8-flash` (padrão a partir 01/01/2027) | US$ 1,50 | US$ 7,50 | **US$ 1,69** | **US$ 4,50** |

*\*Nota: na família Gemini com raciocínio, tokens de `thinking` são cobrados como output. O Paid Tier opera em modelo pós-pago/pay-as-you-go via Google Cloud Billing, sem exigência de pacote mínimo pré-pago.*

---

## 2. OpenAI API e Anthropic API

### OpenAI API
- **Modelos multimodais custo-benefício**: `gpt-5-nano`, `gpt-5-mini`, `gpt-4.1-nano`, `gpt-4.1-mini` e `gpt-4o-mini` — todos suportam visão nativa (texto + imagem) e **Structured Outputs** estritos via `response_format: {"type": "json_schema", "json_schema": {..., "strict": true}}` ([OpenAI API Pricing](https://openai.com/api/pricing/), [OpenAI Models / Vision](https://platform.openai.com/docs/guides/images-vision)).
- **Contagem de imagem**: modelos compactos/mini recentes (`gpt-4.1-mini`, `gpt-5-mini`) usam grade direta de *patches* de `32×32` px (1 token por patch, redimensionado acima do teto); modelos padrão (`gpt-4o`, `gpt-4.1`) usam 85 tokens base + 170 tokens por *tile* de `512×512` px ([OpenAI Vision](https://platform.openai.com/docs/guides/images-vision)).
- **Recarga mínima e política de dados**: exige compra mínima pré-paga de **US$ 5** para ativar faturamento e desbloquear o Tier 1 ([OpenAI Billing](https://platform.openai.com/settings/organization/billing/overview)). Dados enviados via API **não são usados para treinamento por padrão** (apenas retenção de até 30 dias para monitoramento de abuso) ([OpenAI Enterprise Privacy](https://openai.com/enterprise-privacy)).

| Modelo OpenAI | Input (/1M) | Cached In (/1M) | Output (/1M) | Base (300 q.) | Conservador (300 q.) |
|---|---:|---:|---:|---:|---:|
| `gpt-5-nano` | US$ 0,05 | US$ 0,01 | US$ 0,40 | **US$ 0,07** | **US$ 0,20** |
| `gpt-4.1-nano` | US$ 0,10 | US$ 0,025 | US$ 0,40 | **US$ 0,10** | **US$ 0,27** |
| `gpt-4o-mini` | US$ 0,15 | US$ 0,075 | US$ 0,60 | **US$ 0,15** | **US$ 0,41** |
| `gpt-5-mini` | US$ 0,25 | US$ 0,025 | US$ 2,00 | **US$ 0,36** | **US$ 0,98** |
| `gpt-4.1-mini` | US$ 0,40 | US$ 0,10 | US$ 1,60 | **US$ 0,41** | **US$ 1,08** |

### Anthropic API (Claude)
- **Modelos multimodais**: todos os modelos atuais (`Claude Haiku 5.5`, `Claude Sonnet 5.5`, `Claude Opus 5.5`) suportam visão nativa e **Structured Outputs** garantidos por JSON Schema (`output_config.format` / `json_schema`), sem taxa adicional ([Claude Pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Claude Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)).
- **Contagem de imagem**: aproximadamente `(largura × altura) / 750` tokens (com redimensionamento automático para borda máxima de 1.568 px nos modelos padrão) ([Claude Vision](https://platform.claude.com/docs/en/build-with-claude/vision)).
- **Recarga mínima e compatibilidade**: não há free tier de API; o Claude Console opera por créditos pré-pagos com recarga inicial típica de **US$ 5** ([Claude Console Billing](https://platform.claude.com/settings/billing)). A API Messages é proprietária (não OpenAI-compatível), o que exigiria um adaptador dedicado além do OpenAI-compatível.

| Modelo Anthropic | Input (/1M) | Output (/1M) | Base (300 q.) | Conservador (300 q.) |
|---|---:|---:|---:|---:|
| `Claude Haiku 5.5` (prompts ≤ 100k) | US$ 0,10 | US$ 0,50 | **US$ 0,11** | **US$ 0,30** |
| `Claude Sonnet 5.5` | US$ 2,00 | US$ 10,00 | **US$ 2,25** | **US$ 6,00** |

---

## 3. OpenRouter e Groq (agregadores/endpoints OpenAI-compatíveis)

### OpenRouter (`https://openrouter.ai/api/v1`)
- **Modelos gratuitos (`:free` e `openrouter/free`)**: custam US$ 0/token e o meta-roteador `openrouter/free` filtra automaticamente por visão e *structured outputs* quando presentes no payload ([OpenRouter Free Router](https://openrouter.ai/docs/features/model-routing), [OpenRouter Limits](https://openrouter.ai/docs/api-reference/limits)).
- **Limites práticos críticos**:
  - **20 RPM** globais por conta.
  - **50 RPD** para contas com menos de US$ 10 acumulados em compras de crédito (inviabiliza processar 300 questões no mesmo dia — levaria 6 dias; requisições com erro também podem consumir cota).
  - **1.000 RPD** liberados permanentemente após atingir **US$ 10 acumulados** em compras de crédito (*lifetime*).
  - Modelos `:free` rotacionam sem aviso prévio e muitos exigem permitir coleta/treinamento pelo provedor subjacente (controlável nas preferências de privacidade da conta) ([OpenRouter Privacy](https://openrouter.ai/docs/features/privacy-and-logging)).
- **Uso pago**: repassa o preço de tabela do provedor sem markup por token, cobrando taxa de plataforma de **5,5%** (mínimo ~US$ 0,80) na compra de créditos com cartão ([OpenRouter Credits](https://openrouter.ai/docs/faq)). É uma boa opção secundária para testar múltiplos modelos sob uma única chave, mas pior que o Google AI Studio para iniciar com custo zero.

### Groq (`https://api.groq.com/openai/v1`)
- **Situação atual dos modelos de visão (nov/2026)**: os antigos modelos multimodais `llama-4-scout-17b-16e-instruct` e `llama-4-maverick-17b-128e-instruct` foram **descontinuados e desligados em julho de 2026** ([Groq Deprecations](https://console.groq.com/docs/deprecations)).
- **Modelo multimodal ativo**: **`qwen/qwen3.8-27b`** (preview; US$ 0,80/M input, US$ 4,00/M output; até 3 imagens/req, **2.048 tokens fixos por imagem**, suporte a JSON/tool use e modos *thinking*/*instruct*) ([Groq Vision](https://console.groq.com/docs/vision), [Groq Models](https://console.groq.com/docs/models)).
- **Limite prático no Free Plan**: embora ofereça 30 RPM e 1.000 RPD, o teto de **8.000 TPM e 200.000 TPD** ([Groq Rate Limits](https://console.groq.com/docs/rate-limits)) impede classificar 300 questões num único dia (~600k–1M tokens necessários).
- **Valor estratégico**: por rodar exatamente a família `Qwen3.8-27B` (a mesma usada no servidor vLLM local do laboratório), o Groq pago ou em pequenos lotes gratuitos é útil para **validar previamente prompts e schemas** para o futuro vLLM.

---

## 4. Por que assinaturas pessoais de CLI (Antigravity CLI / Claude Code) não são viáveis como API backend

Usar a assinatura pessoal de agentes de código (Antigravity CLI, Gemini CLI ou Claude Code) para alimentar o backend do `enade-questoes` é bloqueado por **dois planos independentes** — contratual e técnico:

1. **Violação explícita de Termos de Serviço (risco de banimento da conta)**:
   - **Google Antigravity Additional Terms of Service** ([antigravity.google/terms](https://antigravity.google/terms)): declara expressamente que *"usar software, ferramentas ou serviços de terceiros para acessar o Serviço (ex.: usando OAuth do Antigravity) constitui violação deste Contrato"* e sujeita as contas Antigravity e/ou Gemini CLI a **suspensão ou encerramento**.
   - **Gemini CLI Terms** ([geminicli.com](https://geminicli.com)): proíbe reaproveitar o fluxo OAuth da conta pessoal em aplicações/proxies próprios; para integrações programáticas, exige chave da Google AI Studio API ou Vertex AI.
   - **Anthropic Claude Code Legal & Compliance** ([code.claude.com/docs/en/legal-and-compliance](https://code.claude.com/docs/en/legal-and-compliance)): define que credenciais OAuth de planos de assinatura (Free, Pro, Max, Team, Enterprise) destinam-se **exclusivamente** ao uso ordinário nos clientes nativos oficiais (Claude.ai e binário oficial Claude Code), proibindo extrair tokens para backends/wrappers próprios ou intermediar o uso em nome de usuários finais. Backends devem usar API keys do Claude Console (ou Bedrock/Vertex).
2. **Incompatibilidades técnicas e operacionais**:
   - **Bloqueio ativo no servidor**: ambos os provedores detectam uso de tokens OAuth fora dos clientes oficiais, retornando `403 PERMISSION_DENIED` (Google) ou `400/401` (Anthropic).
   - **Fragilidade operacional**: sessões OAuth pessoais expiram e exigem login interativo em navegador; cotas são opacas e compartilhadas com o uso interativo do desenvolvedor; não há SLA nem isolamento para deploy em servidor/CI.
   - **Mesmo invocando a CLI via `subprocess`**: além do risco de violação de uso automatizado/intermediação multiusuário, o binário de agente injeta prompts de sistema voltados a edição de código, não expõe decodificação restrita por `response_format` JSON Schema em nível HTTP, tem latência e consumo de contexto imprevisíveis e acopla a infraestrutura da aplicação à máquina/conta pessoal de um desenvolvedor.

---

## 5. Ponte futura para Qwen/vLLM (padrão de porta independente de provedor)

### Padrões essenciais de abstração entre provedores (nuvem vs Qwen/vLLM)
Para trocar entre **Qwen/vLLM** e provedores em nuvem (como **Gemini** ou **OpenAI**) sem alterar regra de negócio, quatro fronteiras práticas são determinantes:

- **Contrato único (`Protocol`)**: encapsular a chamada estruturada atrás de uma interface que recebe texto + imagens + JSON Schema e retorna `(dados_validados, metadados_chamada)`, normalizando erros de truncamento, violação de schema, vazamento de *thinking* e falha transitória de provedor.
- **Particularidades críticas de vLLM com Qwen3/3.8**:
  1. Enviar `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` — sem isso, modelos Qwen3/3.8 com *thinking* ligado podem consumir todo o orçamento de saída em raciocínio e devolver `content` nulo.
  2. Usar `response_format={"type": "json_schema", "json_schema": {"name": ..., "schema": ..., "strict": True}}` — no vLLM, `guided_json` no topo do payload pode ser ignorado silenciosamente e `json_object` sozinho permite campos inventados.
- **Compatibilidade com Gemini e schemas enxutos**: remover chaves supérfluas como `title` e `$defs`/`$ref` do schema gerado pelo Pydantic (que consomem tokens de entrada ou causam rejeição em alguns endpoints) e **sempre revalidar o JSON localmente** contra o schema estrito.
- **Seleção na *composition root* + rastreabilidade**: selecionar o provedor via variável de ambiente (`LLM_PROVIDER`) e expor uma `identidade` (`provider`, `model`, `base_url`) usada para auditar, compor chaves de cache e versionar resultados.

### Desenho enxuto recomendado para o `enade-questoes`

Como **Google Gemini API** (via `https://generativelanguage.googleapis.com/v1beta/openai/`), **OpenAI**, **OpenRouter**, **Groq** e **vLLM/Qwen** falam todos o protocolo **OpenAI Chat Completions** com `image_url` (base64) e `response_format: {"type": "json_schema", ...}`, a v1 **não precisa da complexidade do LangChain nem de múltiplos SDKs** inicialmente:

1. **Porta de domínio/aplicação (`ClassificadorMultimodal`, `Protocol`)**:
   ```python
   class ClassificadorMultimodal(Protocol):
       @property
       def identidade(self) -> dict[str, str]: ...  # provider, model, base_url

       def classificar_estruturado(
           self,
           *,
           system: str,
           user: str,
           imagens_png: list[bytes],
           schema: dict[str, Any],
           nome_schema: str,
           max_tokens: int = 1024,
       ) -> ResultadoEstruturado: ...
   ```
   - Sempre retornar `dados: dict` (já validado localmente via **Pydantic** após `json.loads`), `uso` (`prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `latencia_s`) e `identidade` (para registrar no banco qual modelo/versão de prompt classificou cada questão).
2. **Adaptador único na v1 (`ClienteOpenAICompativel`)**:
   - Instancia `openai.OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key, timeout=settings.llm_timeout_s)`.
   - Aplica um pequeno **perfil de provedor** (`LLM_PROVIDER`) apenas para diferenças de payload:
     - `gemini_openai`: `base_url` padrão `https://generativelanguage.googleapis.com/v1beta/openai/`, respeitando *rate limit* local (`LLM_MAX_RPM=10` no Free Tier) e *retry* com backoff em `429`.
     - `openai` / `openrouter` / `groq`: `base_url` do respectivo provedor; *retry* em `429`/`5xx`.
     - `vllm_qwen`: `api_key` padrão `"EMPTY"`, `temperature=0`, `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` (ou modo configurável) e `response_format` com `json_schema` + `strict: True`.
   - Mantém **validação local obrigatória com Pydantic** independentemente do provedor (nunca confiar apenas no *structured output* remoto).
3. **Troca 100% por variáveis de ambiente (`.env`)**:
   ```env
   # v1 — Google AI Studio (Free Tier ou Paid Tier)
   LLM_PROVIDER=gemini_openai
   LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
   LLM_API_KEY=<sua_gemini_api_key>
   LLM_MODEL=gemini-3.5-flash-lite
   LLM_MAX_RPM=10

   # Futuro — Servidor próprio Qwen/vLLM (sem alterar código de domínio ou aplicação)
   # LLM_PROVIDER=vllm_qwen
   # LLM_BASE_URL=http://<host-vllm>:8005/v1
   # LLM_API_KEY=EMPTY
   # LLM_MODEL=Qwen/Qwen3.8-27B
   # LLM_MAX_RPM=0
   ```
4. **Extensão opcional sem quebra**: se no futuro a v1/v2 precisar de recursos exclusivos do Gemini não expostos no endpoint OpenAI-compatível (ex.: `media_resolution` granular por imagem ou Context Caching explícito), basta adicionar um segundo adaptador `ClienteGeminiNativo` (`google-genai`) atrás da mesma porta `ClassificadorMultimodal`, registrando `LLM_PROVIDER=gemini_native` na *factory*.

---

## Quadro comparativo consolidado (300 questões multimodais)

| Provedor / Modelo | Visão + JSON Schema | Custo Base / Conserv. (300 q.) | Recarga mínima | Privacidade / Treino | Compatível OpenAI | Veredito para v1 |
|---|---|---:|---|---|---|---|
| **Gemini AI Studio (Free)** (`gemini-3.5-flash-lite`) | Sim | **US$ 0 / US$ 0** | Nenhuma | Pode treinar (OK p/ ENADE público) | Sim | **Recomendado p/ começar** |
| **Gemini AI Studio (Paid)** (`gemini-3.5-flash-lite`) | Sim | US$ 0,44 / US$ 1,20 | Nenhuma (pay-as-you-go) | Não treina | Sim | **Melhor upgrade pago** |
| **OpenAI** (`gpt-5-nano` / `gpt-5-mini`) | Sim | US$ 0,07–0,36 / US$ 0,20–0,98 | US$ 5 pré-pago | Não treina (padrão) | Sim | Excelente alternativa paga |
| **Anthropic** (`Claude Haiku 5.5`) | Sim | US$ 0,11 / US$ 0,30 | ~US$ 5 pré-pago | Não treina (API) | Não | Barato, mas exige adaptador próprio |
| **OpenRouter** (`:free` / pagos) | Parcial (rotativo) | US$ 0 (free) / repasse + 5,5% | US$ 0 (50 RPD) / US$ 10 (1.000 RPD) | Depende do endpoint | Sim | Bom *fallback*, ruim p/ lote free |
| **Groq** (`qwen/qwen3.8-27b`) | Sim (até 3 imgs) | US$ 0 (free, TPD 200k) / ~US$ 0,90–2,40 | Nenhuma (free) | Conforme plano | Sim | Ótimo p/ ensaiar Qwen3.8 |
| **CLIs pessoais** (Antigravity / Claude Code) | — | — | — | Viola ToS | Não | **Descartado** |
| **Qwen/vLLM local** (`Qwen3.8-27B`) | Sim | Custo de GPU local | Infra própria | 100% local | Sim | **Alvo futuro (troca via `.env`)** |

---

## Fontes primárias consultadas

- Google Gemini API — Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Google Gemini API — Models: https://ai.google.dev/gemini-api/docs/models
- Google Gemini API — Rate Limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Google Gemini API — Additional Terms of Service (Unpaid vs Paid Services): https://ai.google.dev/gemini-api/terms
- Google Gemini API — Structured Outputs: https://ai.google.dev/gemini-api/docs/structured-output
- Google Gemini API — OpenAI Compatibility: https://ai.google.dev/gemini-api/docs/openai
- Google Gemini API — Image Understanding (tokens e `media_resolution`): https://ai.google.dev/gemini-api/docs/image-understanding
- OpenAI API — Pricing: https://openai.com/api/pricing/
- OpenAI Platform — Vision & Billing: https://platform.openai.com/docs/guides/images-vision e https://platform.openai.com/settings/organization/billing/overview
- OpenAI Enterprise Privacy (API data usage): https://openai.com/enterprise-privacy
- Anthropic Claude Platform — Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Anthropic Claude Platform — Structured Outputs & Vision: https://platform.claude.com/docs/en/build-with-claude/structured-outputs e https://platform.claude.com/docs/en/build-with-claude/vision
- OpenRouter — Rate Limits, Free Routing & Privacy: https://openrouter.ai/docs/api-reference/limits e https://openrouter.ai/docs/features/privacy-and-logging
- Groq Console — Models, Vision, Rate Limits & Deprecations: https://console.groq.com/docs/vision, https://console.groq.com/docs/rate-limits e https://console.groq.com/docs/deprecations
- Google Antigravity Additional Terms of Service: https://antigravity.google/terms
- Gemini CLI Terms: https://geminicli.com
- Anthropic Claude Code Legal & Compliance: https://code.claude.com/docs/en/legal-and-compliance
