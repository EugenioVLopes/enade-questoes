import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ClassificacaoResponse, DetalheQuestaoResponse } from "@/api/revisao";
import type { ItemQuestaoResponse, ListaQuestoesResponse } from "@/api/questoes";
import type { ListaTaxonomiasResponse } from "@/api/taxonomias";
import { ROUTER_FUTURE_FLAGS, createAppRoutes } from "@/app/router";
import { TAXONOMIA_STORAGE_KEY } from "@/components/layout/useTaxonomia";

const TAX_ID = "22222222-2222-2222-2222-222222222222";
const PERFIL_ID = "99999999-9999-9999-9999-999999999999";

const TAXONOMIAS: ListaTaxonomiasResponse = {
  itens: [
    {
      id: TAX_ID,
      codigo: "enade-eng-computacao",
      nome: "ENADE Engenharia de Computação",
      curso_referencia: "Engenharia de Computação",
      disciplinas: [
        { id: "d1", taxonomia_id: TAX_ID, codigo: "redes", nome: "Redes", ementa: "", ativa: true, classificacoes_vigentes_impactadas: 0 },
        { id: "d2", taxonomia_id: TAX_ID, codigo: "algoritmos", nome: "Algoritmos", ementa: "", ativa: true, classificacoes_vigentes_impactadas: 0 },
        { id: "d3", taxonomia_id: TAX_ID, codigo: "banco-de-dados", nome: "Banco de Dados", ementa: "", ativa: true, classificacoes_vigentes_impactadas: 0 },
        { id: "d4", taxonomia_id: TAX_ID, codigo: "legada", nome: "Legada", ementa: "", ativa: false, classificacoes_vigentes_impactadas: 0 },
      ],
    },
  ],
  total: 1,
};

function classificacao(id: string, over: Partial<ClassificacaoResponse> = {}): ClassificacaoResponse {
  return {
    id,
    questao_id: "q1",
    taxonomia_id: TAX_ID,
    disciplina_principal: "redes",
    disciplinas_secundarias: ["algoritmos"],
    topicos: ["roteamento-ospf"],
    justificativa: "Trata de OSPF.",
    confianca: 0.62,
    origem: "automatica",
    status: "pendente_revisao",
    vigente: true,
    revisao_prioritaria: false,
    execucao_id: "eeeeeeee-0000-0000-0000-000000000001",
    substitui_classificacao_id: null,
    alertas_validacao: [],
    criada_em: "2026-01-01T10:00:00Z",
    revisada_em: null,
    ...over,
  };
}

function detalhe(id: string, numero: number, over: Partial<DetalheQuestaoResponse> = {}): DetalheQuestaoResponse {
  return {
    id,
    prova: { id: "p1", exame: "ENADE", curso: "Computação", ano: 2023 },
    numero,
    componente: "especifico",
    tipo: "multipla_escolha",
    paginas: [1],
    enunciado: `Enunciado da questão ${numero} com $x^2$.`,
    editada_manualmente: false,
    versao: 1,
    alternativas: [
      { letra: "A", texto: "Alternativa A" },
      { letra: "B", texto: "Alternativa B" },
      { letra: "C", texto: "Alternativa C" },
      { letra: "D", texto: "Alternativa D" },
      { letra: "E", texto: "Alternativa E" },
    ],
    ativos_visuais: [],
    gabarito: { situacao_gabarito: "valida", alternativa_correta: "B" },
    alertas_extracao: [],
    taxonomia_id: TAX_ID,
    classificacao_vigente: classificacao(`c-${id}`, { questao_id: id }),
    disciplinas_arquivadas_em_uso: [],
    divergencia_aberta: null,
    historico: [],
    outras_taxonomias: [],
    ...over,
  } as DetalheQuestaoResponse;
}

