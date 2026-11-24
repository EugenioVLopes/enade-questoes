import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  AlertaExtracaoResponse,
  AtivoVisualResponse,
  EditarQuestaoRequest,
  LetraAlternativa,
} from "@/api/edicaoQuestao";
import type { ItemQuestaoResponse, ListaQuestoesResponse } from "@/api/questoes";
import type { ClassificacaoResponse, DetalheQuestaoResponse } from "@/api/revisao";
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
        {
          id: "d1",
          taxonomia_id: TAX_ID,
          codigo: "redes",
          nome: "Redes",
          ementa: "",
          ativa: true,
          classificacoes_vigentes_impactadas: 0,
        },
        {
          id: "d2",
          taxonomia_id: TAX_ID,
          codigo: "algoritmos",
          nome: "Algoritmos",
          ementa: "",
          ativa: true,
          classificacoes_vigentes_impactadas: 0,
        },
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
    confianca: 0.88,
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
    paginas: [28, 29],
    enunciado: `Enunciado da questão ${numero}.`,
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

function ativo(
  id: string,
  over: Partial<AtivoVisualResponse> = {},
): AtivoVisualResponse {
  return {
    id,
    origem: "picture_docling",
    alternativa_letra: null,
    ordem: 0,
    pagina: 28,
    url_arquivo: `/api/v1/ativos-visuais/${id}/arquivo`,
    ...over,
  };
}

function alerta(
  id: string,
  codigo: AlertaExtracaoResponse["codigo"],
  over: Partial<AlertaExtracaoResponse> = {},
): AlertaExtracaoResponse {
  const critico =
    codigo === "formula_nao_decodificada" ||
    codigo === "alternativas_incompletas" ||
    codigo === "pdf_via_ocr" ||
    codigo === "enunciado_suspeito";
  return {
    id,
    codigo,
    severidade: critico ? "critico" : "informativo",
    status: "aberto",
    mensagem: `Mensagem do alerta ${codigo}`,
    resolvido_em: null,
    ...over,
  };
}

