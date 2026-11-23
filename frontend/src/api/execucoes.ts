import { useMutation, useMutationState, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import { useExecucoesClassificacaoQuery } from "@/api/operacao";
import { queryKeys } from "@/api/queryKeys";
import type { components } from "@/api/schema";

export type ExecucaoClassificacaoCriarRequest =
  components["schemas"]["ExecucaoClassificacaoCriarRequest"];
export type ExecucaoClassificacaoAceitaResponse =
  components["schemas"]["ExecucaoClassificacaoAceitaResponse"];
export type EscopoExecucao = components["schemas"]["EscopoExecucaoLiteral"];

export type StatusExecucao = components["schemas"]["StatusExecucaoLiteral"];

export function podeRetomarExecucao(status: StatusExecucao): boolean {
  return status === "interrompida" || status === "concluida_com_erros";
}

export function criarExecucaoClassificacao(
  payload: ExecucaoClassificacaoCriarRequest,
): Promise<ExecucaoClassificacaoAceitaResponse> {
  return apiRequest<ExecucaoClassificacaoAceitaResponse>("/api/v1/execucoes-classificacao", {
    method: "POST",
    json: payload,
  });
}

export function retomarExecucaoClassificacao(
  execucaoId: string,
): Promise<ExecucaoClassificacaoAceitaResponse> {
  return apiRequest<ExecucaoClassificacaoAceitaResponse>(
    `/api/v1/execucoes-classificacao/${encodeURIComponent(execucaoId)}/retomar`,
    { method: "POST" },
  );
}

// A chave list(null) é compartilhada com a pílula do worker (sem Taxonomia). Sem Taxonomia
// ativa a consulta fica desabilitada e o dado em cache dessa chave não pertence à aba.
export function useExecucoesDaTaxonomiaQuery(taxonomiaId: string | null) {
  const query = useExecucoesClassificacaoQuery(taxonomiaId, { enabled: taxonomiaId !== null });
  return taxonomiaId === null ? { ...query, data: undefined } : query;
}

function useInvalidarExecucoes() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.execucoesClassificacao.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.health.all }),
    ]);
}

export function useCriarExecucaoMutation() {
  const invalidar = useInvalidarExecucoes();
  return useMutation({ mutationFn: criarExecucaoClassificacao, onSuccess: invalidar });
}

const RETOMAR_MUTATION_KEY = ["execucoes-classificacao", "retomar"] as const;

export function useRetomarExecucaoMutation() {
  const invalidar = useInvalidarExecucoes();
  // onSettled: um 409 indica estado desatualizado, então a lista também é refeita no erro.
  return useMutation({
    mutationKey: RETOMAR_MUTATION_KEY,
    mutationFn: retomarExecucaoClassificacao,
    onSettled: invalidar,
  });
}

// O conjunto de retomadas em voo vive no MutationCache do QueryClient, não no estado da aba:
// trocar de aba e voltar (ou desmontar a página) não reabilita um botão cuja requisição
// ainda está no ar. A guarda lê o cache na hora do clique, sem depender de closure de render.
export function useRetomarExecucao() {
  const queryClient = useQueryClient();
  const mutation = useRetomarExecucaoMutation();
  const emVoo = useMutationState({
    filters: { mutationKey: RETOMAR_MUTATION_KEY, status: "pending" },
    select: (item) => item.state.variables as string,
  });

  function retomar(execucaoId: string): Promise<ExecucaoClassificacaoAceitaResponse | null> {
    const duplicada = queryClient.getMutationCache().findAll({
      mutationKey: RETOMAR_MUTATION_KEY,
      status: "pending",
      predicate: (item) => item.state.variables === execucaoId,
    });
    if (duplicada.length > 0) {
      return Promise.resolve(null);
    }
    return mutation.mutateAsync(execucaoId);
  }

  return { retomar, retomandoIds: new Set<string>(emVoo) as ReadonlySet<string> };
}
