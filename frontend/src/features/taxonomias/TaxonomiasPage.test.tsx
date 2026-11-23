import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { HealthResponse } from "@/api/client";
import type {
  ExecucaoClassificacaoResumoResponse,
  ListaExecucoesClassificacaoResponse,
} from "@/api/operacao";
import type {
  ListaPerfisClassificacaoResponse,
  ListaTaxonomiasResponse,
  TaxonomiaResponse,
} from "@/api/taxonomias";
import { POLL_INTERVAL_MS } from "@/api/provas";
import { ROUTER_FUTURE_FLAGS, createAppRoutes } from "@/app/router";

const TAX_ID = "22222222-2222-2222-2222-222222222222";
const TAX_NOVA_ID = "55555555-5555-5555-5555-555555555555";
const PERFIL_ID = "33333333-3333-3333-3333-333333333333";
const DISC_ID = "66666666-6666-6666-6666-666666666666";
const DISC_ARQ_ID = "77777777-7777-7777-7777-777777777777";

const TAXONOMIA: TaxonomiaResponse = {
  id: TAX_ID,
  codigo: "enade-eng-computacao",
  nome: "ENADE Engenharia de Computação",
  curso_referencia: "Engenharia de Computação",
  disciplinas: [
    {
      id: DISC_ID,
      taxonomia_id: TAX_ID,
      codigo: "algoritmos",
      nome: "Algoritmos",
      ementa: "Estruturas de dados",
      ativa: true,
      classificacoes_vigentes_impactadas: 7,
    },
    {
      id: DISC_ARQ_ID,
      taxonomia_id: TAX_ID,
      codigo: "legado",
      nome: "Legado",
      ementa: "",
      ativa: false,
      classificacoes_vigentes_impactadas: 2,
    },
  ],
};

const PERFIS: ListaPerfisClassificacaoResponse = {
  itens: [
    {
      id: PERFIL_ID,
      codigo: "v2-fronteiras",
      versao: "v1",
      diretrizes_gerais: "Diretriz base",
      guia_fronteiras: "Fronteira base",
      template_prompt: "TEMPLATE-BASE {{questao}}",
      descricao: "Perfil padrão",
    },
  ],
  total: 1,
};

const IDLE_HEALTH: HealthResponse = {
  status: "ok",
  banco_dados: "conectado",
  worker: { estado: "ocioso", tarefa_ativa: null },
};

