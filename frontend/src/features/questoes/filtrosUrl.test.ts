import { describe, expect, it } from "vitest";

import {
  aplicarFiltros,
  buildRevisaoRecorteHref,
  contarMaisFiltrosAtivos,
  filtrosParaApi,
  limparFiltros,
  limparFiltrosDaTaxonomia,
  parseFiltros,
} from "@/features/questoes/filtrosUrl";

const TAX = "22222222-2222-2222-2222-222222222222";
const DISC = "66666666-6666-6666-6666-666666666666";
const sp = (s: string) => new URLSearchParams(s);

describe("parseFiltros", () => {
  it("usa padrões quando a URL só tem a taxonomia", () => {
    const f = parseFiltros(sp(`taxonomia=${TAX}`));
    expect(f.somentePrincipal).toBe(false);
    expect(f.pagina).toBe(1);
    expect(f.q).toBeUndefined();
    expect(f.com_divergencia).toBe(false);
  });

  // G1
  it("ignora pagina acima do limite do backend e valores gigantes", () => {
    expect(parseFiltros(sp("pagina=100000")).pagina).toBe(100000);
    expect(parseFiltros(sp("pagina=100001")).pagina).toBe(1);
    expect(parseFiltros(sp("pagina=99999999999999999999")).pagina).toBe(1);
  });

  it("ignora valores inválidos", () => {
    const f = parseFiltros(
      sp("status_revisao=xyz&situacao_gabarito=foo&ano=abc&pagina=0&q=%20%20&com_divergencia=1"),
    );
    expect(f.status_revisao).toBeUndefined();
    expect(f.situacao_gabarito).toBeUndefined();
    expect(f.ano).toBeUndefined();
    expect(f.pagina).toBe(1);
    expect(f.q).toBeUndefined();
    expect(f.com_divergencia).toBe(false);
  });

  it("lê somente principal e filtros válidos", () => {
    const f = parseFiltros(sp(`disciplina_id=${DISC}&incluir_secundarias=false&ano=2023&status_revisao=aprovada&pagina=3`));
    expect(f.somentePrincipal).toBe(true);
    expect(f.ano).toBe(2023);
    expect(f.status_revisao).toBe("aprovada");
    expect(f.pagina).toBe(3);
  });
});

describe("filtrosParaApi", () => {
  it("envia incluir_secundarias=true por padrão e false com Somente principal", () => {
    expect(filtrosParaApi(parseFiltros(sp("")), TAX).incluir_secundarias).toBe(true);
    expect(filtrosParaApi(parseFiltros(sp(`disciplina_id=${DISC}&incluir_secundarias=false`)), TAX).incluir_secundarias).toBe(false);
  });

  it("não envia flags desligadas e mapeia os demais campos", () => {
    const api = filtrosParaApi(
      parseFiltros(sp("q=ospf&com_divergencia=true&topico=roteamento&ano=2023&pagina=2")),
      TAX,
      20,
    );
    expect(api).toMatchObject({
      taxonomia_id: TAX,
      ordenacao: "consulta",
      q: "ospf",
      com_divergencia: true,
      topico: "roteamento",
      ano: 2023,
      pagina: 2,
      tamanho_pagina: 20,
    });
    expect(api.com_alerta_extracao).toBeUndefined();
    expect(api.revisao_prioritaria).toBeUndefined();
    expect(api.usa_disciplina_arquivada).toBeUndefined();
  });
});

describe("contarMaisFiltrosAtivos", () => {
  it("conta tópico, situação e flags ligadas", () => {
    expect(contarMaisFiltrosAtivos(parseFiltros(sp("")))).toBe(0);
    expect(
      contarMaisFiltrosAtivos(parseFiltros(sp("topico=a&situacao_gabarito=anulada&com_alerta_extracao=true&q=x"))),
    ).toBe(3);
  });
});

