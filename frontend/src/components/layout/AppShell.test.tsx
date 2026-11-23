import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { HealthResponse } from "@/api/client";
import type { ListaExecucoesClassificacaoResponse } from "@/api/operacao";
import type { ListaProvasResponse } from "@/api/provas";
import type { ListaQuestoesResponse } from "@/api/revisao";
import type { ListaTaxonomiasResponse } from "@/api/taxonomias";
import { ROUTER_FUTURE_FLAGS, createAppRoutes } from "@/app/router";
import { TAXONOMIA_STORAGE_KEY } from "@/components/layout/useTaxonomia";

const TAXONOMIA_CUSTOM_ID = "11111111-1111-1111-1111-111111111111";
const TAXONOMIA_ENADE_ID = "22222222-2222-2222-2222-222222222222";

const DEFAULT_TAXONOMIAS: ListaTaxonomiasResponse = {
  itens: [
    {
      id: TAXONOMIA_CUSTOM_ID,
      codigo: "custom-ppc",
      nome: "PPC Customizado",
      curso_referencia: "Ciência da Computação",
      disciplinas: [],
    },
    {
      id: TAXONOMIA_ENADE_ID,
      codigo: "enade-eng-computacao",
      nome: "ENADE Engenharia de Computação",
      curso_referencia: "Engenharia de Computação",
      disciplinas: [],
    },
  ],
  total: 2,
};

const IDLE_HEALTH: HealthResponse = {
  status: "ok",
  banco_dados: "conectado",
  worker: { estado: "ocioso", tarefa_ativa: null },
};

const EMPTY_PROVAS: ListaProvasResponse = { itens: [], total: 0 };
const EMPTY_EXECUCOES: ListaExecucoesClassificacaoResponse = { itens: [], total: 0 };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

type FetchMockRouter = (url: URL, init?: RequestInit) => Response | Promise<Response>;

function renderShell(options?: {
  initialEntries?: string[];
  fetchHandler?: FetchMockRouter;
}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  const router = createMemoryRouter(createAppRoutes(), {
    initialEntries: options?.initialEntries ?? ["/provas"],
    future: ROUTER_FUTURE_FLAGS,
  });

  const defaultHandler: FetchMockRouter = (url) => {
    if (url.pathname === "/api/v1/taxonomias") {
      return jsonResponse(DEFAULT_TAXONOMIAS);
    }
    if (url.pathname === "/api/v1/health") {
      return jsonResponse(IDLE_HEALTH);
    }
    if (url.pathname === "/api/v1/provas") {
      return jsonResponse(EMPTY_PROVAS);
    }
    if (url.pathname === "/api/v1/execucoes-classificacao") {
      return jsonResponse(EMPTY_EXECUCOES);
    }
    if (url.pathname === "/api/v1/questoes") {
      const payload: ListaQuestoesResponse = {
        itens: [],
        total: 0,
        pagina: 1,
        tamanho_pagina: 1,
        taxonomia_id: url.searchParams.get("taxonomia_id"),
        contadores: {
          pendentes: 0,
          divergencias: 0,
          disciplina_arquivada: 0,
        },
      };
      return jsonResponse(payload);
    }
    return jsonResponse({ detail: "Not Found" }, 404);
  };

  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const rawUrl =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const url = new URL(rawUrl, "http://localhost");
    return options?.fetchHandler ? options.fetchHandler(url, init) : defaultHandler(url, init);
  });

  const renderResult = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
    </QueryClientProvider>,
  );

  return { ...renderResult, queryClient, router, fetchSpy };
}