function makeExecucao(
  overrides: Partial<ExecucaoClassificacaoResumoResponse>,
): ExecucaoClassificacaoResumoResponse {
  return {
    id: "exec-1",
    taxonomia_id: TAX_ID,
    perfil_id: PERFIL_ID,
    escopo: "todas",
    escopo_questao_ids: [],
    incluir_revisadas: false,
    status: "concluida",
    total_itens: 10,
    processadas: 10,
    total_erros: 0,
    divergencias_abertas: 3,
    cache_hits: 4,
    prompt_tokens: 1200,
    completion_tokens: 300,
    criada_em: "2026-11-22T18:30:00Z",
    snapshot_resumo: {
      taxonomia: {
        codigo: "enade-eng-computacao",
        nome: "ENADE Engenharia de Computação",
        curso_referencia: "Engenharia de Computação",
        total_disciplinas: 2,
      },
      perfil: { codigo: "v2-fronteiras", versao: "v1", descricao: "Perfil padrão" },
    },
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

type Handler = (url: URL, init?: RequestInit) => Response | undefined | Promise<Response | undefined>;

function renderTaxonomias(options?: { path?: string; handler?: Handler }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(createAppRoutes(), {
    initialEntries: [options?.path ?? "/taxonomias"],
    future: ROUTER_FUTURE_FLAGS,
  });

  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const raw =
      typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const url = new URL(raw, "http://localhost");
    const custom = options?.handler ? await options.handler(url, init) : undefined;
    if (custom) {
      return custom;
    }
    if (url.pathname === "/api/v1/taxonomias") {
      const body: ListaTaxonomiasResponse = { itens: [TAXONOMIA], total: 1 };
      return jsonResponse(body);
    }
    if (url.pathname === "/api/v1/perfis-classificacao") {
      return jsonResponse(PERFIS);
    }
    if (url.pathname === "/api/v1/health") {
      return jsonResponse(IDLE_HEALTH);
    }
    if (url.pathname === "/api/v1/execucoes-classificacao") {
      const body: ListaExecucoesClassificacaoResponse = { itens: [], total: 0 };
      return jsonResponse(body);
    }
    if (url.pathname === "/api/v1/provas") {
      return jsonResponse({ itens: [], total: 0 });
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

function bodyOf(init?: RequestInit): Record<string, unknown> {
  return JSON.parse(String(init?.body)) as Record<string, unknown>;
}

function callsTo(
  fetchSpy: { mock: { calls: unknown[][] } },
  method: string,
  pathname: string,
): [string, RequestInit][] {
  return (fetchSpy.mock.calls as unknown as [string, RequestInit][]).filter(
    ([url, init]) =>
      new URL(url, "http://localhost").pathname === pathname && (init?.method ?? "GET") === method,
  );
}

async function escolher(
  user: ReturnType<typeof userEvent.setup>,
  dialog: HTMLElement,
  rotulo: string,
  opcao: string,
) {
  await user.click(within(dialog).getByRole("combobox", { name: rotulo }));
  await user.click(await screen.findByRole("option", { name: opcao }));
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

describe("Taxonomias: CRUD de Taxonomia e Disciplina", () => {
  it("cria Taxonomia com codigo obrigatório e ativa a nova no seletor após o refetch", async () => {
    const user = userEvent.setup();
    let criada = false;
    const nova: TaxonomiaResponse = {
      id: TAX_NOVA_ID,
      codigo: "nova-tax",
      nome: "Nova Taxonomia X",
      curso_referencia: "Curso X",
      disciplinas: [],
    };

    const { router, fetchSpy } = renderTaxonomias({
      handler: (url, init) => {
        if (url.pathname === "/api/v1/taxonomias" && init?.method === "POST") {
          criada = true;
          return jsonResponse(nova, 201);
        }
        if (url.pathname === "/api/v1/taxonomias" && criada) {
          return jsonResponse({ itens: [TAXONOMIA, nova], total: 2 });
        }
        return undefined;
      },
    });

    await user.click(await screen.findByRole("button", { name: "Nova Taxonomia" }));
    const dialog = await screen.findByRole("dialog");

    await user.type(within(dialog).getByLabelText("Nome"), "Nova Taxonomia X");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));
    expect(await within(dialog).findByText("Informe o código da Taxonomia.")).toBeInTheDocument();
    expect(callsTo(fetchSpy, "POST", "/api/v1/taxonomias")).toHaveLength(0);

    await user.type(within(dialog).getByLabelText("Código"), "nova-tax");
    await user.type(within(dialog).getByLabelText("Curso de referência"), "Curso X");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(callsTo(fetchSpy, "POST", "/api/v1/taxonomias")).toHaveLength(1));
    expect(bodyOf(callsTo(fetchSpy, "POST", "/api/v1/taxonomias")[0][1])).toEqual({
      codigo: "nova-tax",
      nome: "Nova Taxonomia X",
      curso_referencia: "Curso X",
    });

    await waitFor(() =>
      expect(new URLSearchParams(router.state.location.search).get("taxonomia")).toBe(TAX_NOVA_ID),
    );
    expect(await screen.findByTestId("taxonomia-ativa")).toHaveTextContent("Nova Taxonomia X");
  });

  it("edita Taxonomia enviando só nome e curso_referencia, com codigo somente leitura", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderTaxonomias({
      handler: (url, init) =>
        url.pathname === `/api/v1/taxonomias/${TAX_ID}` && init?.method === "PATCH"
          ? jsonResponse({ ...TAXONOMIA, nome: "Renomeada" })
          : undefined,
    });

    await user.click(await screen.findByRole("button", { name: "Editar Taxonomia" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Código")).toHaveAttribute("readonly");

    const nome = within(dialog).getByLabelText("Nome");
    await user.clear(nome);
    await user.type(nome, "Renomeada");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));

    await waitFor(() =>
      expect(callsTo(fetchSpy, "PATCH", `/api/v1/taxonomias/${TAX_ID}`)).toHaveLength(1),
    );
    expect(bodyOf(callsTo(fetchSpy, "PATCH", `/api/v1/taxonomias/${TAX_ID}`)[0][1])).toEqual({
      nome: "Renomeada",
      curso_referencia: "Engenharia de Computação",
    });
  });

  it("cria Disciplina com codigo e edita com codigo somente leitura (sem enviar codigo)", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderTaxonomias({
      handler: (url, init) => {
        if (url.pathname === `/api/v1/taxonomias/${TAX_ID}/disciplinas` && init?.method === "POST") {
          return jsonResponse({ ...TAXONOMIA.disciplinas[0], id: "d-novo" }, 201);
        }
        if (url.pathname === `/api/v1/disciplinas/${DISC_ID}` && init?.method === "PATCH") {
          return jsonResponse(TAXONOMIA.disciplinas[0]);
        }
        return undefined;
      },
    });

    await user.click(await screen.findByRole("button", { name: "Nova Disciplina" }));
    let dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Código"), "redes");
    await user.type(within(dialog).getByLabelText("Nome"), "Redes");
    await user.type(within(dialog).getByLabelText("Ementa"), "TCP/IP");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));

    const postPath = `/api/v1/taxonomias/${TAX_ID}/disciplinas`;
    await waitFor(() => expect(callsTo(fetchSpy, "POST", postPath)).toHaveLength(1));
    expect(bodyOf(callsTo(fetchSpy, "POST", postPath)[0][1])).toMatchObject({
      codigo: "redes",
      nome: "Redes",
      ementa: "TCP/IP",
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Editar Disciplina Algoritmos" }));
    dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Código")).toHaveValue("algoritmos");
    expect(within(dialog).getByLabelText("Código")).toHaveAttribute("readonly");
    const nome = within(dialog).getByLabelText("Nome");
    await user.clear(nome);
    await user.type(nome, "Algoritmos II");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));

    const patchPath = `/api/v1/disciplinas/${DISC_ID}`;
    await waitFor(() => expect(callsTo(fetchSpy, "PATCH", patchPath)).toHaveLength(1));
    expect(bodyOf(callsTo(fetchSpy, "PATCH", patchPath)[0][1])).toEqual({
      nome: "Algoritmos II",
      ementa: "Estruturas de dados",
    });
  });
});

