import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/app/App";
import { ROUTER_FUTURE_FLAGS, createAppRoutes } from "@/app/router";

const TAXONOMIA_SEEDED_ID = "22222222-2222-2222-2222-222222222222";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("App", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
  });

  it("renderiza o shell global, redireciona / para /provas e carrega a Taxonomia padrão", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = new URL(String(input), "http://localhost");
      if (url.pathname === "/api/v1/taxonomias") {
        return jsonResponse({
          itens: [
            {
              id: TAXONOMIA_SEEDED_ID,
              codigo: "enade-eng-computacao",
              nome: "ENADE Engenharia de Computação",
              curso_referencia: "Engenharia de Computação",
              disciplinas: [],
            },
          ],
          total: 1,
        });
      }
      if (url.pathname === "/api/v1/health") {
        return jsonResponse({
          status: "ok",
          banco_dados: "conectado",
          worker: { estado: "ocioso", tarefa_ativa: null },
        });
      }
      if (url.pathname === "/api/v1/provas" || url.pathname === "/api/v1/execucoes-classificacao") {
        return jsonResponse({ itens: [], total: 0 });
      }
      if (url.pathname === "/api/v1/questoes") {
        return jsonResponse({
          itens: [],
          total: 0,
          pagina: 1,
          tamanho_pagina: 1,
          taxonomia_id: TAXONOMIA_SEEDED_ID,
          contadores: { pendentes: 0, divergencias: 0, disciplina_arquivada: 0 },
        });
      }
      return jsonResponse({}, 404);
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const router = createMemoryRouter(createAppRoutes(), {
      initialEntries: ["/"],
      future: ROUTER_FUTURE_FLAGS,
    });

    render(<App queryClient={queryClient} router={router} />);

    expect(screen.getByRole("link", { name: "Enade Questões" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Questões" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Revisão/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Provas" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Taxonomias" })).toBeInTheDocument();

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/provas");
    });

    const combobox = await screen.findByRole("combobox", { name: /taxonomia ativa/i });
    expect(combobox).toHaveTextContent("ENADE Engenharia de Computação");
  });
});
