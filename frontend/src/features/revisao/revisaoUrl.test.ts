import { describe, expect, it } from "vitest";

import { comAba, comQuestao, paramsDaFila, parseRevisaoUrl } from "@/features/revisao/revisaoUrl";

const TAX = "22222222-2222-2222-2222-222222222222";
const sp = (q: string) => new URLSearchParams(q);

describe("parseRevisaoUrl", () => {
  it("sem modo vale o modo abas com aba padrão pendentes", () => {
    expect(parseRevisaoUrl(sp(`taxonomia=${TAX}`))).toEqual({ modo: { tipo: "abas", aba: "pendentes" }, questaoId: null });
  });

  it("aba inválida cai em pendentes e aba válida é respeitada", () => {
    expect(parseRevisaoUrl(sp("aba=xyz")).modo).toEqual({ tipo: "abas", aba: "pendentes" });
    expect(parseRevisaoUrl(sp("aba=divergencias&questao=q1"))).toEqual({
      modo: { tipo: "abas", aba: "divergencias" },
      questaoId: "q1",
    });
  });

  it("modo=recorte lê os filtros de questões (e ignora aba)", () => {
    const estado = parseRevisaoUrl(sp("modo=recorte&aba=divergencias&q=ospf&com_divergencia=true&questao=q2"));
    expect(estado.modo.tipo).toBe("recorte");
    if (estado.modo.tipo === "recorte") {
      expect(estado.modo.filtros.q).toBe("ospf");
      expect(estado.modo.filtros.com_divergencia).toBe(true);
    }
    expect(estado.questaoId).toBe("q2");
  });
});

describe("paramsDaFila", () => {
  it("Pendentes: status_revisao=pendente e fila_revisao", () => {
    expect(paramsDaFila({ tipo: "abas", aba: "pendentes" }, TAX)).toEqual({
      taxonomia_id: TAX,
      tamanho_pagina: 200,
      status_revisao: "pendente",
      ordenacao: "fila_revisao",
    });
  });

  it("Divergências e Disciplina arquivada usam consulta", () => {
    expect(paramsDaFila({ tipo: "abas", aba: "divergencias" }, TAX)).toMatchObject({ com_divergencia: true, ordenacao: "consulta" });
    expect(paramsDaFila({ tipo: "abas", aba: "disciplina_arquivada" }, TAX)).toMatchObject({
      usa_disciplina_arquivada: true,
      ordenacao: "consulta",
    });
  });

  it("recorte usa os filtros com 200 por página e sem pagina", () => {
    const estado = parseRevisaoUrl(sp("modo=recorte&q=ospf&pagina=3"));
    const params = paramsDaFila(estado.modo, TAX);
    expect(params).toMatchObject({ q: "ospf", tamanho_pagina: 200, ordenacao: "consulta", taxonomia_id: TAX });
    expect("pagina" in params).toBe(false);
  });
});

describe("navegação na URL", () => {
  it("comQuestao preserva o resto; null remove", () => {
    expect(comQuestao(sp("modo=recorte&q=a"), "x").toString()).toBe("modo=recorte&q=a&questao=x");
    expect(comQuestao(sp("aba=divergencias&questao=x"), null).toString()).toBe("aba=divergencias");
  });

  it("comAba sai do recorte e preserva só a Taxonomia", () => {
    expect(comAba(sp(`taxonomia=${TAX}&modo=recorte&q=a&questao=x`), "divergencias").toString()).toBe(
      `taxonomia=${TAX}&aba=divergencias`,
    );
  });
});
