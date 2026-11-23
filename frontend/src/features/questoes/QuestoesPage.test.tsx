import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ListaProvasResponse } from "@/api/provas";
import type { ItemQuestaoResponse, ListaQuestoesResponse } from "@/api/questoes";
import type { ListaTaxonomiasResponse } from "@/api/taxonomias";
import { ROUTER_FUTURE_FLAGS, createAppRoutes } from "@/app/router";
import { TAXONOMIA_STORAGE_KEY } from "@/components/layout/useTaxonomia";

const TAX_ID = "22222222-2222-2222-2222-222222222222";
const TAX_OUTRA_ID = "33333333-3333-3333-3333-333333333333";
const DISC_ID = "66666666-6666-6666-6666-666666666666";
const PROVA_ID = "77777777-7777-7777-7777-777777777777";

const TAXONOMIAS: ListaTaxonomiasResponse = {
  itens: [
    {
      id: TAX_ID,
      codigo: "enade-eng-computacao",
      nome: "ENADE Engenharia de Computação",
      curso_referencia: "Engenharia de Computação",
      disciplinas: [
        { id: DISC_ID, taxonomia_id: TAX_ID, codigo: "redes", nome: "Redes", ementa: "", ativa: true, classificacoes_vigentes_impactadas: 0 },
        { id: "d2", taxonomia_id: TAX_ID, codigo: "legada", nome: "Legada", ementa: "", ativa: false, classificacoes_vigentes_impactadas: 0 },
      ],
    },
    { id: TAX_OUTRA_ID, codigo: "outra", nome: "Outra Taxonomia", curso_referencia: "X", disciplinas: [] },
  ],
  total: 2,
};

const PROVAS: ListaProvasResponse = {
  itens: [
    {
      id: PROVA_ID,
      exame: "ENADE",
      curso: "Computação",
      ano: 2023,
      questao_inicio: 1,
      questao_fim: 30,
      possui_gabarito: true,
      questoes: { total: 2 },
      alertas: {},
      classificacao_encadeada: { solicitada: false },
    } as unknown as ListaProvasResponse["itens"][number],
  ],
  total: 1,
};

function makeItem(over: Partial<ItemQuestaoResponse> = {}): ItemQuestaoResponse {
  return {
    id: "q-1",
    prova: { id: PROVA_ID, exame: "ENADE", curso: "Computação", ano: 2023 },
    numero: 7,
    trecho: "Considere o protocolo OSPF **negrito** `codigo` para roteamento.",
    situacao_gabarito: "valida",
    editada_manualmente: false,
    alertas_abertos: [],
    revisao_prioritaria: false,
    tem_divergencia_aberta: false,
    usa_disciplina_arquivada: false,
    possui_ativos_visuais: false,
    classificacao: {
      id: "c-1",
      origem: "llm",
      status: "aprovada",
      confianca: 0.9,
      revisao_prioritaria: false,
      disciplina_principal: "redes",
      disciplinas_secundarias: ["legada"],
      topicos: ["roteamento-ospf"],
    },
    ...over,
  } as ItemQuestaoResponse;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

interface RenderOptions {
  path?: string;
  provas?: ListaProvasResponse;
  itens?: ItemQuestaoResponse[];
  total?: number;
  questoesStatus?: number;
  taxonomias?: ListaTaxonomiasResponse;
  taxonomiasStatus?: number;
  questoesGate?: Promise<void>;
  /** Segura apenas as listagens com pagina >= 2 (G4: refetch por troca de página). */
  questoesGatePagina2?: Promise<void>;
  /** Segura apenas a listagem da outra Taxonomia (G4/F6). */
  questoesGateOutraTaxonomia?: Promise<void>;
  /** Segura apenas as listagens com status_revisao (H1/H2: refetch por troca de filtro). */
  questoesGateStatus?: Promise<void>;
}

function renderQuestoes(options: RenderOptions = {}) {
  window.sessionStorage.removeItem(TAXONOMIA_STORAGE_KEY);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(createAppRoutes(), {
    initialEntries: [options.path ?? `/questoes?taxonomia=${TAX_ID}`],
    future: ROUTER_FUTURE_FLAGS,
  });
  const itens = options.itens ?? [makeItem()];

  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const url = new URL(raw, "http://localhost");
    if (url.pathname === "/api/v1/taxonomias") {
      if (options.taxonomiasStatus) return jsonResponse({ detail: "Falha simulada" }, options.taxonomiasStatus);
      return jsonResponse(options.taxonomias ?? TAXONOMIAS);
    }
    if (url.pathname === "/api/v1/provas") return jsonResponse(options.provas ?? PROVAS);
    if (url.pathname === "/api/v1/health") {
      return jsonResponse({ status: "ok", banco_dados: "conectado", worker: { estado: "ocioso", tarefa_ativa: null } });
    }
    if (url.pathname === "/api/v1/execucoes-classificacao") return jsonResponse({ itens: [], total: 0 });
    if (url.pathname === "/api/v1/questoes") {
      if (options.questoesGate && url.searchParams.get("tamanho_pagina") === "20") await options.questoesGate;
      if (options.questoesGatePagina2 && Number(url.searchParams.get("pagina")) >= 2 && url.searchParams.get("tamanho_pagina") === "20") {
        await options.questoesGatePagina2;
      }
      if (options.questoesGateOutraTaxonomia && url.searchParams.get("taxonomia_id") === TAX_OUTRA_ID && url.searchParams.get("tamanho_pagina") === "20") {
        await options.questoesGateOutraTaxonomia;
      }
      if (options.questoesGateStatus && url.searchParams.has("status_revisao") && url.searchParams.get("tamanho_pagina") === "20") {
        await options.questoesGateStatus;
      }
      if (options.questoesStatus && url.searchParams.get("tamanho_pagina") === "20") {
        return jsonResponse({ detail: "Falha simulada" }, options.questoesStatus);
      }
      const body: ListaQuestoesResponse = {
        itens,
        total: options.total ?? itens.length,
        pagina: Number(url.searchParams.get("pagina") ?? 1),
        tamanho_pagina: Number(url.searchParams.get("tamanho_pagina") ?? 20),
        taxonomia_id: url.searchParams.get("taxonomia_id"),
        contadores: { pendentes: 0, divergencias: 0, disciplina_arquivada: 0 },
      };
      return jsonResponse(body);
    }
    return jsonResponse({ detail: "Not Found" }, 404);
  });

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
    </QueryClientProvider>,
  );
  return { router, fetchSpy };
}

