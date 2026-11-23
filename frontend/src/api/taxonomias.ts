import { useQuery } from "@tanstack/react-query";

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
