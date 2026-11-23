import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { HealthResponse } from "@/api/client";
import type { ListaExecucoesClassificacaoResponse } from "@/api/operacao";
import type { ListaProvasResponse, ProvaDetalheResponse } from "@/api/provas";
import type { ListaQuestoesResponse } from "@/api/revisao";
import type { ListaPerfisClassificacaoResponse, ListaTaxonomiasResponse } from "@/api/taxonomias";
import { ROUTER_FUTURE_FLAGS, createAppRoutes } from "@/app/router";
import { formatarFaixaCE, resolverFaixaPadraoPorAno } from "@/features/provas/faixasEnade";
import { parseIngestaoFormValues, pdfFileSchema } from "@/features/provas/ingestaoSchema";
import {
  getClassificacaoEncadeadaBadgeMeta,
  getIngestaoStatusMeta,
} from "@/features/provas/provasStatus";

const TAXONOMIA_ENADE_ID = "22222222-2222-2222-2222-222222222222";
const PERFIL_V2_ID = "33333333-3333-3333-3333-333333333333";

const DEFAULT_TAXONOMIAS: ListaTaxonomiasResponse = {
  itens: [
    {
      id: TAXONOMIA_ENADE_ID,
      codigo: "enade-eng-computacao",
      nome: "ENADE Engenharia de Computação",
      curso_referencia: "Engenharia de Computação",
      disciplinas: [],
    },
  ],
  total: 1,
};

const DEFAULT_PERFIS: ListaPerfisClassificacaoResponse = {
  itens: [
    {
      id: "44444444-4444-4444-4444-444444444444",
      codigo: "outro-perfil",
      versao: "v1",
      diretrizes_gerais: "",
      guia_fronteiras: "",
      template_prompt: "",
      descricao: "Outro perfil",
    },
    {
      id: PERFIL_V2_ID,
      codigo: "v2-fronteiras",
      versao: "v1",
      diretrizes_gerais: "",
      guia_fronteiras: "",
      template_prompt: "",
      descricao: "Perfil padrão",
    },
  ],
  total: 2,
};

const IDLE_HEALTH: HealthResponse = {
  status: "ok",
  banco_dados: "conectado",
  worker: { estado: "ocioso", tarefa_ativa: null },
};

const EMPTY_EXECUCOES: ListaExecucoesClassificacaoResponse = { itens: [], total: 0 };