function itemResumo(q: DetalheQuestaoResponse): ItemQuestaoResponse {
  return {
    id: q.id,
    prova: q.prova,
    numero: q.numero,
    trecho: q.enunciado.slice(0, 60),
    situacao_gabarito: q.gabarito.situacao_gabarito,
    editada_manualmente: q.editada_manualmente,
    alertas_abertos: q.alertas_extracao.filter((a) => a.status === "aberto").map((a) => a.codigo),
    revisao_prioritaria: q.classificacao_vigente?.revisao_prioritaria ?? false,
    tem_divergencia_aberta: q.divergencia_aberta !== null,
    usa_disciplina_arquivada: q.disciplinas_arquivadas_em_uso.length > 0,
    possui_ativos_visuais: q.ativos_visuais.length > 0,
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
  formData?: FormData;
}

interface Servidor {
  pendentes: string[];
  recorte: string[];
  detalhes: Map<string, DetalheQuestaoResponse>;
  erros: Map<string, { status: number; detail: unknown }>;
  chamadas: Chamada[];
  perfis: { id: string; codigo: string; versao: string }[];
  proximoAtivoSeq: number;
}

function criarServidor(over: Partial<Servidor> = {}): Servidor {
  const detalhes = new Map<string, DetalheQuestaoResponse>();
  for (const [id, numero] of [
    ["q1", 1],
    ["q2", 2],
    ["q3", 3],
  ] as const) {
    detalhes.set(id, detalhe(id, numero));
  }
  return {
    pendentes: ["q1", "q2", "q3"],
    recorte: ["q1", "q2", "q3"],
    detalhes,
    erros: new Map(),
    chamadas: [],
    perfis: [{ id: PERFIL_ID, codigo: "v2-fronteiras", versao: "v1" }],
    proximoAtivoSeq: 100,
    ...over,
  };
}

function recalcularPrioridade(
  vigente: ClassificacaoResponse | null | undefined,
  alertas: readonly AlertaExtracaoResponse[],
): ClassificacaoResponse | null | undefined {
  if (!vigente || vigente.status !== "pendente_revisao") {
    return vigente;
  }
  const temCriticoAberto = alertas.some((a) => a.severidade === "critico" && a.status === "aberto");
  const temSaneamento = vigente.alertas_validacao.some((a) => a !== "baixa_confianca");
  const revisaoPrioritaria = temCriticoAberto || temSaneamento || vigente.confianca < 0.75;
  return { ...vigente, revisao_prioritaria: revisaoPrioritaria };
}

function reavaliarAlertasEstruturais(
  questao: DetalheQuestaoResponse,
): AlertaExtracaoResponse[] {
  const formulaAberta =
    /<!--\s*formula-not-decoded\s*-->/.test(questao.enunciado) ||
    questao.alternativas.some((alt) => /<!--\s*formula-not-decoded\s*-->/.test(alt.texto));
  const letrasEsperadas: readonly LetraAlternativa[] = ["A", "B", "C", "D", "E"];
  const alternativasIncompletas =
    questao.tipo === "multipla_escolha" &&
    (questao.alternativas.length !== 5 ||
      questao.alternativas.some((alt, idx) => alt.letra !== letrasEsperadas[idx] || alt.texto.trim() === ""));

  const condicoes = new Map<AlertaExtracaoResponse["codigo"], boolean>([
    ["formula_nao_decodificada", formulaAberta],
    ["alternativas_incompletas", alternativasIncompletas],
  ]);

  const atualizados = questao.alertas_extracao.map((a) => {
    const deveEstarAberto = condicoes.get(a.codigo);
    if (deveEstarAberto === undefined) {
      return a;
    }
    if (deveEstarAberto) {
      return { ...a, status: "aberto" as const, resolvido_em: null };
    }
    return a.status === "aberto"
      ? { ...a, status: "resolvido" as const, resolvido_em: "2026-01-02T10:00:00Z" }
      : a;
  });

  for (const [codigo, ativoAgora] of condicoes.entries()) {
    if (ativoAgora && !atualizados.some((a) => a.codigo === codigo)) {
      atualizados.push(alerta(`auto-${codigo}`, codigo));
    }
  }
  return atualizados;
}

function renderRevisao(path: string, servidor: Servidor) {
  window.sessionStorage.removeItem(TAXONOMIA_STORAGE_KEY);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(createAppRoutes(), { initialEntries: [path], future: ROUTER_FUTURE_FLAGS });

  const contadores = () => ({
    pendentes: servidor.pendentes.length,
    divergencias: 0,
    disciplina_arquivada: 0,
  });

  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const url = new URL(raw, "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const formData = init?.body instanceof FormData ? init.body : undefined;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
    servidor.chamadas.push({ method, path: url.pathname, search: url.searchParams, body, formData });

    if (url.pathname === "/api/v1/taxonomias") return jsonResponse(TAXONOMIAS);
    if (url.pathname === "/api/v1/perfis-classificacao") {
      return jsonResponse({
        itens: servidor.perfis.map((p) => ({ ...p, taxonomia_id: TAX_ID })),
        total: servidor.perfis.length,
      });
    }
    if (url.pathname === "/api/v1/health") {
      return jsonResponse({ status: "ok", banco_dados: "conectado", worker: { estado: "ocioso", tarefa_ativa: null } });
    }
    if (url.pathname === "/api/v1/execucoes-classificacao" && method === "GET") {
      return jsonResponse({ itens: [], total: 0 });
    }
    if (url.pathname === "/api/v1/execucoes-classificacao" && method === "POST") {
      const erro = servidor.erros.get("execucoes-classificacao");
      if (erro) return jsonResponse({ detail: erro.detail }, erro.status);
      const req = body as { taxonomia_id: string; perfil_id: string; escopo: string; questao_ids?: string[] };
      return jsonResponse(
        {
          execucao_id: "exec-1",
          taxonomia_id: req.taxonomia_id,
          perfil_id: req.perfil_id,
          escopo: req.escopo,
          escopo_questao_ids: req.questao_ids ?? [],
          status: "enfileirada",
        },
        202,
      );
    }

    if (url.pathname === "/api/v1/questoes") {
      const tamanhoSolicitado = Number(url.searchParams.get("tamanho_pagina") ?? 20);
      if (tamanhoSolicitado === 1) {
        return jsonResponse({ itens: [], total: 0, pagina: 1, tamanho_pagina: 1, contadores: contadores() });
      }
      const baseIds = url.searchParams.get("status_revisao") === "pendente" ? servidor.pendentes : servidor.recorte;
      let itensFiltrados = baseIds.map((id) => itemResumo(servidor.detalhes.get(id)!));
      if (url.searchParams.get("com_alerta_extracao") === "true") {
        itensFiltrados = itensFiltrados.filter((item) => item.alertas_abertos.length > 0);
      }
      if (url.searchParams.get("revisao_prioritaria") === "true") {
        itensFiltrados = itensFiltrados.filter((item) => item.revisao_prioritaria);
      }
      if (url.searchParams.get("ordenacao") === "fila_revisao") {
        itensFiltrados = [...itensFiltrados].sort(
          (a, b) => Number(b.revisao_prioritaria) - Number(a.revisao_prioritaria),
        );
      }
      const pagina = Number(url.searchParams.get("pagina") ?? 1);
      const resposta: ListaQuestoesResponse = {
        itens: itensFiltrados,
        total: itensFiltrados.length,
        pagina,
        tamanho_pagina: tamanhoSolicitado,
        taxonomia_id: TAX_ID,
        contadores: contadores(),
      };
      return jsonResponse(resposta);
    }

    const ativoMatch = url.pathname.match(/^\/api\/v1\/ativos-visuais\/([^/]+)$/);
    if (ativoMatch) {
      const ativoId = decodeURIComponent(ativoMatch[1]);
      let questaoDona: DetalheQuestaoResponse | undefined;
      for (const q of servidor.detalhes.values()) {
        if (q.ativos_visuais.some((a) => a.id === ativoId)) {
          questaoDona = q;
          break;
        }
      }
      if (!questaoDona) return jsonResponse({ detail: "Ativo visual não encontrado." }, 404);

      if (method === "DELETE") {
        servidor.detalhes.set(questaoDona.id, {
          ...questaoDona,
          editada_manualmente: true,
          ativos_visuais: questaoDona.ativos_visuais.filter((a) => a.id !== ativoId),
        });
        return new Response(null, { status: 204 });
      }

      if (method === "PATCH") {
        const arquivo = formData?.get("arquivo");
        const ordemRaw = formData?.get("ordem");
        const altRaw = formData?.get("alternativa_letra");
        const removerAlt = formData?.get("remover_alternativa_letra");
        if (altRaw && removerAlt === "true") {
          return jsonResponse({ detail: "Conflito entre alternativa_letra e remover_alternativa_letra." }, 422);
        }
        let atualizado: AtivoVisualResponse | undefined;
        const ativosAtualizados = questaoDona.ativos_visuais
          .map((a) => {
            if (a.id !== ativoId) return a;
            const proximo: AtivoVisualResponse = {
              ...a,
              ...(typeof ordemRaw === "string" ? { ordem: Number(ordemRaw) } : {}),
              ...(removerAlt === "true"
                ? { alternativa_letra: null }
                : typeof altRaw === "string"
                  ? { alternativa_letra: altRaw as LetraAlternativa }
                  : {}),
              ...(arquivo instanceof File ? { origem: "upload_manual" as const } : {}),
            };
            atualizado = proximo;
            return proximo;
          })
          .sort((a, b) => a.ordem - b.ordem);
        servidor.detalhes.set(questaoDona.id, {
          ...questaoDona,
          editada_manualmente: true,
          ativos_visuais: ativosAtualizados,
        });
        return jsonResponse(atualizado);
      }
    }

    const partes = url.pathname.match(/^\/api\/v1\/questoes\/([^/]+)(?:\/(.*))?$/);
    if (partes) {
      const [, rawId, resto] = partes;
      const id = decodeURIComponent(rawId);
      const d = servidor.detalhes.get(id);

      if (method === "GET" && !resto) {
        return d ? jsonResponse(d) : jsonResponse({ detail: "Não encontrada" }, 404);
      }

      const erro = [...servidor.erros.entries()].find(([sufixo]) => (resto ?? url.pathname).endsWith(sufixo));
      if (erro) return jsonResponse({ detail: erro[1].detail }, erro[1].status);

      if (!d) return jsonResponse({ detail: "Não encontrada" }, 404);

      if (method === "PATCH" && !resto) {
        const req = body as EditarQuestaoRequest;
        if (req.versao != null && req.versao !== d.versao) {
          return jsonResponse(
            {
              detail: `Questão '${id}' está na versão ${d.versao}; o pedido foi feito sobre a versão ${req.versao}.`,
            },
            409,
          );
        }
        const comConteudo: DetalheQuestaoResponse = {
          ...d,
          enunciado: req.enunciado ?? d.enunciado,
          alternativas: req.alternativas ?? d.alternativas,
          gabarito: req.gabarito ?? d.gabarito,
          editada_manualmente: true,
          versao: d.versao + 1,
        };
        const alertas = reavaliarAlertasEstruturais(comConteudo);
        const atualizada: DetalheQuestaoResponse = {
          ...comConteudo,
          alertas_extracao: alertas,
          classificacao_vigente: recalcularPrioridade(comConteudo.classificacao_vigente, alertas),
        };
        servidor.detalhes.set(id, atualizada);
        return jsonResponse(atualizada);
      }

      const alertaMatch = resto?.match(/^alertas\/([^/]+)$/);
      if (method === "PATCH" && alertaMatch) {
        const alertaId = decodeURIComponent(alertaMatch[1]);
        const req = body as { status?: string } | undefined;
        if (req?.status !== "resolvido") {
          return jsonResponse({ detail: "Status inválido." }, 422);
        }
        const alvo = d.alertas_extracao.find((a) => a.id === alertaId);
        if (!alvo) return jsonResponse({ detail: "Alerta não encontrado." }, 404);
        if (alvo.codigo !== "pdf_via_ocr" && alvo.codigo !== "fonte_symbol_detectada") {
          return jsonResponse({ detail: "Alerta estrutural não pode ser resolvido manualmente." }, 422);
        }
        const alertas = d.alertas_extracao.map((a) =>
          a.id === alertaId ? { ...a, status: "resolvido" as const, resolvido_em: "2026-01-02T10:00:00Z" } : a,
        );
        const atualizada: DetalheQuestaoResponse = {
          ...d,
          editada_manualmente: true,
          alertas_extracao: alertas,
          classificacao_vigente: recalcularPrioridade(d.classificacao_vigente, alertas),
        };
        servidor.detalhes.set(id, atualizada);
        return jsonResponse(atualizada);
      }

      if (method === "POST" && resto === "ativos-visuais") {
        const arquivo = formData?.get("arquivo");
        if (!(arquivo instanceof File)) {
          return jsonResponse({ detail: "Arquivo obrigatório." }, 422);
        }
        const altRaw = formData?.get("alternativa_letra");
        const ordemRaw = formData?.get("ordem");
        const proximaOrdem =
          typeof ordemRaw === "string" && ordemRaw.trim() !== ""
            ? Number(ordemRaw)
            : d.ativos_visuais.reduce((max, a) => Math.max(max, a.ordem), -1) + 1;
        const novoId = `av-${servidor.proximoAtivoSeq++}`;
        const novoAtivo: AtivoVisualResponse = {
          id: novoId,
          origem: "upload_manual",
          alternativa_letra: typeof altRaw === "string" ? (altRaw as LetraAlternativa) : null,
          ordem: proximaOrdem,
          pagina: null,
          url_arquivo: `/api/v1/ativos-visuais/${novoId}/arquivo`,
        };
        servidor.detalhes.set(id, {
          ...d,
          editada_manualmente: true,
          ativos_visuais: [...d.ativos_visuais, novoAtivo].sort((a, b) => a.ordem - b.ordem),
        });
        return jsonResponse(novoAtivo, 201);
      }

      if (resto?.endsWith("/aprovar")) {
        servidor.pendentes = servidor.pendentes.filter((q) => q !== id);
        servidor.detalhes.set(id, {
          ...d,
          classificacao_vigente: { ...d.classificacao_vigente!, status: "aprovada" },
        });
        return jsonResponse(servidor.detalhes.get(id)!.classificacao_vigente);
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

async function escolher(user: ReturnType<typeof userEvent.setup>, combobox: string, opcao: string) {
  await user.click(screen.getByRole("combobox", { name: combobox }));
  await user.click(await screen.findByRole("option", { name: opcao }));
}

const chamadasExecucao = (s: Servidor) =>
  s.chamadas.filter((c) => c.path === "/api/v1/execucoes-classificacao" && c.method === "POST");

afterEach(() => {
  vi.restoreAllMocks();
});

describe("EdicaoConteudoMidia: edição inline, Preview e Gabarito", () => {
  it("edita enunciado com KaTeX + script sanitizado, adiciona alternativa E, altera Gabarito, fecha alertas estruturais e não dispara LLM", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        enunciado: "Calcule a densidade <!-- formula-not-decoded -->",
        alternativas: [
          { letra: "A", texto: "1 kg/m³" },
          { letra: "B", texto: "2 kg/m³" },
          { letra: "C", texto: "3 kg/m³" },
          { letra: "D", texto: "4 kg/m³" },
        ],
        gabarito: { situacao_gabarito: "pendente", alternativa_correta: null },
        alertas_extracao: [
          alerta("al-formula", "formula_nao_decodificada"),
          alerta("al-alt", "alternativas_incompletas"),
        ],
        classificacao_vigente: classificacao("c-q1", { revisao_prioritaria: true }),
      }),
    );

    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    expect(screen.getByText("Fórmula não decodificada")).toBeInTheDocument();
    expect(screen.getByText("Alternativas incompletas")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));

    const campoEnunciado = screen.getByLabelText("Enunciado");
    const novoEnunciado = "Calcule a densidade $\\rho = \\frac{m}{V}$. <script>alert(1)</script>";
    await user.clear(campoEnunciado);
    await user.click(campoEnunciado);
    await user.paste(novoEnunciado);

    await user.click(screen.getByRole("tab", { name: "Preview" }));
    const preview = screen.getByTestId("preview-enunciado");
    expect(preview.querySelector(".katex")).not.toBeNull();
    expect(preview.querySelector("script")).toBeNull();
    expect(preview.innerHTML).not.toMatch(/<script/i);

    await user.click(screen.getByRole("tab", { name: "Editar" }));
    expect(screen.getByLabelText("Enunciado")).toHaveValue(novoEnunciado);

    await user.click(screen.getByRole("button", { name: "Adicionar alternativa E" }));
    const altE = screen.getByLabelText("Alternativa E");
    await user.click(altE);
    await user.paste("5 kg/m³");

    await escolher(user, "Situação do Gabarito", "Válida");
    await escolher(user, "Alternativa correta", "E");

    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    await screen.findByText("Editada manualmente");
    const patch = servidor.chamadas.find((c) => c.method === "PATCH" && c.path === "/api/v1/questoes/q1");
    expect(patch).toBeDefined();
    expect(patch?.search.get("taxonomia_id")).toBe(TAX_ID);
    expect(patch?.body).toEqual({
      enunciado: novoEnunciado,
      alternativas: [
        { letra: "A", texto: "1 kg/m³" },
        { letra: "B", texto: "2 kg/m³" },
        { letra: "C", texto: "3 kg/m³" },
        { letra: "D", texto: "4 kg/m³" },
        { letra: "E", texto: "5 kg/m³" },
      ],
      gabarito: { situacao_gabarito: "valida", alternativa_correta: "E" },
      versao: 1,
    });

    expect(screen.queryByText("Fórmula não decodificada")).not.toBeInTheDocument();
    expect(screen.queryByText("Alternativas incompletas")).not.toBeInTheDocument();
    expect(screen.getByText("Gabarito: E")).toBeInTheDocument();
    const altEItem = within(screen.getByRole("region", { name: "Alternativas" }))
      .getByText("5 kg/m³")
      .closest("li");
    expect(altEItem).toHaveAttribute("data-correta", "true");
    expect(chamadasExecucao(servidor)).toHaveLength(0);
    expect(servidor.detalhes.get("q1")?.versao).toBe(2);
    expect(servidor.detalhes.get("q1")?.editada_manualmente).toBe(true);
  });

  it("ao mudar Gabarito para anulada envia alternativa_correta: null", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    await escolher(user, "Situação do Gabarito", "Anulada");
    expect(screen.getByRole("combobox", { name: "Alternativa correta" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
    await screen.findByText("Gabarito: ANULADA");

    const patch = servidor.chamadas.find((c) => c.method === "PATCH" && c.path === "/api/v1/questoes/q1");
    expect(patch?.body).toMatchObject({
      gabarito: { situacao_gabarito: "anulada", alternativa_correta: null },
      versao: 1,
    });
    expect(chamadasExecucao(servidor)).toHaveLength(0);
  });
});

describe("EdicaoConteudoMidia: conflito 409 e CTA de reclassificação", () => {
  it("409 ao salvar mantém o rascunho no editor, mostra alerta e Recarregar dados atuais traz a nova versão", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    const campoEnunciado = screen.getByLabelText("Enunciado");
    await user.clear(campoEnunciado);
    await user.click(campoEnunciado);
    await user.paste("Rascunho digitado antes do conflito");

    // Simula alteração concorrente no servidor elevando versão para 2.
    const atual = servidor.detalhes.get("q1")!;
    servidor.detalhes.set("q1", {
      ...atual,
      versao: 2,
      enunciado: "Enunciado atualizado no servidor (v2).",
    });

    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
    const alertaErro = await screen.findByRole("alert");
    expect(alertaErro).toHaveTextContent("versão 2");
    expect(screen.getByLabelText("Enunciado")).toHaveValue("Rascunho digitado antes do conflito");

    const botaoRecarregar = screen.getByRole("button", { name: "Recarregar dados atuais" });
    await user.click(botaoRecarregar);

    await waitFor(() =>
      expect(screen.getByLabelText("Enunciado")).toHaveValue("Enunciado atualizado no servidor (v2)."),
    );
    expect(screen.queryByRole("button", { name: "Recarregar dados atuais" })).not.toBeInTheDocument();
  });

  it("banner após edição oferece Reclassificar esta questão e envia POST para execucoes-classificacao", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    const campoEnunciado = screen.getByLabelText("Enunciado");
    await user.clear(campoEnunciado);
    await user.click(campoEnunciado);
    await user.paste("Enunciado revisado para reclassificação.");
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    const regiaoBanner = await screen.findByRole("region", { name: "Reclassificação sob demanda" });
    expect(chamadasExecucao(servidor)).toHaveLength(0);

    const botaoReclassificar = within(regiaoBanner).getByRole("button", {
      name: "Reclassificar esta questão",
    });
    await waitFor(() => expect(botaoReclassificar).toBeEnabled());
    await user.click(botaoReclassificar);

    expect(
      await within(regiaoBanner).findByText(/Reclassificação enfileirada no worker local/),
    ).toBeInTheDocument();
    expect(chamadasExecucao(servidor)).toEqual([
      expect.objectContaining({
        method: "POST",
        path: "/api/v1/execucoes-classificacao",
        body: {
          taxonomia_id: TAX_ID,
          perfil_id: PERFIL_ID,
          escopo: "questao_ids",
          questao_ids: ["q1"],
          incluir_revisadas: true,
        },
      }),
    ]);
  });
});

