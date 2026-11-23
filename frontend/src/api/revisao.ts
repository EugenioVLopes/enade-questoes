import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import { isApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import type { ListarQuestoesParams } from "@/api/questoes";
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

export type DetalheQuestaoResponse = components["schemas"]["DetalheQuestaoResponse"];
export type ClassificacaoResponse = components["schemas"]["ClassificacaoResponse"];
export type DivergenciaResponse = components["schemas"]["DivergenciaResponse"];
export type AtivoVisualResponse = components["schemas"]["AtivoVisualResponse"];
export type AlertaExtracaoResponse = components["schemas"]["AlertaExtracaoResponse"];
export type CorrigirClassificacaoRequest = components["schemas"]["CorrigirClassificacaoRequest"];
export type ResolverDivergenciaRequest = components["schemas"]["ResolverDivergenciaRequest"];
type ResolverDivergenciaResponse = components["schemas"]["ResolverDivergenciaResponse"];

/** Itens por página da fila de Revisão (máximo aceito pela API). */
export const TAMANHO_PAGINA_FILA = 200;

const rotaQuestao = (questaoId: string) => `/api/v1/questoes/${encodeURIComponent(questaoId)}`;

function obterQuestaoDetalhe(
  questaoId: string,
  taxonomiaId: string,
): Promise<DetalheQuestaoResponse> {
  return apiRequest<DetalheQuestaoResponse>(rotaQuestao(questaoId), {
    query: { taxonomia_id: taxonomiaId },
  });
}

export function useQuestaoDetalheQuery(
  questaoId: string | null | undefined,
  taxonomiaId: string | null | undefined,
) {
  return useQuery({
    queryKey: queryKeys.questoes.detalhe(questaoId ?? "", taxonomiaId ?? ""),
    queryFn: () => obterQuestaoDetalhe(questaoId as string, taxonomiaId as string),
    enabled: Boolean(questaoId) && Boolean(taxonomiaId),
  });
}

/** Fila de Revisão: páginas de `TAMANHO_PAGINA_FILA` itens, a seguinte sob demanda (`params` sem `pagina`). */
export function useFilaRevisaoQuery(params: ListarQuestoesParams | null) {
  return useInfiniteQuery({
    queryKey: queryKeys.questoes.fila(params ?? {}),
    queryFn: ({ pageParam }) =>
      apiRequest<ListaQuestoesResponse>("/api/v1/questoes", {
        query: { ...(params as ListarQuestoesParams), pagina: pageParam },
      }),
    initialPageParam: 1,
    getNextPageParam: (ultima) =>
      ultima.pagina * ultima.tamanho_pagina < ultima.total ? ultima.pagina + 1 : undefined,
    enabled: params !== null,
  });
}

function aprovarClassificacao({
  questaoId,
  taxonomiaId,
}: {
  questaoId: string;
  taxonomiaId: string;
}): Promise<ClassificacaoResponse> {
  return apiRequest<ClassificacaoResponse>(
    `${rotaQuestao(questaoId)}/classificacoes/${encodeURIComponent(taxonomiaId)}/aprovar`,
    { method: "POST" },
  );
}

function corrigirClassificacao({
  questaoId,
  taxonomiaId,
  correcao,
}: {
  questaoId: string;
  taxonomiaId: string;
  correcao: CorrigirClassificacaoRequest;
}): Promise<ClassificacaoResponse> {
  return apiRequest<ClassificacaoResponse>(
    `${rotaQuestao(questaoId)}/classificacoes/${encodeURIComponent(taxonomiaId)}/corrigir`,
    { method: "POST", json: correcao },
  );
}

function resolverDivergencia({
  questaoId,
  divergenciaId,
  ...payload
}: ResolverDivergenciaRequest & {
  questaoId: string;
  divergenciaId: string;
}): Promise<ResolverDivergenciaResponse> {
  return apiRequest<ResolverDivergenciaResponse>(
    `${rotaQuestao(questaoId)}/divergencias/${encodeURIComponent(divergenciaId)}/resolver`,
    { method: "POST", json: payload },
  );
}

// Todo veredito invalida `questoes.all`: fila, detalhe e o badge global (`questoes.contadores`).
// As mutations devolvem a promessa da invalidação para o chamador só avançar com a fila já atualizada.
function useInvalidarQuestoes() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.questoes.all });
}

export function useAprovarClassificacaoMutation() {
  const invalidar = useInvalidarQuestoes();
  return useMutation({ mutationFn: aprovarClassificacao, onSuccess: invalidar });
}

export function useCorrigirClassificacaoMutation() {
  const invalidar = useInvalidarQuestoes();
  return useMutation({ mutationFn: corrigirClassificacao, onSuccess: invalidar });
}

export function useResolverDivergenciaMutation() {
  const invalidar = useInvalidarQuestoes();
  return useMutation({ mutationFn: resolverDivergencia, onSuccess: invalidar });
}