function item(id: string, numero: number): ItemQuestaoResponse {
  return {
    id,
    prova: { id: "p1", exame: "ENADE", curso: "Computação", ano: 2023 },
    numero,
    trecho: `Trecho ${numero}`,
    situacao_gabarito: "valida",
    editada_manualmente: false,
    alertas_abertos: [],
    revisao_prioritaria: false,
    tem_divergencia_aberta: false,
    usa_disciplina_arquivada: false,
    possui_ativos_visuais: false,
    classificacao: null,
  } as ItemQuestaoResponse;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

interface Chamada {
  method: string;
  path: string;
  search: URLSearchParams;
  body: unknown;
}

interface Servidor {
  pendentes: string[];
  divergencias: string[];
  arquivada: string[];
  recorte: string[];
  detalhes: Map<string, DetalheQuestaoResponse>;
  tamanhoFila?: number;
  erros: Map<string, { status: number; detail: unknown }>;
  chamadas: Chamada[];
  portaAprovar?: Promise<void>;
  perfis: { id: string; codigo: string; versao: string }[];
  redeFora?: boolean;
  portaPost?: Promise<void>;
}

function criarServidor(over: Partial<Servidor> = {}): Servidor {
  const detalhes = new Map<string, DetalheQuestaoResponse>();
  for (const [id, numero] of [["q1", 1], ["q2", 2], ["q3", 3]] as const) detalhes.set(id, detalhe(id, numero));
  return {
    pendentes: ["q1", "q2", "q3"],
    divergencias: [],
    arquivada: [],
    recorte: ["q1", "q2", "q3"],
    detalhes,
    erros: new Map(),
    chamadas: [],
    perfis: [{ id: PERFIL_ID, codigo: "v2-fronteiras", versao: "v1" }],
    ...over,
  };
}

function renderRevisao(path: string, servidor: Servidor) {
  window.sessionStorage.removeItem(TAXONOMIA_STORAGE_KEY);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(createAppRoutes(), { initialEntries: [path], future: ROUTER_FUTURE_FLAGS });

  const contadores = () => ({
    pendentes: servidor.pendentes.length,
    divergencias: servidor.divergencias.length,
    disciplina_arquivada: servidor.arquivada.length,
  });

  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const url = new URL(raw, "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
    servidor.chamadas.push({ method, path: url.pathname, search: url.searchParams, body });
    if (servidor.redeFora) throw new TypeError("Failed to fetch");

    if (url.pathname === "/api/v1/taxonomias") return jsonResponse(TAXONOMIAS);
    if (url.pathname === "/api/v1/perfis-classificacao") return jsonResponse({ itens: servidor.perfis.map((p) => ({ ...p, taxonomia_id: TAX_ID })), total: servidor.perfis.length });
    if (url.pathname === "/api/v1/health") {
      return jsonResponse({ status: "ok", banco_dados: "conectado", worker: { estado: "ocioso", tarefa_ativa: null } });
    }
    if (url.pathname === "/api/v1/execucoes-classificacao" && method === "GET") return jsonResponse({ itens: [], total: 0 });
    if (url.pathname === "/api/v1/execucoes-classificacao" && method === "POST") {
      const erro = servidor.erros.get("execucoes-classificacao");
      if (erro) return jsonResponse({ detail: erro.detail }, erro.status);
      return jsonResponse({ execucao_id: "exec-1", status: "enfileirada" }, 202);
    }

    if (url.pathname === "/api/v1/questoes") {
      const tamanhoSolicitado = Number(url.searchParams.get("tamanho_pagina") ?? 20);
      if (tamanhoSolicitado === 1) {
        return jsonResponse({ itens: [], total: 0, pagina: 1, tamanho_pagina: 1, contadores: contadores() });
      }
      const ids = url.searchParams.get("status_revisao") === "pendente"
        ? servidor.pendentes
        : url.searchParams.get("com_divergencia") === "true" && !url.searchParams.has("q")
          ? servidor.divergencias
          : url.searchParams.get("usa_disciplina_arquivada") === "true"
            ? servidor.arquivada
            : servidor.recorte;
      const tamanho = servidor.tamanhoFila ?? tamanhoSolicitado;
      const pagina = Number(url.searchParams.get("pagina") ?? 1);
      const fatia = ids.slice((pagina - 1) * tamanho, pagina * tamanho);
      const resposta: ListaQuestoesResponse = {
        itens: fatia.map((id) => item(id, Number(id.slice(1)))),
        total: ids.length,
        pagina,
        tamanho_pagina: tamanho,
        taxonomia_id: TAX_ID,
        contadores: contadores(),
      };
      return jsonResponse(resposta);
    }

    const partes = url.pathname.match(/^\/api\/v1\/questoes\/([^/]+)(?:\/(.*))?$/);
    if (partes) {
      const [, id, resto] = partes;
      if (method === "GET" && !resto) {
        const d = servidor.detalhes.get(id);
        return d ? jsonResponse(d) : jsonResponse({ detail: "Não encontrada" }, 404);
      }
      if (method === "POST") await servidor.portaPost;
      const chave = resto ?? "";
      const erro = [...servidor.erros.entries()].find(([sufixo]) => chave.endsWith(sufixo));
      if (erro) return jsonResponse({ detail: erro[1].detail }, erro[1].status);
      if (resto?.endsWith("/aprovar")) {
        await servidor.portaAprovar;
        servidor.pendentes = servidor.pendentes.filter((q) => q !== id);
        const d = servidor.detalhes.get(id)!;
        servidor.detalhes.set(id, { ...d, classificacao_vigente: { ...d.classificacao_vigente!, status: "aprovada" } });
        return jsonResponse(servidor.detalhes.get(id)!.classificacao_vigente);
      }
      if (resto?.endsWith("/corrigir")) {
        servidor.pendentes = servidor.pendentes.filter((q) => q !== id);
        const humana = classificacao(`h-${id}`, { origem: "humana", status: "aprovada", ...(body as object) } as Partial<ClassificacaoResponse>);
        const d = servidor.detalhes.get(id)!;
        servidor.detalhes.set(id, { ...d, classificacao_vigente: humana });
        return jsonResponse(humana, 201);
      }
      if (resto?.startsWith("divergencias/") && resto.endsWith("/resolver")) {
        servidor.divergencias = servidor.divergencias.filter((q) => q !== id);
        return jsonResponse({ divergencia: { id: "dv-1" }, classificacao_vigente: null });
      }
    }
    return jsonResponse({ detail: "Not Found" }, 404);
  });

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
    </QueryClientProvider>,
  );
  return { router, fetchSpy, queryClient };
}

