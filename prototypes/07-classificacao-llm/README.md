# Protótipo 07 (Descartável) — Classificação Multimodal, Perfis e Travas Determinísticas

Código descartável para resolver o ticket [Definir estratégia de classificação multimodal, reclassificação e validação](../../docs/planejamento-inicial/decisoes/07-estrategia-classificacao-e-reclassificacao.md).

## O que este protótipo testa

1. **Amostra real (14 questões do ENADE 2023 CE)** extraídas pelo Docling no protótipo 05 (`data/prototype-05/docling_2023/`), incluindo todas as 7 questões com `Ativo Visual` real (circuitos, diagramas, grafos) e 7 questões de fronteira interdisciplinar / código / pegadinha de contexto.
2. **Porta `ClassificadorMultimodal` + `ClienteOpenAICompativel`** com `temperature=0`, JSON Schema estrito sem `$defs`, envio de imagens em base64, throttle local (`LLM_MAX_RPM`), retry com feedback de erro e cache em disco por hash de conteúdo.
3. **Travas determinísticas pós-LLM** (validação contra catálogo ativo, remoção de duplicatas, `secundárias != principal`, máx. 2 secundárias, normalização de `Tópico`s, sinais de baixa confiança e alertas de extração).
4. **Comparação de `Perfil de Classificação` (`v1-ementas` vs `v2-fronteiras`)** na `Taxonomia` oficial de 18 disciplinas do ENADE.
5. **Ablation multimodal (com imagem vs sem imagem)** em Q13, Q23 e Q24 + **teste de estabilidade** (`temperature=0`, segunda passada sem cache).
6. **Reclassificação em segunda `Taxonomia` (`ppc-enxuto-v1`, 9 disciplinas)** e detecção de `Divergência de Reclassificação`.

## Como rodar

```bash
# 1. Dry-run (sem API key): valida parsing das 14 questões, imagens filtradas, hashes de cache e travas determinísticas
cd prototypes/07-classificacao-llm
uv run python run_prototype.py --dry-run

# 2. Execução real com Google Gemini AI Studio (copie .env.example -> .env na raiz e coloque GEMINI_API_KEY)
uv run python run_prototype.py
```

O relatório interativo é gerado em `data/prototype-07/relatorio-classificacao.html` (fora do Git via `.gitignore`).