function makeProva(overrides?: Partial<ProvaDetalheResponse>): ProvaDetalheResponse {
  return {
    id: "prova-1",
    exame: "ENADE",
    curso: "Engenharia de Computação",
    ano: 2023,
    questao_inicio: 10,
    questao_fim: 38,
    possui_gabarito: true,
    ultima_ingestao: {
      id: "ing-1",
      status: "concluida",
      mensagem_erro: null,
      concluida_em: "2026-11-22T18:30:00Z",
      metadados: {
        total_questoes_extraidas: 29,
        imagens_detectadas: 3,
        imagens_filtradas_margem: 1,
        formulas_recortadas: 2,
        usou_ocr: false,
        paginas_fonte_symbol: [],
        gabarito_enviado: true,
      },
    },
    questoes: {
      total: 29,
      editadas_manualmente: 2,
      gabarito_validas: 27,
      gabarito_anuladas: 2,
      gabarito_pendentes: 0,
    },
    alertas: {
      abertos: 1,
      criticos_abertos: 0,
      questoes_com_alerta_aberto: 1,
    },
    classificacao_encadeada: {
      solicitada: true,
      taxonomia_id: TAXONOMIA_ENADE_ID,
      perfil_id: PERFIL_V2_ID,
      execucao_id: "exec-1",
      status: "concluida",
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

type FetchMockRouter = (url: URL, init?: RequestInit) => Response | Promise<Response>;

function renderProvasApp(options?: {
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
    if (url.pathname === "/api/v1/perfis-classificacao") {
      return jsonResponse(DEFAULT_PERFIS);
    }
    if (url.pathname === "/api/v1/health") {
      return jsonResponse(IDLE_HEALTH);
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
    if (url.pathname === "/api/v1/provas") {
      const empty: ListaProvasResponse = { itens: [], total: 0 };
      return jsonResponse(empty);
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
    const custom = options?.fetchHandler ? await options.fetchHandler(url, init) : undefined;
    return custom ?? defaultHandler(url, init);
  });

  const renderResult = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
    </QueryClientProvider>,
  );

  return { ...renderResult, queryClient, router, fetchSpy };
}

describe("faixasEnade, ingestaoSchema e provasStatus", () => {
  it("resolve faixas padrão do ENADE por ano e formata faixa CE", () => {
    expect(resolverFaixaPadraoPorAno(2013)).toBeNull();
    expect(resolverFaixaPadraoPorAno(2014)).toEqual({ inicio: 9, fim: 35 });
    expect(resolverFaixaPadraoPorAno(2017)).toEqual({ inicio: 9, fim: 35 });
    expect(resolverFaixaPadraoPorAno(2019)).toEqual({ inicio: 9, fim: 35 });
    expect(resolverFaixaPadraoPorAno(2022)).toBeNull();
    expect(resolverFaixaPadraoPorAno(2023)).toEqual({ inicio: 10, fim: 38 });
    expect(resolverFaixaPadraoPorAno(2025)).toBeNull();
    expect(resolverFaixaPadraoPorAno(2026)).toEqual({ inicio: 16, fim: 45 });
    expect(resolverFaixaPadraoPorAno(2027)).toEqual({ inicio: 16, fim: 45 });
    expect(formatarFaixaCE(9, 35)).toBe("09–35");
  });

  it("valida PDFs e invariantes da ingestão com Zod", () => {
    const emptyPdf = new File([], "vazio.pdf", { type: "application/pdf" });
    const pngFakePdf = new File(["png"], "prova.pdf", { type: "image/png" });
    const validPdf = new File(["%PDF-1.7"], "prova.pdf", { type: "application/pdf" });
    const validEmptyMimePdf = new File(["%PDF-1.7"], "prova.pdf", { type: "" });

    expect(pdfFileSchema.safeParse(emptyPdf).success).toBe(false);
    expect(pdfFileSchema.safeParse(pngFakePdf).success).toBe(false);
    expect(pdfFileSchema.safeParse(validPdf).success).toBe(true);
    expect(pdfFileSchema.safeParse(validEmptyMimePdf).success).toBe(true);

    const pairedFailure = parseIngestaoFormValues({
      exame: "ENADE",
      curso: "Engenharia de Computação",
      ano: "2023",
      questao_inicio: "10",
      questao_fim: "",
      classificar_automaticamente: true,
      arquivo_prova: validPdf,
      arquivo_gabarito: null,
    });
    expect(pairedFailure.success).toBe(false);
    if (!pairedFailure.success) {
      expect(pairedFailure.fieldErrors.questao_fim).toMatch(/juntas/i);
    }

    const orderingFailure = parseIngestaoFormValues({
      exame: "ENADE",
      curso: "Engenharia de Computação",
      ano: "2023",
      questao_inicio: "30",
      questao_fim: "15",
      classificar_automaticamente: true,
      arquivo_prova: validPdf,
      arquivo_gabarito: null,
    });
    expect(orderingFailure.success).toBe(false);
    if (!orderingFailure.success) {
      expect(orderingFailure.fieldErrors.questao_fim).toMatch(/maior ou igual/i);
    }
  });

  it("mapeia todos os status de Ingestão e Classificação encadeada com fallback seguro", () => {
    expect(getIngestaoStatusMeta("pendente").isActive).toBe(true);
    expect(getIngestaoStatusMeta("processando").isActive).toBe(true);
    expect(getIngestaoStatusMeta("concluida").label).toBe("Ingestão concluída");
    expect(getIngestaoStatusMeta("erro").variant).toBe("destructive");
    expect(getIngestaoStatusMeta("interrompida").variant).toBe("destructive");
    expect(getIngestaoStatusMeta(null).label).toBe("Sem ingestão");

    const knownStatuses = [
      "aguardando_ingestao",
      "aguardando_agendamento",
      "agendada",
      "pendente",
      "processando",
      "concluida",
      "concluida_com_erros",
      "interrompida",
      "erro",
      "nao_executada",
      "hook_nao_configurado",
      "erro_agendamento",
    ];
    for (const status of knownStatuses) {
      const meta = getClassificacaoEncadeadaBadgeMeta({ solicitada: true, status });
      expect(meta).not.toBeNull();
      expect(meta?.label.length).toBeGreaterThan(0);
    }

    expect(
      getClassificacaoEncadeadaBadgeMeta({
        solicitada: true,
        status: "status_futuro_desconhecido",
      })?.label,
    ).toBe("Classificação: status_futuro_desconhecido");

    expect(getClassificacaoEncadeadaBadgeMeta({ solicitada: false, status: "pendente" })).toBeNull();
  });
});

describe("ProvasPage (F7–F12)", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it("exibe estado vazio com CTA 'Ingerir primeira prova' que abre o formulário", async () => {
    const user = userEvent.setup();
    renderProvasApp();

    expect(await screen.findByText("Nenhuma Prova ingerida ainda")).toBeInTheDocument();
    const cta = screen.getByRole("button", { name: "Ingerir primeira prova" });
    await user.click(cta);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Nova Ingestão" })).toBeInTheDocument();
  });

  it("abre o formulário automaticamente com ?acao=ingerir e limpa acao preservando ?taxonomia=", async () => {
    const { router } = renderProvasApp({
      initialEntries: [`/provas?acao=ingerir&taxonomia=${TAXONOMIA_ENADE_ID}`],
    });

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Nova Ingestão" })).toBeInTheDocument();

    await waitFor(() => {
      expect(router.state.location.search).not.toContain("acao=ingerir");
      expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_ENADE_ID}`);
    });
  });

  it("preenche faixa CE por ano, respeita edição manual, auto-expande ano sem faixa padrão e valida Zod", async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderProvasApp();

    await user.click(await screen.findByRole("button", { name: "Ingerir primeira prova" }));
    const dialog = await screen.findByRole("dialog");

    const toggleAvancadas = within(dialog).getByRole("button", { name: "Opções avançadas" });
    expect(toggleAvancadas).toHaveAttribute("aria-expanded", "false");
    await user.click(toggleAvancadas);
    expect(toggleAvancadas).toHaveAttribute("aria-expanded", "true");

    const anoInput = within(dialog).getByLabelText("Ano");
    const inicioInput = within(dialog).getByLabelText("Questão inicial (CE)");
    const fimInput = within(dialog).getByLabelText("Questão final (CE)");

    await user.clear(anoInput);
    await user.type(anoInput, "2017");
    expect(inicioInput).toHaveValue(9);
    expect(fimInput).toHaveValue(35);

    await user.clear(anoInput);
    await user.type(anoInput, "2019");
    expect(inicioInput).toHaveValue(9);
    expect(fimInput).toHaveValue(35);

    await user.clear(anoInput);
    await user.type(anoInput, "2023");
    expect(inicioInput).toHaveValue(10);
    expect(fimInput).toHaveValue(38);

    await user.clear(anoInput);
    await user.type(anoInput, "2026");
    expect(inicioInput).toHaveValue(16);
    expect(fimInput).toHaveValue(45);

    // Edição manual não deve ser sobrescrita ao mudar o ano
    await user.clear(inicioInput);
    await user.type(inicioInput, "12");
    await user.clear(fimInput);
    await user.type(fimInput, "40");
    await user.clear(anoInput);
    await user.type(anoInput, "2017");
    expect(inicioInput).toHaveValue(12);
    expect(fimInput).toHaveValue(40);

    // Botão de restauração devolve o padrão do ano
    await user.click(within(dialog).getByRole("button", { name: /Usar padrão do ano/i }));
    expect(inicioInput).toHaveValue(9);
    expect(fimInput).toHaveValue(35);

    // Fecha avançadas e testa auto-expansão para ano 2022 sem faixa padrão
    await user.click(toggleAvancadas);
    expect(toggleAvancadas).toHaveAttribute("aria-expanded", "false");
    await user.clear(anoInput);
    await user.type(anoInput, "2022");
    expect(toggleAvancadas).toHaveAttribute("aria-expanded", "true");
    expect(within(dialog).getByLabelText("Questão inicial (CE)")).toHaveValue(null);
    expect(within(dialog).getByLabelText("Questão final (CE)")).toHaveValue(null);
    expect(within(dialog).getByText(/Ano 2022 não possui faixa padrão/i)).toBeInTheDocument();

    // Validação Zod de PDF não-PDF e submissão sem faixa para 2022
    const provaFileInput = within(dialog).getByLabelText("PDF da Prova");
    await user.upload(provaFileInput, new File(["png"], "imagem.png", { type: "image/png" }));
    await user.click(within(dialog).getByRole("button", { name: "Iniciar Ingestão" }));

    expect(
      await within(dialog).findByText("Envie um documento no formato PDF (.pdf)."),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Ano sem faixa padrão conhecida/i),
    ).toBeInTheDocument();
  });

  it("envia FormData multipart com e sem 'Classificar automaticamente ao concluir'", async () => {
    const user = userEvent.setup();
    const submittedForms: FormData[] = [];

    renderProvasApp({
      fetchHandler: async (url, init) => {
        if (url.pathname === "/api/v1/provas" && init?.method === "POST") {
          submittedForms.push(init.body as FormData);
          return jsonResponse(
            {
              prova_id: "prova-nova",
              ingestao_id: "ing-nova",
              status: "pendente",
              exame: "ENADE",
              curso: "Engenharia de Computação",
              ano: 2023,
              questao_inicio: 10,
              questao_fim: 38,
              possui_gabarito: true,
            },
            202,
          );
        }
        return undefined as unknown as Response;
      },
    });

    // 1. Submissão padrão com auto-classificação marcada
    await user.click(await screen.findByRole("button", { name: "Ingerir primeira prova" }));
    let dialog = await screen.findByRole("dialog");

    expect(
      within(dialog).getByRole("checkbox", { name: /Classificar automaticamente ao concluir/i }),
    ).toBeChecked();

    await user.upload(
      within(dialog).getByLabelText("PDF da Prova"),
      new File(["%PDF-1.7"], "enade-2023.pdf", { type: "application/pdf" }),
    );
    await user.upload(
      within(dialog).getByLabelText("PDF do Gabarito (opcional)"),
      new File(["%PDF-1.7"], "gabarito-2023.pdf", { type: "application/pdf" }),
    );
    await user.type(within(dialog).getByLabelText("Ano"), "2023");

    await user.click(within(dialog).getByRole("button", { name: "Iniciar Ingestão" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    expect(submittedForms).toHaveLength(1);
    expect(submittedForms[0].get("exame")).toBe("ENADE");
    expect(submittedForms[0].get("curso")).toBe("Engenharia de Computação");
    expect(submittedForms[0].get("ano")).toBe("2023");
    expect(submittedForms[0].get("questao_inicio")).toBe("10");
    expect(submittedForms[0].get("questao_fim")).toBe("38");
    expect(submittedForms[0].get("taxonomia_id")).toBe(TAXONOMIA_ENADE_ID);
    expect(submittedForms[0].get("perfil_id")).toBe(PERFIL_V2_ID);
    expect(submittedForms[0].get("arquivo_gabarito")).toBeInstanceOf(File);

    // 2. Submissão desmarcando auto-classificação
    await user.click(screen.getByRole("button", { name: "Ingerir primeira prova" }));
    dialog = await screen.findByRole("dialog");

    await user.upload(
      within(dialog).getByLabelText("PDF da Prova"),
      new File(["%PDF-1.7"], "enade-2019.pdf", { type: "application/pdf" }),
    );
    await user.type(within(dialog).getByLabelText("Ano"), "2019");
    await user.click(
      within(dialog).getByRole("checkbox", { name: /Classificar automaticamente ao concluir/i }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Iniciar Ingestão" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    expect(submittedForms).toHaveLength(2);
    expect(submittedForms[1].get("taxonomia_id")).toBeNull();
    expect(submittedForms[1].get("perfil_id")).toBeNull();
    expect(submittedForms[1].get("arquivo_gabarito")).toBeNull();
  });

  it("trata 409 Conflict oferecendo Atualizar Gabarito e Reprocessar Prova (incluindo fallback sem cache)", async () => {
    const user = userEvent.setup();
    const conflictProvaId = "99999999-9999-9999-9999-999999999999";

    renderProvasApp({
      fetchHandler: async (url, init) => {
        if (url.pathname === "/api/v1/provas" && init?.method === "POST") {
          return jsonResponse(
            {
              detail: "Já existe uma Prova cadastrada para ENADE / Engenharia de Computação / 2023.",
              prova_id: conflictProvaId,
              exame: "ENADE",
              curso: "Engenharia de Computação",
              ano: 2023,
            },
            409,
          );
        }
        if (url.pathname === `/api/v1/provas/${conflictProvaId}`) {
          return jsonResponse(
            makeProva({
              id: conflictProvaId,
              questoes: {
                total: 29,
                editadas_manualmente: 4,
                gabarito_validas: 29,
                gabarito_anuladas: 0,
                gabarito_pendentes: 0,
              },
            }),
          );
        }
        return undefined as unknown as Response;
      },
    });

    // Fluxo 1: 409 -> Atualizar Gabarito
    await user.click(await screen.findByRole("button", { name: "Ingerir primeira prova" }));
    let drawer = await screen.findByRole("dialog");

    await user.upload(
      within(drawer).getByLabelText("PDF da Prova"),
      new File(["%PDF-1.7"], "enade-2023.pdf", { type: "application/pdf" }),
    );
    await user.type(within(drawer).getByLabelText("Ano"), "2023");
    await user.click(within(drawer).getByRole("button", { name: "Iniciar Ingestão" }));

    expect(await within(drawer).findByText("Prova já cadastrada")).toBeInTheDocument();
    expect(within(drawer).getByText("ENADE · Engenharia de Computação · 2023")).toBeInTheDocument();

    await user.click(within(drawer).getByRole("button", { name: "Atualizar Gabarito" }));
    const gabaritoDialog = await screen.findByRole("dialog");
    expect(
      within(gabaritoDialog).getByRole("heading", { name: "Atualizar Gabarito" }),
    ).toBeInTheDocument();
    await user.click(within(gabaritoDialog).getByRole("button", { name: "Cancelar" }));

    // Fluxo 2: 409 -> Reprocessar Prova (com busca de detalhe quando ausente da lista)
    await user.click(screen.getByRole("button", { name: "Ingerir primeira prova" }));
    drawer = await screen.findByRole("dialog");
    await user.upload(
      within(drawer).getByLabelText("PDF da Prova"),
      new File(["%PDF-1.7"], "enade-2023.pdf", { type: "application/pdf" }),
    );
    await user.type(within(drawer).getByLabelText("Ano"), "2023");
    await user.click(within(drawer).getByRole("button", { name: "Iniciar Ingestão" }));

    await within(drawer).findByText("Prova já cadastrada");
    await user.click(within(drawer).getByRole("button", { name: "Reprocessar Prova" }));

    const alertDialog = await screen.findByRole("alertdialog");
    expect(
      within(alertDialog).getByRole("heading", { name: "Reprocessar Prova" }),
    ).toBeInTheDocument();
    expect(
      await within(alertDialog).findByText("4 Questões editadas manualmente"),
    ).toBeInTheDocument();
  });

  it("renderiza contadores, ações desabilitadas enquanto ativa, 'Tentar novamente' e atalho de revisão", async () => {
    const user = userEvent.setup();
    const reprocessCalls: Array<{ provaId: string; sobrescrever_editadas: boolean }> = [];

    const provaAtiva = makeProva({
      id: "prova-ativa",
      ano: 2026,
      questao_inicio: 16,
      questao_fim: 45,
      possui_gabarito: false,
      ultima_ingestao: {
        id: "ing-ativa",
        status: "processando",
        metadados: {
          total_questoes_extraidas: 0,
          imagens_detectadas: 0,
          imagens_filtradas_margem: 0,
          formulas_recortadas: 0,
          usou_ocr: false,
          paginas_fonte_symbol: [],
          gabarito_enviado: false,
        },
      },
      questoes: {
        total: 0,
        editadas_manualmente: 0,
        gabarito_validas: 0,
        gabarito_anuladas: 0,
        gabarito_pendentes: 0,
      },
      alertas: { abertos: 0, criticos_abertos: 0, questoes_com_alerta_aberto: 0 },
      classificacao_encadeada: { solicitada: false },
    });

    const provaErro = makeProva({
      id: "prova-erro",
      ano: 2019,
      questao_inicio: 9,
      questao_fim: 35,
      ultima_ingestao: {
        id: "ing-erro",
        status: "erro",
        mensagem_erro: "PDF corrompido na página 4.",
        metadados: {
          total_questoes_extraidas: 12,
          imagens_detectadas: 1,
          imagens_filtradas_margem: 0,
          formulas_recortadas: 0,
          usou_ocr: true,
          paginas_fonte_symbol: [4],
          gabarito_enviado: true,
        },
      },
      classificacao_encadeada: {
        solicitada: true,
        taxonomia_id: TAXONOMIA_ENADE_ID,
        status: "status_futuro_desconhecido",
      },
    });

    const { router } = renderProvasApp({
      fetchHandler: async (url, init) => {
        if (url.pathname === "/api/v1/provas" && (!init?.method || init.method === "GET")) {
          return jsonResponse({ itens: [provaAtiva, provaErro], total: 2 });
        }
        if (url.pathname === `/api/v1/provas/${provaErro.id}/reprocessar` && init?.method === "POST") {
          const parsed = JSON.parse(String(init.body)) as { sobrescrever_editadas: boolean };
          reprocessCalls.push({ provaId: provaErro.id, ...parsed });
          return jsonResponse(
            {
              prova_id: provaErro.id,
              ingestao_id: "ing-retry",
              status: "pendente",
              sobrescrever_editadas: parsed.sobrescrever_editadas,
            },
            202,
          );
        }
        return undefined as unknown as Response;
      },
    });

    const cardAtiva = await screen.findByTestId("prova-card-prova-ativa");
    expect(screen.getByRole("button", { name: "Nova Ingestão" })).toBeInTheDocument();
    expect(within(cardAtiva).getByText("Ingestão em processamento")).toBeInTheDocument();
    expect(within(cardAtiva).getByText("Gabarito pendente")).toBeInTheDocument();
    expect(within(cardAtiva).getByRole("button", { name: "Atualizar Gabarito" })).toBeDisabled();
    expect(within(cardAtiva).getByRole("button", { name: "Reprocessar Prova" })).toBeDisabled();
    expect(
      within(cardAtiva).getByRole("button", { name: "Revisar questões desta prova" }),
    ).toBeDisabled();

    const cardErro = screen.getByTestId("prova-card-prova-erro");
    expect(within(cardErro).getByText("Erro na ingestão")).toBeInTheDocument();
    expect(within(cardErro).getByText("PDF corrompido na página 4.")).toBeInTheDocument();
    expect(
      within(cardErro).getByText(/Classificação: status_futuro_desconhecido/i),
    ).toBeInTheDocument();
    expect(within(cardErro).getByText("2 editadas manualmente")).toBeInTheDocument();

    await user.click(within(cardErro).getByRole("button", { name: "Tentar novamente" }));
    await waitFor(() => {
      expect(reprocessCalls).toEqual([{ provaId: "prova-erro", sobrescrever_editadas: false }]);
    });

    const revisaoLink = within(cardErro).getByRole("link", { name: "Revisar questões desta prova" });
    expect(revisaoLink).toHaveAttribute(
      "href",
      `/revisao?taxonomia=${TAXONOMIA_ENADE_ID}&modo=recorte&prova_id=prova-erro`,
    );

    await user.click(revisaoLink);
    expect(router.state.location.pathname).toBe("/revisao");
    expect(router.state.location.search).toContain("prova_id=prova-erro");
    expect(router.state.location.search).toContain(`taxonomia=${TAXONOMIA_ENADE_ID}`);
  });

  it("atualiza Gabarito via PUT e exibe resumo mantidas / alteradas / anuladas", async () => {
    const user = userEvent.setup();
    let putMethod: string | undefined;

    renderProvasApp({
      fetchHandler: async (url, init) => {
        if (url.pathname === "/api/v1/provas" && (!init?.method || init.method === "GET")) {
          return jsonResponse({ itens: [makeProva()], total: 1 });
        }
        if (url.pathname === "/api/v1/provas/prova-1/gabarito") {
          putMethod = init?.method;
          return jsonResponse({
            mantidas: 25,
            alteradas: 2,
            anuladas: 2,
            sem_correspondencia: [41],
            questoes_sem_gabarito: [38],
          });
        }
        return undefined as unknown as Response;
      },
    });

    const card = await screen.findByTestId("prova-card-prova-1");
    await user.click(within(card).getByRole("button", { name: "Atualizar Gabarito" }));

    const dialog = await screen.findByRole("dialog");
    await user.upload(
      within(dialog).getByLabelText("PDF do Gabarito"),
      new File(["%PDF-1.7"], "gabarito-novo.pdf", { type: "application/pdf" }),
    );
    await user.click(within(dialog).getByRole("button", { name: "Atualizar Gabarito" }));

    expect(await within(dialog).findByText("Gabarito atualizado")).toBeInTheDocument();
    expect(putMethod).toBe("PUT");
    expect(within(dialog).getByText("Mantidas")).toBeInTheDocument();
    expect(within(dialog).getByText("25")).toBeInTheDocument();
    expect(within(dialog).getByText("Alteradas")).toBeInTheDocument();
    expect(within(dialog).getByText("Anuladas")).toBeInTheDocument();
    expect(within(dialog).getByText("Sem correspondência na Prova: 41")).toBeInTheDocument();
    expect(within(dialog).getByText("Questões sem Gabarito: 38")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Concluir" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("exige confirmação explícita ao reprocessar Prova mantendo sobrescrever_editadas = false por padrão", async () => {
    const user = userEvent.setup();
    const sentPayloads: boolean[] = [];

    renderProvasApp({
      fetchHandler: async (url, init) => {
        if (url.pathname === "/api/v1/provas" && (!init?.method || init.method === "GET")) {
          return jsonResponse({
            itens: [
              makeProva({
                questoes: {
                  total: 29,
                  editadas_manualmente: 3,
                  gabarito_validas: 29,
                  gabarito_anuladas: 0,
                  gabarito_pendentes: 0,
                },
              }),
            ],
            total: 1,
          });
        }
        if (url.pathname === "/api/v1/provas/prova-1/reprocessar" && init?.method === "POST") {
          const body = JSON.parse(String(init.body)) as { sobrescrever_editadas: boolean };
          sentPayloads.push(body.sobrescrever_editadas);
          return jsonResponse(
            {
              prova_id: "prova-1",
              ingestao_id: "ing-rep",
              status: "pendente",
              sobrescrever_editadas: body.sobrescrever_editadas,
            },
            202,
          );
        }
        return undefined as unknown as Response;
      },
    });

    const card = await screen.findByTestId("prova-card-prova-1");

    // 1. Confirma com padrão desmarcado -> false
    await user.click(within(card).getByRole("button", { name: "Reprocessar Prova" }));
    let dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("3 Questões editadas manualmente")).toBeInTheDocument();
    let checkbox = within(dialog).getByRole("checkbox", {
      name: /Sobrescrever questões editadas manualmente/i,
    });
    expect(checkbox).not.toBeChecked();

    await user.click(within(dialog).getByRole("button", { name: "Confirmar reprocessamento" }));
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
    expect(sentPayloads).toEqual([false]);

    // 2. Reabre, marca checkbox e confirma -> true
    await user.click(within(card).getByRole("button", { name: "Reprocessar Prova" }));
    dialog = await screen.findByRole("alertdialog");
    checkbox = within(dialog).getByRole("checkbox", {
      name: /Sobrescrever questões editadas manualmente/i,
    });
    expect(checkbox).not.toBeChecked();
    await user.click(checkbox);
    expect(checkbox).toBeChecked();

    await user.click(within(dialog).getByRole("button", { name: "Confirmar reprocessamento" }));
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
    expect(sentPayloads).toEqual([false, true]);

    // 3. Reabre novamente -> checkbox resetado para false
    await user.click(within(card).getByRole("button", { name: "Reprocessar Prova" }));
    dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByRole("checkbox", {
        name: /Sobrescrever questões editadas manualmente/i,
      }),
    ).not.toBeChecked();
  });

  it("faz polling a cada ~2 s enquanto há Ingestão ativa e interrompe ao concluir", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let phase: "processando" | "concluida" = "processando";
    let provasGetCount = 0;

    renderProvasApp({
      fetchHandler: async (url, init) => {
        if (url.pathname === "/api/v1/provas" && (!init?.method || init.method === "GET")) {
          provasGetCount += 1;
          if (phase === "processando") {
            return jsonResponse({
              itens: [
                makeProva({
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
                  classificacao_encadeada: { solicitada: false },
                }),
              ],
              total: 1,
            });
          }
          return jsonResponse({
            itens: [
              makeProva({
                questoes: {
                  total: 27,
                  editadas_manualmente: 0,
                  gabarito_validas: 27,
                  gabarito_anuladas: 0,
                  gabarito_pendentes: 0,
                },
              }),
            ],
            total: 1,
          });
        }
        return undefined as unknown as Response;
      },
    });

    const card = await screen.findByTestId("prova-card-prova-1");
    expect(within(card).getByText("Ingestão em processamento")).toBeInTheDocument();
    const countAfterInitial = provasGetCount;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });
    expect(provasGetCount).toBeGreaterThan(countAfterInitial);

    phase = "concluida";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });

    await waitFor(() => {
      expect(within(card).getByText("Ingestão concluída")).toBeInTheDocument();
      expect(within(card).getByText("27")).toBeInTheDocument();
    });

    const countWhenIdle = provasGetCount;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(provasGetCount).toBe(countWhenIdle);
  });
});
