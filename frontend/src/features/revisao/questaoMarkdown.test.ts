import { describe, expect, it } from "vitest";

import type { DetalheQuestaoResponse } from "@/api/revisao";
import { montarQuestaoMarkdown } from "@/features/revisao/questaoMarkdown";

const base = {
  numero: 7,
  prova: { id: "p", exame: "ENADE", curso: "Computação", ano: 2023 },
  enunciado: "Qual o custo de $O(n)$?",
  alternativas: [
    { letra: "A", texto: "Linear" },
    { letra: "B", texto: "Constante" },
  ],
  gabarito: { situacao_gabarito: "valida", alternativa_correta: "A" },
} as DetalheQuestaoResponse;

describe("montarQuestaoMarkdown", () => {
  it("monta cabeçalho, enunciado, alternativas e gabarito", () => {
    expect(montarQuestaoMarkdown(base)).toBe(
      "## Questão 7 — ENADE Computação 2023\n\nQual o custo de $O(n)$?\n\n**A)** Linear\n\n**B)** Constante\n\nGabarito: A",
    );
  });

  it("ANULADA e pendente", () => {
    expect(montarQuestaoMarkdown({ ...base, gabarito: { situacao_gabarito: "anulada" } })).toMatch(/Gabarito: ANULADA$/);
    expect(montarQuestaoMarkdown({ ...base, gabarito: { situacao_gabarito: "pendente" } })).toMatch(/Gabarito: pendente$/);
  });
});
