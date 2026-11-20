# Avaliar provedores e custos de API de LLM multimodal para classificação

Type: research
Status: resolved
Blocked by: none

## Question

Considerando um volume inicial de ~100 a 300 questões objetivas do ENADE (muitas com imagens/diagramas/tabelas) e a necessidade de saída JSON estruturada com baixo custo ou tier gratuito, quais provedores oficiais de API de LLM multimodal são mais viáveis para a v1 — e como desenhar a integração para manter compatibilidade futura com um servidor **Qwen/vLLM** próprio?

Investigar em fontes primárias (documentação oficial de preços, limites e APIs):
1. **Google Gemini API (Google AI Studio)**: modelos multimodais atuais recomendados, limites do tier gratuito, política de dados no tier gratuito vs pago, custo estimado para 300 questões com imagens e suporte a structured outputs.
2. **OpenAI API** e **Anthropic API**: modelos custo-benefício com visão e structured outputs, custo estimado para 300 questões e exigência de recarga mínima.
3. **OpenRouter** (e/ou Groq/outros agregadores OpenAI-compatíveis): disponibilidade de modelos multimodais gratuitos ou muito baratos e limites práticos.
4. **Incompatibilidade de assinaturas pessoais de CLI** (Antigravity CLI, Claude Code) como API backend de aplicação própria (motivos técnicos e de política/licenciamento).
5. **Ponte futura para Qwen/vLLM**: como padronizar uma porta interna para trocar de provedor apenas por configuração.

## Answer

- **Recomendação para a v1 (custo zero)**: iniciar com **Google Gemini API (Google AI Studio — Free Tier)** usando `gemini-3.5-flash-lite` via endpoint **OpenAI-compatível** (`https://generativelanguage.googleapis.com/v1beta/openai/`). Suporta visão nativa e *structured outputs* (`response_format` com `json_schema`), dispensa cartão de crédito e processa ~300 questões em ~25–35 min respeitando ~10–15 RPM (~1.500 RPD). Como as provas do ENADE são públicas (INEP, sem PII), a política de uso de dados do *Unpaid Services* não bloqueia a v1; caso passem a entrar provas privadas/inéditas, basta ativar o Paid Tier (*pay-as-you-go*, ~US$ 0,44–1,20 para 300 questões, sem treinamento em dados) ou migrar para vLLM local.
- **Alternativas pagas oficiais**: **OpenAI** (`gpt-5-nano` ~US$ 0,07–0,20; `gpt-5-mini` ~US$ 0,36–0,98 para 300 questões, sem treino por padrão, recarga mínima de US$ 5) e **Anthropic** (`Claude Haiku 5.5` ~US$ 0,11–0,30, recarga mínima ~US$ 5, mas protocolo proprietário não OpenAI-compatível).
- **Agregadores OpenAI-compatíveis**: **OpenRouter** (`:free`) limita contas sem recarga a **50 req/dia** (sobe para 1.000/dia após US$ 10 acumulados) e rotaciona modelos gratuitos; **Groq** aposentou Llama 4 Scout/Maverick (jul/2026) e hoje oferece `qwen/qwen3.8-27b` com visão (útil para ensaiar prompts do futuro vLLM, mas o Free Plan limita a 200k tokens/dia).
- **CLIs pessoais descartadas**: reutilizar OAuth/assinatura pessoal do **Antigravity CLI**, **Gemini CLI** ou **Claude Code** como backend de aplicação viola explicitamente os Termos de Serviço de Google e Anthropic (com bloqueio `403`/`401` e risco de suspensão de conta), além de ser operacionalmente frágil.
- **Ponte para Qwen/vLLM**: definir uma porta interna `ClassificadorMultimodal` (com seleção por env na *composition root*) e um único adaptador `ClienteOpenAICompativel` (Pydantic validando localmente) com perfis por `LLM_PROVIDER` — permitindo trocar de `gemini_openai` para `vllm_qwen` (incluindo `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` e `response_format` `json_schema` estrito) apenas alterando `.env`.

[Relatório completo](../pesquisas/provedores-api-llm-multimodal.md)