/** URLs de listagem (tamanho_pagina=20); ignora a consulta de contadores do shell (tamanho_pagina=1). */
function listagens(fetchSpy: { mock: { calls: unknown[][] } }): URL[] {
  return fetchSpy.mock.calls
    .map(([input]) => new URL(String(input instanceof Request ? input.url : input), "http://localhost"))
    .filter((u) => u.pathname === "/api/v1/questoes" && u.searchParams.get("tamanho_pagina") === "20");
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("QuestoesPage", () => {
  it("consulta por padrão com taxonomia, ordenacao=consulta e incluir_secundarias=true, sem flags", async () => {
    const { fetchSpy } = renderQuestoes();
    expect(await screen.findByText(/Questão Nº 7/)).toBeInTheDocument();
    const url = listagens(fetchSpy).at(-1)!;
    expect(url.searchParams.get("taxonomia_id")).toBe(TAX_ID);
    expect(url.searchParams.get("ordenacao")).toBe("consulta");
    expect(url.searchParams.get("incluir_secundarias")).toBe("true");
    expect(url.searchParams.get("pagina")).toBe("1");
    for (const flag of ["com_alerta_extracao", "revisao_prioritaria", "com_divergencia", "usa_disciplina_arquivada", "q", "disciplina_id"]) {
      expect(url.searchParams.has(flag)).toBe(false);
    }
  });

  it("lê filtros da URL e os envia à API", async () => {
    const { fetchSpy } = renderQuestoes({
      path: `/questoes?taxonomia=${TAX_ID}&q=ospf&ano=2023&status_revisao=aprovada&situacao_gabarito=anulada&com_divergencia=true&disciplina_id=${DISC_ID}&incluir_secundarias=false&topico=roteamento-ospf`,
    });
    await screen.findByText(/Questão Nº 7/);
    const url = listagens(fetchSpy).at(-1)!;
    expect(Object.fromEntries(url.searchParams)).toMatchObject({
      q: "ospf",
      ano: "2023",
      status_revisao: "aprovada",
      situacao_gabarito: "anulada",
      com_divergencia: "true",
      disciplina_id: DISC_ID,
      incluir_secundarias: "false",
      topico: "roteamento-ospf",
    });
    expect(screen.getByRole("button", { name: "Mais filtros (3)" })).toBeInTheDocument();
  });

  it("renderiza todos os badges, ícones, nomes de Disciplina e snippet como texto puro", async () => {
    renderQuestoes({
      itens: [
        makeItem({
          classificacao: { ...makeItem().classificacao!, status: "pendente_revisao" },
          revisao_prioritaria: true,
          tem_divergencia_aberta: true,
          situacao_gabarito: "anulada",
          usa_disciplina_arquivada: true,
          possui_ativos_visuais: true,
          alertas_abertos: ["pdf_via_ocr", "fonte_symbol_detectada"],
        }),
        makeItem({ id: "q-2", numero: 8, situacao_gabarito: "pendente" }),
      ],
    });
    const cards = await screen.findAllByRole("link", { name: /Questão Nº/ });
    expect(cards).toHaveLength(2);
    const [primeiro, segundo] = cards.map((c) => within(c));

    for (const label of ["Pendente", "Prioritária", "Divergência", "Anulada", "Disciplina arquivada"]) {
      expect(primeiro.getByText(label)).toBeInTheDocument();
    }
    expect(primeiro.queryByText("Aprovada")).not.toBeInTheDocument();
    expect(primeiro.getByText("Gabarito anulado")).toBeInTheDocument();
    expect(primeiro.getByRole("img", { name: "Possui ativo visual" })).toBeInTheDocument();
    expect(primeiro.getByRole("img", { name: "2 alerta(s) de extração aberto(s)" })).toBeInTheDocument();
    expect(primeiro.getByText("Redes")).toBeInTheDocument();
    expect(primeiro.getByText("Legada")).toBeInTheDocument();
    expect(primeiro.getByText("roteamento-ospf")).toBeInTheDocument();
    expect(primeiro.getByText(/\*\*negrito\*\* `codigo`/)).toHaveClass("line-clamp-2");

    expect(segundo.getByText("Aprovada")).toBeInTheDocument();
    expect(segundo.getByText("Gabarito pendente")).toBeInTheDocument();
    for (const label of ["Pendente", "Prioritária", "Divergência", "Anulada", "Disciplina arquivada"]) {
      expect(segundo.queryByText(label)).not.toBeInTheDocument();
    }
    expect(segundo.queryByRole("img", { name: "Possui ativo visual" })).not.toBeInTheDocument();
    expect(segundo.queryByRole("img", { name: /alerta/ })).not.toBeInTheDocument();
  });

  it("toggle Somente principal exige Disciplina e envia incluir_secundarias=false", async () => {
    const user = userEvent.setup();
    const { router, fetchSpy } = renderQuestoes();
    await screen.findByText(/Questão Nº 7/);

    const toggle = screen.getByRole("checkbox", { name: "Somente principal" });
    expect(toggle).toBeDisabled();

    await user.click(screen.getByRole("combobox", { name: "Disciplina" }));
    await user.click(await screen.findByRole("option", { name: /Redes \(redes\)$/ }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("disciplina_id")).toBe(DISC_ID));
    expect(listagens(fetchSpy).at(-1)!.searchParams.get("incluir_secundarias")).toBe("true");

    await user.click(screen.getByRole("checkbox", { name: "Somente principal" }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("incluir_secundarias")).toBe("false"));
    expect(router.state.location.search).toContain("incluir_secundarias=false");

    await user.click(screen.getByRole("checkbox", { name: "Somente principal" }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("incluir_secundarias")).toBe("true"));
    expect(router.state.location.search).not.toContain("incluir_secundarias");
  });

  it("Mais filtros: ligar envia a flag e mostra contador; desligar remove da URL e da API", async () => {
    const user = userEvent.setup();
    const { router, fetchSpy } = renderQuestoes({ path: `/questoes?taxonomia=${TAX_ID}&pagina=2` });
    await screen.findByText(/Questão Nº 7/);
    expect(screen.getByRole("button", { name: "Mais filtros" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Mais filtros" }));
    await user.click(await screen.findByRole("checkbox", { name: "Com divergência" }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("com_divergencia")).toBe("true"));
    expect(listagens(fetchSpy).at(-1)!.searchParams.get("pagina")).toBe("1");
    expect(listagens(fetchSpy).at(-1)!.searchParams.has("revisao_prioritaria")).toBe(false);
    expect(router.state.location.search).toContain("com_divergencia=true");
    expect(screen.getByRole("button", { name: "Mais filtros (1)" })).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Com divergência" }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.has("com_divergencia")).toBe(false));
    expect(router.state.location.search).not.toContain("com_divergencia");
  });

  it("Mais filtros: Tópico aplicado ao confirmar com Enter", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderQuestoes();
    await screen.findByText(/Questão Nº 7/);
    await user.click(screen.getByRole("button", { name: "Mais filtros" }));
    await user.type(await screen.findByLabelText("Tópico"), "roteamento-ospf{Enter}");
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("topico")).toBe("roteamento-ospf"));
  });

  it("busca textual grava q na URL após debounce", async () => {
    const user = userEvent.setup();
    const { router, fetchSpy } = renderQuestoes();
    await screen.findByText(/Questão Nº 7/);
    await user.type(screen.getByLabelText("Busca textual"), "ospf");
    expect(router.state.location.search).not.toContain("q=");
    await waitFor(() => expect(router.state.location.search).toContain("q=ospf"));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("q")).toBe("ospf"));
  });

  it("Revisar este recorte e card navegam para /revisao preservando o recorte", async () => {
    const user = userEvent.setup();
    const { router } = renderQuestoes({
      path: `/questoes?taxonomia=${TAX_ID}&q=ospf&disciplina_id=${DISC_ID}&incluir_secundarias=false&pagina=1`,
      total: 45,
    });
    const revisar = await screen.findByRole("link", { name: "Revisar este recorte (45)" });
    expect(revisar).toHaveAttribute("href", `/revisao?taxonomia=${TAX_ID}&q=ospf&disciplina_id=${DISC_ID}&incluir_secundarias=false`);
    expect(screen.getByRole("link", { name: /Questão Nº 7/ })).toHaveAttribute(
      "href",
      `/revisao?taxonomia=${TAX_ID}&q=ospf&disciplina_id=${DISC_ID}&incluir_secundarias=false&questao=q-1`,
    );
    await user.click(revisar);
    expect(router.state.location.pathname).toBe("/revisao");
    expect(router.state.location.search).toBe(`?taxonomia=${TAX_ID}&q=ospf&disciplina_id=${DISC_ID}&incluir_secundarias=false`);
  });

  it("paginação grava pagina na URL e refaz a consulta", async () => {
    const user = userEvent.setup();
    const { router, fetchSpy } = renderQuestoes({ total: 45 });
    expect(await screen.findByText("Página 1 de 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Anterior/ })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: /Próxima/ }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("pagina")).toBe("2"));
    expect(router.state.location.search).toContain("pagina=2");
    expect(await screen.findByText("Página 2 de 3")).toBeInTheDocument();
  });

  it("sem Provas mostra CTA Ingerir primeira prova", async () => {
    renderQuestoes({ provas: { itens: [], total: 0 }, itens: [] });
    const cta = await screen.findByRole("link", { name: "Ingerir primeira prova" });
    expect(cta).toHaveAttribute("href", `/provas?taxonomia=${TAX_ID}&acao=ingerir`);
    expect(screen.queryByRole("link", { name: /Revisar este recorte/ })).not.toBeInTheDocument();
  });

  it("filtros sem resultado mostram Limpar filtros, que mantém só a taxonomia", async () => {
    const user = userEvent.setup();
    const { router } = renderQuestoes({
      path: `/questoes?taxonomia=${TAX_ID}&q=zzz&com_divergencia=true&pagina=2`,
      itens: [],
    });
    expect(await screen.findByText("Nenhuma questão encontrada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revisar este recorte (0)" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Limpar filtros" }));
    await waitFor(() => expect(router.state.location.search).toBe(`?taxonomia=${TAX_ID}`));
  });

  it("sem filtros e sem resultados não oferece Limpar filtros", async () => {
    renderQuestoes({ itens: [] });
    expect(await screen.findByText("Nenhuma questão encontrada")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Limpar filtros" })).not.toBeInTheDocument();
  });

  it("erro na consulta mostra alerta e Tentar novamente", async () => {
    renderQuestoes({ questoesStatus: 500 });
    expect(await screen.findByText("Não foi possível carregar as Questões")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tentar novamente" })).toBeInTheDocument();
  });

  it("trocar a Taxonomia ativa refaz a consulta e descarta Disciplina, Tópico e página", async () => {
    const user = userEvent.setup();
    const { router, fetchSpy } = renderQuestoes({
      path: `/questoes?taxonomia=${TAX_ID}&disciplina_id=${DISC_ID}&topico=x&pagina=2&q=ospf`,
    });
    await screen.findByText(/Questão Nº 7/);
    await user.click(screen.getByRole("combobox", { name: "Taxonomia ativa" }));
    await user.click(await screen.findByRole("option", { name: /Outra Taxonomia/ }));
    await waitFor(() => expect(router.state.location.search).not.toContain("disciplina_id"));
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get("taxonomia")).toBe(TAX_OUTRA_ID);
    expect(params.get("q")).toBe("ospf");
    expect(params.has("topico")).toBe(false);
    expect(params.has("pagina")).toBe(false);
    await waitFor(() => {
      const ultima = listagens(fetchSpy).at(-1)!;
      expect(ultima.searchParams.get("taxonomia_id")).toBe(TAX_OUTRA_ID);
      expect(ultima.searchParams.has("disciplina_id")).toBe(false);
    });
  });

  // F1
  it("pagina além do total avisa, sem rótulo de paginação, e leva à última página válida", async () => {
    const user = userEvent.setup();
    const { router } = renderQuestoes({ path: `/questoes?taxonomia=${TAX_ID}&pagina=999`, itens: [], total: 45 });
    expect(await screen.findByText("Página 999 não existe")).toBeInTheDocument();
    expect(screen.queryByText("Nenhuma questão encontrada")).not.toBeInTheDocument();
    // G3: sem o rótulo contraditório "Página 999 de 3" ao lado do aviso.
    expect(screen.queryByText(/Página 999 de/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ir para a última página" }));
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get("pagina")).toBe("3"));
  });

  it("pagina além do total com uma única página válida remove pagina da URL", async () => {
    const user = userEvent.setup();
    const { router } = renderQuestoes({ path: `/questoes?taxonomia=${TAX_ID}&pagina=999`, itens: [], total: 5 });
    await user.click(await screen.findByRole("button", { name: "Ir para a última página" }));
    await waitFor(() => expect(router.state.location.search).toBe(`?taxonomia=${TAX_ID}`));
  });

  // F2
  it("não envia disciplina_id que não pertence à Taxonomia ativa nem ao href do recorte", async () => {
    const { fetchSpy } = renderQuestoes({
      path: `/questoes?taxonomia=${TAX_ID}&disciplina_id=99999999-9999-9999-9999-999999999999`,
    });
    const revisar = await screen.findByRole("link", { name: /Revisar este recorte/ });
    expect(listagens(fetchSpy).length).toBeGreaterThan(0);
    for (const url of listagens(fetchSpy)) {
      expect(url.searchParams.has("disciplina_id")).toBe(false);
    }
    expect(revisar.getAttribute("href")).not.toContain("disciplina_id");
  });

  // F3
  it("voltar Disciplina para Todas desmarca Somente principal e remove incluir_secundarias da URL", async () => {
    const user = userEvent.setup();
    const { router, fetchSpy } = renderQuestoes({
      path: `/questoes?taxonomia=${TAX_ID}&disciplina_id=${DISC_ID}&incluir_secundarias=false`,
    });
    await screen.findByText(/Questão Nº 7/);
    expect(screen.getByRole("checkbox", { name: "Somente principal" })).toBeChecked();
    await user.click(screen.getByRole("combobox", { name: "Disciplina" }));
    await user.click(await screen.findByRole("option", { name: "Todas" }));
    await waitFor(() => expect(router.state.location.search).not.toContain("incluir_secundarias"));
    expect(screen.getByRole("checkbox", { name: "Somente principal" })).not.toBeChecked();
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("incluir_secundarias")).toBe("true"));
  });

  // F5
  it("sem Taxonomia cadastrada mostra mensagem com link para Taxonomias, sem skeleton eterno", async () => {
    renderQuestoes({ taxonomias: { itens: [], total: 0 }, path: "/questoes" });
    expect(await screen.findByText("Nenhuma Taxonomia cadastrada")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cadastrar Taxonomia" })).toHaveAttribute("href", "/taxonomias");
    expect(screen.queryByLabelText("Carregando Questões")).not.toBeInTheDocument();
  });

  it("erro ao carregar Taxonomias mostra alerta com Tentar novamente que refaz a consulta", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderQuestoes({ taxonomiasStatus: 500, path: "/questoes" });
    expect(await screen.findByText("Não foi possível carregar as Taxonomias")).toBeInTheDocument();
    expect(screen.queryByLabelText("Carregando Questões")).not.toBeInTheDocument();
    const antes = fetchSpy.mock.calls.filter(([i]) => String(i).includes("/api/v1/taxonomias")).length;
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await waitFor(() =>
      expect(fetchSpy.mock.calls.filter(([i]) => String(i).includes("/api/v1/taxonomias")).length).toBeGreaterThan(antes),
    );
  });

  // F6
  it("trocar a Taxonomia não consulta a nova Taxonomia com Disciplina, Tópico ou página antigos", async () => {
    const user = userEvent.setup();
    const { router, fetchSpy } = renderQuestoes({
      path: `/questoes?taxonomia=${TAX_ID}&disciplina_id=${DISC_ID}&topico=x&pagina=2`,
    });
    await screen.findByText(/Questão Nº 7/);
    await user.click(screen.getByRole("combobox", { name: "Taxonomia ativa" }));
    await user.click(await screen.findByRole("option", { name: /Outra Taxonomia/ }));
    await waitFor(() => expect(router.state.location.search).not.toContain("topico"));
    await waitFor(() =>
      expect(listagens(fetchSpy).some((u) => u.searchParams.get("taxonomia_id") === TAX_OUTRA_ID)).toBe(true),
    );
    for (const url of listagens(fetchSpy).filter((u) => u.searchParams.get("taxonomia_id") === TAX_OUTRA_ID)) {
      expect(url.searchParams.has("disciplina_id")).toBe(false);
      expect(url.searchParams.has("topico")).toBe(false);
      expect(url.searchParams.get("pagina")).toBe("1");
    }
  });

  // F7
  it("não mostra contador nem botão Revisar este recorte antes da primeira resposta", async () => {
    let liberar!: () => void;
    const questoesGate = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    renderQuestoes({ questoesGate });
    await screen.findByLabelText("Carregando Questões");
    expect(screen.queryByText(/Revisar este recorte/)).not.toBeInTheDocument();
    liberar();
    expect(await screen.findByRole("link", { name: "Revisar este recorte (1)" })).toBeInTheDocument();
  });

  // F9
  it("filtros Prova, Ano e Status de revisão enviam seus params", async () => {
    const user = userEvent.setup();
    const { router, fetchSpy } = renderQuestoes();
    await screen.findByText(/Questão Nº 7/);

    await user.click(screen.getByRole("combobox", { name: "Prova" }));
    await user.click(await screen.findByRole("option", { name: "ENADE Computação 2023" }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("prova_id")).toBe(PROVA_ID));

    await user.click(screen.getByRole("combobox", { name: "Ano" }));
    await user.click(await screen.findByRole("option", { name: "2023" }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("ano")).toBe("2023"));

    await user.click(screen.getByRole("combobox", { name: "Status de revisão" }));
    await user.click(await screen.findByRole("option", { name: "Pendente de revisão" }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("status_revisao")).toBe("pendente_revisao"));
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get("prova_id")).toBe(PROVA_ID);
    expect(params.get("ano")).toBe("2023");
    expect(params.get("status_revisao")).toBe("pendente_revisao");
  });

  it("Mais filtros: Situação do gabarito e as flags restantes enviam seus params e somam ao contador", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderQuestoes();
    await screen.findByText(/Questão Nº 7/);
    await user.click(screen.getByRole("button", { name: "Mais filtros" }));

    await user.click(await screen.findByRole("combobox", { name: "Situação do gabarito" }));
    await user.click(await screen.findByRole("option", { name: /anulad/i }));
    await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get("situacao_gabarito")).toBe("anulada"));

    for (const [label, key] of [
      ["Com alerta de extração", "com_alerta_extracao"],
      ["Revisão prioritária", "revisao_prioritaria"],
      ["Usa disciplina arquivada", "usa_disciplina_arquivada"],
    ] as const) {
      await user.click(screen.getByRole("checkbox", { name: label }));
      await waitFor(() => expect(listagens(fetchSpy).at(-1)!.searchParams.get(key)).toBe("true"));
    }
    expect(screen.getByRole("button", { name: "Mais filtros (4)" })).toBeInTheDocument();
  });

  // G2
  it("aceita disciplina_id em maiúsculas e envia o id como está na Taxonomia", async () => {
    const discHex = "abcdefab-cdef-abcd-efab-cdefabcdefab";
    const taxonomias: ListaTaxonomiasResponse = {
      ...TAXONOMIAS,
      itens: [
        {
          ...TAXONOMIAS.itens[0],
          disciplinas: [{ ...TAXONOMIAS.itens[0].disciplinas[0], id: discHex }],
        },
        TAXONOMIAS.itens[1],
      ],
    };
    const { fetchSpy } = renderQuestoes({
      path: `/questoes?taxonomia=${TAX_ID}&disciplina_id=${discHex.toUpperCase()}`,
      taxonomias,
    });
    await screen.findByText(/Questão Nº 7/);
    expect(listagens(fetchSpy).at(-1)!.searchParams.get("disciplina_id")).toBe(discHex);
  });

  // G4
  it("mantém total e Revisar este recorte durante a troca de página dentro da mesma Taxonomia", async () => {
    const user = userEvent.setup();
    let liberar!: () => void;
    const questoesGatePagina2 = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    renderQuestoes({ itens: [makeItem()], total: 45, questoesGatePagina2 });
    await screen.findByRole("link", { name: "Revisar este recorte (45)" });
    await user.click(screen.getByRole("button", { name: /Próxima/ }));
    await waitFor(() => expect(screen.getByRole("navigation", { name: "Paginação" })).toBeInTheDocument());
    expect(screen.getByTestId("questoes-total")).toHaveTextContent("45");
    // H1: durante o placeholder o botão fica visível porém desabilitado (antes era link).
    expect(screen.getByRole("button", { name: "Revisar este recorte (45)" })).toBeDisabled();
    liberar();
  });

  // G4 (F6): o placeholder não atravessa a troca de Taxonomia
  it("não exibe o total da Taxonomia anterior enquanto a nova carrega", async () => {
    const user = userEvent.setup();
    let liberar!: () => void;
    const questoesGateOutraTaxonomia = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    renderQuestoes({ itens: [makeItem()], total: 45, questoesGateOutraTaxonomia });
    await screen.findByRole("link", { name: "Revisar este recorte (45)" });
    await user.click(screen.getByRole("combobox", { name: "Taxonomia ativa" }));
    await user.click(await screen.findByRole("option", { name: /Outra Taxonomia/ }));
    await waitFor(() => expect(screen.queryByText(/Revisar este recorte/)).not.toBeInTheDocument());
    liberar();
  });

  // H1
  it("desabilita Revisar este recorte e os cards enquanto o dado exibido é de filtros anteriores", async () => {
    let liberar!: () => void;
    const questoesGateStatus = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    const { router } = renderQuestoes({ itens: [makeItem()], total: 45, questoesGateStatus });
    await screen.findByRole("link", { name: "Revisar este recorte (45)" });
    await act(async () => {
      await router.navigate(`/questoes?taxonomia=${TAX_ID}&status_revisao=pendente`);
    });
    await waitFor(() => expect(screen.queryByRole("link", { name: "Revisar este recorte (45)" })).not.toBeInTheDocument());
    expect(screen.getByTestId("questoes-total")).toHaveTextContent("45");
    expect(screen.getByRole("button", { name: "Revisar este recorte (45)" })).toBeDisabled();
    expect(screen.getByText(/Questão Nº 7/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Questão Nº 7/ })).not.toBeInTheDocument();
    liberar();
    expect(await screen.findByRole("link", { name: "Revisar este recorte (45)" })).toHaveAttribute(
      "href",
      expect.stringContaining("status_revisao=pendente"),
    );
  });

  // H2
  it("não exibe o estado vazio do recorte anterior enquanto o novo filtro carrega", async () => {
    let liberar!: () => void;
    const questoesGateStatus = new Promise<void>((resolve) => {
      liberar = resolve;
    });
    const { router } = renderQuestoes({ itens: [], total: 0, questoesGateStatus });
    await screen.findByText("Nenhuma questão encontrada");
    await act(async () => {
      await router.navigate(`/questoes?taxonomia=${TAX_ID}&status_revisao=pendente`);
    });
    await waitFor(() => expect(screen.getByLabelText("Carregando Questões")).toBeInTheDocument());
    expect(screen.queryByText("Nenhuma Questão corresponde aos filtros aplicados.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Limpar filtros" })).not.toBeInTheDocument();
    // I1: cabeçalho do recorte vazio anterior também não aparece.
    expect(screen.queryByText("0 questão(ões)")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revisar este recorte (0)" })).not.toBeInTheDocument();
    liberar();
  });
});