describe("EdicaoConteudoMidia: visualizador multipágina do PDF", () => {
  it("abre página 28, alterna para página 29 e exibe alerta com Tentar novamente ao falhar o carregamento", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        prova: { id: "prova-42", exame: "ENADE", curso: "Computação", ano: 2023 },
        paginas: [29, 28],
      }),
    );

    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    await user.click(screen.getByRole("button", { name: "Ver página original do PDF" }));
    const dialog = await screen.findByRole("dialog");

    const img28 = within(dialog).getByRole("img", { name: /Página 28/ });
    expect(img28).toHaveAttribute("src", "/api/v1/provas/prova-42/paginas/28/imagem");

    await user.click(within(dialog).getByRole("button", { name: "Página 29" }));
    const img29 = within(dialog).getByRole("img", { name: /Página 29/ });
    expect(img29).toHaveAttribute("src", "/api/v1/provas/prova-42/paginas/29/imagem");

    fireEvent.error(img29);
    const alertaErro = await within(dialog).findByRole("alert");
    expect(alertaErro).toHaveTextContent("Não foi possível carregar a imagem desta página do PDF.");
    const botaoTentar = within(alertaErro).getByRole("button", { name: "Tentar novamente" });

    await user.click(botaoTentar);
    const imgRecarregada = within(dialog).getByRole("img", { name: /Página 29/ });
    expect(imgRecarregada).toHaveAttribute("src", "/api/v1/provas/prova-42/paginas/29/imagem?r=1");
  });
});

