import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type { ListaQuestoesResponse } from "@/api/revisao";
import type { components, operations } from "@/api/schema";

export type { ListaQuestoesResponse };
export type ItemQuestaoResponse = components["schemas"]["ItemQuestaoResponse"];
export type ListarQuestoesParams = NonNullable<
  operations["listar_questoes_api_v1_questoes_get"]["parameters"]["query"]
>;

export function listarQuestoes(params: ListarQuestoesParams): Promise<ListaQuestoesResponse> {
  return apiRequest<ListaQuestoesResponse>("/api/v1/questoes", { query: params });
}

export function useQuestoesQuery(params: ListarQuestoesParams, options: { enabled: boolean }) {
  return useQuery({
    queryKey: queryKeys.questoes.list(params),
    queryFn: () => listarQuestoes(params),
    enabled: options.enabled,
    // Mantém total/lista durante a troca de página/filtro, mas nunca atravessa a troca de Taxonomia.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] !== undefined &&
      (previousQuery.queryKey[2] as ListarQuestoesParams).taxonomia_id === params.taxonomia_id
        ? previous
        : undefined,
  });
}
