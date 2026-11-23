import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest, fetchHealth } from "@/api/client";
import {
  ApiError,
  ProvaConflictError,
  extractErrorMessage,
  isApiError,
  isProvaConflictError,
} from "@/api/errors";
import { atualizarGabarito, criarProva, reprocessarProva } from "@/api/provas";
import {
  findDefaultPerfil,
  findDefaultTaxonomia,
  type PerfilClassificacaoResponse,
  type TaxonomiaResponse,
} from "@/api/taxonomias";

describe("api/errors", () => {
  it("extrai detail string, ValidationError[] e fallback", () => {
    expect(extractErrorMessage({ detail: "Prova não encontrada." })).toBe("Prova não encontrada.");
    expect(
      extractErrorMessage({
        detail: [
          {
            loc: ["body", "ano"],
            msg: "Input should be greater than 2000",
            type: "greater_than",
          },
          {
            loc: ["query", "pagina"],
            msg: "Must be positive",
            type: "value_error",
          },
        ],
      }),
    ).toBe("ano: Input should be greater than 2000; pagina: Must be positive");
    expect(extractErrorMessage({}, "Fallback custom")).toBe("Fallback custom");
  });

  it("identifica ProvaConflictError com instanceof", () => {
    const err = new ProvaConflictError({
      detail: "Prova já existente",
      prova_id: "prova-123",
      exame: "ENADE",
      curso: "Engenharia de Computação",
      ano: 2023,
    });

    expect(isApiError(err)).toBe(true);
    expect(isProvaConflictError(err)).toBe(true);
    expect(err.status).toBe(409);
    expect(err.provaId).toBe("prova-123");
  });
});