describe("EdicaoConteudoMidia: CRUD manual de Ativo Visual", () => {
  it("exibe origens, valida arquivo .txt localmente, faz upload na alternativa C, substitui, reordena, altera vínculo e exclui", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        ativos_visuais: [
          ativo("av-1", { origem: "picture_docling", ordem: 0, alternativa_letra: null }),
          ativo("av-2", { origem: "formula_recorte", ordem: 1, alternativa_letra: "A" }),
        ],
      }),
    );

    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));

    const listaAtivos = screen.getByRole("list", { name: "Ativos Visuais da Questão" });
    expect(within(listaAtivos).getByText("Docling")).toBeInTheDocument();
    expect(within(listaAtivos).getByText("Recorte de fórmula")).toBeInTheDocument();

    // 1) Rejeição local de .txt sem chamar API
    const inputNovo = screen.getByLabelText("Novo Ativo Visual (PNG ou JPEG)");
    const txtInvalido = new File(["nao e imagem"], "invalido.txt", { type: "text/plain" });
    await user.upload(inputNovo, txtInvalido);
    await user.click(screen.getByRole("button", { name: "Enviar Ativo Visual" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Envie uma imagem no formato PNG ou JPEG.");
    expect(
      servidor.chamadas.filter((c) => c.path.endsWith("/ativos-visuais") && c.method === "POST"),
    ).toHaveLength(0);

    // 2) Upload válido vinculado à alternativa C
    const pngValido = new File(["png-bytes"], "diagrama.png", { type: "image/png" });
    await user.upload(inputNovo, pngValido);
    await escolher(user, "Vincular novo Ativo Visual a", "Alternativa C");
    await user.click(screen.getByRole("button", { name: "Enviar Ativo Visual" }));

    await waitFor(() => expect(within(listaAtivos).getAllByRole("listitem")).toHaveLength(3));
    expect(within(listaAtivos).getByText("Upload manual")).toBeInTheDocument();

    const postAtivo = servidor.chamadas.find(
      (c) => c.method === "POST" && c.path === "/api/v1/questoes/q1/ativos-visuais",
    );
    expect(postAtivo?.formData?.get("alternativa_letra")).toBe("C");
    const arquivoEnviado = postAtivo?.formData?.get("arquivo");
    expect(arquivoEnviado).toBeInstanceOf(File);
    expect((arquivoEnviado as File).name).toBe("diagrama.png");

    // 3) Substituição de arquivo atualiza src com ?v= no editor e na galeria de leitura
    const inputSubstituir = screen.getByLabelText("Substituir arquivo do Ativo Visual 1");
    const jpegSubstituto = new File(["jpg-bytes"], "substituto.jpg", { type: "image/jpeg" });
    await user.upload(inputSubstituir, jpegSubstituto);

    await waitFor(() =>
      expect(within(listaAtivos).getByAltText("Ativo Visual 1")).toHaveAttribute(
        "src",
        "/api/v1/ativos-visuais/av-1/arquivo?v=1",
      ),
    );
    const patchSubstituicao = servidor.chamadas.find(
      (c) => c.method === "PATCH" && c.path === "/api/v1/ativos-visuais/av-1",
    );
    expect(patchSubstituicao?.formData?.get("arquivo")).toBeInstanceOf(File);

    // 4) Reordenação sequencial (descer item 1 -> av-2 vira #1 e av-1 vira #2)
    await user.click(screen.getByRole("button", { name: "Mover Ativo Visual 1 para baixo" }));
    await waitFor(() =>
      expect(within(listaAtivos).getByAltText("Ativo Visual 1")).toHaveAttribute(
        "src",
        "/api/v1/ativos-visuais/av-2/arquivo",
      ),
    );
    expect(within(listaAtivos).getByAltText("Ativo Visual 2")).toHaveAttribute(
      "src",
      "/api/v1/ativos-visuais/av-1/arquivo?v=1",
    );

    const patchesReordenacao = servidor.chamadas.filter(
      (c) => c.method === "PATCH" && c.path.startsWith("/api/v1/ativos-visuais/") && c.formData?.has("ordem"),
    );
    expect(patchesReordenacao.map((c) => [c.path, c.formData?.get("ordem")])).toEqual([
      ["/api/v1/ativos-visuais/av-2", "0"],
      ["/api/v1/ativos-visuais/av-1", "1"],
    ]);

    // Subir item 2 restaura av-1 como #1 e av-2 como #2
    await user.click(screen.getByRole("button", { name: "Mover Ativo Visual 2 para cima" }));
    await waitFor(() =>
      expect(within(listaAtivos).getByAltText("Ativo Visual 1")).toHaveAttribute(
        "src",
        "/api/v1/ativos-visuais/av-1/arquivo?v=1",
      ),
    );
    // Desce novamente para prosseguir com av-2 como #1 nos testes de vínculo
    await user.click(screen.getByRole("button", { name: "Mover Ativo Visual 1 para baixo" }));
    await waitFor(() =>
      expect(within(listaAtivos).getByAltText("Ativo Visual 1")).toHaveAttribute(
        "src",
        "/api/v1/ativos-visuais/av-2/arquivo",
      ),
    );

    // 5) Vínculo / desvínculo refletido na galeria de leitura
    // Ativo #1 (av-2) estava em Alternativa A -> desvincula para Enunciado
    await escolher(user, "Vínculo do Ativo Visual 1", "Enunciado");
    await waitFor(() =>
      expect(
        servidor.chamadas.some(
          (c) =>
            c.method === "PATCH" &&
            c.path === "/api/v1/ativos-visuais/av-2" &&
            c.formData?.get("remover_alternativa_letra") === "true",
        ),
      ).toBe(true),
    );

    // Ativo #2 (av-1) estava em Enunciado -> vincula à Alternativa B
    await escolher(user, "Vínculo do Ativo Visual 2", "Alternativa B");
    await waitFor(() =>
      expect(
        servidor.chamadas.some(
          (c) =>
            c.method === "PATCH" &&
            c.path === "/api/v1/ativos-visuais/av-1" &&
            c.formData?.get("alternativa_letra") === "B",
        ),
      ).toBe(true),
    );

    // Fecha edição e verifica na galeria de leitura os vínculos e o ?v=1
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    const regiaoEnunciado = await screen.findByRole("region", { name: "Enunciado" });
    expect(within(regiaoEnunciado).getByRole("img")).toHaveAttribute(
      "src",
      "/api/v1/ativos-visuais/av-2/arquivo",
    );
    const regiaoAlt = screen.getByRole("region", { name: "Alternativas" });
    const itemAltB = within(regiaoAlt).getByText("Alternativa B").closest("li")!;
    expect(within(itemAltB).getByRole("img")).toHaveAttribute(
      "src",
      "/api/v1/ativos-visuais/av-1/arquivo?v=1",
    );
    const itemAltC = within(regiaoAlt).getByText("Alternativa C").closest("li")!;
    expect(within(itemAltC).getByRole("img")).toHaveAttribute(
      "src",
      "/api/v1/ativos-visuais/av-100/arquivo",
    );

    // Reabre edição para testar exclusão com AlertDialog
    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    await user.click(screen.getByRole("button", { name: "Excluir Ativo Visual 1" }));
    const confirmacao = await screen.findByRole("alertdialog");
    expect(within(confirmacao).getByText("Excluir Ativo Visual?")).toBeInTheDocument();
    await user.click(within(confirmacao).getByRole("button", { name: "Confirmar exclusão" }));

    await waitFor(() =>
      expect(
        within(screen.getByRole("list", { name: "Ativos Visuais da Questão" })).getAllByRole("listitem"),
      ).toHaveLength(2),
    );
    expect(
      servidor.chamadas.some((c) => c.method === "DELETE" && c.path === "/api/v1/ativos-visuais/av-2"),
    ).toBe(true);
  });
});