describe("AppShell & Global Shell", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it("seleciona a Taxonomia padrão ENADE Engenharia de Computação e sincroniza URL e sessionStorage", async () => {
    const { router } = renderShell();

    const combobox = await screen.findByRole("combobox", { name: /taxonomia ativa/i });
    expect(combobox).toHaveTextContent("ENADE Engenharia de Computação");

    await waitFor(() => {
      expect(window.sessionStorage.getItem(TAXONOMIA_STORAGE_KEY)).toBe(TAXONOMIA_ENADE_ID);
      expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_ENADE_ID}`);
    });
  });

  it("trocar a Taxonomia ativa atualiza URL, sessionStorage e refaz consulta do badge de Revisão", async () => {
    const user = userEvent.setup();

    const { router, fetchSpy } = renderShell({
      fetchHandler: (url) => {
        if (url.pathname === "/api/v1/taxonomias") {
          return jsonResponse(DEFAULT_TAXONOMIAS);
        }
        if (url.pathname === "/api/v1/health") {
          return jsonResponse(IDLE_HEALTH);
        }
        if (url.pathname === "/api/v1/provas") {
          return jsonResponse(EMPTY_PROVAS);
        }
        if (url.pathname === "/api/v1/execucoes-classificacao") {
          return jsonResponse(EMPTY_EXECUCOES);
        }
        if (url.pathname === "/api/v1/questoes") {
          const taxId = url.searchParams.get("taxonomia_id");
          const contadores =
            taxId === TAXONOMIA_CUSTOM_ID
              ? { pendentes: 2, divergencias: 1, disciplina_arquivada: 4 }
              : { pendentes: 4, divergencias: 2, disciplina_arquivada: 5 };
          return jsonResponse({
            itens: [],
            total: 0,
            pagina: 1,
            tamanho_pagina: 1,
            taxonomia_id: taxId,
            contadores,
          });
        }
        return jsonResponse({}, 404);
      },
    });

    const combobox = await screen.findByRole("combobox", { name: /taxonomia ativa/i });
    expect(await screen.findByLabelText("6 pendências para revisão")).toHaveTextContent("6");

    await user.click(combobox);
    const customOption = await screen.findByRole("option", { name: "PPC Customizado" });
    await user.click(customOption);

    await waitFor(() => {
      expect(window.sessionStorage.getItem(TAXONOMIA_STORAGE_KEY)).toBe(TAXONOMIA_CUSTOM_ID);
      expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_CUSTOM_ID}`);
      expect(screen.getByLabelText("3 pendências para revisão")).toHaveTextContent("3");
    });

    const questoesCalls = fetchSpy.mock.calls.filter(([input]) =>
      String(input).includes("/api/v1/questoes"),
    );
    expect(
      questoesCalls.some(([input]) => String(input).includes(`taxonomia_id=${TAXONOMIA_CUSTOM_ID}`)),
    ).toBe(true);
  });

  it("exibe as 4 seções canônicas, badge (pendentes + divergencias), preserva ?taxonomia= e mostra CTA de estado vazio", async () => {
    const user = userEvent.setup();

    const { router } = renderShell({
      fetchHandler: (url) => {
        if (url.pathname === "/api/v1/taxonomias") {
          return jsonResponse(DEFAULT_TAXONOMIAS);
        }
        if (url.pathname === "/api/v1/health") {
          return jsonResponse(IDLE_HEALTH);
        }
        if (url.pathname === "/api/v1/provas") {
          return jsonResponse(EMPTY_PROVAS);
        }
        if (url.pathname === "/api/v1/execucoes-classificacao") {
          return jsonResponse(EMPTY_EXECUCOES);
        }
        if (url.pathname === "/api/v1/questoes") {
          return jsonResponse({
            itens: [],
            total: 0,
            pagina: 1,
            tamanho_pagina: 1,
            taxonomia_id: url.searchParams.get("taxonomia_id"),
            contadores: {
              pendentes: 4,
              divergencias: 2,
              disciplina_arquivada: 5,
            },
          });
        }
        return jsonResponse({}, 404);
      },
    });

    expect(screen.getByRole("link", { name: "Questões" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Revisão/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Provas" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Taxonomias" })).toBeInTheDocument();

    const badge = await screen.findByLabelText("6 pendências para revisão");
    expect(badge).toHaveTextContent("6");

    await waitFor(() => {
      expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_ENADE_ID}`);
    });

    await user.click(screen.getByRole("link", { name: "Questões" }));
    expect(router.state.location.pathname).toBe("/questoes");
    expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_ENADE_ID}`);
    expect(screen.getByRole("heading", { name: "Questões" })).toBeInTheDocument();

    const ctaLink = await screen.findByRole("link", { name: "Ingerir primeira prova" });
    expect(ctaLink).toHaveAttribute(
      "href",
      `/provas?taxonomia=${TAXONOMIA_ENADE_ID}&acao=ingerir`,
    );

    await user.click(screen.getByRole("link", { name: /Revisão/i }));
    expect(router.state.location.pathname).toBe("/revisao");
    expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_ENADE_ID}`);
    expect(screen.getByRole("heading", { name: "Revisão" })).toBeInTheDocument();
  });

  it("exibe pílula do worker com polling de 2 s (mesmo em 503), navega ao clicar e invalida caches ao concluir", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    let workerOcupado = true;
    let provasFetches = 0;
    let questoesFetches = 0;
    let execucoesFetches = 0;

    const { router } = renderShell({
      fetchHandler: (url) => {
        if (url.pathname === "/api/v1/taxonomias") {
          return jsonResponse(DEFAULT_TAXONOMIAS);
        }
        if (url.pathname === "/api/v1/health") {
          if (workerOcupado) {
            return jsonResponse(
              {
                status: "degradado",
                banco_dados: "indisponivel",
                worker: {
                  estado: "ocupado",
                  tarefa_ativa: "Classificando ENADE 2023: 14/29",
                  tipo: "classificacao",
                  alvo: "ENADE 2023",
                  processadas: 14,
                  total: 29,
                },
              },
              503,
            );
          }
          return jsonResponse(IDLE_HEALTH, 200);
        }
        if (url.pathname === "/api/v1/provas") {
          provasFetches += 1;
          return jsonResponse(EMPTY_PROVAS);
        }
        if (url.pathname === "/api/v1/execucoes-classificacao") {
          execucoesFetches += 1;
          return jsonResponse(EMPTY_EXECUCOES);
        }
        if (url.pathname === "/api/v1/questoes") {
          questoesFetches += 1;
          return jsonResponse({
            itens: [],
            total: 0,
            pagina: 1,
            tamanho_pagina: 1,
            taxonomia_id: url.searchParams.get("taxonomia_id"),
            contadores: {
              pendentes: 0,
              divergencias: 0,
              disciplina_arquivada: 0,
            },
          });
        }
        return jsonResponse({}, 404);
      },
    });

    const pill = await screen.findByRole("button", { name: /Classificando ENADE 2023: 14\/29/i });
    expect(pill).toBeInTheDocument();

    await user.click(pill);
    expect(router.state.location.pathname).toBe("/taxonomias");
    expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_ENADE_ID}`);

    const provasBeforeIdle = provasFetches;
    const questoesBeforeIdle = questoesFetches;
    const execucoesBeforeIdle = execucoesFetches;

    workerOcupado = false;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /Classificando ENADE 2023: 14\/29/i }),
      ).not.toBeInTheDocument();
    });

    await waitFor(() => {
      expect(provasFetches).toBeGreaterThan(provasBeforeIdle);
      expect(questoesFetches).toBeGreaterThan(questoesBeforeIdle);
      expect(execucoesFetches).toBeGreaterThan(execucoesBeforeIdle);
    });
  });

  it("exibe pílula para Prova com Ingestão ativa mesmo com worker em transição e navega para /provas", async () => {
    const user = userEvent.setup();

    const { router } = renderShell({
      initialEntries: ["/questoes"],
      fetchHandler: (url) => {
        if (url.pathname === "/api/v1/taxonomias") {
          return jsonResponse(DEFAULT_TAXONOMIAS);
        }
        if (url.pathname === "/api/v1/health") {
          return jsonResponse(IDLE_HEALTH);
        }
        if (url.pathname === "/api/v1/execucoes-classificacao") {
          return jsonResponse(EMPTY_EXECUCOES);
        }
        if (url.pathname === "/api/v1/provas") {
          return jsonResponse({
            itens: [
              {
                id: "prova-ingestao-1",
                exame: "ENADE",
                curso: "Engenharia de Computação",
                ano: 2023,
                questao_inicio: 10,
                questao_fim: 38,
                possui_gabarito: true,
                ultima_ingestao: {
                  id: "ing-1",
                  status: "processando",
                  metadados: {
                    total_questoes_extraidas: 0,
                    imagens_detectadas: 0,
                    imagens_filtradas_margem: 0,
                    formulas_recortadas: 0,
                    usou_ocr: false,
                    paginas_fonte_symbol: [],
                    gabarito_enviado: true,
                  },
                },
                questoes: {
                  total: 0,
                  editadas_manualmente: 0,
                  gabarito_validas: 0,
                  gabarito_anuladas: 0,
                  gabarito_pendentes: 0,
                },
                alertas: {
                  abertos: 0,
                  criticos_abertos: 0,
                  questoes_com_alerta_aberto: 0,
                },
                classificacao_encadeada: {
                  solicitada: false,
                },
              },
            ],
            total: 1,
          });
        }
        if (url.pathname === "/api/v1/questoes") {
          return jsonResponse({
            itens: [],
            total: 0,
            pagina: 1,
            tamanho_pagina: 1,
            taxonomia_id: url.searchParams.get("taxonomia_id"),
            contadores: { pendentes: 0, divergencias: 0, disciplina_arquivada: 0 },
          });
        }
        return jsonResponse({}, 404);
      },
    });

    const pill = await screen.findByRole("button", { name: /Ingerindo ENADE 2023/i });
    await user.click(pill);

    expect(router.state.location.pathname).toBe("/provas");
    expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_ENADE_ID}`);
  });
});