describe("api/client & endpoint wrappers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("omite Content-Type ao enviar FormData e trata 204 No Content", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const formData = new FormData();
    formData.append("arquivo_prova", new File(["pdf"], "prova.pdf", { type: "application/pdf" }));

    const res = await apiRequest<{ ok: boolean }>("/api/v1/provas", {
      method: "POST",
      body: formData,
      headers: { "Content-Type": "multipart/form-data" },
    });
    expect(res).toEqual({ ok: true });

    const firstInit = fetchSpy.mock.calls[0]?.[1];
    const firstHeaders = new Headers(firstInit?.headers);
    expect(firstHeaders.has("Content-Type")).toBe(false);

    const emptyRes = await apiRequest<void>("/api/v1/ativos-visuais/1", { method: "DELETE" });
    expect(emptyRes).toBeUndefined();
  });

  it("lança ProvaConflictError em 409 ConflitoProvaResponse e ApiError em 422", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            detail: "Já existe uma prova cadastrada.",
            prova_id: "p-99",
            exame: "ENADE",
            curso: "Engenharia de Computação",
            ano: 2023,
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            detail: [{ loc: ["body", "curso"], msg: "Campo obrigatório", type: "missing" }],
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      );

    await expect(apiRequest("/api/v1/provas", { method: "POST" })).rejects.toSatisfy(
      (err: unknown) => isProvaConflictError(err) && err.provaId === "p-99",
    );

    await expect(apiRequest("/api/v1/provas", { method: "POST" })).rejects.toSatisfy(
      (err: unknown) =>
        isApiError(err) &&
        !(err instanceof ProvaConflictError) &&
        err.status === 422 &&
        err.detail === "curso: Campo obrigatório" &&
        err.validationErrors?.length === 1,
    );
  });

  it("fetchHealth aceita 200 e 503 com HealthResponse válido e rejeita 503 HTML inválido", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "ok",
            banco_dados: "conectado",
            worker: { estado: "ocioso" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "degradado",
            banco_dados: "indisponivel",
            worker: {
              estado: "ocupado",
              tarefa_ativa: "Classificando ENADE 2023: 5/10",
              tipo: "classificacao",
              alvo: "ENADE 2023",
              processadas: 5,
              total: 10,
            },
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response("<html>503 Service Unavailable</html>", {
          status: 503,
          statusText: "Service Unavailable",
        }),
      );

    const healthy = await fetchHealth();
    expect(healthy.worker.estado).toBe("ocioso");

    const degraded = await fetchHealth();
    expect(degraded.status).toBe("degradado");
    expect(degraded.banco_dados).toBe("indisponivel");
    expect(degraded.worker.tarefa_ativa).toBe("Classificando ENADE 2023: 5/10");

    await expect(fetchHealth()).rejects.toBeInstanceOf(ApiError);
  });

  it("seleciona Taxonomia e Perfil de Classificação padrão", () => {
    const taxonomias: TaxonomiaResponse[] = [
      {
        id: "t-1",
        codigo: "ppc-custom",
        nome: "PPC Customizado",
        curso_referencia: "Computação",
        disciplinas: [],
      },
      {
        id: "t-2",
        codigo: "enade-eng-computacao",
        nome: "ENADE Engenharia de Computação",
        curso_referencia: "Engenharia de Computação",
        disciplinas: [],
      },
    ];
    expect(findDefaultTaxonomia(taxonomias)?.id).toBe("t-2");

    const perfis: PerfilClassificacaoResponse[] = [
      {
        id: "p-1",
        codigo: "v2-fronteiras",
        versao: "v2",
        diretrizes_gerais: "",
        guia_fronteiras: "",
        template_prompt: "",
        descricao: "",
      },
      {
        id: "p-2",
        codigo: "v2-fronteiras",
        versao: "v1",
        diretrizes_gerais: "",
        guia_fronteiras: "",
        template_prompt: "",
        descricao: "",
      },
    ];
    expect(findDefaultPerfil(perfis)?.id).toBe("p-2");
  });

  it("criarProva omite arquivo_gabarito opcional, faixa isolada e perfil_id sem taxonomia_id", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          prova_id: "p-1",
          ingestao_id: "i-1",
          status: "pendente",
          exame: "ENADE",
          curso: "Engenharia de Computação",
          ano: 2023,
          questao_inicio: 10,
          questao_fim: 38,
          possui_gabarito: false,
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );

    const provaPdf = new File(["pdf"], "enade2023.pdf", { type: "application/pdf" });
    await criarProva({
      arquivo_prova: provaPdf,
      curso: " Engenharia de Computação ",
      ano: 2023,
      exame: "ENADE",
      arquivo_gabarito: null,
      questao_inicio: 10,
      questao_fim: null,
      taxonomia_id: null,
      perfil_id: "perfil-1",
    });

    const body = fetchSpy.mock.calls[0]?.[1]?.body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("curso")).toBe("Engenharia de Computação");
    expect(body.get("ano")).toBe("2023");
    expect(body.has("arquivo_gabarito")).toBe(false);
    expect(body.has("questao_inicio")).toBe(false);
    expect(body.has("questao_fim")).toBe(false);
    expect(body.has("perfil_id")).toBe(false);
  });

  it("atualizarGabarito usa PUT e reprocessarProva envia sobrescrever_editadas", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            mantidas: 20,
            alteradas: 2,
            anuladas: 1,
            sem_correspondencia: [],
            questoes_sem_gabarito: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            prova_id: "p-1",
            ingestao_id: "i-2",
            status: "pendente",
            sobrescrever_editadas: false,
          }),
          { status: 202, headers: { "Content-Type": "application/json" } },
        ),
      );

    const gabaritoPdf = new File(["gab"], "gabarito.pdf", { type: "application/pdf" });
    const resumo = await atualizarGabarito({ provaId: "p-1", arquivo_gabarito: gabaritoPdf });
    expect(resumo.mantidas).toBe(20);
    expect(fetchSpy.mock.calls[0]?.[0]).toBe("/api/v1/provas/p-1/gabarito");
    expect(fetchSpy.mock.calls[0]?.[1]?.method).toBe("PUT");

    await reprocessarProva({ provaId: "p-1" });
    expect(fetchSpy.mock.calls[1]?.[0]).toBe("/api/v1/provas/p-1/reprocessar");
    expect(fetchSpy.mock.calls[1]?.[1]?.method).toBe("POST");
    expect(fetchSpy.mock.calls[1]?.[1]?.body).toBe(
      JSON.stringify({ sobrescrever_editadas: false }),
    );
  });
});