describe("Taxonomias: arquivar e reativar Disciplina", () => {
  it("mostra a contagem de Classificações vigentes impactadas e envia ativa=false", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderTaxonomias({
      handler: (url, init) =>
        url.pathname === `/api/v1/disciplinas/${DISC_ID}` && init?.method === "PATCH"
          ? jsonResponse({ ...TAXONOMIA.disciplinas[0], ativa: false })
          : undefined,
    });

    await user.click(await screen.findByRole("button", { name: "Arquivar Disciplina Algoritmos" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByTestId("impacto-classificacoes")).toHaveTextContent(
      "7 Classificações vigentes será marcada",
    );
    expect(callsTo(fetchSpy, "PATCH", `/api/v1/disciplinas/${DISC_ID}`)).toHaveLength(0);

    await user.click(within(dialog).getByRole("button", { name: "Confirmar arquivamento" }));
    await waitFor(() =>
      expect(callsTo(fetchSpy, "PATCH", `/api/v1/disciplinas/${DISC_ID}`)).toHaveLength(1),
    );
    expect(bodyOf(callsTo(fetchSpy, "PATCH", `/api/v1/disciplinas/${DISC_ID}`)[0][1])).toEqual({
      ativa: false,
    });
  });

  it("reativa Disciplina arquivada enviando ativa=true", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderTaxonomias({
      handler: (url, init) =>
        url.pathname === `/api/v1/disciplinas/${DISC_ARQ_ID}` && init?.method === "PATCH"
          ? jsonResponse({ ...TAXONOMIA.disciplinas[1], ativa: true })
          : undefined,
    });

    await user.click(await screen.findByRole("button", { name: "Reativar Disciplina Legado" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByTestId("impacto-classificacoes")).toHaveTextContent(
      "2 Classificações vigentes",
    );
    await user.click(within(dialog).getByRole("button", { name: "Confirmar reativação" }));

    await waitFor(() =>
      expect(callsTo(fetchSpy, "PATCH", `/api/v1/disciplinas/${DISC_ARQ_ID}`)).toHaveLength(1),
    );
    expect(bodyOf(callsTo(fetchSpy, "PATCH", `/api/v1/disciplinas/${DISC_ARQ_ID}`)[0][1])).toEqual({
      ativa: true,
    });
  });
});

describe("Taxonomias: Perfis", () => {
  it("lista perfil com template em Avançado e cria nova versão pré-preenchida", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderTaxonomias({
      path: "/taxonomias?aba=perfis",
      handler: (url, init) =>
        url.pathname === "/api/v1/perfis-classificacao" && init?.method === "POST"
          ? jsonResponse({ ...PERFIS.itens[0], id: "novo", versao: "v2" }, 201)
          : undefined,
    });

    const card = await screen.findByTestId(`perfil-card-${PERFIL_ID}`);
    expect(within(card).getByText("Diretriz base")).toBeInTheDocument();
    const avancado = card.querySelector("details");
    expect(avancado).not.toBeNull();
    expect(avancado).not.toHaveAttribute("open");
    expect(avancado).toHaveTextContent("TEMPLATE-BASE");

    await user.click(within(card).getByRole("button", { name: /Criar nova versão/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Diretrizes gerais")).toHaveValue("Diretriz base");
    expect(within(dialog).getByLabelText("Guia de fronteiras")).toHaveValue("Fronteira base");
    const detailsDialog = dialog.querySelector("details");
    expect(detailsDialog).not.toHaveAttribute("open");
    expect(detailsDialog).toContainElement(within(dialog).getByLabelText("Template do prompt", { selector: "textarea" }));

    await user.click(within(dialog).getByRole("button", { name: "Criar versão" }));
    expect(
      await within(dialog).findByText("Informe o identificador da nova versão."),
    ).toBeInTheDocument();

    await user.type(within(dialog).getByLabelText("Versão"), "v2");
    const diretrizes = within(dialog).getByLabelText("Diretrizes gerais");
    await user.clear(diretrizes);
    await user.type(diretrizes, "Diretriz editada");
    await user.click(within(dialog).getByRole("button", { name: "Criar versão" }));

    await waitFor(() =>
      expect(callsTo(fetchSpy, "POST", "/api/v1/perfis-classificacao")).toHaveLength(1),
    );
    expect(bodyOf(callsTo(fetchSpy, "POST", "/api/v1/perfis-classificacao")[0][1])).toMatchObject({
      perfil_base_id: PERFIL_ID,
      codigo: "v2-fronteiras",
      versao: "v2",
      diretrizes_gerais: "Diretriz editada",
      guia_fronteiras: "Fronteira base",
      template_prompt: "TEMPLATE-BASE {{questao}}",
    });
  });
});

describe("Taxonomias: Execuções", () => {
  it("dispara Execução com incluir_revisadas=false por padrão e escopo todas", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: (url, init) =>
        url.pathname === "/api/v1/execucoes-classificacao" && init?.method === "POST"
          ? jsonResponse({ execucao_id: "nova" }, 202)
          : undefined,
    });

    await user.click(await screen.findByRole("button", { name: "Nova Execução" }));
    const dialog = await screen.findByRole("dialog");
    const checkbox = within(dialog).getByRole("checkbox", {
      name: "Incluir questões já revisadas por humano",
    });
    expect(checkbox).not.toBeChecked();
    expect(within(dialog).getByText(/nunca são sobrescritas automaticamente/)).toBeInTheDocument();

    await waitFor(() =>
      expect(within(dialog).getByRole("combobox", { name: "Perfil de Classificação" })).toHaveTextContent("v2-fronteiras · v1"),
    );
    await user.click(within(dialog).getByRole("button", { name: "Iniciar Execução" }));

    await waitFor(() =>
      expect(callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao")).toHaveLength(1),
    );
    expect(bodyOf(callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao")[0][1])).toEqual({
      taxonomia_id: TAX_ID,
      perfil_id: PERFIL_ID,
      escopo: "todas",
      incluir_revisadas: false,
    });
  });

  it("suporta escopo por Prova (exige prova_id) e opt-in de incluir_revisadas", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: (url, init) => {
        if (url.pathname === "/api/v1/provas") {
          return jsonResponse({
            itens: [{ id: "prova-9", exame: "ENADE", curso: "Computação", ano: 2023 }],
            total: 1,
          });
        }
        if (url.pathname === "/api/v1/execucoes-classificacao" && init?.method === "POST") {
          return jsonResponse({ execucao_id: "nova" }, 202);
        }
        return undefined;
      },
    });

    await user.click(await screen.findByRole("button", { name: "Nova Execução" }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() =>
      expect(within(dialog).getByRole("combobox", { name: "Perfil de Classificação" })).toHaveTextContent("v2-fronteiras · v1"),
    );

    await escolher(user, dialog, "Escopo", "Por Prova");
    await user.click(within(dialog).getByRole("checkbox"));
    await user.click(within(dialog).getByRole("button", { name: "Iniciar Execução" }));
    expect(await within(dialog).findByText("Selecione a Prova do escopo.")).toBeInTheDocument();
    expect(callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao")).toHaveLength(0);

    await within(dialog).findByRole("combobox", { name: "Prova" });
    await escolher(user, dialog, "Prova", "ENADE 2023 · Computação");
    await user.click(within(dialog).getByRole("button", { name: "Iniciar Execução" }));

    await waitFor(() =>
      expect(callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao")).toHaveLength(1),
    );
    expect(bodyOf(callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao")[0][1])).toEqual({
      taxonomia_id: TAX_ID,
      perfil_id: PERFIL_ID,
      escopo: "prova_id",
      prova_id: "prova-9",
      incluir_revisadas: true,
    });
  });

  it("oferece os escopos pendentes e disciplina_arquivada", async () => {
    const user = userEvent.setup();
    renderTaxonomias({ path: "/taxonomias?aba=execucoes" });
    await user.click(await screen.findByRole("button", { name: "Nova Execução" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("combobox", { name: "Escopo" }));
    const rotulos = (await screen.findAllByRole("option")).map((option) => option.textContent);
    expect(rotulos).toEqual([
      "Todas as questões",
      "Por Prova",
      "Apenas não classificadas (pendentes)",
      "Com Disciplina arquivada",
    ]);
  });

  it("exibe métricas e habilita retomada apenas para interrompida e concluida_com_erros", async () => {
    const user = userEvent.setup();
    const itens = [
      makeExecucao({ id: "e-ok", status: "concluida" }),
      makeExecucao({ id: "e-int", status: "interrompida", processadas: 4, total_erros: 2 }),
      makeExecucao({ id: "e-err", status: "concluida_com_erros", total_erros: 3 }),
      makeExecucao({ id: "e-run", status: "processando", processadas: 1 }),
    ];
    let retomada = false;
    const { fetchSpy } = renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: (url, init) => {
        if (url.pathname === "/api/v1/execucoes-classificacao" && !init?.method) {
          // Só responde à consulta da Taxonomia ativa; a da pílula (sem filtro) segue o padrão.
          if (!url.searchParams.has("taxonomia_id")) {
            return undefined;
          }
          const atual = retomada
            ? itens.map((item) => (item.id === "e-int" ? { ...item, status: "processando" as const } : item))
            : itens;
          return jsonResponse({ itens: atual, total: atual.length });
        }
        if (url.pathname === "/api/v1/execucoes-classificacao/e-int/retomar") {
          retomada = true;
          return jsonResponse({ execucao_id: "e-int" }, 202);
        }
        return undefined;
      },
    });

    // Espera o estado resolvido (os quatro cards da Taxonomia ativa) antes de asserir.
    const ok = await screen.findByTestId("execucao-card-e-ok");
    await screen.findByTestId("execucao-card-e-run");
    expect(within(ok).getByText("10/10")).toBeInTheDocument();
    expect(within(ok).getByText("1200")).toBeInTheDocument();
    expect(within(ok).getByText("Divergências na rodada")).toBeInTheDocument();

    const botao = (id: string) =>
      within(screen.getByTestId(`execucao-card-${id}`)).getByRole("button", {
        name: /Retomar \/ Reprocessar falhas/,
      });
    expect(botao("e-ok")).toBeDisabled();
    expect(botao("e-run")).toBeDisabled();
    expect(botao("e-int")).toBeEnabled();
    expect(botao("e-err")).toBeEnabled();

    await user.click(botao("e-int"));
    await waitFor(() =>
      expect(
        callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao/e-int/retomar"),
      ).toHaveLength(1),
    );
    // A lista é refeita depois da retomada: e-int passa a processando e o botão se desabilita.
    await waitFor(() => expect(botao("e-int")).toBeDisabled());
    expect(
      within(screen.getByTestId("execucao-card-e-int")).getByText("Processando"),
    ).toBeInTheDocument();
  });

  it("faz polling enquanto há rodada processando e para ao concluir", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let chamadas = 0;
    renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: (url, init) => {
        if (
          url.pathname === "/api/v1/execucoes-classificacao" &&
          !init?.method &&
          url.searchParams.has("taxonomia_id")
        ) {
          chamadas += 1;
          const status = chamadas === 1 ? "processando" : "concluida";
          return jsonResponse({ itens: [makeExecucao({ id: "e-1", status })], total: 1 });
        }
        return undefined;
      },
    });

    const card = await screen.findByTestId("execucao-card-e-1");
    expect(within(card).getByText("Processando")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS + 100);
    });
    await waitFor(() => expect(within(card).getByText("Concluída")).toBeInTheDocument());
    const aposConcluir = chamadas;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3);
    });
    expect(chamadas).toBe(aposConcluir);
  });
});

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("Taxonomias: regressões da revisão (M2, A1, C1-C4, m1)", () => {
  it("M2: sem Taxonomia ativa a aba não mostra rodadas de outra Taxonomia vindas do cache da pílula", async () => {
    const { queryClient } = renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: (url, init) => {
        if (url.pathname === "/api/v1/taxonomias" && !init?.method) {
          return jsonResponse({ itens: [], total: 0 });
        }
        if (url.pathname === "/api/v1/execucoes-classificacao" && !init?.method) {
          return jsonResponse({ itens: [makeExecucao({ id: "e-outra" })], total: 1 });
        }
        return undefined;
      },
    });

    // A pílula (sem taxonomiaId) popula a chave list(null) com a rodada de outra Taxonomia.
    await waitFor(() =>
      expect(queryClient.getQueryData(["execucoes-classificacao", "list", null])).toBeDefined(),
    );
    expect(
      await screen.findByText("Selecione uma Taxonomia para ver as Execuções."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("execucao-card-e-outra")).not.toBeInTheDocument();
  });

  it("A1: não cria versão de Perfil com diretrizes_gerais ou template_prompt vazios", async () => {
    const user = userEvent.setup();
    const { fetchSpy } = renderTaxonomias({ path: "/taxonomias?aba=perfis" });

    const card = await screen.findByTestId(`perfil-card-${PERFIL_ID}`);
    await user.click(within(card).getByRole("button", { name: /Criar nova versão/ }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Versão"), "v2");
    await user.clear(within(dialog).getByLabelText("Diretrizes gerais"));
    await user.clear(within(dialog).getByLabelText("Template do prompt", { selector: "textarea" }));
    await user.click(within(dialog).getByRole("button", { name: "Criar versão" }));

    expect(
      await within(dialog).findByText("Informe as diretrizes gerais."),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Informe o template do prompt.")).toBeInTheDocument();
    expect(callsTo(fetchSpy, "POST", "/api/v1/perfis-classificacao")).toHaveLength(0);
  });

  it("C1: seleciona a Taxonomia criada mesmo quando o refetch da lista falha", async () => {
    const user = userEvent.setup();
    let criada = false;
    const nova: TaxonomiaResponse = {
      id: TAX_NOVA_ID,
      codigo: "nova-tax",
      nome: "Nova Taxonomia X",
      curso_referencia: "",
      disciplinas: [],
    };
    const { router } = renderTaxonomias({
      handler: (url, init) => {
        if (url.pathname === "/api/v1/taxonomias" && init?.method === "POST") {
          criada = true;
          return jsonResponse(nova, 201);
        }
        if (url.pathname === "/api/v1/taxonomias" && criada) {
          return jsonResponse({ detail: "falha" }, 500);
        }
        return undefined;
      },
    });

    await user.click(await screen.findByRole("button", { name: "Nova Taxonomia" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Código"), "nova-tax");
    await user.type(within(dialog).getByLabelText("Nome"), "Nova Taxonomia X");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));

    await waitFor(() =>
      expect(new URLSearchParams(router.state.location.search).get("taxonomia")).toBe(TAX_NOVA_ID),
    );
    expect(await screen.findByTestId("taxonomia-ativa")).toHaveTextContent("Nova Taxonomia X");
    // O refetch falhou: o diálogo não fecha em silêncio e avisa o usuário.
    expect(
      await within(screen.getByRole("dialog")).findByText(
        "Taxonomia salva, mas a lista não foi atualizada",
      ),
    ).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Salvar" })).toBeDisabled();
  });

  it("C2: duas retomadas concorrentes mantêm ambos os botões desabilitados e não duplicam POST", async () => {
    const user = userEvent.setup();
    const itens = [
      makeExecucao({ id: "e-a", status: "interrompida" }),
      makeExecucao({ id: "e-b", status: "interrompida" }),
    ];
    const gateA = deferred();
    const gateB = deferred();
    const { fetchSpy } = renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: async (url, init) => {
        if (url.pathname === "/api/v1/execucoes-classificacao" && !init?.method) {
          return url.searchParams.has("taxonomia_id")
            ? jsonResponse({ itens, total: 2 })
            : undefined;
        }
        if (url.pathname === "/api/v1/execucoes-classificacao/e-a/retomar") {
          await gateA.promise;
          return jsonResponse({ execucao_id: "e-a" }, 202);
        }
        if (url.pathname === "/api/v1/execucoes-classificacao/e-b/retomar") {
          await gateB.promise;
          return jsonResponse({ execucao_id: "e-b" }, 202);
        }
        return undefined;
      },
    });

    const botao = (id: string) =>
      within(screen.getByTestId(`execucao-card-${id}`)).getByRole("button", {
        name: /Retomar \/ Reprocessar falhas/,
      });
    await screen.findByTestId("execucao-card-e-b");

    await user.click(botao("e-a"));
    await user.click(botao("e-b"));
    await waitFor(() => expect(botao("e-b")).toBeDisabled());
    expect(botao("e-a")).toBeDisabled();

    await user.click(botao("e-a"));
    expect(callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao/e-a/retomar")).toHaveLength(1);

    gateA.resolve();
    gateB.resolve();
  });

  it("C2: trocar de aba com a retomada em voo mantém o botão desabilitado e gera um POST por rodada", async () => {
    const user = userEvent.setup();
    const itens = [
      makeExecucao({ id: "e-a", status: "interrompida" }),
      makeExecucao({ id: "e-b", status: "interrompida" }),
    ];
    const gates = { "e-a": deferred(), "e-b": deferred() };
    const { fetchSpy } = renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: async (url, init) => {
        if (url.pathname === "/api/v1/execucoes-classificacao" && !init?.method) {
          return url.searchParams.has("taxonomia_id")
            ? jsonResponse({ itens, total: 2 })
            : undefined;
        }
        for (const id of ["e-a", "e-b"] as const) {
          if (url.pathname === `/api/v1/execucoes-classificacao/${id}/retomar`) {
            await gates[id].promise;
            return jsonResponse({ execucao_id: id }, 202);
          }
        }
        return undefined;
      },
    });

    const botao = (id: string) =>
      within(screen.getByTestId(`execucao-card-${id}`)).getByRole("button", {
        name: /Retomar \/ Reprocessar falhas/,
      });
    async function irParaAba(nome: string) {
      await user.click(screen.getByRole("tab", { name: nome }));
    }

    for (const id of ["e-a", "e-b"] as const) {
      await screen.findByTestId(`execucao-card-${id}`);
      await user.click(botao(id));
      await waitFor(() => expect(botao(id)).toBeDisabled());

      await irParaAba("Perfis");
      await screen.findByTestId(`perfil-card-${PERFIL_ID}`);
      await irParaAba("Execuções");
      await screen.findByTestId(`execucao-card-${id}`);

      expect(botao(id)).toBeDisabled();
      await user.click(botao(id));
      expect(
        callsTo(fetchSpy, "POST", `/api/v1/execucoes-classificacao/${id}/retomar`),
      ).toHaveLength(1);
    }

    gates["e-a"].resolve();
    gates["e-b"].resolve();
  });

  it("C3: refaz a lista quando a retomada falha com 409", async () => {
    const user = userEvent.setup();
    let estado: "interrompida" | "concluida" = "interrompida";
    const { fetchSpy } = renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: (url, init) => {
        if (url.pathname === "/api/v1/execucoes-classificacao" && !init?.method) {
          return url.searchParams.has("taxonomia_id")
            ? jsonResponse({ itens: [makeExecucao({ id: "e-a", status: estado })], total: 1 })
            : undefined;
        }
        if (url.pathname === "/api/v1/execucoes-classificacao/e-a/retomar") {
          estado = "concluida";
          return jsonResponse({ detail: "Execução não é retomável." }, 409);
        }
        return undefined;
      },
    });

    const card = await screen.findByTestId("execucao-card-e-a");
    const botao = within(card).getByRole("button", { name: /Retomar \/ Reprocessar falhas/ });
    expect(botao).toBeEnabled();
    const antes = fetchSpy.mock.calls.filter(([input]) =>
      String(input).includes("taxonomia_id="),
    ).length;

    await user.click(botao);
    expect(await screen.findByText("Falha ao retomar Execução")).toBeInTheDocument();
    await waitFor(() => expect(within(card).getByText("Concluída")).toBeInTheDocument());
    const depois = fetchSpy.mock.calls.filter(([input]) =>
      String(input).includes("taxonomia_id="),
    ).length;
    expect(depois).toBeGreaterThan(antes);
    expect(botao).toBeDisabled();
  });

  it("C4: Nova Execução aberta antes das Taxonomias carregarem usa a Taxonomia ativa", async () => {
    const user = userEvent.setup();
    const gate = deferred();
    const { fetchSpy } = renderTaxonomias({
      path: "/taxonomias?aba=execucoes",
      handler: async (url, init) => {
        if (url.pathname === "/api/v1/taxonomias" && !init?.method) {
          await gate.promise;
          return undefined;
        }
        if (url.pathname === "/api/v1/execucoes-classificacao" && init?.method === "POST") {
          return jsonResponse({ execucao_id: "nova" }, 202);
        }
        return undefined;
      },
    });

    await user.click(await screen.findByRole("button", { name: "Nova Execução" }));
    const dialog = await screen.findByRole("dialog");
    gate.resolve();

    await waitFor(() =>
      expect(within(dialog).getByRole("combobox", { name: "Taxonomia" })).toHaveTextContent(
        "ENADE Engenharia de Computação",
      ),
    );
    await waitFor(() =>
      expect(within(dialog).getByRole("combobox", { name: "Perfil de Classificação" })).toHaveTextContent(
        "v2-fronteiras",
      ),
    );
    await user.click(within(dialog).getByRole("button", { name: "Iniciar Execução" }));
    await waitFor(() =>
      expect(callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao")).toHaveLength(1),
    );
    expect(bodyOf(callsTo(fetchSpy, "POST", "/api/v1/execucoes-classificacao")[0][1])).toMatchObject({
      taxonomia_id: TAX_ID,
    });
  });

  it("C4: trocar a Taxonomia ativa com o diálogo de editar Disciplina aberto o fecha e nunca envia PATCH", async () => {
    const user = userEvent.setup();
    const outra: TaxonomiaResponse = {
      id: TAX_NOVA_ID,
      codigo: "outra",
      nome: "Outra Taxonomia",
      curso_referencia: "",
      disciplinas: [],
    };
    const { router, fetchSpy } = renderTaxonomias({
      handler: (url, init) =>
        url.pathname === "/api/v1/taxonomias" && !init?.method
          ? jsonResponse({ itens: [TAXONOMIA, outra], total: 2 })
          : undefined,
    });

    await user.click(await screen.findByRole("button", { name: "Editar Disciplina Algoritmos" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await act(async () => {
      await router.navigate(`/taxonomias?taxonomia=${TAX_NOVA_ID}`);
    });
    await waitFor(() =>
      expect(screen.getByTestId("taxonomia-ativa")).toHaveTextContent("Outra Taxonomia"),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(callsTo(fetchSpy, "PATCH", `/api/v1/disciplinas/${DISC_ID}`)).toHaveLength(0);

    // Voltar à Taxonomia original não reabre o diálogo.
    await act(async () => {
      await router.navigate(`/taxonomias?taxonomia=${TAX_ID}`);
    });
    await waitFor(() =>
      expect(screen.getByTestId("taxonomia-ativa")).toHaveTextContent("ENADE Engenharia"),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("m1: o seletor global reflete o novo nome após editar a Taxonomia", async () => {
    const user = userEvent.setup();
    let editada = false;
    renderTaxonomias({
      handler: (url, init) => {
        if (url.pathname === `/api/v1/taxonomias/${TAX_ID}` && init?.method === "PATCH") {
          editada = true;
          return jsonResponse({ ...TAXONOMIA, nome: "Renomeada" });
        }
        if (url.pathname === "/api/v1/taxonomias" && !init?.method && editada) {
          return jsonResponse({ itens: [{ ...TAXONOMIA, nome: "Renomeada" }], total: 1 });
        }
        return undefined;
      },
    });

    const seletor = await screen.findByRole("combobox", { name: /taxonomia ativa/i });
    expect(seletor).toHaveTextContent("ENADE Engenharia de Computação");
    await user.click(await screen.findByRole("button", { name: "Editar Taxonomia" }));
    const dialog = await screen.findByRole("dialog");
    const nome = within(dialog).getByLabelText("Nome");
    await user.clear(nome);
    await user.type(nome, "Renomeada");
    await user.click(within(dialog).getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(seletor).toHaveTextContent("Renomeada"));
  });
});