const filas = (s: Servidor) => s.chamadas.filter((c) => c.path === "/api/v1/questoes" && c.search.get("tamanho_pagina") !== "1");
const badge = (s: Servidor) => s.chamadas.filter((c) => c.path === "/api/v1/questoes" && c.search.get("tamanho_pagina") === "1");
const posts = (s: Servidor) => s.chamadas.filter((c) => c.method === "POST");

function divergenciaFixture(id: string): DetalheQuestaoResponse {
  return detalhe(id, 1, {
    classificacao_vigente: classificacao("cv", {
      questao_id: id,
      origem: "humana",
      status: "aprovada",
      disciplina_principal: "redes",
      disciplinas_secundarias: [],
      topicos: ["roteamento-ospf"],
      justificativa: "Humana decidiu.",
      confianca: 1,
      execucao_id: null,
    }),
    divergencia_aberta: {
      id: "dv-1",
      questao_id: id,
      taxonomia_id: TAX_ID,
      execucao_id: "bbbbbbbb-0000-0000-0000-000000000002",
      classificacao_vigente_id: "cv",
      classificacao_candidata_id: "cc",
      disciplina_principal_candidata: "algoritmos",
      disciplinas_secundarias_candidatas: ["banco-de-dados"],
      topicos_candidatos: ["roteamento-ospf", "grafos"],
      justificativa_candidata: "IA discorda.",
      confianca_candidata: 0.71,
      status: "aberta",
      resolucao: null,
    } as DetalheQuestaoResponse["divergencia_aberta"],
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RevisaoPage: filas por aba", () => {
  it("Pendentes (padrão) consulta status_revisao=pendente, fila_revisao e 200 por página; contadores nas abas", async () => {
    const servidor = criarServidor({ divergencias: ["q9"], arquivada: ["q8", "q7"] });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    const fila = filas(servidor)[0];
    expect(Object.fromEntries(fila.search)).toMatchObject({
      taxonomia_id: TAX_ID,
      status_revisao: "pendente",
      ordenacao: "fila_revisao",
      tamanho_pagina: "200",
      pagina: "1",
    });
    expect(screen.getByRole("tab", { name: "Pendentes (3)" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Divergências (1)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Disciplina arquivada (2)" })).toBeInTheDocument();
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("1 de 3");
  });

  it("Divergências e Disciplina arquivada usam seus filtros com ordenacao=consulta", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor({ divergencias: ["q1"], arquivada: ["q2"] });
    servidor.detalhes.set("q1", divergenciaFixture("q1"));
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    await user.click(screen.getByRole("tab", { name: /Divergências/ }));
    await waitFor(() => expect(router.state.location.search).toContain("aba=divergencias"));
    await screen.findByRole("table", { name: "Comparador de Divergência" });
    const div = filas(servidor).find((c) => c.search.get("com_divergencia") === "true")!;
    expect(div.search.get("ordenacao")).toBe("consulta");
    expect(div.search.has("status_revisao")).toBe(false);

    await user.click(screen.getByRole("tab", { name: /Disciplina arquivada/ }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    const arq = filas(servidor).find((c) => c.search.get("usa_disciplina_arquivada") === "true")!;
    expect(arq.search.get("ordenacao")).toBe("consulta");
  });

  it("aba da URL (aba=divergencias) vale quando não há modo=recorte", async () => {
    const servidor = criarServidor({ divergencias: ["q1"] });
    servidor.detalhes.set("q1", divergenciaFixture("q1"));
    renderRevisao(`/revisao?taxonomia=${TAX_ID}&aba=divergencias`, servidor);
    await screen.findByRole("table", { name: "Comparador de Divergência" });
    expect(screen.getByRole("tab", { name: /Divergências/ })).toHaveAttribute("aria-selected", "true");
  });
});

describe("RevisaoPage: recorte filtrado", () => {
  it("modo=recorte usa os filtros da URL, posiciona por questao e mostra X de N com Anterior/Próxima", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&q=ospf&com_divergencia=true&questao=q2`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 2" });

    const fila = filas(servidor)[0];
    expect(Object.fromEntries(fila.search)).toMatchObject({ q: "ospf", com_divergencia: "true", ordenacao: "consulta", tamanho_pagina: "200" });
    expect(fila.search.has("status_revisao")).toBe(false);
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.getByText("Recorte filtrado")).toBeInTheDocument();
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("2 de 3");

    await user.click(screen.getByRole("button", { name: "Próxima" }));
    await screen.findByRole("heading", { name: "Questão Nº 3" });
    expect(router.state.location.search).toContain("questao=q3");
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("3 de 3");
    expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Anterior" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("2 de 3");
  });

  it("carrega a página seguinte sob demanda ao avançar além da primeira e para posicionar questao", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor({ tamanhoFila: 2 });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&questao=q2`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(filas(servidor).map((c) => c.search.get("pagina"))).toEqual(["1"]);

    await user.click(screen.getByRole("button", { name: "Próxima" }));
    await screen.findByRole("heading", { name: "Questão Nº 3" });
    expect(filas(servidor).map((c) => c.search.get("pagina"))).toEqual(["1", "2"]);
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("3 de 3");
  });

  it("questao fora da primeira página é localizada carregando as seguintes", async () => {
    const servidor = criarServidor({ tamanhoFila: 2 });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&questao=q3`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 3" });
    await waitFor(() => expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("3 de 3"));
  });
});

describe("RevisaoPage: aprovar e avançar", () => {
  it("Aprovar sugestão envia POST, atualiza a fila, avança para a próxima questão e refaz o badge global", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await waitFor(() => expect(badge(servidor).length).toBeGreaterThan(0));
    const badgeAntes = badge(servidor).length;
    const filasAntes = filas(servidor).length;

    await user.click(screen.getByRole("button", { name: "Aprovar sugestão" }));

    await screen.findByRole("heading", { name: "Questão Nº 2" });
    const aprovacoes = posts(servidor);
    expect(aprovacoes).toHaveLength(1);
    expect(aprovacoes[0].path).toBe(`/api/v1/questoes/q1/classificacoes/${TAX_ID}/aprovar`);
    expect(aprovacoes[0].body).toBeUndefined();
    expect(router.state.location.search).toContain("questao=q2");
    expect(filas(servidor).length).toBeGreaterThan(filasAntes);
    expect(badge(servidor).length).toBeGreaterThan(badgeAntes);
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("1 de 2");
    expect(screen.getByRole("tab", { name: "Pendentes (2)" })).toBeInTheDocument();
  });

  it("ao aprovar a última da fila volta para a anterior; fila esvaziada mostra estado vazio", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor({ pendentes: ["q1", "q2"] });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}&questao=q2`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    await user.click(screen.getByRole("button", { name: "Aprovar sugestão" }));
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Aprovar sugestão" }));
    expect(await screen.findByText("Fila vazia")).toBeInTheDocument();
  });

  it("erro 409 ao aprovar é exibido e a questão permanece", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.erros.set("/aprovar", { status: 409, detail: "Classificação já aprovada." });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Aprovar sugestão" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Classificação já aprovada.");
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
  });
});

describe("RevisaoPage: regressões da revisão do gate", () => {
  it("G1: trocar a principal para uma já secundária remove a duplicata e nunca envia principal entre as secundárias", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    expect(screen.getByRole("combobox", { name: "Disciplina secundária 1" })).toHaveTextContent("Algoritmos");
    await escolher(user, "Disciplina principal", "Algoritmos");
    expect(screen.getByRole("combobox", { name: "Disciplina principal" })).toHaveTextContent("Algoritmos");
    expect(screen.getByRole("combobox", { name: "Disciplina secundária 1" })).toHaveTextContent("Nenhuma");
    expect(screen.getByRole("combobox", { name: "Disciplina secundária 1" })).not.toHaveTextContent("Algoritmos");
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    const [corrigir] = posts(servidor);
    expect(corrigir.body).toMatchObject({ disciplina_principal: "algoritmos", disciplinas_secundarias: [] });
  });

  it("G2: trocar de aba durante o veredito pendente não é revertido pelo avanço automático", async () => {
    const user = userEvent.setup();
    let liberar: () => void = () => {};
    const servidor = criarServidor({ portaAprovar: new Promise<void>((resolve) => (liberar = resolve)) });
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Aprovar sugestão" }));
    await user.click(screen.getByRole("tab", { name: /Divergências/ }));
    await waitFor(() => expect(router.state.location.search).toContain("aba=divergencias"));
    liberar();
    await waitFor(() => expect(posts(servidor)).toHaveLength(1));
    await waitFor(() => expect(screen.getByRole("tab", { name: /Divergências/ })).toHaveAttribute("aria-selected", "true"));
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(router.state.location.search).toContain("aba=divergencias");
    expect(router.state.location.search).not.toContain("questao=");
    expect(screen.getByRole("tabpanel")).toBeInTheDocument();
  });

  it("G3: em 409 o detalhe e a fila são recarregados e o veredito vigente substitui o botão Aprovar", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.erros.set("/aprovar", { status: 409, detail: "Classificação já aprovada." });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    const d = servidor.detalhes.get("q1")!;
    servidor.detalhes.set("q1", { ...d, classificacao_vigente: { ...d.classificacao_vigente!, status: "aprovada" } });
    const filasAntes = filas(servidor).length;
    await user.click(screen.getByRole("button", { name: "Aprovar sugestão" }));
    expect(await screen.findByText("Aprovada (IA)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aprovar sugestão" })).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Classificação já aprovada.");
    expect(filas(servidor).length).toBeGreaterThan(filasAntes);
  });

  it("K1: 409 ao corrigir mantém o formulário aberto com os valores digitados e a mensagem, mesmo após o refetch mudar o estado da questão", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.erros.set("/corrigir", { status: 409, detail: "Classificação já aprovada." });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    const just = screen.getByLabelText("Justificativa");
    await user.clear(just);
    await user.type(just, "Texto digitado");
    const d = servidor.detalhes.get("q1")!;
    servidor.detalhes.set("q1", { ...d, classificacao_vigente: { ...d.classificacao_vigente!, status: "aprovada" } });
    const filasAntes = filas(servidor).length;
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Classificação já aprovada.");
    await waitFor(() => expect(filas(servidor).length).toBeGreaterThan(filasAntes));
    await screen.findByText("Aprovada (IA)");
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
    expect(screen.getByLabelText("Justificativa")).toHaveValue("Texto digitado");
  });

  it("K1: 409 ao resolver com edição manual mantém o formulário aberto e os valores", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set("q1", divergenciaFixture("q1"));
    servidor.divergencias = ["q1", "q2"];
    servidor.erros.set("/resolver", { status: 409, detail: "Divergência já resolvida." });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}&aba=divergencias`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Editar manualmente" }));
    await escolher(user, "Disciplina principal", "Algoritmos");
    await user.click(screen.getByRole("button", { name: "Resolver com edição manual" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Divergência já resolvida.");
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Disciplina principal" })).toHaveTextContent("Algoritmos");
  });

  it("K2: a edição aberta não reaparece ao voltar para a questão (Próxima e depois Anterior)", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&questao=q1`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Próxima" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(screen.queryByRole("form", { name: "Formulário de classificação" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Anterior" }));
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    expect(screen.queryByRole("form", { name: "Formulário de classificação" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aprovar sugestão" })).toBeInTheDocument();
  });

  it("L1: 409 ao corrigir sem questao= na URL e com q1 removida da fila mantém questão, erro, formulário e permite ir para Próxima", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.erros.set("/corrigir", { status: 409, detail: "Classificação já aprovada." });
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    const just = screen.getByLabelText("Justificativa");
    await user.clear(just);
    await user.type(just, "Texto digitado");

    servidor.pendentes = ["q2", "q3"];
    const d = servidor.detalhes.get("q1")!;
    servidor.detalhes.set("q1", { ...d, classificacao_vigente: { ...d.classificacao_vigente!, status: "aprovada" } });

    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    const alerta = await screen.findByText("Classificação já aprovada.");
    expect(alerta.closest('[role="alert"]')).not.toBeNull();
    await screen.findByText("Aprovada (IA)");
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
    expect(router.state.location.search).toContain("questao=q1");
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
    expect(screen.getByLabelText("Justificativa")).toHaveValue("Texto digitado");
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("Fora da fila · 2 na fila");
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Próxima" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Próxima" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("1 de 2");
  });

  it("L1: 409 ao aprovar sem questao= na URL e com q1 removida da fila mantém questão e erro visíveis", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor({ pendentes: ["q1", "q2"] });
    servidor.erros.set("/aprovar", { status: 409, detail: "Classificação já aprovada." });
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    servidor.pendentes = ["q2"];
    const d = servidor.detalhes.get("q1")!;
    servidor.detalhes.set("q1", { ...d, classificacao_vigente: { ...d.classificacao_vigente!, status: "aprovada" } });

    await user.click(screen.getByRole("button", { name: "Aprovar sugestão" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Classificação já aprovada.");
    await screen.findByText("Aprovada (IA)");
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
    expect(router.state.location.search).toContain("questao=q1");
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("Fora da fila · 1 na fila");
  });

  it("L1: 409 ao resolver divergência com edição manual sem questao= na URL e com q1 removida da fila mantém questão, erro e formulário", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set("q1", divergenciaFixture("q1"));
    servidor.detalhes.set("q2", { ...divergenciaFixture("q2"), id: "q2", numero: 2 });
    servidor.divergencias = ["q1", "q2"];
    servidor.erros.set("/resolver", { status: 409, detail: "Divergência já resolvida." });
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}&aba=divergencias`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    await user.click(screen.getByRole("button", { name: "Editar manualmente" }));
    await escolher(user, "Disciplina principal", "Algoritmos");

    servidor.divergencias = ["q2"];
    servidor.detalhes.set("q1", { ...divergenciaFixture("q1"), divergencia_aberta: null });

    await user.click(screen.getByRole("button", { name: "Resolver com edição manual" }));
    const alerta = await screen.findByText("Divergência já resolvida.");
    expect(alerta.closest('[role="alert"]')).not.toBeNull();
    await screen.findByText("Aprovada (humana)");
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
    expect(router.state.location.search).toContain("questao=q1");
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Disciplina principal" })).toHaveTextContent("Algoritmos");
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("Fora da fila · 1 na fila");
  });

  it("L2: 409 ao salvar em Sem classificação mantém o formulário e o texto mesmo quando o refetch traz classificação vigente", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set("q1", detalhe("q1", 1, { classificacao_vigente: null }));
    servidor.erros.set("/corrigir", { status: 409, detail: "Conflito na classificação." });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByText("Sem classificação");

    await escolher(user, "Disciplina principal", "Redes");
    const just = screen.getByLabelText("Justificativa");
    await user.type(just, "Texto PA");

    servidor.detalhes.set("q1", detalhe("q1", 1));
    await user.click(screen.getByRole("button", { name: "Salvar classificação" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Conflito na classificação.");
    await screen.findByText("Sugestão da IA");
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
    expect(screen.getByLabelText("Justificativa")).toHaveValue("Texto PA");
    expect(screen.getByRole("combobox", { name: "Disciplina principal" })).toHaveTextContent("Redes");
  });

  it("L3: auto-repeat do atalho A é ignorado e não aprova questões em cascata", async () => {
    const servidor = criarServidor();
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    fireEvent.keyDown(document.body, { key: "a", repeat: true });
    expect(posts(servidor)).toHaveLength(0);

    fireEvent.keyDown(document.body, { key: "a", repeat: false });
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    fireEvent.keyDown(document.body, { key: "a", repeat: true });
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(posts(servidor)).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "Questão Nº 2" })).toBeInTheDocument();
  });

  it("L4: dois keydown A síncronos no mesmo tick disparam apenas um POST de aprovação", async () => {
    let liberar: () => void = () => {};
    const servidor = criarServidor({ portaAprovar: new Promise<void>((resolve) => (liberar = resolve)) });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "a", bubbles: true }));
    document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "a", bubbles: true }));

    liberar();
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(posts(servidor)).toHaveLength(1);
  });
});

async function escolher(user: ReturnType<typeof userEvent.setup>, combobox: string, opcao: string) {
  await user.click(screen.getByRole("combobox", { name: combobox }));
  await user.click(await screen.findByRole("option", { name: opcao }));
}

describe("RevisaoPage: corrigir e aprovar", () => {
  it("envia 1 principal + 2 secundárias + tópicos + justificativa e avança", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));

    await user.click(screen.getByRole("combobox", { name: "Disciplina principal" }));
    expect(screen.queryByRole("option", { name: "Legada" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("option", { name: "Banco de Dados" }));
    await user.click(screen.getByRole("combobox", { name: "Disciplina secundária 1" }));
    expect(screen.queryByRole("option", { name: "Banco de Dados" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("option", { name: "Redes" }));
    await escolher(user, "Disciplina secundária 2", "Algoritmos");

    await user.type(screen.getByLabelText("Tópicos"), "SQL Joins{Enter}");
    await user.click(screen.getByRole("button", { name: "Remover Tópico SQL Joins" }));
    await user.type(screen.getByLabelText("Tópicos"), "indices");
    await user.click(screen.getByRole("button", { name: "Adicionar Tópico" }));
    const just = screen.getByLabelText("Justificativa");
    await user.clear(just);
    await user.type(just, "Ajuste do revisor.");

    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    const [corrigir] = posts(servidor);
    expect(corrigir.path).toBe(`/api/v1/questoes/q1/classificacoes/${TAX_ID}/corrigir`);
    expect(corrigir.body).toEqual({
      disciplina_principal: "banco-de-dados",
      disciplinas_secundarias: ["redes", "algoritmos"],
      topicos: ["roteamento-ospf", "indices"],
      justificativa: "Ajuste do revisor.",
    });
  });

  it("erro 422 aparece sem perder o formulário preenchido; só há duas secundárias", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.erros.set("/corrigir", { status: 422, detail: "Disciplina 'x' não existe ou está arquivada." });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));
    expect(screen.queryByRole("combobox", { name: "Disciplina secundária 3" })).not.toBeInTheDocument();
    const just = screen.getByLabelText("Justificativa");
    await user.clear(just);
    await user.type(just, "Texto digitado");
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("não existe ou está arquivada");
    expect(screen.getByLabelText("Justificativa")).toHaveValue("Texto digitado");
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
  });

  it("Aprovada: mostra o veredito vigente e Editar classificação abre o formulário", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set("q1", detalhe("q1", 1, { classificacao_vigente: classificacao("c1", { status: "aprovada", origem: "humana", confianca: 1 }) }));
    renderRevisao(`/revisao?taxonomia=${TAX_ID}&questao=q1`, servidor);
    expect(await screen.findByText("Aprovada (humana)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aprovar sugestão" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Editar classificação" }));
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
  });
});

describe("RevisaoPage: sem classificação", () => {
  it("formulário manual usa corrigir e o botão dispara Execução individual com o perfil padrão", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set("q1", detalhe("q1", 1, { classificacao_vigente: null }));
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByText("Sem classificação");

    await waitFor(() => expect(screen.getByRole("button", { name: /Classificar com IA/ })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: /Classificar com IA/ }));
    await screen.findByText(/Execução de Classificação enfileirada/);
    const exec = posts(servidor).find((c) => c.path === "/api/v1/execucoes-classificacao")!;
    expect(exec.body).toEqual({
      taxonomia_id: TAX_ID,
      perfil_id: PERFIL_ID,
      escopo: "questao_ids",
      questao_ids: ["q1"],
      incluir_revisadas: false,
    });

    await escolher(user, "Disciplina principal", "Redes");
    await user.click(screen.getByRole("button", { name: "Salvar classificação" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    const corrigir = posts(servidor).find((c) => c.path.endsWith("/corrigir"))!;
    expect(corrigir.body).toEqual({
      disciplina_principal: "redes",
      disciplinas_secundarias: [],
      topicos: [],
      justificativa: "",
    });
  });
});

describe("RevisaoPage: Divergências", () => {
  async function abrir(servidor: Servidor) {
    servidor.divergencias = ["q1", "q2"];
    servidor.detalhes.set("q1", divergenciaFixture("q1"));
    servidor.detalhes.set("q2", { ...divergenciaFixture("q2"), id: "q2", numero: 2 });
    renderRevisao(`/revisao?taxonomia=${TAX_ID}&aba=divergencias`, servidor);
    return screen.findByRole("table", { name: "Comparador de Divergência" });
  }

  it("comparador destaca as diferenças entre vigente humana e candidata IA", async () => {
    const servidor = criarServidor();
    const tabela = await abrir(servidor);
    const linhas = within(tabela).getAllByRole("row");
    const marcadas = linhas.filter((l) => l.getAttribute("data-diferente") === "true");
    expect(marcadas).toHaveLength(5);
    expect(within(tabela).getByText("Vigente humana")).toBeInTheDocument();
    expect(within(tabela).getByText("Candidata IA")).toBeInTheDocument();
    expect(within(tabela).getByText("Algoritmos")).toBeInTheDocument();
    expect(within(tabela).getByText("roteamento-ospf, grafos")).toBeInTheDocument();
  });

  it("Manter humana envia resolucao sem classificacao e avança", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    await abrir(servidor);
    await user.click(screen.getByRole("button", { name: "Manter humana" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    const [resolver] = posts(servidor);
    expect(resolver.path).toBe("/api/v1/questoes/q1/divergencias/dv-1/resolver");
    expect(resolver.body).toEqual({ resolucao: "manter_humana" });
  });

  it("Aceitar candidata envia resolucao sem classificacao", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    await abrir(servidor);
    await user.click(screen.getByRole("button", { name: "Aceitar candidata" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(posts(servidor)[0].body).toEqual({ resolucao: "aceitar_candidata" });
  });

  it("Editar manualmente envia editar_manualmente com classificacao", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    await abrir(servidor);
    await user.click(screen.getByRole("button", { name: "Editar manualmente" }));
    await escolher(user, "Disciplina principal", "Algoritmos");
    await user.click(screen.getByRole("button", { name: "Resolver com edição manual" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(posts(servidor)[0].body).toEqual({
      resolucao: "editar_manualmente",
      classificacao: {
        disciplina_principal: "algoritmos",
        disciplinas_secundarias: [],
        topicos: ["roteamento-ospf"],
        justificativa: "Humana decidiu.",
      },
    });
  });
});

describe("RevisaoPage: acordeão e leitura", () => {
  it("Outras taxonomias (N) e histórico fica recolhido e expande sem trocar de tela", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        historico: [
          classificacao("h1", { vigente: false, origem: "automatica", justificativa: "Predição original" }),
          classificacao("h2", { origem: "humana", status: "aprovada", justificativa: "Revisão humana final" }),
        ],
        outras_taxonomias: [
          { taxonomia_id: "t2", taxonomia_codigo: "outra", taxonomia_nome: "Outra Taxonomia", classificacao: classificacao("o1", { justificativa: "Na outra" }) },
        ],
      }),
    );
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    const botao = screen.getByRole("button", { name: "Outras taxonomias (1) e histórico" });
    expect(botao).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Predição original")).not.toBeInTheDocument();

    await user.click(botao);
    expect(botao).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Outra Taxonomia")).toBeInTheDocument();
    expect(screen.getByText("Predição original")).toBeInTheDocument();
    expect(screen.getByText("Revisão humana final")).toBeInTheDocument();
    expect(screen.getByText("Predição da IA")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
  });

  it("distingue Alertas de Extração críticos de informativos e destaca a alternativa correta", async () => {
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        alertas_extracao: [
          { id: "a1", codigo: "formula_nao_decodificada", severidade: "critico", status: "aberto", mensagem: "m" },
          { id: "a2", codigo: "pdf_via_ocr", severidade: "informativo", status: "aberto", mensagem: "m" },
          { id: "a3", codigo: "enunciado_suspeito", severidade: "critico", status: "resolvido", mensagem: "m" },
        ] as DetalheQuestaoResponse["alertas_extracao"],
      }),
    );
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    const lista = screen.getByRole("list", { name: "Alertas de Extração" });
    const itens = within(lista).getAllByRole("listitem");
    expect(itens).toHaveLength(2);
    expect(within(lista).getByText("Fórmula não decodificada").closest("[data-severidade]")).toHaveAttribute("data-severidade", "critico");
    expect(within(lista).getByText("PDF lido via OCR").closest("[data-severidade]")).toHaveAttribute("data-severidade", "informativo");
    const alternativas = within(screen.getByRole("region", { name: "Alternativas" })).getAllByRole("listitem");
    expect(alternativas.filter((a) => a.getAttribute("data-correta") === "true")).toHaveLength(1);
    expect(alternativas[1]).toHaveAttribute("data-correta", "true");
  });

  it("renderiza fórmula do enunciado com KaTeX e copia a questão em Markdown", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    expect(document.querySelector(".katex")).not.toBeNull();

    const spy = vi.spyOn(navigator.clipboard, "writeText");
    await user.click(screen.getByRole("button", { name: "Copiar questão em Markdown" }));
    expect(spy).toHaveBeenCalledWith(
      "## Questão 1 — ENADE Computação 2023\n\nEnunciado da questão 1 com $x^2$.\n\n**A)** Alternativa A\n\n**B)** Alternativa B\n\n**C)** Alternativa C\n\n**D)** Alternativa D\n\n**E)** Alternativa E\n\nGabarito: B",
    );
    expect(await screen.findByText("Questão copiada em Markdown.")).toBeInTheDocument();
  });

  it("galeria separa Ativos do enunciado e da alternativa; clique abre o lightbox e Esc fecha", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        ativos_visuais: [
          { id: "v1", origem: "picture_docling", alternativa_letra: null, ordem: 1, pagina: 1, url_arquivo: "/api/v1/ativos-visuais/v1/arquivo" },
          { id: "v2", origem: "picture_docling", alternativa_letra: "C", ordem: 2, pagina: 1, url_arquivo: "/api/v1/ativos-visuais/v2/arquivo" },
        ] as DetalheQuestaoResponse["ativos_visuais"],
      }),
    );
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    const enunciado = screen.getByRole("region", { name: "Enunciado" });
    expect(within(enunciado).getAllByRole("img")).toHaveLength(1);
    const altC = within(screen.getByRole("region", { name: "Alternativas" })).getByText("Alternativa C").closest("li")!;
    expect(within(altC).getAllByRole("img")).toHaveLength(1);

    await user.click(within(enunciado).getByRole("button", { name: /Ampliar/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("img")).toHaveAttribute("src", "/api/v1/ativos-visuais/v1/arquivo");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("RevisaoPage: atalhos de teclado", () => {
  it("A aprova, ←/→ navegam e E abre a edição, Esc fecha", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&questao=q2`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 2" });

    await user.keyboard("{ArrowRight}");
    await screen.findByRole("heading", { name: "Questão Nº 3" });
    await user.keyboard("{ArrowLeft}");
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(router.state.location.search).toContain("questao=q2");

    await user.keyboard("e");
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
    expect(posts(servidor)).toHaveLength(0);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("form", { name: "Formulário de classificação" })).not.toBeInTheDocument());

    await user.keyboard("a");
    await waitFor(() => expect(posts(servidor)).toHaveLength(1));
    expect(posts(servidor)[0].path).toBe(`/api/v1/questoes/q2/classificacoes/${TAX_ID}/aprovar`);
  });

  it("atalhos são ignorados com foco em input, textarea ou select", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&questao=q2`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    await user.click(screen.getByRole("button", { name: "Corrigir e aprovar" }));

    const justificativa = screen.getByLabelText("Justificativa");
    await user.click(justificativa);
    await user.keyboard("a e{ArrowLeft}{ArrowRight}");
    expect(justificativa).toHaveValue("Trata de OSPF.a e");
    const topico = screen.getByLabelText("Tópicos");
    await user.click(topico);
    await user.keyboard("a{ArrowRight}{Escape}");
    expect(topico).toHaveValue("a");
    expect(screen.getByRole("form", { name: "Formulário de classificação" })).toBeInTheDocument();
    expect(posts(servidor)).toHaveLength(0);
    expect(router.state.location.search).toContain("questao=q2");
    expect(screen.getByRole("heading", { name: "Questão Nº 2" })).toBeInTheDocument();

    screen.getByRole("combobox", { name: "Disciplina principal" }).focus();
    await user.keyboard("{ArrowLeft}");
    expect(router.state.location.search).toContain("questao=q2");
  });
});