describe("EdicaoConteudoMidia: alertas de inspeção e revisao_prioritaria", () => {
  it("exibe Marcar como verificado só para inspeção aberta e atualiza revisao_prioritaria ao resolver último gatilho", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        alertas_extracao: [
          alerta("al-formula", "formula_nao_decodificada"),
          alerta("al-alt", "alternativas_incompletas"),
          alerta("al-ocr", "pdf_via_ocr"),
          alerta("al-symbol", "fonte_symbol_detectada"),
        ],
        classificacao_vigente: classificacao("c-q1", { confianca: 0.92, revisao_prioritaria: true }),
      }),
    );

    renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    const listaAlertas = screen.getByRole("list", { name: "Alertas de Extração" });
    const botoesVerificar = within(listaAlertas).getAllByRole("button", { name: /Marcar como verificado/ });
    expect(botoesVerificar).toHaveLength(2);

    const itemFormula = within(listaAlertas).getByText("Fórmula não decodificada").closest("li")!;
    const itemAlt = within(listaAlertas).getByText("Alternativas incompletas").closest("li")!;
    expect(within(itemFormula).queryByRole("button")).not.toBeInTheDocument();
    expect(within(itemAlt).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("Revisão prioritária")).toBeInTheDocument();

    // Fecha os alertas estruturais editando o conteúdo, deixando apenas pdf_via_ocr como gatilho crítico
    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));
    await screen.findByText("Editada manualmente");

    expect(screen.queryByText("Fórmula não decodificada")).not.toBeInTheDocument();
    expect(screen.queryByText("Alternativas incompletas")).not.toBeInTheDocument();
    expect(screen.getByText("Revisão prioritária")).toBeInTheDocument();

    // Agora resolve o último gatilho crítico (pdf_via_ocr)
    await user.click(screen.getByRole("button", { name: "Marcar como verificado (PDF lido via OCR)" }));

    await waitFor(() => expect(screen.queryByText("PDF lido via OCR")).not.toBeInTheDocument());
    expect(screen.queryByText("Revisão prioritária")).not.toBeInTheDocument();

    const patchOcr = servidor.chamadas.find(
      (c) => c.method === "PATCH" && c.path === "/api/v1/questoes/q1/alertas/al-ocr",
    );
    expect(patchOcr?.body).toEqual({ status: "resolvido" });

    // Resolve também fonte_symbol_detectada (informativo)
    await user.click(screen.getByRole("button", { name: "Marcar como verificado (Fonte Symbol detectada)" }));
    await waitFor(() => expect(screen.queryByText("Fonte Symbol detectada")).not.toBeInTheDocument());
  });
});