describe("aplicarFiltros e limparFiltros", () => {
  it("volta para a página 1 e preserva os demais params", () => {
    const next = aplicarFiltros(sp(`taxonomia=${TAX}&pagina=4&q=a`), { status_revisao: "aprovada" });
    expect(next.get("pagina")).toBeNull();
    expect(next.get("q")).toBe("a");
    expect(next.get("taxonomia")).toBe(TAX);
    expect(next.get("status_revisao")).toBe("aprovada");
  });

  it("flag desligada remove o param e Somente principal alterna incluir_secundarias", () => {
    const ligado = aplicarFiltros(sp("com_divergencia=true"), { com_divergencia: false, somentePrincipal: true });
    expect(ligado.has("com_divergencia")).toBe(false);
    expect(ligado.get("incluir_secundarias")).toBe("false");
    expect(aplicarFiltros(ligado, { somentePrincipal: false }).has("incluir_secundarias")).toBe(false);
  });

  it("limparFiltros mantém só a taxonomia", () => {
    expect(limparFiltros(sp(`taxonomia=${TAX}&q=a&pagina=2`)).toString()).toBe(`taxonomia=${TAX}`);
  });
});

describe("buildRevisaoRecorteHref", () => {
  it("preserva o recorte sem pagina e acrescenta questao", () => {
    const search = sp(`taxonomia=${TAX}&pagina=3&q=ospf&disciplina_id=${DISC}&incluir_secundarias=false&com_divergencia=true`);
    expect(buildRevisaoRecorteHref(search)).toBe(
      `/revisao?taxonomia=${TAX}&modo=recorte&q=ospf&disciplina_id=${DISC}&incluir_secundarias=false&com_divergencia=true`,
    );
    expect(buildRevisaoRecorteHref(search, "abc")).toBe(
      `/revisao?taxonomia=${TAX}&modo=recorte&q=ospf&disciplina_id=${DISC}&incluir_secundarias=false&com_divergencia=true&questao=abc`,
    );
  });
});

describe("modo=recorte", () => {
  it("o marcador vem sempre, mesmo sem Taxonomia nem filtros", () => {
    expect(buildRevisaoRecorteHref(sp(""))).toBe("/revisao?modo=recorte");
  });
});

describe("achados do gate r1", () => {
  it("F2: ignora ano fora de 1900-2100 e ids que não são UUID", () => {
    const f = parseFiltros(sp("ano=3000&disciplina_id=abc&prova_id=123"));
    expect(f.ano).toBeUndefined();
    expect(f.disciplina_id).toBeUndefined();
    expect(f.prova_id).toBeUndefined();
    expect(parseFiltros(sp("ano=1899")).ano).toBeUndefined();
    const valido = parseFiltros(sp(`ano=2100&disciplina_id=${DISC}&prova_id=${DISC}`));
    expect(valido.ano).toBe(2100);
    expect(valido.disciplina_id).toBe(DISC);
    expect(valido.prova_id).toBe(DISC);
  });

  it("F3: incluir_secundarias=false sem Disciplina é ignorado em parse, API, contagem e href", () => {
    const search = sp(`taxonomia=${TAX}&incluir_secundarias=false`);
    expect(parseFiltros(search).somentePrincipal).toBe(false);
    expect(filtrosParaApi(parseFiltros(search), TAX).incluir_secundarias).toBe(true);
    expect(buildRevisaoRecorteHref(search)).toBe(`/revisao?taxonomia=${TAX}&modo=recorte`);
  });

  it("F3: remover a Disciplina ou trocar a Taxonomia limpa incluir_secundarias", () => {
    const base = sp(`disciplina_id=${DISC}&incluir_secundarias=false`);
    expect(aplicarFiltros(base, { disciplina_id: undefined }).has("incluir_secundarias")).toBe(false);
    expect(limparFiltrosDaTaxonomia(base).has("incluir_secundarias")).toBe(false);
  });
});
