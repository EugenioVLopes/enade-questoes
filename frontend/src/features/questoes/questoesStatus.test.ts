import { describe, expect, it } from "vitest";

import type { ItemQuestaoResponse } from "@/api/questoes";
import { getGabaritoLabel, getStatusBadges } from "@/features/questoes/questoesStatus";

function item(over: Partial<ItemQuestaoResponse> = {}): ItemQuestaoResponse {
  return {
    id: "q1",
    prova: { id: "p1", exame: "ENADE", curso: "Computação", ano: 2023 },
    numero: 1,
    trecho: "t",
    situacao_gabarito: "valida",
    editada_manualmente: false,
    alertas_abertos: [],
    revisao_prioritaria: false,
    tem_divergencia_aberta: false,
    usa_disciplina_arquivada: false,
    possui_ativos_visuais: false,
    classificacao: {
      id: "c1",
      origem: "llm",
      status: "aprovada",
      confianca: 0.9,
      revisao_prioritaria: false,
      disciplina_principal: "redes",
      disciplinas_secundarias: [],
      topicos: [],
    },
    ...over,
  } as ItemQuestaoResponse;
}
const labels = (i: ItemQuestaoResponse) => getStatusBadges(i).map((b) => b.label);

describe("getStatusBadges", () => {
  it("aprovada sem sinalizações só tem Aprovada", () => {
    expect(labels(item())).toEqual(["Aprovada"]);
  });
  it("sem classificação é Pendente", () => {
    expect(labels(item({ classificacao: null }))).toEqual(["Pendente"]);
  });
  it("todos os badges na ordem da tarefa", () => {
    const todos = item({
      classificacao: { ...item().classificacao!, status: "pendente_revisao" },
      revisao_prioritaria: true,
      tem_divergencia_aberta: true,
      situacao_gabarito: "anulada",
      usa_disciplina_arquivada: true,
    });
    expect(labels(todos)).toEqual(["Pendente", "Prioritária", "Divergência", "Anulada", "Disciplina arquivada"]);
  });
});

describe("getGabaritoLabel", () => {
  it("traduz situações", () => {
    expect(getGabaritoLabel("valida")).toBe("Gabarito válido");
    expect(getGabaritoLabel("anulada")).toBe("Gabarito anulado");
    expect(getGabaritoLabel("pendente")).toBe("Gabarito pendente");
  });
});