describe("EdicaoConteudoMidia: atalhos de teclado desabilitados", () => {
  it("bloqueia a, e, ArrowLeft e ArrowRight enquanto Editar conteúdo ou visualizador de PDF estão abertos", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&questao=q2`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 2" });

    // 1) Durante Editar conteúdo aberto (inclusive com foco fora do textarea, em botão/container)
    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    await user.click(screen.getByRole("tab", { name: "Preview" }));
    await user.click(screen.getByRole("heading", { name: "Questão Nº 2" }));

    await user.keyboard("ae{ArrowLeft}{ArrowRight}");
    fireEvent.keyDown(document.body, { key: "a" });
    fireEvent.keyDown(document.body, { key: "e" });
    fireEvent.keyDown(document.body, { key: "ArrowLeft" });
    fireEvent.keyDown(document.body, { key: "ArrowRight" });

    expect(servidor.chamadas.filter((c) => c.method === "POST")).toHaveLength(0);
    expect(screen.queryByRole("form", { name: "Formulário de classificação" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Questão Nº 2" })).toBeInTheDocument();
    expect(router.state.location.search).toContain("questao=q2");

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("form", { name: "Formulário de edição de conteúdo" })).not.toBeInTheDocument();

    // 2) Durante visualizador de PDF aberto
    await user.click(screen.getByRole("button", { name: "Ver página original do PDF" }));
    const dialogPdf = await screen.findByRole("dialog");

    await user.keyboard("ae{ArrowLeft}{ArrowRight}");
    fireEvent.keyDown(document.body, { key: "a" });
    fireEvent.keyDown(document.body, { key: "e" });
    fireEvent.keyDown(document.body, { key: "ArrowLeft" });
    fireEvent.keyDown(document.body, { key: "ArrowRight" });

    expect(servidor.chamadas.filter((c) => c.method === "POST")).toHaveLength(0);
    expect(screen.queryByRole("form", { name: "Formulário de classificação" })).not.toBeInTheDocument();
    expect(within(dialogPdf).getByRole("heading", { name: /Questão Nº 2/ })).toBeInTheDocument();
    expect(router.state.location.search).toContain("questao=q2");

    await user.click(within(dialogPdf).getByRole("button", { name: "Fechar" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Questão Nº 2" })).toBeInTheDocument();
  });
});

describe("EdicaoConteudoMidia: fixação da questão ao editar ou verificar alerta sem ?questao= na URL", () => {
  it("ao salvar edição em fila_revisao sem ?questao=, mantém a questão e o BannerReclassificacao mesmo quando rebaixada na fila", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        enunciado: "Calcule $x$ <!-- formula-not-decoded -->",
        alertas_extracao: [alerta("al-formula", "formula_nao_decodificada")],
        classificacao_vigente: classificacao("c-q1", {
          questao_id: "q1",
          confianca: 0.92,
          revisao_prioritaria: true,
        }),
      }),
    );
    servidor.detalhes.set(
      "q2",
      detalhe("q2", 2, {
        classificacao_vigente: classificacao("c-q2", {
          questao_id: "q2",
          confianca: 0.55,
          revisao_prioritaria: true,
        }),
      }),
    );

    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("1 de 3");

    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    const campoEnunciado = screen.getByLabelText("Enunciado");
    await user.clear(campoEnunciado);
    await user.click(campoEnunciado);
    await user.paste("Calcule $x = 2$.");
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    await screen.findByText("Editada manualmente");
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Reclassificação sob demanda" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reclassificar esta questão" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("2 de 3"));
    expect(router.state.location.search).toContain("questao=q1");
  });

  it("ao salvar edição no recorte com_alerta_extracao=true sem ?questao=, mantém a questão fora da fila e exibe BannerReclassificacao", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor({ recorte: ["q1", "q2"] });
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        enunciado: "Fórmula quebrada <!-- formula-not-decoded -->",
        alertas_extracao: [alerta("al-formula", "formula_nao_decodificada")],
      }),
    );
    servidor.detalhes.set(
      "q2",
      detalhe("q2", 2, {
        alertas_extracao: [alerta("al-ocr-2", "pdf_via_ocr")],
      }),
    );

    renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&com_alerta_extracao=true`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("1 de 2");

    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    const campoEnunciado = screen.getByLabelText("Enunciado");
    await user.clear(campoEnunciado);
    await user.click(campoEnunciado);
    await user.paste("Fórmula corrigida $a^2 + b^2 = c^2$.");
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    await screen.findByText("Editada manualmente");
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Reclassificação sob demanda" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("Fora da fila · 1 na fila"));

    await user.click(screen.getByRole("button", { name: "Próxima" }));
    await screen.findByRole("heading", { name: "Questão Nº 2" });
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("1 de 1");
  });

  it("ao clicar Marcar como verificado durante a edição sem ?questao=, preserva o editor aberto e o rascunho", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor({ recorte: ["q1", "q2"] });
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        alertas_extracao: [alerta("al-ocr", "pdf_via_ocr")],
        classificacao_vigente: classificacao("c-q1", {
          questao_id: "q1",
          confianca: 0.92,
          revisao_prioritaria: true,
        }),
      }),
    );
    servidor.detalhes.set(
      "q2",
      detalhe("q2", 2, {
        alertas_extracao: [alerta("al-ocr-2", "pdf_via_ocr")],
        classificacao_vigente: classificacao("c-q2", {
          questao_id: "q2",
          confianca: 0.55,
          revisao_prioritaria: true,
        }),
      }),
    );

    renderRevisao(`/revisao?taxonomia=${TAX_ID}&modo=recorte&com_alerta_extracao=true`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });

    await user.click(screen.getByRole("button", { name: "Editar conteúdo" }));
    const campoEnunciado = screen.getByLabelText("Enunciado");
    await user.clear(campoEnunciado);
    await user.click(campoEnunciado);
    await user.paste("Rascunho em andamento");

    await user.click(screen.getByRole("button", { name: "Marcar como verificado (PDF lido via OCR)" }));

    await waitFor(() => expect(screen.queryByText("PDF lido via OCR")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("Fora da fila · 1 na fila"));
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Formulário de edição de conteúdo" })).toBeInTheDocument();
    expect(screen.getByLabelText("Enunciado")).toHaveValue("Rascunho em andamento");
  });

  it("ao clicar Marcar como verificado no modo leitura sem ?questao=, mantém a questão mesmo quando rebaixada em fila_revisao", async () => {
    const user = userEvent.setup();
    const servidor = criarServidor();
    servidor.detalhes.set(
      "q1",
      detalhe("q1", 1, {
        alertas_extracao: [
          alerta("al-ocr", "pdf_via_ocr"),
          alerta("al-symbol", "fonte_symbol_detectada"),
        ],
        classificacao_vigente: classificacao("c-q1", {
          questao_id: "q1",
          confianca: 0.92,
          revisao_prioritaria: true,
        }),
      }),
    );
    servidor.detalhes.set(
      "q2",
      detalhe("q2", 2, {
        classificacao_vigente: classificacao("c-q2", {
          questao_id: "q2",
          confianca: 0.55,
          revisao_prioritaria: true,
        }),
      }),
    );

    const { router } = renderRevisao(`/revisao?taxonomia=${TAX_ID}`, servidor);
    await screen.findByRole("heading", { name: "Questão Nº 1" });
    expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("1 de 3");

    await user.click(screen.getByRole("button", { name: "Marcar como verificado (PDF lido via OCR)" }));

    await waitFor(() => expect(screen.queryByText("PDF lido via OCR")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Questão Nº 1" })).toBeInTheDocument();
    expect(screen.getByText("Fonte Symbol detectada")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("revisao-posicao")).toHaveTextContent("2 de 3"));
    expect(router.state.location.search).toContain("questao=q1");
  });
});
