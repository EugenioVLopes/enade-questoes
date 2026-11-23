import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import { isApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import type { components } from "@/api/schema";

export type ListaQuestoesResponse = components["schemas"]["ListaQuestoesResponse"];
export type ContadoresRevisaoResponse = components["schemas"]["ContadoresRevisaoResponse"];

export interface RevisaoContadores {
  pendentes: number;
  divergencias: number;
  disciplina_arquivada: number;
  totalBadge: number;
}

export async function obterContadoresRevisao(taxonomiaId: string): Promise<RevisaoContadores> {
  const response = await apiRequest<ListaQuestoesResponse>("/api/v1/questoes", {
    query: {
      taxonomia_id: taxonomiaId,
      pagina: 1,
      tamanho_pagina: 1,
    },
  });

  const pendentes = response.contadores?.pendentes ?? 0;
  const divergencias = response.contadores?.divergencias ?? 0;
  const disciplina_arquivada = response.contadores?.disciplina_arquivada ?? 0;

  return {
    pendentes,
    divergencias,
    disciplina_arquivada,
    totalBadge: pendentes + divergencias,
  };
}

export function useRevisaoContadoresQuery(taxonomiaId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.questoes.contadores(taxonomiaId),
    queryFn: () => obterContadoresRevisao(taxonomiaId as string),
    enabled: Boolean(taxonomiaId),
    retry: (failureCount, error) => {
      if (isApiError(error) && error.status === 404) {
        return false;
      }
      return failureCount < 1;
    },
  });
}
