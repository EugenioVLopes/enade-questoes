import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type { components } from "@/api/schema";

export const CODIGO_TAXONOMIA_PADRAO = "enade-eng-computacao";
export const NOME_TAXONOMIA_PADRAO = "ENADE Engenharia de Computação";
export const CODIGO_PERFIL_PADRAO = "v2-fronteiras";
export const VERSAO_PERFIL_PADRAO = "v1";

export type TaxonomiaResponse = components["schemas"]["TaxonomiaResponse"];
export type DisciplinaResponse = components["schemas"]["DisciplinaResponse"];
export type ListaTaxonomiasResponse = components["schemas"]["ListaTaxonomiasResponse"];
export type PerfilClassificacaoResponse = components["schemas"]["PerfilClassificacaoResponse"];
export type ListaPerfisClassificacaoResponse =
  components["schemas"]["ListaPerfisClassificacaoResponse"];
export type TaxonomiaCriarRequest = components["schemas"]["TaxonomiaCriarRequest"];
export type TaxonomiaAtualizarRequest = components["schemas"]["TaxonomiaAtualizarRequest"];
export type DisciplinaCriarRequest = components["schemas"]["DisciplinaCriarRequest"];
export type DisciplinaAtualizarRequest = components["schemas"]["DisciplinaAtualizarRequest"];
export type PerfilClassificacaoCriarRequest =
  components["schemas"]["PerfilClassificacaoCriarRequest"];

export function listarTaxonomias(): Promise<ListaTaxonomiasResponse> {
  return apiRequest<ListaTaxonomiasResponse>("/api/v1/taxonomias");
}

export function listarPerfisClassificacao(): Promise<ListaPerfisClassificacaoResponse> {
  return apiRequest<ListaPerfisClassificacaoResponse>("/api/v1/perfis-classificacao");
}

export function findDefaultTaxonomia(
  itens: readonly TaxonomiaResponse[],
): TaxonomiaResponse | undefined {
  return (
    itens.find((item) => item.codigo === CODIGO_TAXONOMIA_PADRAO) ??
    itens.find((item) => item.nome === NOME_TAXONOMIA_PADRAO) ??
    itens[0]
  );
}

export function findDefaultPerfil(
  itens: readonly PerfilClassificacaoResponse[],
): PerfilClassificacaoResponse | undefined {
  return (
    itens.find(
      (item) => item.codigo === CODIGO_PERFIL_PADRAO && item.versao === VERSAO_PERFIL_PADRAO,
    ) ??
    itens.find((item) => item.codigo === CODIGO_PERFIL_PADRAO) ??
    itens[0]
  );
}

export function useTaxonomiasQuery() {
  return useQuery({
    queryKey: queryKeys.taxonomias.all,
    queryFn: listarTaxonomias,
    staleTime: 60_000,
  });
}

export function usePerfisClassificacaoQuery(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.perfisClassificacao.all,
    queryFn: listarPerfisClassificacao,
    staleTime: 60_000,
    enabled: options?.enabled ?? true,
  });
}

export function criarTaxonomia(payload: TaxonomiaCriarRequest): Promise<TaxonomiaResponse> {
  return apiRequest<TaxonomiaResponse>("/api/v1/taxonomias", { method: "POST", json: payload });
}

export function atualizarTaxonomia({
  taxonomiaId,
  ...payload
}: TaxonomiaAtualizarRequest & { taxonomiaId: string }): Promise<TaxonomiaResponse> {
  return apiRequest<TaxonomiaResponse>(`/api/v1/taxonomias/${encodeURIComponent(taxonomiaId)}`, {
    method: "PATCH",
    json: payload,
  });
}

export function criarDisciplina({
  taxonomiaId,
  ...payload
}: DisciplinaCriarRequest & { taxonomiaId: string }): Promise<DisciplinaResponse> {
  return apiRequest<DisciplinaResponse>(
    `/api/v1/taxonomias/${encodeURIComponent(taxonomiaId)}/disciplinas`,
    { method: "POST", json: payload },
  );
}

export function atualizarDisciplina({
  disciplinaId,
  ...payload
}: DisciplinaAtualizarRequest & { disciplinaId: string }): Promise<DisciplinaResponse> {
  return apiRequest<DisciplinaResponse>(
    `/api/v1/disciplinas/${encodeURIComponent(disciplinaId)}`,
    { method: "PATCH", json: payload },
  );
}

export function criarPerfilClassificacao(
  payload: PerfilClassificacaoCriarRequest,
): Promise<PerfilClassificacaoResponse> {
  return apiRequest<PerfilClassificacaoResponse>("/api/v1/perfis-classificacao", {
    method: "POST",
    json: payload,
  });
}

// As mutations retornam a promessa da invalidação para que o chamador só prossiga
// depois do refetch (necessário para o seletor global enxergar a nova Taxonomia).
export function useCriarTaxonomiaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: criarTaxonomia,
    onSuccess: async (criada) => {
      // Insere a nova Taxonomia no cache antes do refetch: se o GET falhar, o provider
      // ainda conhece o id e o seletor global consegue selecioná-la.
      queryClient.setQueryData<ListaTaxonomiasResponse>(queryKeys.taxonomias.all, (atual) => {
        if (!atual) {
          return atual;
        }
        const itens = [...atual.itens.filter((item) => item.id !== criada.id), criada];
        return { ...atual, itens, total: itens.length };
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.taxonomias.all });
    },
  });
}

export function useAtualizarTaxonomiaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: atualizarTaxonomia,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taxonomias.all }),
  });
}

export function useCriarDisciplinaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: criarDisciplina,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taxonomias.all }),
  });
}

export function useAtualizarDisciplinaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: atualizarDisciplina,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.taxonomias.all }),
  });
}

export function useCriarPerfilMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: criarPerfilClassificacao,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.perfisClassificacao.all }),
  });
}
